import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv

# Load local .env if present
load_dotenv()

logger = logging.getLogger("fish_feeder.database")

# Build connection parameters
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "postgres")
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "db")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "fishfeeder")

# Prefer postgresql+psycopg2:// or postgresql://
DEFAULT_PG_URL = f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_PG_URL)

# Normalize plain postgresql:// to postgresql+psycopg2:// for broad driver compatibility
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

USE_SQLITE = os.getenv("USE_SQLITE", "false").lower() in ("true", "1", "yes")

engine = None
is_sqlite = False

if USE_SQLITE or DATABASE_URL.startswith("sqlite"):
    is_sqlite = True
    SQLITE_URL = os.getenv("SQLITE_URL", "sqlite:///./fishfeeder.db")
    engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
    logger.info("Using SQLite database: %s", SQLITE_URL)
else:
    try:
        # Attempt to configure PostgreSQL
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        logger.info("Configured PostgreSQL engine with URL: %s@%s:%s/%s", POSTGRES_USER, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB)
    except Exception as exc:
        logger.warning(
            "Could not configure PostgreSQL driver (%s). Falling back to SQLite for local run.", exc
        )
        is_sqlite = True
        SQLITE_URL = "sqlite:///./fishfeeder.db"
        engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """
    FastAPI dependency yielding a database session per request.
    Ensures sessions are closed cleanly after handling the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create database tables if they do not exist.
    If PostgreSQL host is unreachable (e.g. running on Windows host where 'db' does not resolve),
    falls back cleanly to SQLite for seamless local testing.
    """
    global engine, SessionLocal, is_sqlite
    try:
        # Test connection first if using PostgreSQL
        if not is_sqlite:
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
            except Exception as conn_err:
                logger.warning(
                    "PostgreSQL at '%s' is not reachable from this environment (%s). "
                    "Automatically activating local SQLite fallback (fishfeeder.db) for smooth local testing.",
                    POSTGRES_HOST, conn_err
                )
                is_sqlite = True
                SQLITE_URL = "sqlite:///./fishfeeder.db"
                engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
                SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        Base.metadata.create_all(bind=engine)
        logger.info("Database schema initialized successfully (using %s).", "SQLite" if is_sqlite else "PostgreSQL")
    except Exception as exc:
        logger.error("Failed to initialize database schema: %s", exc)
        raise exc
