"""IST-aware time helpers. Server time is source of truth."""
from datetime import datetime, date, time as dtime
import pytz

from app.core.config import settings

_IST = pytz.timezone("Asia/Kolkata")


def ist_tz():
    return pytz.timezone(settings.APP_TZ or "Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(ist_tz())


def now_utc() -> datetime:
    return datetime.now(pytz.utc)


def today_ist_date() -> date:
    return now_ist().date()


def parse_hhmm(s: str) -> dtime:
    try:
        parts = s.strip().split(":")
        if len(parts) != 2:
            raise ValueError("expected HH:MM")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("hour/minute out of range")
        return dtime(hour=h, minute=m)
    except Exception as e:
        raise ValueError(f"Invalid time '{s}', expected HH:MM (00:00-23:59)") from e


def as_aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; coerce to IST-aware for arithmetic."""
    if dt is None:
        return dt  # type: ignore
    if dt.tzinfo is None:
        return ist_tz().localize(dt)
    return dt
