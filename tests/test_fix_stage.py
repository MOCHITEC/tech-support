"""再現/修正段階: PipelineResult を状態遷移へ写像する。

REPRODUCING のチケットを、再現可否・修正可否に応じて遷移させる:
- 再現できない → AWAITING_INFO
- 再現+修正成功 → FIXING → AWAITING_REVIEW
- 再現+修正失敗 → FIXING → ESCALATED
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.fix_stage import apply_pipeline_result
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


@pytest.fixture
def ticket(db):
    user = User(name="デモ太郎")
    db.add(user)
    db.commit()
    t = Ticket(
        user_id=user.id,
        title="二重予約",
        steps="s",
        tobe="t",
        asis="a",
        state=TicketState.REPRODUCING.name,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def test_not_reproduced_awaits_info(db, ticket):
    apply_pipeline_result(
        db, ticket, PipelineResult(kind="bug", reproduced=False, message="不足")
    )
    assert ticket.state == TicketState.AWAITING_INFO.name


def test_reproduced_and_fixed_awaits_review(db, ticket):
    apply_pipeline_result(
        db,
        ticket,
        PipelineResult(kind="bug", reproduced=True, fixed=True, message="修正完了"),
    )
    assert ticket.state == TicketState.AWAITING_REVIEW.name
    assert [h.state for h in ticket.history] == [
        TicketState.FIXING.name,
        TicketState.AWAITING_REVIEW.name,
    ]


def test_reproduced_not_fixed_escalates(db, ticket):
    apply_pipeline_result(
        db,
        ticket,
        PipelineResult(kind="bug", reproduced=True, fixed=False, message="上限超過"),
    )
    assert ticket.state == TicketState.ESCALATED.name
    assert [h.state for h in ticket.history] == [
        TicketState.FIXING.name,
        TicketState.ESCALATED.name,
    ]
