from app.services.rules import calc_status, calc_minutes, haversine_m


def test_hours():
    assert calc_minutes(5400) == 90
    assert calc_minutes(100) == 1


def test_late():
    assert calc_status("10:00", "09:30", 15, 500, 4.0) == "Late"
    assert calc_status("09:35", "09:30", 15, 500, 4.0) == "Present"


def test_half_day():
    assert calc_status("09:00", "09:30", 15, 120, 4.0) == "Half-day"


def test_haversine():
    d = haversine_m(28.6139, 77.2090, 28.6149, 77.2090)
    assert 100 < d < 130
