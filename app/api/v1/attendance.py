"""Punch in/out, today, history, route, summary."""
import csv, io
from datetime import datetime, timedelta, date as _date
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_db, get_current_user, require_admin
from app.core.time import now_ist, today_ist_date, parse_hhmm, as_aware, ist_tz
from app.models.user import User
from app.models.attendance import Attendance, Break
from app.models.user_policy import UserPolicy
from app.models.tracking import LocationLog, Setting
from app.services.rules import haversine_m, is_outside, calc_status, net_minutes, can_punch_out, settle_break, gps_ok, sane_segment, overtime_minutes
from app.services.storage import get_storage
from app.schemas.api import PunchResp, TodayOut, BreakOut

router = APIRouter(prefix="/attendance", tags=["attendance"])


def _settings(db: Session):
    s = db.get(Setting, 1)
    if not s:
        s = Setting(id=1, shift_start=settings.SHIFT_START, shift_end=settings.SHIFT_END,
                    late_after=settings.LATE_AFTER_MINUTES, half_day_hours=settings.HALF_DAY_HOURS,
                    min_shift_hours=settings.MIN_SHIFT_HOURS,
                    max_break_minutes=settings.MAX_BREAK_MINUTES,
                    max_accuracy_m=settings.MAX_GPS_ACCURACY_M,
                    geofence_lat=settings.GEOFENCE_LAT, geofence_lng=settings.GEOFENCE_LNG,
                    geofence_radius=settings.GEOFENCE_RADIUS_M)
        db.add(s)
        db.commit()
    changed = False
    if getattr(s, "min_shift_hours", None) is None:
        s.min_shift_hours = settings.MIN_SHIFT_HOURS
        changed = True
    if getattr(s, "max_break_minutes", None) is None:
        s.max_break_minutes = settings.MAX_BREAK_MINUTES
        changed = True
    if getattr(s, "max_accuracy_m", None) is None:
        s.max_accuracy_m = settings.MAX_GPS_ACCURACY_M
        changed = True
    if getattr(s, "lunch_reminder_at", None) is None:
        s.lunch_reminder_at = settings.LUNCH_REMINDER_AT
        changed = True
    if changed:
        db.commit()
    return s


def _check_gps(db: Session, u, accuracy: float | None, action: str):
    """Real-GPS gate: punch/break only with a fresh, tight fix.
    Returns the user's effective policy dict."""
    P = _pol(db, u.id if u else None)
    ok, msg = gps_ok(accuracy, P["max_accuracy_m"])
    if not ok:
        raise HTTPException(400, f"{action} failed — {msg}")
    return P


def _pol(db: Session, uid: int | None = None) -> dict:
    """Effective policy: global settings overlaid with per-user custom
    policy (admin can set custom time/rules for specific users)."""
    s = _settings(db)
    P = {"shift_start": s.shift_start, "shift_end": s.shift_end,
         "late_after": s.late_after, "half_day_hours": s.half_day_hours,
         "min_shift_hours": s.min_shift_hours or settings.MIN_SHIFT_HOURS,
         "max_break_minutes": s.max_break_minutes or settings.MAX_BREAK_MINUTES,
         "max_accuracy_m": s.max_accuracy_m or settings.MAX_GPS_ACCURACY_M,
         "overtime_allowed": (s.overtime_allowed
                              if getattr(s, "overtime_allowed", None) is not None
                              else settings.OVERTIME_ALLOWED),
         "overtime_limit_hours": (s.overtime_limit_hours or settings.OVERTIME_LIMIT_HOURS),
         "lunch_reminder_at": (getattr(s, "lunch_reminder_at", None)
                               or settings.LUNCH_REMINDER_AT),
         "custom": False}
    if uid is not None:
        up = db.get(UserPolicy, uid)
        if up:
            P["custom"] = True
            for k in ("shift_start", "shift_end"):
                if getattr(up, k):
                    P[k] = getattr(up, k)
            for k in ("late_after", "min_shift_hours", "max_break_minutes",
                      "max_accuracy_m", "overtime_limit_hours"):
                if getattr(up, k) is not None:
                    P[k] = getattr(up, k)
            if up.overtime_allowed is not None:
                P["overtime_allowed"] = up.overtime_allowed
    return P


def _shift_end_dt(day, hhmm: str):
    from datetime import date as _d
    return ist_tz().localize(datetime.combine(day, parse_hhmm(hhmm)))


def _open_break(db: Session, attendance_id: int):
    return db.query(Break).filter(
        Break.attendance_id == attendance_id, Break.end_time.is_(None)).first()


def _settle_open_break(db: Session, att_id: int, max_minutes: int, now=None):
    """Auto-close an over-long break at the 45-min cap. Returns the break (or None)."""
    from app.core.time import now_ist as _now
    now = now or _now()
    b = _open_break(db, att_id)
    if not b:
        return None
    mins, capped = settle_break((now - as_aware(b.start_time)).total_seconds(), max_minutes)
    if capped:
        b.end_time = as_aware(b.start_time) + timedelta(minutes=max_minutes)
        b.duration_minutes = mins
        db.commit()
    return b


def _break_total(db: Session, attendance_id: int) -> int:
    rows = db.query(Break).filter(Break.attendance_id == attendance_id).all()
    return sum((r.duration_minutes or 0) for r in rows)


def _break_list(db: Session, attendance_id: int):
    rows = db.query(Break).filter(
        Break.attendance_id == attendance_id).order_by(Break.start_time).all()
    return [{"id": r.id, "start": r.start_time, "end": r.end_time,
             "minutes": r.duration_minutes,
             "start_lat": r.start_lat, "start_lng": r.start_lng,
             "end_lat": r.end_lat, "end_lng": r.end_lng} for r in rows]


def _open_today(db, uid: int):
    # any un-punched-out shift counts as the running shift (continue)
    return db.query(Attendance).filter(
        Attendance.user_id == uid,
        Attendance.punch_out_time.is_(None)).first()


@router.post("/punch-in", response_model=PunchResp)
async def punch_in(lat: float = Form(...), lng: float = Form(...),
                   accuracy: float | None = Form(None), is_mock: bool = Form(False),
                   device_ts: str | None = Form(None), device_info: str | None = Form(None),
                   selfie: UploadFile = File(...),
                   db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    if is_mock and settings.STRICT_MOCK_BLOCK:
        raise HTTPException(400, "Mock location detected — punch-in blocked")
    open_att = _open_today(db, u.id)
    if open_att:
        raise HTTPException(
            400, f"Shift from {open_att.date} is still running — punch out first to continue")
    if db.query(Attendance).filter(
            Attendance.user_id == u.id, Attendance.date == today_ist_date()).first():
        raise HTTPException(400, "Already punched in today")
    s = _settings(db)
    P = _check_gps(db, u, accuracy, "Punch-in")
    outside = is_outside(lat, lng, s.geofence_lat, s.geofence_lng, s.geofence_radius)
    if outside and settings.STRICT_GEOFENCE:
        raise HTTPException(400, "Outside office geofence")
    data = await selfie.read()
    try:
        url = get_storage().save(data, selfie.filename or "in.jpg")
    except ValueError as e:
        raise HTTPException(400, str(e))
    now = now_ist()
    dev_at = None
    try:
        if device_ts:
            dev_at = datetime.fromisoformat(device_ts)
    except Exception:
        dev_at = None
    # late counted at punch-in itself (shift + grace, per-user policy)
    sh = parse_hhmm(P["shift_start"])
    late_by = (now.hour * 60 + now.minute) - (sh.hour * 60 + sh.minute + P["late_after"])
    init_status = "Late" if late_by > 0 else "Present"
    att = Attendance(user_id=u.id, date=today_ist_date(), punch_in_time=now, device_in_at=dev_at,
                     in_lat=lat, in_lng=lng, in_accuracy=accuracy, in_selfie_url=url, status=init_status,
                     is_mock_in=is_mock, outside_geofence=outside, device_info=device_info)
    db.add(att)
    db.commit()
    db.refresh(att)
    return PunchResp(id=att.id, date=str(att.date), punch_in_time=att.punch_in_time,
                     status=att.status, outside_geofence=outside)


@router.post("/break-start", response_model=BreakOut)
def break_start(lat: float = Form(...), lng: float = Form(...),
                accuracy: float | None = Form(None),
                db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    """Start a lunch/rest break with actual GPS. Only one open break at a time."""
    att = _open_today(db, u.id)
    if not att:
        raise HTTPException(400, "Punch in first — no open shift today")
    _check_gps(db, u, accuracy, "Break-start")
    if _open_break(db, att.id):
        raise HTTPException(400, "Break already running — end it first")
    b = Break(attendance_id=att.id, user_id=u.id, start_time=now_ist(),
              start_lat=lat, start_lng=lng)
    db.add(b)
    db.commit()
    db.refresh(b)
    P = _pol(db, u.id)
    return BreakOut(id=b.id, start_time=b.start_time, on_break=True,
                    max_minutes=P["max_break_minutes"] or settings.MAX_BREAK_MINUTES)


@router.post("/break-end", response_model=BreakOut)
def break_end(lat: float = Form(...), lng: float = Form(...),
              accuracy: float | None = Form(None),
              db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    """End the open break, calculates break duration. GPS captured again.
    One break is capped at max_break_minutes (45) — longer breaks auto-close."""
    att = _open_today(db, u.id)
    if not att:
        raise HTTPException(400, "No open shift today")
    s = _settings(db)
    P = _check_gps(db, u, accuracy, "Break-end")
    bmax = P["max_break_minutes"]
    _settle_open_break(db, att.id, bmax)
    b = _open_break(db, att.id)
    if not b:
        raise HTTPException(400, "No break running (45-min cap auto-closed it?)")
    now = now_ist()
    mins, capped = settle_break((now - as_aware(b.start_time)).total_seconds(), bmax)
    b.end_lat, b.end_lng = lat, lng
    if capped:
        b.end_time = as_aware(b.start_time) + timedelta(minutes=bmax)
    else:
        b.end_time = now
    b.duration_minutes = mins
    db.commit()
    return BreakOut(id=b.id, start_time=b.start_time, end_time=b.end_time,
                    duration_minutes=b.duration_minutes, on_break=False,
                    capped=capped, max_minutes=bmax)


@router.post("/overtime-start")
def overtime_start(db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    """Employee chooses OVERTIME when shift time is over (from the alarm dialog).
    Backend records it; auto punch-out will not force-close an OT shift
    until the OT limit is crossed."""
    att = _open_today(db, u.id)
    if not att:
        raise HTTPException(400, "No open shift today")
    P = _pol(db, u.id)
    if not P["overtime_allowed"]:
        raise HTTPException(400, "Overtime is not allowed — please punch out")
    if att.overtime_started_at:
        return {"overtime": True, "since": att.overtime_started_at,
                "limit_hours": P["overtime_limit_hours"]}
    now = now_ist()
    if now < _shift_end_dt(att.date, P["shift_end"]):
        raise HTTPException(400, "Shift time is not over yet")
    att.overtime_started_at = now
    db.commit()
    return {"overtime": True, "since": now, "limit_hours": P["overtime_limit_hours"]}


@router.post("/punch-out", response_model=PunchResp)
async def punch_out(lat: float = Form(...), lng: float = Form(...),
                    accuracy: float | None = Form(None),
                    device_ts: str | None = Form(None),
                    force: bool = Form(False),
                    selfie: UploadFile = File(...),
                    db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    att = _open_today(db, u.id)
    if not att:
        raise HTTPException(400, "No open punch-in found for today")
    now = now_ist()
    P = _check_gps(db, u, accuracy, "Punch-out")
    _settle_open_break(db, att.id, P["max_break_minutes"], now)
    if _open_break(db, att.id):
        raise HTTPException(400, "Break is running — end your break before punch-out")
    gross_sec = (now - as_aware(att.punch_in_time)).total_seconds()
    bmins = _break_total(db, att.id)
    allowed, remaining = can_punch_out(gross_sec, bmins, P["min_shift_hours"])
    if not allowed and not force:
        raise HTTPException(400, f"Min {P['min_shift_hours']}h not done — {remaining} min left (or retry with force=true for early leave)")
    data = await selfie.read()
    try:
        url = get_storage().save(data, selfie.filename or "out.jpg")
    except ValueError as e:
        raise HTTPException(400, str(e))
    att.punch_out_time = now
    att.out_lat, att.out_lng, att.out_accuracy, att.out_selfie_url = lat, lng, accuracy, url
    try:
        att.device_out_at = datetime.fromisoformat(device_ts) if device_ts else None
    except Exception:
        pass
    # NET working time: gross shift minus all breaks
    att.break_minutes = _break_total(db, att.id)
    att.total_minutes = net_minutes(gross_sec, att.break_minutes)
    raw_ot = overtime_minutes(now, _shift_end_dt(att.date, P["shift_end"]))
    if not P["overtime_allowed"]:
        raw_ot = 0
    else:
        raw_ot = min(raw_ot, int((P["overtime_limit_hours"] or 3.0) * 60))
    att.overtime_minutes = raw_ot
    hhmm = as_aware(att.punch_in_time).strftime("%H:%M")
    att.status = calc_status(hhmm, P["shift_start"], P["late_after"], att.total_minutes, P["half_day_hours"])
    # distance from tracked points (teleport jumps ignored)
    pts = db.query(LocationLog).filter(LocationLog.attendance_id == att.id).order_by(LocationLog.recorded_at).all()
    dist = 0.0
    prev = (att.in_lat, att.in_lng)
    for p in pts:
        dist += sane_segment(prev[0], prev[1], p.lat, p.lng)
        prev = (p.lat, p.lng)
    if att.out_lat and prev:
        dist += sane_segment(prev[0], prev[1], att.out_lat, att.out_lng)
    att.total_distance_m = dist
    db.commit()
    return PunchResp(id=att.id, date=str(att.date), punch_in_time=att.punch_in_time,
                     punch_out_time=att.punch_out_time, status=att.status,
                     outside_geofence=att.outside_geofence)


@router.get("/policy")
def policy(db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    """Effective shift policy for THIS user (custom override if admin set one)."""
    P = _pol(db, u.id)
    return {"shift_start": P["shift_start"], "shift_end": P["shift_end"],
            "late_after_minutes": P["late_after"],
            "min_shift_hours": P["min_shift_hours"],
            "max_break_minutes": P["max_break_minutes"],
            "max_accuracy_m": P["max_accuracy_m"],
            "overtime_allowed": P["overtime_allowed"],
            "overtime_limit_hours": P["overtime_limit_hours"],
            "lunch_reminder_at": P["lunch_reminder_at"],
            "custom_policy": P["custom"],
            "track_interval_sec": settings.TRACK_INTERVAL_SEC,
            "track_min_distance_m": settings.TRACK_MIN_DISTANCE_M}


@router.get("/today", response_model=TodayOut)
def today(db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    # An un-punched-out shift CONTINUES showing — even if the day changed.
    att = db.query(Attendance).filter(
        Attendance.user_id == u.id, Attendance.punch_out_time.is_(None)).first()
    if not att:
        att = db.query(Attendance).filter(
            Attendance.user_id == u.id, Attendance.date == today_ist_date()).first()
    if not att:
        return TodayOut(has_punched_in=False, has_punched_out=False, server_time=now_ist())
    P = _pol(db, u.id)
    _settle_open_break(db, att.id, P["max_break_minutes"])
    bmins = _break_total(db, att.id)
    ob = _open_break(db, att.id) if att.punch_out_time is None else None
    net_so_far, remaining, can_out = None, None, False
    if att.punch_out_time is None:
        now = now_ist()
        gross = (now - as_aware(att.punch_in_time)).total_seconds()
        open_break_extra = 0
        if ob is not None:
            open_break_extra = max(0, int((now - as_aware(ob.start_time)).total_seconds() // 60))
        net_so_far = max(0, net_minutes(gross, bmins + open_break_extra))
        can_out, remaining = can_punch_out(gross, bmins + open_break_extra, P["min_shift_hours"])
    ot = att.overtime_started_at is not None
    d = {"id": att.id, "date": str(att.date),
         "punch_in_time": att.punch_in_time, "punch_out_time": att.punch_out_time,
         "status": att.status, "in_lat": att.in_lat, "in_lng": att.in_lng,
         "on_break": ob is not None,
         "break_start": ob.start_time if ob else None,
         "break_minutes": bmins, "breaks": _break_list(db, att.id),
         "net_minutes": att.total_minutes if att.punch_out_time else net_so_far,
         "min_shift_hours": P["min_shift_hours"],
         "can_punch_out": True if att.punch_out_time else can_out,
         "remaining_minutes": 0 if att.punch_out_time else remaining,
         "overtime": ot, "overtime_start": att.overtime_started_at,
         "overtime_minutes": att.overtime_minutes or 0,
         "shift_end": P["shift_end"],
         "overtime_allowed": P["overtime_allowed"],
         "overtime_limit_hours": P["overtime_limit_hours"],
         "lunch_reminder_at": P["lunch_reminder_at"]}
    return TodayOut(has_punched_in=True, has_punched_out=att.punch_out_time is not None,
                    attendance=d, server_time=now_ist())


def _month_bounds(month: str) -> tuple[_date, _date]:
    y, m = map(int, month.split("-"))
    start = _date(y, m, 1)
    end = _date(y + (m == 12), m % 12 + 1, 1)
    return start, end


@router.get("/history")
def history(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
            db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    start, end = _month_bounds(month)
    rows = db.query(Attendance).filter(
        Attendance.user_id == u.id,
        Attendance.date >= start,
        Attendance.date < end).order_by(Attendance.date.desc()).all()
    return [{"id": r.id, "date": str(r.date), "punch_in": r.punch_in_time, "punch_out": r.punch_out_time,
             "total_minutes": r.total_minutes, "break_minutes": r.break_minutes or 0,
             "overtime_minutes": r.overtime_minutes or 0, "status": r.status,
             "in_selfie": r.in_selfie_url, "out_selfie": r.out_selfie_url,
             "in_lat": r.in_lat, "in_lng": r.in_lng, "out_lat": r.out_lat, "out_lng": r.out_lng,
             "distance_m": r.total_distance_m} for r in rows]


@router.get("/{att_id}/route")
def route(att_id: int, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    att = db.get(Attendance, att_id)
    if not att or (att.user_id != u.id and u.role != "admin"):
        raise HTTPException(404, "Not found")
    pts = db.query(LocationLog).filter(LocationLog.attendance_id == att_id).order_by(LocationLog.recorded_at).all()
    emp = db.get(User, att.user_id)
    return {"attendance_id": att_id,
            "user": {"id": att.user_id, "name": emp.name if emp else "",
                     "mobile": emp.mobile if emp else ""},
            "date": str(att.date), "status": att.status,
            "punch_in": att.punch_in_time, "punch_out": att.punch_out_time,
            "in_selfie": att.in_selfie_url, "out_selfie": att.out_selfie_url,
            "points": [{"lat": p.lat, "lng": p.lng, "at": p.recorded_at,
                        "accuracy": p.accuracy, "speed": p.speed, "is_mock": p.is_mock} for p in pts],
            "in": {"lat": att.in_lat, "lng": att.in_lng, "accuracy": att.in_accuracy},
            "out": {"lat": att.out_lat, "lng": att.out_lng, "accuracy": att.out_accuracy},
            "distance_m": att.total_distance_m,
            "break_minutes": att.break_minutes or 0,
            "overtime_minutes": att.overtime_minutes or 0,
            "overtime_start": att.overtime_started_at,
            "breaks": _break_list(db, att_id)}


@router.get("/summary")
def summary(month: str = Query(..., pattern=r"^\d{4}-\d{2}$"),
            db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    start, end = _month_bounds(month)
    rows = db.query(Attendance).filter(
        Attendance.user_id == u.id,
        Attendance.date >= start,
        Attendance.date < end).all()
    present = [r for r in rows if r.status in ("Present", "Late")]
    half = [r for r in rows if r.status == "Half-day"]
    tot_min = sum((r.total_minutes or 0) for r in rows)
    tot_break = sum((r.break_minutes or 0) for r in rows)
    tot_ot = sum((r.overtime_minutes or 0) for r in rows)
    dist = sum((r.total_distance_m or 0) for r in rows)
    days = len(present) + len(half) * 0.5
    return {"month": month, "present_days": len(present), "half_days": len(half),
            "late_count": sum(1 for r in rows if r.status == "Late"),
            "total_minutes": tot_min, "total_hours": round(tot_min / 60, 2),
            "total_break_minutes": tot_break,
            "total_break_hours": round(tot_break / 60, 2),
            "total_overtime_minutes": tot_ot,
            "total_overtime_hours": round(tot_ot / 60, 2),
            "avg_hours_per_day": round((tot_min / 60) / days, 2) if days else 0,
            "total_distance_m": round(dist, 1), "total_distance_km": round(dist / 1000, 2)}
