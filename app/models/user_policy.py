from sqlalchemy import String, Integer, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class UserPolicy(Base):
    """Per-user overrides. NULL = use global settings row.
    Admin sets custom shift/overtime/break for specific employees."""
    __tablename__ = "user_policy"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
    shift_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    shift_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    late_after: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_shift_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_break_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    overtime_allowed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    overtime_limit_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
