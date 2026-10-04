import math


def haversine_m(lat1, lng1, lat2, lng2) -> float:
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def is_outside(lat, lng, c_lat, c_lng, radius_m) -> bool:
    return haversine_m(lat, lng, c_lat, c_lng) > radius_m


def calc_status(punch_in_hhmm: str, shift_start: str, late_after_min: int,
                total_minutes: int | None, half_day_hours: float) -> str:
    """Pure function — unit tested."""
    if total_minutes is not None and total_minutes < half_day_hours * 60:
        return "Half-day"
    try:
        from datetime import datetime
        fmt = "%H:%M"
        t_in = datetime.strptime(punch_in_hhmm, fmt)
        t_shift = datetime.strptime(shift_start, fmt)
        late_line = t_shift.hour * 60 + t_shift.minute + late_after_min
        in_min = t_in.hour * 60 + t_in.minute
        if in_min > late_line:
            return "Late"
    except Exception:
        pass
    return "Present"


def calc_minutes(delta_seconds: float) -> int:
    return max(0, int(delta_seconds // 60))


def net_minutes(gross_seconds: float, break_minutes: int) -> int:
    """Net working minutes = gross shift time minus breaks."""
    return max(0, calc_minutes(gross_seconds) - (break_minutes or 0))


def can_punch_out(gross_seconds: float, break_minutes: int, min_shift_hours: float) -> tuple[bool, int]:
    """Returns (allowed, remaining_minutes). Punch-out blocked until the
    employee completes min_shift_hours of NET working time."""
    need = int(min_shift_hours * 60)
    worked = net_minutes(gross_seconds, break_minutes)
    if worked >= need:
        return True, 0
    return False, need - worked


def settle_break(elapsed_seconds: float, max_minutes: int) -> tuple[int, bool]:
    """Cap one break at max_minutes. Returns (duration_minutes, capped)."""
    mins = max(0, int(elapsed_seconds // 60))
    if mins > max_minutes:
        return max_minutes, True
    return mins, False


def gps_ok(accuracy: float | None, max_m: float) -> tuple[bool, str]:
    """Real-GPS gate: fix must exist and be tighter than max_m metres."""
    if accuracy is None:
        return False, "No GPS fix — turn location on and retry in open sky"
    if accuracy <= 0 or accuracy > max_m:
        return False, f"Weak GPS (±{accuracy:.0f}m) — need better than {max_m:.0f}m, move to open sky and retry"
    return True, ""


# A single tracking segment longer than this is GPS junk (teleport),
# never real movement at 60-90s cadence. Excluded from distance.
MAX_SEGMENT_M = 2000


def overtime_minutes(out_time, shift_end_time) -> int:
    """Minutes worked past shift end (both timezone-aware)."""
    try:
        return max(0, int((out_time - shift_end_time).total_seconds() // 60))
    except Exception:
        return 0


def sane_segment(lat1, lng1, lat2, lng2) -> float:
    d = haversine_m(lat1, lng1, lat2, lng2)
    return d if d <= MAX_SEGMENT_M else 0.0
