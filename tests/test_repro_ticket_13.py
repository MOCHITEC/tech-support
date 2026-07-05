import datetime as dt
import pytest
from app.services import create_reservation
from app.models import Reservation

def test_cannot_create_overlapping_reservation(db, room, user, now):
    """同一会議室で時間帯が重複する予約は作成できないことを検証する。"""
    # 1. 会議室Aに17:30-18:30の予約を作成
    start_time_1 = now + dt.timedelta(hours=7, minutes=30) # 17:30
    end_time_1 = now + dt.timedelta(hours=8, minutes=30)   # 18:30
    
    reservation_1 = create_reservation(
        db=db,
        room_id=room.id,
        user_id=user.id,
        start=start_time_1,
        end=end_time_1
    )
    
    # 2. 同じ会議室、同じ時間帯で再度予約を試みる
    # 期待される正しい挙動: 2回目の予約は失敗し、例外が発生する
    with pytest.raises(ValueError): # またはより具体的な例外型
        create_reservation(
            db=db,
            room_id=room.id,
            user_id=user.id,
            start=start_time_1,
            end=end_time_1
        )
    
    # データベースに予約が1つしか存在しないことを確認
    reservations_in_db = db.query(Reservation).filter(Reservation.room_id == room.id).all()
    assert len(reservations_in_db) == 1
    assert reservations_in_db[0].id == reservation_1.id
    assert reservations_in_db[0].start_time == start_time_1
    assert reservations_in_db[0].end_time == end_time_1
    assert reservations_in_db[0].status == "active"
