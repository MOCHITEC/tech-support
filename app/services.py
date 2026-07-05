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

    # 同一会議室で時間帯が重複するactiveな予約が存在しないか確認
    # 重複の条件: (新規予約の開始時刻 < 既存予約の終了時刻) AND (新規予約の終了時刻 > 既存予約の開始時刻)
    overlapping_reservations = db.query(Reservation).filter(
        Reservation.room_id == room_id,
        Reservation.status == "active",
        Reservation.start_time < end,
        Reservation.end_time > start
    ).first()

    if overlapping_reservations:
        raise ValueError("指定された時間帯は既に予約されています。")

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
