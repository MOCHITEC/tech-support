"""予約の業務ロジック。"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.models import Reservation


def create_reservation(
    db: Session, *, room_id: int, user_id: int, start: dt.datetime, end: dt.datetime
) -> Reservation:
    """予約を作成する。"""
    if end <= start:
        raise ValueError("end_time は start_time より後でなければなりません")

    # Check for overlapping reservations
    # 重複とは、対象会議室の既存の active 予約と区間 [start_time, end_time) が交差することを指す
    # (境界が接するだけ、例: 既存予約の end_time と新規予約の start_time が同一、は重複ではない)。
    # Overlap condition: (start < existing_end) AND (existing_start < end)
    overlapping_reservations = db.query(Reservation).filter(
        Reservation.room_id == room_id,
        Reservation.status == "active",
        Reservation.start_time < end,  # New reservation starts before existing one ends
        Reservation.end_time > start   # New reservation ends after existing one starts
    ).all()

    if overlapping_reservations:
        raise ValueError("指定された時間帯は既に予約されています")

    res = Reservation(
        room_id=room_id, user_id=user_id, start_time=start, end_time=end, status="active"
    )
    db.add(res)
    db.commit()
    db.refresh(res)
    return res


def cancel_reservation(db: Session, *, reservation_id: int, user_id: int) -> Reservation:
    """予約をキャンセルする。"""
    res = db.get(Reservation, reservation_id)
    if res is None:
        raise ValueError("予約が見つかりません")
    if res.user_id != user_id:
        raise ValueError("他の利用者の予約はキャンセルできません")
    if res.status != "active":
        raise ValueError("active な予約のみキャンセルできます")

    res.status = "cancelled"
    db.commit()
    db.refresh(res)
    return res
