"""@agent fix による再修正(run_refix_for_ticket)。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.fix_stage import run_refix_for_ticket
from app.agents.schemas import PipelineResult
from app.db import Base
from app.models import Ticket, User
from app.state_machine import TicketState


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _ticket(db, state):
    user = User(name="デモ太郎")
    db.add(user)
    db.commit()
    t = Ticket(user_id=user.id, title="t", steps="s", tobe="t", asis="a", state=state.name)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _run(db, ticket, *, fixed):
    calls = []
    run_refix_for_ticket(
        db,
        ticket,
        reproduce_fix=lambda t: PipelineResult(
            kind="bug", reproduced=True, fixed=fixed, message="m"
        ),
        pr_creator=lambda t, r: calls.append(t.id) or "url",
    )
    return calls


def test_refix_success_reopens_review_and_prs(db):
    t = _ticket(db, TicketState.AWAITING_REVIEW)
    calls = _run(db, t, fixed=True)
    assert t.state == TicketState.AWAITING_REVIEW.name
    assert [h.state for h in t.history] == [
        TicketState.FIXING.name,
        TicketState.AWAITING_REVIEW.name,
    ]
    assert calls == [t.id]


def test_refix_failure_escalates(db):
    t = _ticket(db, TicketState.AWAITING_REVIEW)
    calls = _run(db, t, fixed=False)
    assert t.state == TicketState.ESCALATED.name
    assert calls == []


def test_refix_skipped_when_not_transitionable(db):
    t = _ticket(db, TicketState.RECEIVED)  # RECEIVED -> FIXING は不許可
    calls = _run(db, t, fixed=True)
    assert t.state == TicketState.RECEIVED.name
    assert calls == []
