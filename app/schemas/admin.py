from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    name: str
    mobile: str = Field(min_length=10, max_length=15)
    password: str = Field(min_length=4)
    role: str = "employee"


class UserUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


class UserPolicyIn(BaseModel):
    """All optional — only set fields override global. Null clears back to global."""
    shift_start: str | None = None
    shift_end: str | None = None
    late_after: int | None = None
    min_shift_hours: float | None = None
    max_break_minutes: int | None = None
    max_accuracy_m: float | None = None
    overtime_allowed: bool | None = None
    overtime_limit_hours: float | None = None


class SettingsIn(BaseModel):
    """Global shift rules — admin can change fixed 10-7 timings etc."""
    shift_start: str | None = None
    shift_end: str | None = None
    late_after: int | None = None
    half_day_hours: float | None = None
    min_shift_hours: float | None = None
    max_break_minutes: int | None = None
    max_accuracy_m: float | None = None
    overtime_allowed: bool | None = None
    overtime_limit_hours: float | None = None
    lunch_reminder_at: str | None = None
    geofence_lat: float | None = None
    geofence_lng: float | None = None
    geofence_radius: float | None = None
