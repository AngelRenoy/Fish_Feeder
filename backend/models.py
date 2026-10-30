from sqlalchemy import Column, Integer, Float, String, DateTime, Index
from sqlalchemy.sql import func
from database import Base


class SensorReading(Base):
    """
    SQLAlchemy ORM model for storing HC-SR04 ultrasonic sensor readings
    and food-level classifications transmitted by the ESP32.
    """
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String(64), nullable=False, index=True)
    distance_cm = Column(Float, nullable=False)
    food_status = Column(String(32), nullable=False, index=True)
    uptime_seconds = Column(Integer, nullable=True)
    recorded_at = Column(DateTime(timezone=True), nullable=False, index=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_device_received", "device_id", "received_at"),
    )

    def __repr__(self):
        return f"<SensorReading(id={self.id}, device='{self.device_id}', dist={self.distance_cm}cm, status='{self.food_status}')>"


class FeederCommand(Base):
    """
    SQLAlchemy ORM model for queueing and tracking servo gate actions
    (e.g., FEED, OPEN, CLOSE) requested by the dashboard and executed by ESP32.
    """
    __tablename__ = "feeder_commands"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    device_id = Column(String(64), nullable=False, default="esp32_feeder_01", index=True)
    action = Column(String(32), nullable=False)  # 'FEED', 'OPEN', 'CLOSE'
    status = Column(String(32), nullable=False, default="PENDING", index=True)  # 'PENDING', 'EXECUTED', 'FAILED'
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self):
        return f"<FeederCommand(id={self.id}, action='{self.action}', status='{self.status}')>"

