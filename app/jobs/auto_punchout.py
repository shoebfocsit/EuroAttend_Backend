"""Closes sessions past shift_end (IST) so forgotten punch-outs don't stay open."""
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import timedelta
from app.db.session import SessionLocal
from app.core.time import now_ist, parse_hhmm, as_aware
from app.models.attendance import Attendance, Break
from app.models.user_policy import UserPolicy
from app.models.tracking import Setting
from app.services.rules import net_minutes, calc_status, settle_break, overtime_minutes
from app.core.config import settings as app_settings

_sched = None

# shift_end ke baad itna time do: employee overtime start kare ya khud punch-out
# kare. Isse 19:00:00 pe turant auto-close nahi hota.
GRACE_MINUTES = 30


def _run():
    db = SessionLocal()
    try:
        s = db.get(Setting, 1)
        now = now_ist()
        open_rows = db.query(Attendance).filter(Attendance.punch_out_time.is_(None)).all()
        for a in open_rows:
            # per-user shift end (custom policy if admin set one)
            up = db.get(UserPolicy, a.user_id)
            se_str = (up.shift_end if up and up.shift_end
                      else (s.shift_end if s and s.shift_end else app_settings.SHIFT_END))
            bmax = (up.max_break_minutes
                    if up and up.max_break_minutes is not None
                    else (s.max_break_minutes if s and s.max_break_minutes is not None
                          else app_settings.MAX_BREAK_MINUTES))
            try:
                se_today = parse_hhmm(se_str)
            except ValueError:
                continue
            # close at THIS row's shift-end, not wall-clock — stale multi-day rows
            # must not inflate to now (24h+ totals)
            from app.core.time import ist_tz as _tz
            from datetime import datetime as _dt
            se_dt = _tz().localize(_dt.combine(a.date, se_today))
            # grace window: shift-end ke turant baad close mat karo
            if now < se_dt + timedelta(minutes=GRACE_MINUTES):
                continue
            ot_limit = (up.overtime_limit_hours
                        if up and up.overtime_limit_hours is not None
                        else (s.overtime_limit_hours if s else app_settings.OVERTIME_LIMIT_HOURS))
            ot_allowed = (up.overtime_allowed
                          if up and up.overtime_allowed is not None
                          else (s.overtime_allowed if s and s.overtime_allowed is not None
                                else app_settings.OVERTIME_ALLOWED))
            # overtime chal rahi hai aur limit baki hai -> haath mat lagao
            close_at = se_dt
            if a.overtime_started_at and ot_allowed:
                ot_done = (now - as_aware(a.overtime_started_at)).total_seconds() / 3600
                if ot_done <= (ot_limit or 3.0):
                    continue
                # OT limit cross -> OT limit tak count karo
                close_at = se_dt + timedelta(hours=(ot_limit or 3.0))
            # close any running break at punch-out time (capped at max)
            bmins = 0
            for b in db.query(Break).filter(Break.attendance_id == a.id).all():
                if b.end_time is None:
                    mins, capped = settle_break(
                        max(0.0, (close_at - as_aware(b.start_time)).total_seconds()), bmax)
                    b.end_time = as_aware(b.start_time) + timedelta(minutes=bmax) if capped else close_at
                    b.duration_minutes = mins
                bmins += b.duration_minutes or 0
            # shift-end pe close karo (now pe nahi) taaki grace totals na badhaye
            a.punch_out_time = close_at
            a.auto_punched_out = True
            a.break_minutes = bmins
            a.total_minutes = net_minutes(
                (close_at - as_aware(a.punch_in_time)).total_seconds(), bmins)
            a.overtime_minutes = overtime_minutes(close_at, se_dt)
            hhmm = as_aware(a.punch_in_time).strftime("%H:%M")
            ss = (up.shift_start if up and up.shift_start
                  else (s.shift_start if s and s.shift_start else app_settings.SHIFT_START))
            late_after = s.late_after if s and s.late_after is not None else 15
            half_day = s.half_day_hours if s and s.half_day_hours is not None else 4.0
            a.status = calc_status(hhmm, ss, late_after, a.total_minutes, half_day)
        db.commit()
    finally:
        db.close()


def start():
    global _sched
    if _sched:
        return
    _sched = BackgroundScheduler(timezone="Asia/Kolkata")
    _sched.add_job(_run, "cron", minute="*/15", max_instances=1, coalesce=True)
    _sched.start()
