import pytest

from app.models import User
from app.state_machine import TicketState
from app.tickets import (
    create_ticket,
    get_user_ticket,
    list_user_tickets,
    transition_ticket,
)


def _make(db, user):
    return create_ticket(
        db,
        user_id=user.id,
        title="二重予約できてしまう",
        steps="1. 会議室Aを10-11時で予約\n2. もう一度同じ枠で予約",
        tobe="2回目は重複エラーになる",
        asis="2回目も予約できてしまう",
    )


def test_create_ticket_starts_received_with_history(db, user):
    ticket = _make(db, user)

    assert ticket.state == TicketState.RECEIVED.name
    assert len(ticket.history) == 1
    assert ticket.history[0].state == TicketState.RECEIVED.name


def test_legal_transition_updates_state_and_appends_history(db, user):
    ticket = _make(db, user)

    transition_ticket(db, ticket, TicketState.TRIAGING, note="自動トリアージ開始")

    assert ticket.state == TicketState.TRIAGING.name
    assert ticket.history[-1].state == TicketState.TRIAGING.name
    assert ticket.history[-1].note == "自動トリアージ開始"


def test_illegal_transition_raises_and_keeps_state(db, user):
    ticket = _make(db, user)

    with pytest.raises(ValueError):
        transition_ticket(db, ticket, TicketState.RELEASED)

    assert ticket.state == TicketState.RECEIVED.name
    assert len(ticket.history) == 1


def test_get_user_ticket_rejects_non_owner(db, user):
    ticket = _make(db, user)
    other = User(name="別ユーザ")
    db.add(other)
    db.commit()

    with pytest.raises(ValueError):
        get_user_ticket(db, ticket_id=ticket.id, user_id=other.id)


def test_list_user_tickets_only_returns_own(db, user):
    _make(db, user)
    other = User(name="別ユーザ")
    db.add(other)
    db.commit()
    create_ticket(
        db, user_id=other.id, title="他人の報告", steps="s", tobe="t", asis="a"
    )

    mine = list_user_tickets(db, user_id=user.id)

    assert len(mine) == 1
    assert mine[0].user_id == user.id
