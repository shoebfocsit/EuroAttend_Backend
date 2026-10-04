from datetime import datetime
from sqlalchemy import Float, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class LocationLog(Base):
    __tablename__ = "location_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendance.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    is_mock: Mapped[bool] = mapped_column(Boolean, default=False)


class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int | None] = mapped_column(ForeignKey("attendance.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column()  # gps_off|gps_on|app_killed|sync|mock_detected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Setting(Base):
    __tablename__ = "settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    shift_start: Mapped[str] = mapped_column(default="09:30")
    shift_end: Mapped[str] = mapped_column(default="18:30")
    late_after: Mapped[int] = mapped_column(Integer, default=15)
    half_day_hours: Mapped[float] = mapped_column(Float, default=4.0)
    geofence_lat: Mapped[float] = mapped_column(Float, default=28.6139)
    geofence_lng: Mapped[float] = mapped_column(Float, default=77.2090)
    geofence_radius: Mapped[float] = mapped_column(Float, default=500)
    min_shift_hours: Mapped[float] = mapped_column(Float, default=8.0)
    max_break_minutes: Mapped[int] = mapped_column(Integer, default=45)
    max_accuracy_m: Mapped[float] = mapped_column(Float, default=200)
    overtime_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    overtime_limit_hours: Mapped[float] = mapped_column(Float, default=3.0)
    lunch_reminder_at: Mapped[str] = mapped_column(default="13:00")
