import datetime as dt
import pytest
from app.services import create_reservation
from app.models import Reservation

def test_cannot_create_overlapping_reservation(db, room, user, now):
    """
    同一会議室で時間帯が重複する予約は作成できないことを検証する。
    報告: 同一時間同一会議室が予約できる
    """
    # 1. 最初の予約を作成
    # 報告の「17:30-18:30」を再現
    start_time = now.replace(hour=17, minute=30, second=0, microsecond=0)
    end_time = now.replace(hour=18, minute=30, second=0, microsecond=0)

    first_reservation = create_reservation(
        db=db,
        room_id=room.id,
        user_id=user.id,
        start=start_time,
        end=end_time
    )
    assert first_reservation.id is not None
    assert first_reservation.room_id == room.id
    assert first_reservation.user_id == user.id
    assert first_reservation.start_time == start_time
    assert first_reservation.end_time == end_time
    assert first_reservation.status == "active"

    # 2. 同じ時間帯、同じ会議室で2回目の予約を試みる
    # 期待される挙動: ValueError が発生し、予約が作成されない
    with pytest.raises(ValueError): # 仕様書に基づき、重複予約は拒否されるべき
        create_reservation(
            db=db,
            room_id=room.id,
            user_id=user.id,
            start=start_time,
            end=end_time
        )

    # 3. データベースに予約が1つしか存在しないことを確認
    # これは、2回目の予約が失敗し、余分な予約が作成されなかったことを間接的に確認する
    reservations = db.query(Reservation).filter_by(room_id=room.id).all()
    assert len(reservations) == 1
    assert reservations[0].id == first_reservation.id
