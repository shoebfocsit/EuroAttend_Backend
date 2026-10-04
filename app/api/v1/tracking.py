"""Batch upload (offline-tolerant) + realtime WS + GPS events."""
from datetime import datetime
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query
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


def _max_acc(db: Session) -> float:
    s = db.get(Setting, 1)
    if s and getattr(s, "max_accuracy_m", None):
        return float(s.max_accuracy_m)
    return float(app_settings.MAX_GPS_ACCURACY_M)


@router.post("/batch")
async def batch(body: BatchIn, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    att = db.get(Attendance, body.attendance_id)
    if not att or att.user_id != u.id or att.punch_out_time:
        return {"saved": 0, "error": "invalid/closed session"}
    max_acc = _max_acc(db)
    n, skipped = 0, 0
    for p in body.points:
        # junk filter: 96km-accuracy IP fixes must never pollute the route
        if not gps_ok(p.accuracy, max_acc)[0]:
            skipped += 1
            continue
        exists = db.query(LocationLog).filter(
            LocationLog.attendance_id == att.id,
            LocationLog.recorded_at == p.recorded_at).first()
        if exists:
            continue
        db.add(LocationLog(attendance_id=att.id, user_id=u.id, lat=p.lat, lng=p.lng,
                           accuracy=p.accuracy, speed=p.speed,
                           recorded_at=p.recorded_at, is_mock=p.is_mock))
        n += 1
        # realtime push to subscribed admins (non-blocking best effort)
        await hub.broadcast({"type": "location", "user_id": u.id, "user_name": u.name,
                             "attendance_id": att.id, "lat": p.lat, "lng": p.lng,
                             "accuracy": p.accuracy, "speed": p.speed,
                             "at": p.recorded_at.isoformat(), "is_mock": p.is_mock})
    db.commit()
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
        while True:
            msg = await ws.receive_json()  # {attendance_id,lat,lng,accuracy,speed,recorded_at,is_mock}
            att = db.get(Attendance, msg.get("attendance_id"))
            if not att or att.user_id != uid or att.punch_out_time:
                await ws.send_json({"error": "invalid/closed session"})
                continue
            try:
                rec = datetime.fromisoformat(msg["recorded_at"])
            except Exception:
                rec = now_ist()
            if not gps_ok(msg.get("accuracy"), _max_acc(db))[0]:
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
async def admin_live(ws: WebSocket):
    """Admin dashboard subscribes for all-employee realtime positions. No auth query for brevity — pass token header check in prod via cookie; here accept then send snapshot."""
    await hub.join_admin(ws)
    try:
        await ws.send_json({"type": "snapshot", "positions": hub.last_pos})
        while True:
            await ws.receive_text()  # keep-alive / ping
    except WebSocketDisconnect:
        hub.leave_admin(ws)
