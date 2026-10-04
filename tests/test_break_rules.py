from app.services.rules import net_minutes, can_punch_out, settle_break, gps_ok, overtime_minutes


def test_net_subtracts_breaks():
    assert net_minutes(9 * 3600, 60) == 480
    assert net_minutes(3600, 9999) == 0


def test_punchout_blocked_before_8h():
    ok, remaining = can_punch_out(7 * 3600, 0, 8.0)
    assert ok is False and remaining == 60


def test_breaks_dont_count():
    # 8.5h gross with 1h break = 7.5h net -> still blocked
    ok, remaining = can_punch_out(8.5 * 3600, 60, 8.0)
    assert ok is False and remaining == 30


def test_punchout_allowed_after_8h_net():
    ok, remaining = can_punch_out(9 * 3600, 60, 8.0)
    assert ok is True and remaining == 0


def test_break_cap_45():
    assert settle_break(30 * 60, 45) == (30, False)
    assert settle_break(45 * 60, 45) == (45, False)
    assert settle_break(90 * 60, 45) == (45, True)


def test_gps_gate():
    assert gps_ok(12, 200)[0] is True
    assert gps_ok(None, 200)[0] is False
    assert gps_ok(500, 200)[0] is False


def test_overtime_calc():
    import datetime, pytz
    ist = pytz.timezone("Asia/Kolkata")
    se = ist.localize(datetime.datetime(2026, 10, 1, 19, 0))
    assert overtime_minutes(ist.localize(datetime.datetime(2026, 10, 1, 20, 30)), se) == 90
    assert overtime_minutes(ist.localize(datetime.datetime(2026, 10, 1, 18, 0)), se) == 0
