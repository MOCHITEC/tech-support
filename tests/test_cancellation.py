import datetime as dt

import pytest

from app.models import User
from app.services import cancel_reservation, create_reservation


def _future_reservation(db, room, user):
    start = dt.datetime(2026, 12, 1, 10, 0)
    end = dt.datetime(2026, 12, 1, 11, 0)
    return create_reservation(db, room_id=room.id, user_id=user.id, start=start, end=end)


def test_cancel_future_reservation_sets_cancelled(db, room, user):
    res = _future_reservation(db, room, user)

    cancel_reservation(db, reservation_id=res.id, user_id=user.id)

    assert res.status == "cancelled"


def test_cannot_recancel_cancelled_reservation(db, room, user):
    res = _future_reservation(db, room, user)
    cancel_reservation(db, reservation_id=res.id, user_id=user.id)

    with pytest.raises(ValueError):
        cancel_reservation(db, reservation_id=res.id, user_id=user.id)


def test_cannot_cancel_other_users_reservation(db, room, user):
    res = _future_reservation(db, room, user)
    other = User(name="別ユーザ")
    db.add(other)
    db.commit()

    with pytest.raises(ValueError):
        cancel_reservation(db, reservation_id=res.id, user_id=other.id)
