import datetime as dt

import pytest

from app.models import Reservation
from app.services import create_reservation


def test_create_reservation_persists_active(db, room, user):
    start = dt.datetime(2026, 6, 18, 10, 0)
    end = dt.datetime(2026, 6, 18, 11, 0)

    res = create_reservation(db, room_id=room.id, user_id=user.id, start=start, end=end)

    assert res.id is not None
    assert res.status == "active"
    assert db.query(Reservation).count() == 1


def test_end_must_be_after_start(db, room, user):
    start = dt.datetime(2026, 6, 18, 11, 0)
    end = dt.datetime(2026, 6, 18, 10, 0)

    with pytest.raises(ValueError):
        create_reservation(db, room_id=room.id, user_id=user.id, start=start, end=end)
