from datetime import datetime, timezone
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator


# Permitted food-level status values based on specified thresholds
VALID_FOOD_STATUSES = {"Empty", "Fill", "Half", "Full", "Sensor Error"}
VALID_COMMAND_ACTIONS = {"FEED", "OPEN", "CLOSE"}


class ReadingCreate(BaseModel):
    """
    Schema for incoming sensor readings sent by ESP32 or manual API tests.
    """
    device_id: str = Field(..., min_length=1, max_length=64, description="Unique identifier of the ESP32 feeder")
    distance_cm: float = Field(..., description="Ultrasonic distance in centimeters (-1 for sensor error)")
    food_status: str = Field(..., description="Estimated food container level: Empty, Fill, Half, Full, or Sensor Error")
    uptime_seconds: Optional[int] = Field(None, ge=0, description="Device uptime in seconds since boot")
    recorded_at: Optional[datetime] = Field(None, description="Optional timestamp from device; defaults to current UTC time")

    @field_validator("food_status")
    @classmethod
    def validate_food_status(cls, value: str) -> str:
        trimmed = value.strip()
        if trimmed not in VALID_FOOD_STATUSES:
            raise ValueError(
                f"Invalid food_status '{value}'. Must be one of: {', '.join(sorted(VALID_FOOD_STATUSES))}"
            )
        return trimmed

    @field_validator("distance_cm")
    @classmethod
    def validate_distance(cls, value: float) -> float:
        # Distance must be -1 (error) or a plausible ultrasonic reading between 0 and 500 cm
        if value < -1.0 or value > 500.0:
            raise ValueError("distance_cm must be -1.0 (sensor error) or between 0.0 and 500.0 cm")
        return round(value, 2)


class ReadingResponse(BaseModel):
    """
    Schema for serialized sensor readings returned to clients.
    """
    id: int
    device_id: str
    distance_cm: float
    food_status: str
    uptime_seconds: Optional[int] = None
    recorded_at: datetime
    received_at: datetime

    class Config:
        from_attributes = True


class CommandCreate(BaseModel):
    """
    Schema for issuing a gate/feed command from the dashboard.
    """
    device_id: str = Field("esp32_feeder_01", min_length=1, max_length=64)
    action: str = Field(..., description="FEED (cycle servo), OPEN (90 degrees), or CLOSE (0 degrees)")

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        upper = value.strip().upper()
        if upper not in VALID_COMMAND_ACTIONS:
            raise ValueError(
                f"Invalid action '{value}'. Must be one of: {', '.join(sorted(VALID_COMMAND_ACTIONS))}"
            )
        return upper


class CommandResponse(BaseModel):
    """
    Schema for command status returned to dashboard or ESP32.
    """
    id: int
    device_id: str
    action: str
    status: str
    created_at: datetime
    executed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ReadingIngestResponse(BaseModel):
    """
    Response returned to ESP32 upon POST /api/readings.
    Includes any pending servo command so the ESP32 executes it immediately
    without needing an independent polling thread.
    """
    status: str = "success"
    message: str = "Reading stored successfully"
    reading: ReadingResponse
    pending_command: Optional[CommandResponse] = None


class StatsResponse(BaseModel):
    """
    Summary statistics for the dashboard header and cards.
    """
    total_readings: int
    latest_reading: Optional[ReadingResponse] = None
    current_food_status: str
    status_distribution: Dict[str, int]
    min_distance_cm: Optional[float] = None
    max_distance_cm: Optional[float] = None
    avg_distance_cm: Optional[float] = None
    active_device_id: Optional[str] = None
    last_updated_at: Optional[datetime] = None
    pending_commands_count: int


class DeviceSummary(BaseModel):
    """
    Summary information per connected ESP32 device.
    """
    device_id: str
    readings_count: int
    last_seen_at: Optional[datetime] = None
    latest_distance_cm: Optional[float] = None
    latest_food_status: Optional[str] = None


class HealthResponse(BaseModel):
    """
    API health check schema.
    """
    status: str
    database: str
    environment: str
    timestamp: datetime

