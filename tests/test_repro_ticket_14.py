import pytest
import datetime as dt
from app.services import create_reservation
from app.models import Reservation
from sqlalchemy.orm import Session

def test_cannot_create_overlapping_reservation(db: Session, room, user, now):
    """同一会議室で時間帯が重複する予約は作成できないことを検証する。"""
    # 1. 最初の予約を作成
    # 例: 2026-06-17 11:00 から 12:00 までの予約
    start_time_1 = now + dt.timedelta(hours=1)
    end_time_1 = now + dt.timedelta(hours=2)

    first_reservation = create_reservation(
        db,
        room_id=room.id,
        user_id=user.id,
        start=start_time_1,
        end=end_time_1
    )

    # データベースに最初の予約が正しく作成されたことを確認
    assert first_reservation.room_id == room.id
    assert first_reservation.user_id == user.id
    assert first_reservation.start_time == start_time_1
    assert first_reservation.end_time == end_time_1
    assert first_reservation.status == "active"

    # 2. 同じ会議室で時間帯が重複する予約を作成しようとする
    # 既存の予約: [11:00, 12:00)
    # 新規の予約: [11:30, 12:30) -> 重複する
    start_time_2 = now + dt.timedelta(hours=1, minutes=30)
    end_time_2 = now + dt.timedelta(hours=2, minutes=30)

    # 期待される挙動: ValueError が発生し、重複予約が拒否される
    with pytest.raises(ValueError):
        create_reservation(
            db,
            room_id=room.id,
            user_id=user.id,
            start=start_time_2,
            end=end_time_2
        )

    # データベースに重複する予約が作成されていないことを確認
    # 最初の予約1件のみが存在するはず
    reservations_in_db = db.query(Reservation).filter(Reservation.room_id == room.id).all()
    assert len(reservations_in_db) == 1
    assert reservations_in_db[0].id == first_reservation.id
