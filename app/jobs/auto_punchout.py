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


def _run():
    db = SessionLocal()
    try:
        s = db.get(Setting, 1)
        now = now_ist()
        open_rows = db.query(Attendance).filter(Attendance.punch_out_time.is_(None)).all()
        bmax = 45
        for a in open_rows:
            # per-user shift end (custom policy if admin set one)
            up = db.get(UserPolicy, a.user_id)
            se_str = (up.shift_end if up and up.shift_end
                      else (s.shift_end if s else app_settings.SHIFT_END))
            if now.time() < parse_hhmm(se_str):
                continue
            ot_limit = (up.overtime_limit_hours
                        if up and up.overtime_limit_hours is not None
                        else (s.overtime_limit_hours if s else app_settings.OVERTIME_LIMIT_HOURS))
            ot_allowed = (up.overtime_allowed
                          if up and up.overtime_allowed is not None
                          else (s.overtime_allowed if s and s.overtime_allowed is not None
                                else app_settings.OVERTIME_ALLOWED))
            # overtime chal rahi hai aur limit baki hai -> haath mat lagao
            if a.overtime_started_at and ot_allowed:
                ot_done = (now - as_aware(a.overtime_started_at)).total_seconds() / 3600
                if ot_done <= (ot_limit or 3.0):
                    continue
            # close any running break at punch-out time (capped at max)
            bmins = 0
            for b in db.query(Break).filter(Break.attendance_id == a.id).all():
                if b.end_time is None:
                    mins, capped = settle_break(
                        (now - as_aware(b.start_time)).total_seconds(), bmax)
                    b.end_time = as_aware(b.start_time) + timedelta(minutes=bmax) if capped else now
                    b.duration_minutes = mins
                bmins += b.duration_minutes or 0
            # only auto-close same-day stale sessions
            a.punch_out_time = now
            a.auto_punched_out = True
            a.break_minutes = bmins
            a.total_minutes = net_minutes(
                (now - as_aware(a.punch_in_time)).total_seconds(), bmins)
            from app.core.time import ist_tz as _tz
            from datetime import datetime as _dt
            se_dt = _tz().localize(_dt.combine(a.date, parse_hhmm(se_str)))
            a.overtime_minutes = overtime_minutes(now, se_dt)
            hhmm = as_aware(a.punch_in_time).strftime("%H:%M")
            ss = (up.shift_start if up and up.shift_start
                  else (s.shift_start if s else app_settings.SHIFT_START))
            a.status = calc_status(hhmm, ss, s.late_after if s else 15,
                                   a.total_minutes, s.half_day_hours if s else 4.0)
        db.commit()
    finally:
        db.close()


def start():
    global _sched
    if _sched:
        return
    _sched = BackgroundScheduler(timezone="Asia/Kolkata")
    _sched.add_job(_run, "cron", minute="*/15")
    _sched.start()
