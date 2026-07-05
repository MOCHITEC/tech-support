import datetime as dt
import pytest
from app.services import create_reservation
from app.models import Reservation

def test_cannot_create_overlapping_reservation(db, room, user, now):
    """同一会議室で時間帯が重複する予約は作成できないことを検証する。"""
    # 予約1の開始・終了時刻を設定
    start_time_1 = now.replace(hour=17, minute=30, second=0, microsecond=0)
    end_time_1 = now.replace(hour=18, minute=30, second=0, microsecond=0)

    # 最初の予約を作成
    first_reservation = create_reservation(
        db=db,
        room_id=room.id,
        user_id=user.id,
        start=start_time_1,
        end=end_time_1
    )
    assert first_reservation.id is not None
    assert first_reservation.status == "active"

    # 予約2（予約1と完全に重複する時間帯）の開始・終了時刻を設定
    start_time_2 = now.replace(hour=17, minute=30, second=0, microsecond=0)
    end_time_2 = now.replace(hour=18, minute=30, second=0, microsecond=0)

    # 重複する予約を作成しようとするとValueErrorが発生することを確認
    with pytest.raises(ValueError):
        create_reservation(
            db=db,
            room_id=room.id,
            user_id=user.id,
            start=start_time_2,
            end=end_time_2
        )

    # DBに予約が1件しか存在しないことを確認
    reservations_in_db = db.query(Reservation).filter(Reservation.room_id == room.id).all()
    assert len(reservations_in_db) == 1
    assert reservations_in_db[0].id == first_reservation.id

    # 予約3（予約1と部分的に重複する時間帯）の開始・終了時刻を設定
    start_time_3 = now.replace(hour=18, minute=0, second=0, microsecond=0) # 予約1の途中から開始
    end_time_3 = now.replace(hour=19, minute=0, second=0, microsecond=0)

    # 部分的に重複する予約を作成しようとするとValueErrorが発生することを確認
    with pytest.raises(ValueError):
        create_reservation(
            db=db,
            room_id=room.id,
            user_id=user.id,
            start=start_time_3,
            end=end_time_3
        )

    # 予約4（予約1の終了時刻と開始時刻が接する時間帯）の開始・終了時刻を設定
    # 仕様: 境界が接するだけは重複ではない
    start_time_4 = now.replace(hour=18, minute=30, second=0, microsecond=0) # 予約1の終了時刻から開始
    end_time_4 = now.replace(hour=19, minute=30, second=0, microsecond=0)

    # 接する予約は作成できることを確認
    third_reservation = create_reservation(
        db=db,
        room_id=room.id,
        user_id=user.id,
        start=start_time_4,
        end=end_time_4
    )
    assert third_reservation.id is not None
    assert third_reservation.status == "active"

    # DBに予約が2件存在することを確認
    reservations_in_db_after_third = db.query(Reservation).filter(Reservation.room_id == room.id).all()
    assert len(reservations_in_db_after_third) == 2
