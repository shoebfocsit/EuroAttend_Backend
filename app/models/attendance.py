from datetime import datetime, date
from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Attendance(Base):
    __tablename__ = "attendance"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    punch_in_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    punch_out_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    device_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    in_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    out_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    out_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    out_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_selfie_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    out_selfie_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    total_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    overtime_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0)
    total_distance_m: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(20), default="Present")
    is_mock_in: Mapped[bool] = mapped_column(Boolean, default=False)
    outside_geofence: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_punched_out: Mapped[bool] = mapped_column(Boolean, default=False)
    device_info: Mapped[str | None] = mapped_column(String(500), nullable=True)


class Break(Base):
    """Lunch/rest break inside one attendance day. total_minutes stored on
    attendance is NET (gross minus all breaks)."""
    __tablename__ = "breaks"
    id: Mapped[int] = mapped_column(primary_key=True)
    attendance_id: Mapped[int] = mapped_column(ForeignKey("attendance.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    start_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    start_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
