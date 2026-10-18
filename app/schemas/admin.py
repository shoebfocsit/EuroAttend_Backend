from pydantic import BaseModel, Field, field_validator
from typing import Literal
import re

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _check_hhmm(v: str | None) -> str | None:
    if v is None:
        return v
    if not _HHMM.match(v):
        raise ValueError("expected HH:MM (00:00-23:59)")
    return v


class UserCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    mobile: str = Field(min_length=10, max_length=15)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "employee"] = "employee"


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Literal["admin", "employee"] | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserPolicyIn(BaseModel):
    """All optional — only set fields override global. Null clears back to global."""
    shift_start: str | None = None
    shift_end: str | None = None
    late_after: int | None = Field(default=None, ge=0, le=180)
    min_shift_hours: float | None = Field(default=None, ge=1, le=16)
    max_break_minutes: int | None = Field(default=None, ge=5, le=240)
    max_accuracy_m: float | None = Field(default=None, ge=10, le=1000)
    overtime_allowed: bool | None = None
    overtime_limit_hours: float | None = Field(default=None, ge=0, le=12)

    @field_validator("shift_start", "shift_end")
    @classmethod
    def _v_hhmm(cls, v: str | None) -> str | None:
        return _check_hhmm(v)


class SettingsIn(BaseModel):
    """Global shift rules — admin can change fixed 10-7 timings etc."""
    shift_start: str | None = None
    shift_end: str | None = None
    late_after: int | None = Field(default=None, ge=0, le=180)
    half_day_hours: float | None = Field(default=None, ge=1, le=12)
    min_shift_hours: float | None = Field(default=None, ge=1, le=16)
    max_break_minutes: int | None = Field(default=None, ge=5, le=240)
    max_accuracy_m: float | None = Field(default=None, ge=10, le=1000)
    overtime_allowed: bool | None = None
    overtime_limit_hours: float | None = Field(default=None, ge=0, le=12)
    lunch_reminder_at: str | None = None
    geofence_lat: float | None = Field(default=None, ge=-90, le=90)
    geofence_lng: float | None = Field(default=None, ge=-180, le=180)
    geofence_radius: float | None = Field(default=None, ge=50, le=10000)

    @field_validator("shift_start", "shift_end", "lunch_reminder_at")
    @classmethod
    def _v_hhmm(cls, v: str | None) -> str | None:
        return _check_hhmm(v)
