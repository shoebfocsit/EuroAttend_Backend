"""Seed admin + default settings. Run: python -m scripts.seed"""
from app.db.session import SessionLocal, engine
from app.db.base import Base
from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User
from app.models.tracking import Setting
import app.models.attendance  # noqa

Base.metadata.create_all(bind=engine)
try:
    from app.db.patch import ensure_columns
    ensure_columns()
except Exception:
    pass
db = SessionLocal()
if not db.query(User).filter(User.mobile == settings.ADMIN_MOBILE).first():
    db.add(User(name=settings.ADMIN_NAME, mobile=settings.ADMIN_MOBILE,
                password_hash=hash_password(settings.ADMIN_PASSWORD), role="admin"))
    print(f"seeded admin {settings.ADMIN_MOBILE}")
if not db.get(Setting, 1):
    db.add(Setting(id=1, shift_start=settings.SHIFT_START, shift_end=settings.SHIFT_END,
                   late_after=settings.LATE_AFTER_MINUTES, half_day_hours=settings.HALF_DAY_HOURS,
                   min_shift_hours=settings.MIN_SHIFT_HOURS,
                   max_break_minutes=settings.MAX_BREAK_MINUTES,
                   max_accuracy_m=settings.MAX_GPS_ACCURACY_M,
                   overtime_allowed=settings.OVERTIME_ALLOWED,
                   overtime_limit_hours=settings.OVERTIME_LIMIT_HOURS,
                   lunch_reminder_at=settings.LUNCH_REMINDER_AT,
                   geofence_lat=settings.GEOFENCE_LAT, geofence_lng=settings.GEOFENCE_LNG,
                   geofence_radius=settings.GEOFENCE_RADIUS_M))
    print("seeded settings")
else:
    s = db.get(Setting, 1)
    if s.min_shift_hours is None:
        s.min_shift_hours = settings.MIN_SHIFT_HOURS
    if getattr(s, "max_break_minutes", None) is None:
        s.max_break_minutes = settings.MAX_BREAK_MINUTES
    if getattr(s, "max_accuracy_m", None) is None:
        s.max_accuracy_m = settings.MAX_GPS_ACCURACY_M
    if getattr(s, "overtime_allowed", None) is None:
        s.overtime_allowed = settings.OVERTIME_ALLOWED
    if getattr(s, "overtime_limit_hours", None) is None:
        s.overtime_limit_hours = settings.OVERTIME_LIMIT_HOURS
    if getattr(s, "lunch_reminder_at", None) is None:
        s.lunch_reminder_at = settings.LUNCH_REMINDER_AT
db.commit()
