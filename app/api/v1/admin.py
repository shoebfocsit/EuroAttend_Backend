import csv, io
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.core.security import hash_password
from app.core.time import today_ist_date
from app.models.user import User
from app.models.attendance import Attendance, Break
from app.models.user_policy import UserPolicy
from app.models.tracking import LocationLog, Setting
from app.schemas.admin import UserCreate, UserUpdate, UserPolicyIn, SettingsIn
from app.core.config import settings as app_settings

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Global rules: fixed 10-7 timings, break, OT, GPS — admin can change."""
    s = db.get(Setting, 1)
    if not s:
        return {"shift_start": app_settings.SHIFT_START, "shift_end": app_settings.SHIFT_END}
    return {"shift_start": s.shift_start, "shift_end": s.shift_end,
            "late_after": s.late_after, "half_day_hours": s.half_day_hours,
            "min_shift_hours": getattr(s, "min_shift_hours", None),
            "max_break_minutes": getattr(s, "max_break_minutes", None),
            "max_accuracy_m": getattr(s, "max_accuracy_m", None),
            "overtime_allowed": getattr(s, "overtime_allowed", None),
            "overtime_limit_hours": getattr(s, "overtime_limit_hours", None),
            "lunch_reminder_at": getattr(s, "lunch_reminder_at", None),
            "geofence_lat": s.geofence_lat, "geofence_lng": s.geofence_lng,
            "geofence_radius": s.geofence_radius}


@router.put("/settings")
def set_settings(body: SettingsIn, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    s = db.get(Setting, 1)
    if not s:
        s = Setting(id=1)
        db.add(s)
    for f in ("shift_start", "shift_end", "late_after", "half_day_hours",
              "min_shift_hours", "max_break_minutes", "max_accuracy_m",
              "overtime_allowed", "overtime_limit_hours", "lunch_reminder_at",
              "geofence_lat", "geofence_lng", "geofence_radius"):
        v = getattr(body, f)
        if v is not None:
            setattr(s, f, v)
    db.commit()
    return {"ok": True}


@router.get("/overview")
def overview(month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
             db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """One row per active employee: working now? where? last seen,
    plus that month's total working hours and day-wise records link data.

    state = on_duty (punched in, not out) | done (punched out) | not_in.
    """
    today = today_ist_date()
    month = month or today.strftime("%Y-%m")
    y, m = map(int, month.split("-"))
    m_start, m_end = f"{y:04d}-{m:02d}-01", f"{y + (m == 12):04d}-{m % 12 + 1:02d}-01"
    out = []
    for u in db.query(User).filter(User.role != "admin", User.is_active == True).order_by(User.id).all():  # noqa
        att = db.query(Attendance).filter(
            Attendance.user_id == u.id, Attendance.date == today).first()
        mrows = db.query(Attendance).filter(
            Attendance.user_id == u.id,
            Attendance.date >= m_start, Attendance.date < m_end).all()
        m_min = sum((r.total_minutes or 0) for r in mrows)
        m_days = [{"id": r.id, "date": str(r.date), "in": r.punch_in_time,
                   "out": r.punch_out_time, "minutes": r.total_minutes,
                   "break_minutes": r.break_minutes or 0,
                   "overtime_minutes": r.overtime_minutes or 0,
                   "status": r.status,
                   "distance_m": round(r.total_distance_m or 0, 1)}
                  for r in sorted(mrows, key=lambda r: r.date, reverse=True)]
        last = None
        if att:
            p = db.query(LocationLog).filter(
                LocationLog.attendance_id == att.id).order_by(
                LocationLog.recorded_at.desc()).first()
            if p:
                last = {"lat": p.lat, "lng": p.lng, "at": p.recorded_at,
                        "accuracy": p.accuracy, "is_mock": p.is_mock}
            elif att.in_lat:
                last = {"lat": att.in_lat, "lng": att.in_lng,
                        "at": att.punch_in_time, "accuracy": None, "is_mock": att.is_mock_in}
        state = "not_in"
        on_break = False
        bmins = 0
        if att:
            bmins = sum((r.duration_minutes or 0) for r in db.query(Break).filter(
                Break.attendance_id == att.id).all())
            if att.punch_out_time:
                state = "done"
            elif db.query(Break).filter(
                    Break.attendance_id == att.id, Break.end_time.is_(None)).first():
                state = "on_break"
                on_break = True
            else:
                state = "on_duty"
        out.append({"user_id": u.id, "name": u.name, "mobile": u.mobile, "state": state,
                    "on_break": on_break, "break_minutes": bmins,
                    "overtime": att.overtime_started_at is not None if att else False,
                    "overtime_start": att.overtime_started_at if att else None,
                    "overtime_minutes": att.overtime_minutes if att else 0,
                    "attendance_id": att.id if att else None,
                    "punch_in": att.punch_in_time if att else None,
                    "punch_out": att.punch_out_time if att and att.punch_out_time else None,
                    "status": att.status if att else None,
                    "total_minutes": att.total_minutes if att else None,
                    "month": month,
                    "month_minutes": m_min,
                    "month_hours": round(m_min / 60, 2),
                    "month_days": m_days,
                    "last_location": last})
    return out


@router.get("/users/{uid}/policy")
def get_user_policy(uid: int, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Custom policy for one user (null fields = global applies)."""
    if not db.get(User, uid):
        raise HTTPException(404, "User not found")
    up = db.get(UserPolicy, uid)
    if not up:
        return {"user_id": uid, "custom": False}
    return {"user_id": uid, "custom": True, "shift_start": up.shift_start,
            "shift_end": up.shift_end, "late_after": up.late_after,
            "min_shift_hours": up.min_shift_hours,
            "max_break_minutes": up.max_break_minutes,
            "max_accuracy_m": up.max_accuracy_m,
            "overtime_allowed": up.overtime_allowed,
            "overtime_limit_hours": up.overtime_limit_hours}


@router.put("/users/{uid}/policy")
def set_user_policy(uid: int, body: UserPolicyIn,
                    db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """Set/clear custom time & rules for one user."""
    if not db.get(User, uid):
        raise HTTPException(404, "User not found")
    up = db.get(UserPolicy, uid)
    if not up:
        up = UserPolicy(user_id=uid)
        db.add(up)
    for f in ("shift_start", "shift_end", "late_after", "min_shift_hours",
              "max_break_minutes", "max_accuracy_m",
              "overtime_allowed", "overtime_limit_hours"):
        setattr(up, f, getattr(body, f))
    db.commit()
    return {"ok": True, "user_id": uid}


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)):
    out = []
    for u in db.query(User).order_by(User.id).all():
        up = db.get(UserPolicy, u.id)
        custom = up is not None and any(
            getattr(up, f) is not None for f in (
                "shift_start", "shift_end", "late_after", "min_shift_hours",
                "max_break_minutes", "max_accuracy_m",
                "overtime_allowed", "overtime_limit_hours"))
        shift = None
        if up and up.shift_start and up.shift_end:
            shift = f"{up.shift_start}-{up.shift_end}"
        out.append({"id": u.id, "name": u.name, "mobile": u.mobile,
                    "role": u.role, "is_active": u.is_active,
                    "custom": custom, "custom_shift": shift})
    return out


@router.post("/users")
def create_user(body: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    if db.query(User).filter(User.mobile == body.mobile).first():
        raise HTTPException(400, "Mobile already exists")
    u = User(name=body.name, mobile=body.mobile,
             password_hash=hash_password(body.password), role=body.role)
    db.add(u)
    db.commit()
    return {"id": u.id}


@router.patch("/users/{uid}")
def update_user(uid: int, body: UserUpdate, db: Session = Depends(get_db), _: User = Depends(require_admin)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Not found")
    if body.name is not None:
        u.name = body.name
    if body.role is not None:
        u.role = body.role
    if body.is_active is not None:
        u.is_active = body.is_active
    if body.password:
        u.password_hash = hash_password(body.password)
    db.commit()
    return {"ok": True}


@router.get("/users/{uid}/attendance")
def user_attendance(uid: int, month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
                    db: Session = Depends(get_db), _: User = Depends(require_admin)):
    """One employee's overall attendance: all days (or one month) + totals.
    Admin can see any old user's full record."""
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found")
    q = db.query(Attendance).filter(Attendance.user_id == uid)
    if month:
        y, m = map(int, month.split("-"))
        q = q.filter(
            Attendance.date >= f"{y:04d}-{m:02d}-01",
            Attendance.date < f"{y + (m == 12):04d}-{m % 12 + 1:02d}-01")
    rows = q.order_by(Attendance.date.desc()).limit(1000).all()
    days = [{"id": r.id, "date": str(r.date), "in": r.punch_in_time, "out": r.punch_out_time,
             "minutes": r.total_minutes, "break_minutes": r.break_minutes or 0,
             "status": r.status, "distance_m": round(r.total_distance_m or 0, 1),
             "in_selfie": r.in_selfie_url, "out_selfie": r.out_selfie_url,
             "in_lat": r.in_lat, "in_lng": r.in_lng,
             "out_lat": r.out_lat, "out_lng": r.out_lng} for r in rows]
    tot = sum((r.total_minutes or 0) for r in rows)
    return {"user": {"id": u.id, "name": u.name, "mobile": u.mobile,
                     "role": u.role, "is_active": u.is_active},
            "month": month or "all", "count": len(rows), "days": days,
            "totals": {"present": sum(1 for r in rows if r.status in ("Present", "Late")),
                       "half_days": sum(1 for r in rows if r.status == "Half-day"),
                       "late": sum(1 for r in rows if r.status == "Late"),
                       "minutes": tot, "hours": round(tot / 60, 2),
                       "break_minutes": sum((r.break_minutes or 0) for r in rows),
                       "distance_km": round(sum((r.total_distance_m or 0) for r in rows) / 1000, 2)}}


@router.get("/attendance")
def all_attendance(date: str | None = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
                   user_id: int | None = None,
                   db: Session = Depends(get_db), _: User = Depends(require_admin)):
    q = db.query(Attendance)
    if date:
        q = q.filter(Attendance.date == date)
    if user_id:
        q = q.filter(Attendance.user_id == user_id)
    rows = q.order_by(Attendance.date.desc()).limit(500).all()
    return [{"id": r.id, "user_id": r.user_id, "date": str(r.date), "in": r.punch_in_time,
             "out": r.punch_out_time, "minutes": r.total_minutes, "status": r.status,
             "in_selfie": r.in_selfie_url, "out_selfie": r.out_selfie_url} for r in rows]


@router.get("/report.csv")
def report(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
           db: Session = Depends(get_db), _: User = Depends(require_admin)):
    y, m = map(int, month.split("-"))
    rows = db.query(Attendance, User).join(User, Attendance.user_id == User.id).filter(
        Attendance.date >= f"{y:04d}-{m:02d}-01",
        Attendance.date < f"{y + (m == 12):04d}-{m % 12 + 1:02d}-01").all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["user_id", "name", "mobile", "date", "in", "out", "minutes", "hours", "status", "distance_m"])
    for a, usr in rows:
        w.writerow([usr.id, usr.name, usr.mobile, a.date, a.punch_in_time, a.punch_out_time,
                    a.total_minutes, round((a.total_minutes or 0) / 60, 2), a.status, round(a.total_distance_m or 0, 1)])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=report-{month}.csv"})
