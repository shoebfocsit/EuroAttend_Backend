from datetime import datetime
from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    mobile: str = Field(min_length=10, max_length=15)
    password: str = Field(min_length=4)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    name: str
    mobile: str
    role: str
    is_active: bool
    model_config = {"from_attributes": True}


class PunchResp(BaseModel):
    id: int
    date: str
    punch_in_time: datetime | None
    punch_out_time: datetime | None = None
    status: str
    outside_geofence: bool = False


class TodayOut(BaseModel):
    has_punched_in: bool
    has_punched_out: bool
    attendance: dict | None = None
    server_time: datetime


class TrackPoint(BaseModel):
    lat: float
    lng: float
    accuracy: float | None = None
    speed: float | None = None
    recorded_at: datetime
    is_mock: bool = False


class BatchIn(BaseModel):
    attendance_id: int
    points: list[TrackPoint]


class EventIn(BaseModel):
    attendance_id: int | None = None
    type: str  # gps_off|gps_on|app_killed|sync|mock_detected


class BreakOut(BaseModel):
    id: int
    start_time: datetime
    end_time: datetime | None = None
    duration_minutes: int | None = None
    on_break: bool = False
    capped: bool = False
    max_minutes: int = 45
