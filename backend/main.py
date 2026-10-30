import os
import logging
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Query, status, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func, text
from sqlalchemy.exc import SQLAlchemyError

from database import engine, get_db, init_db
from models import SensorReading, FeederCommand
from schemas import (
    ReadingCreate,
    ReadingResponse,
    ReadingIngestResponse,
    CommandCreate,
    CommandResponse,
    StatsResponse,
    DeviceSummary,
    HealthResponse,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("fish_feeder.main")

# ===========================================================================
# API Key Security
# The ESP32 must send header:  X-API-Key: <your_key>
# Set ESP32_API_KEY env var in Render dashboard (Environment tab)
# If not set, API key check is DISABLED (open access)
# ===========================================================================
ESP32_API_KEY = os.getenv("ESP32_API_KEY", "")  # empty = no auth enforced
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(key: str = Security(api_key_header)):
    """Validate ESP32_API_KEY header. If ESP32_API_KEY env var is not set, allow all."""
    if not ESP32_API_KEY:
        return  # auth disabled — open access
    if key != ESP32_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing X-API-Key header"
        )

# Initialize FastAPI app
app = FastAPI(
    title="IoT Smart Fish Feeder API",
    description="Backend API and real-time dashboard for IoT automatic fish feeder with HC-SR04 ultrasonic sensor and SG90 servo gate.",
    version="1.0.0"
)

# Configure CORS
# For local college development, permit connections from any local dashboard / LAN IP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Locate dashboard directory
# In Docker, backend is at /app and dashboard is copied to /app/dashboard or mounted at ../dashboard
DASHBOARD_DIR = Path(__file__).resolve().parent.parent / "dashboard"
if not DASHBOARD_DIR.exists():
    DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"


@app.on_event("startup")
def startup_event():
    """
    Initialize database schema safely on application startup.
    """
    logger.info("Initializing database schema...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as exc:
        logger.warning(
            "Could not initialize database on startup (it may not be ready yet): %s", exc
        )


# ============================================================================
# Core & Health Endpoints
# ============================================================================

@app.get("/", tags=["Dashboard & Info"])
def root():
    """
    Root endpoint: serves the real-time web dashboard if available,
    otherwise returns a JSON welcome message.
    """
    index_file = DASHBOARD_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {
        "project": "IoT-Based Automatic Fish Feeder with Real-Time Monitoring",
        "status": "online",
        "dashboard_url": "/dashboard",
        "api_docs_url": "/docs",
        "health_url": "/health"
    }


@app.get("/style.css", include_in_schema=False)
def get_dashboard_css():
    """Direct route for dashboard stylesheet."""
    css_file = DASHBOARD_DIR / "style.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="Stylesheet not found")


@app.get("/app.js", include_in_schema=False)
def get_dashboard_js():
    """Direct route for dashboard JavaScript application."""
    js_file = DASHBOARD_DIR / "app.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JavaScript file not found")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health_check(db: Session = Depends(get_db)):
    """
    Verifies backend operation and checks live database connectivity.
    """
    from database import is_sqlite
    db_status = "connected (sqlite)" if is_sqlite else "connected (postgresql)"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        db_status = f"disconnected: {exc}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connectivity check failed: {str(exc)}"
        )

    return HealthResponse(
        status="healthy",
        database=db_status,
        environment=os.getenv("ENVIRONMENT", "production"),
        timestamp=datetime.now(timezone.utc)
    )


# ============================================================================
# Sensor Readings Endpoints
# ============================================================================

@app.post(
    "/api/readings",
    response_model=ReadingIngestResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Sensor Readings"]
)
def create_reading(
    reading_in: ReadingCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """
    Receives and persists a new ultrasonic sensor reading from the ESP32.
    Also returns any pending servo gate command so the ESP32 can act on it immediately.
    """
    try:
        recorded_time = reading_in.recorded_at or datetime.now(timezone.utc)
        db_reading = SensorReading(
            device_id=reading_in.device_id,
            distance_cm=reading_in.distance_cm,
            food_status=reading_in.food_status,
            uptime_seconds=reading_in.uptime_seconds,
            recorded_at=recorded_time,
            received_at=datetime.now(timezone.utc)
        )
        db.add(db_reading)
        db.commit()
        db.refresh(db_reading)

        # Check if there is a pending command for this device
        pending_cmd = db.query(FeederCommand).filter(
            FeederCommand.device_id == reading_in.device_id,
            FeederCommand.status == "PENDING"
        ).order_by(FeederCommand.created_at.asc()).first()

        logger.info(
            "Stored reading #%d from %s: %.2f cm -> %s",
            db_reading.id, db_reading.device_id, db_reading.distance_cm, db_reading.food_status
        )

        return ReadingIngestResponse(
            status="success",
            message="Sensor reading successfully recorded",
            reading=ReadingResponse.model_validate(db_reading),
            pending_command=CommandResponse.model_validate(pending_cmd) if pending_cmd else None
        )
    except SQLAlchemyError as exc:
        db.rollback()
        logger.error("Failed to insert sensor reading: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while saving reading"
        )


@app.get(
    "/api/readings/latest",
    response_model=ReadingResponse,
    tags=["Sensor Readings"]
)
def get_latest_reading(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    db: Session = Depends(get_db)
):
    """
    Returns the most recent sensor reading recorded by any or a specific device.
    """
    query = db.query(SensorReading)
    if device_id:
        query = query.filter(SensorReading.device_id == device_id)

    latest = query.order_by(desc(SensorReading.received_at)).first()
    if not latest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sensor readings have been recorded yet"
        )
    return ReadingResponse.model_validate(latest)


@app.get(
    "/api/readings",
    response_model=List[ReadingResponse],
    tags=["Sensor Readings"]
)
def list_readings(
    limit: int = Query(50, ge=1, le=500, description="Number of readings to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    device_id: Optional[str] = Query(None, description="Optional device filter"),
    db: Session = Depends(get_db)
):
    """
    Returns historical readings ordered from newest to oldest with pagination.
    """
    query = db.query(SensorReading)
    if device_id:
        query = query.filter(SensorReading.device_id == device_id)

    readings = query.order_by(desc(SensorReading.received_at)).offset(offset).limit(limit).all()
    return [ReadingResponse.model_validate(r) for r in readings]


# ============================================================================
# Statistics & Devices Endpoints
# ============================================================================

@app.get(
    "/api/stats",
    response_model=StatsResponse,
    tags=["Statistics"]
)
def get_stats(db: Session = Depends(get_db)):
    """
    Computes key summary statistics for the dashboard cards and charts:
    total readings, latest reading, status counts, min/max/average distance.
    """
    total = db.query(func.count(SensorReading.id)).scalar() or 0
    latest = db.query(SensorReading).order_by(desc(SensorReading.received_at)).first()

    # Distribution per status
    status_counts = (
        db.query(SensorReading.food_status, func.count(SensorReading.id))
        .group_by(SensorReading.food_status)
        .all()
    )
    dist = {k: 0 for k in ["Empty", "Fill", "Half", "Full", "Sensor Error"]}
    for status_name, cnt in status_counts:
        dist[status_name] = cnt

    # Distance metrics (excluding negative error values)
    metrics = (
        db.query(
            func.min(SensorReading.distance_cm),
            func.max(SensorReading.distance_cm),
            func.avg(SensorReading.distance_cm)
        )
        .filter(SensorReading.distance_cm >= 0)
        .first()
    )

    min_dist = round(metrics[0], 2) if metrics and metrics[0] is not None else None
    max_dist = round(metrics[1], 2) if metrics and metrics[1] is not None else None
    avg_dist = round(metrics[2], 2) if metrics and metrics[2] is not None else None

    pending_count = db.query(func.count(FeederCommand.id)).filter(
        FeederCommand.status == "PENDING"
    ).scalar() or 0

    return StatsResponse(
        total_readings=total,
        latest_reading=ReadingResponse.model_validate(latest) if latest else None,
        current_food_status=latest.food_status if latest else "No Data",
        status_distribution=dist,
        min_distance_cm=min_dist,
        max_distance_cm=max_dist,
        avg_distance_cm=avg_dist,
        active_device_id=latest.device_id if latest else None,
        last_updated_at=latest.received_at if latest else None,
        pending_commands_count=pending_count
    )


@app.get(
    "/api/devices",
    response_model=List[DeviceSummary],
    tags=["Devices"]
)
def get_devices(db: Session = Depends(get_db)):
    """
    Returns known ESP32 devices that have reported to the system.
    """
    device_rows = (
        db.query(
            SensorReading.device_id,
            func.count(SensorReading.id).label("cnt"),
            func.max(SensorReading.received_at).label("last_seen")
        )
        .group_by(SensorReading.device_id)
        .all()
    )

    results = []
    for d_id, count, last_seen in device_rows:
        latest = (
            db.query(SensorReading)
            .filter(SensorReading.device_id == d_id)
            .order_by(desc(SensorReading.received_at))
            .first()
        )
        results.append(
            DeviceSummary(
                device_id=d_id,
                readings_count=count,
                last_seen_at=last_seen,
                latest_distance_cm=latest.distance_cm if latest else None,
                latest_food_status=latest.food_status if latest else None
            )
        )
    return results


# ============================================================================
# Servo Gate Commands Endpoints (Hardware Remote Control)
# ============================================================================

@app.post(
    "/api/commands",
    response_model=CommandResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Servo Commands"]
)
def create_command(
    cmd_in: CommandCreate,
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """
    Enqueues a servo gate command from the dashboard (FEED, OPEN, or CLOSE).
    The ESP32 will pick up and execute this command upon its next communication cycle.
    """
    cmd = FeederCommand(
        device_id=cmd_in.device_id,
        action=cmd_in.action,
        status="PENDING",
        created_at=datetime.now(timezone.utc)
    )
    db.add(cmd)
    db.commit()
    db.refresh(cmd)
    logger.info("Enqueued command #%d: %s for device %s", cmd.id, cmd.action, cmd.device_id)
    return CommandResponse.model_validate(cmd)


@app.get(
    "/api/commands/pending",
    response_model=Optional[CommandResponse],
    tags=["Servo Commands"]
)
def get_pending_command(
    device_id: str = Query("esp32_feeder_01"),
    db: Session = Depends(get_db)
):
    """
    Endpoint polled by ESP32 or checked by backend to retrieve the oldest pending command.
    """
    cmd = db.query(FeederCommand).filter(
        FeederCommand.device_id == device_id,
        FeederCommand.status == "PENDING"
    ).order_by(FeederCommand.created_at.asc()).first()

    return CommandResponse.model_validate(cmd) if cmd else None


@app.post(
    "/api/commands/{command_id}/ack",
    response_model=CommandResponse,
    tags=["Servo Commands"]
)
def acknowledge_command(
    command_id: int,
    status_code: str = Query("EXECUTED", regex="^(EXECUTED|FAILED)$"),
    db: Session = Depends(get_db),
    _: None = Depends(verify_api_key)
):
    """
    Called by the ESP32 after physical servo execution to confirm completion.
    """
    cmd = db.query(FeederCommand).filter(FeederCommand.id == command_id).first()
    if not cmd:
        raise HTTPException(status_code=404, detail="Command not found")

    cmd.status = status_code
    cmd.executed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cmd)
    logger.info("Command #%d acknowledged as %s", cmd.id, cmd.status)
    return CommandResponse.model_validate(cmd)


@app.get(
    "/api/commands/latest",
    response_model=List[CommandResponse],
    tags=["Servo Commands"]
)
def list_latest_commands(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db)
):
    """
    Returns recent feeder commands and their execution state for the dashboard.
    """
    cmds = db.query(FeederCommand).order_by(desc(FeederCommand.created_at)).limit(limit).all()
    return [CommandResponse.model_validate(c) for c in cmds]


# Mount static assets for the dashboard
if DASHBOARD_DIR.exists():
    app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")
    logger.info("Mounted dashboard from %s", DASHBOARD_DIR)

