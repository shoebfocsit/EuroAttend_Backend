"""Batch upload (offline-tolerant) + realtime WS + GPS events."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_user
from app.core.time import now_ist
from app.core.security import decode
from app.db.session import SessionLocal
from app.models.user import User
from app.models.attendance import Attendance
from app.models.tracking import LocationLog, Event, Setting
from app.realtime.manager import hub
from app.schemas.api import BatchIn, EventIn
from app.services.rules import gps_ok
from app.core.config import settings as app_settings

router = APIRouter(prefix="/tracking", tags=["tracking"])


def _max_acc(db: Session, user_id: int | None = None) -> float:
    # per-user override wins, else global, else config default
    if user_id is not None:
        from app.models.user_policy import UserPolicy
        up = db.get(UserPolicy, user_id)
        if up is not None and getattr(up, "max_accuracy_m", None) is not None:
            return float(up.max_accuracy_m)
    s = db.get(Setting, 1)
    if s and getattr(s, "max_accuracy_m", None):
        return float(s.max_accuracy_m)
    return float(app_settings.MAX_GPS_ACCURACY_M)


@router.post("/batch")
async def batch(body: BatchIn, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    att = db.get(Attendance, body.attendance_id)
    if not att or att.user_id != u.id or att.punch_out_time:
        raise HTTPException(404, "invalid/closed session")
    max_acc = _max_acc(db, u.id)
    # future-dated points (>10 min ahead) are device-clock junk
    now = now_ist()
    n, skipped = 0, 0
    existing = {r[0] for r in db.query(LocationLog.recorded_at).filter(
        LocationLog.attendance_id == att.id).all()}
    pending = []
    for p in body.points:
        rec = p.recorded_at
        if rec.tzinfo is None:
            rec = rec.replace(tzinfo=timezone.utc)
        if (rec - now).total_seconds() > 600:
            skipped += 1
            continue
        # junk filter: 96km-accuracy IP fixes must never pollute the route
        if not gps_ok(p.accuracy, max_acc)[0]:
            skipped += 1
            continue
        if rec in existing:
            continue
        existing.add(rec)
        pending.append(LocationLog(attendance_id=att.id, user_id=u.id, lat=p.lat, lng=p.lng,
                                   accuracy=p.accuracy, speed=p.speed,
                                   recorded_at=rec, is_mock=p.is_mock))
        n += 1
    if pending:
        db.add_all(pending)
        db.commit()
        for log in pending:  # one broadcast per saved point (admin map stays live)
            await hub.broadcast({"type": "location", "user_id": u.id, "user_name": u.name,
                                 "attendance_id": att.id, "lat": log.lat, "lng": log.lng,
                                 "accuracy": log.accuracy, "speed": log.speed,
                                 "at": log.recorded_at.isoformat(), "is_mock": log.is_mock})
    return {"saved": n, "skipped": skipped}


@router.post("/events")
def log_event(body: EventIn, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    db.add(Event(attendance_id=body.attendance_id, user_id=u.id,
                type=body.type, created_at=now_ist()))
    db.commit()
    return {"ok": True}


@router.websocket("/live")
async def live(ws: WebSocket, token: str = Query(...)):
    """Employee streams live GPS: ?token=<access>. Admins subscribe via /tracking/admin-live."""
    uid = decode(token, "access")
    if not uid:
        await ws.close(code=4401)
        return
    await ws.accept()
    db = SessionLocal()
    try:
        u = db.get(User, uid)
        if not u or not u.is_active:
            await ws.close(code=4401)
            return
        while True:
            msg = await ws.receive_json()  # {attendance_id,lat,lng,accuracy,speed,recorded_at,is_mock}
            try:
                att = db.get(Attendance, int(msg.get("attendance_id") or 0))
            except Exception:
                await ws.send_json({"error": "invalid/closed session"})
                continue
            if not att or att.user_id != uid or att.punch_out_time:
                await ws.send_json({"error": "invalid/closed session"})
                continue
            try:
                lat = float(msg["lat"]); lng = float(msg["lng"])
                if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                    raise ValueError("lat/lng out of range")
            except Exception:
                await ws.send_json({"error": "invalid lat/lng"})
                continue
            try:
                rec = datetime.fromisoformat(msg["recorded_at"])
            except Exception:
                rec = now_ist()
            if not gps_ok(msg.get("accuracy"), _max_acc(db, uid))[0]:
                await ws.send_json({"ok": True, "skipped": "weak-gps"})
                continue
            db.add(LocationLog(attendance_id=att.id, user_id=uid, lat=msg["lat"], lng=msg["lng"],
                               accuracy=msg.get("accuracy"), speed=msg.get("speed"),
                               recorded_at=rec, is_mock=msg.get("is_mock", False)))
            db.commit()
            payload = {"type": "location", "user_id": uid, "user_name": u.name if u else "",
                       "attendance_id": att.id, **{k: msg.get(k) for k in ("lat", "lng", "accuracy", "speed")},
                       "at": rec.isoformat(), "is_mock": msg.get("is_mock", False)}
            await hub.broadcast(payload)
            await ws.send_json({"ok": True})
    except WebSocketDisconnect:
        pass
    finally:
        db.close()


@router.websocket("/admin-live")
async def admin_live(ws: WebSocket, token: str = Query(...)):
    """Admin dashboard subscribes for all-employee realtime positions. Requires admin JWT."""
    uid = decode(token, "access")
    db = SessionLocal()
    try:
        u = db.get(User, uid) if uid else None
        if not u or not u.is_active or u.role != "admin":
            await ws.close(code=4401)
            return
    finally:
        db.close()
    await hub.join_admin(ws)
    try:
        await ws.send_json({"type": "snapshot", "positions": hub.last_pos})
        while True:
            await ws.receive_text()  # keep-alive / ping
    except WebSocketDisconnect:
        hub.leave_admin(ws)
