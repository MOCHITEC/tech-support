"""予約料金の計算。"""
import datetime as dt


def calculate_price(hourly_rate: int, start: dt.datetime, end: dt.datetime) -> int:
    """予約料金を算出する。利用時間(時間) × 時間単価。"""
    hours = (end - start).total_seconds() / 3600
    return int(hourly_rate * hours)
