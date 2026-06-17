import datetime as dt

from app.pricing import calculate_price


def test_one_hour_booking_costs_hourly_rate():
    start = dt.datetime(2026, 6, 17, 10, 0)
    end = dt.datetime(2026, 6, 17, 11, 0)
    assert calculate_price(hourly_rate=1000, start=start, end=end) == 1000
