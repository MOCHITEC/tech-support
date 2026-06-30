"""single-pass オーケストレーション: triage→(bug)再現/修正→(fixed)PR。

LLM・再現/修正エンジン・PR 作成は注入。チケットが正しい終端状態へ進み、
PR は修正成功時のみ作成されることを検証する。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.fix_stage import run_full_pipeline_for_ticket
from app.agents.schemas import PipelineResult, TicketInput, TriageResult
from app.db import Base
from app.models import Ticket, User
from app.state_machine import TicketState


class StubLLM:
    def __init__(self, kind):
        self.kind = kind

    def triage(self, ticket: TicketInput, spec: str) -> TriageResult:
        return TriageResult(kind=self.kind, rationale="r")


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
def spec(tmp_path):
    p = tmp_path / "spec.md"
    p.write_text("dummy", encoding="utf-8")
    return p


@pytest.fixture
def ticket(db):
    user = User(name="デモ太郎")
    db.add(user)
    db.commit()
    t = Ticket(
        user_id=user.id, title="二重予約", steps="s", tobe="t", asis="a",
        state=TicketState.RECEIVED.name,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _run(db, ticket, *, kind, result=None, spec):
    calls = {"reproduce_fix": 0, "pr": []}

    def reproduce_fix(_ticket):
        calls["reproduce_fix"] += 1
        return result

    def pr_creator(_ticket, _result):
        calls["pr"].append(_ticket.id)
        return "https://github.com/o/r/pull/1"

    run_full_pipeline_for_ticket(
        db, ticket, llm=StubLLM(kind), reproduce_fix=reproduce_fix,
        pr_creator=pr_creator, spec_path=spec,
    )
    return calls


def test_feature_stops_after_triage(db, ticket, spec):
    calls = _run(db, ticket, kind="feature", spec=spec)
    assert ticket.state == TicketState.FEATURE_REQUEST.name
    assert calls["reproduce_fix"] == 0
    assert calls["pr"] == []


def test_bug_fixed_reaches_review_and_opens_pr(db, ticket, spec):
    result = PipelineResult(kind="bug", reproduced=True, fixed=True, message="ok")
    calls = _run(db, ticket, kind="bug", result=result, spec=spec)
    assert ticket.state == TicketState.AWAITING_REVIEW.name
    assert calls["reproduce_fix"] == 1
    assert calls["pr"] == [ticket.id]


def test_bug_not_reproduced_awaits_info_no_pr(db, ticket, spec):
    result = PipelineResult(kind="bug", reproduced=False, message="不足")
    calls = _run(db, ticket, kind="bug", result=result, spec=spec)
    assert ticket.state == TicketState.AWAITING_INFO.name
    assert calls["pr"] == []


def test_bug_unfixed_escalates_no_pr(db, ticket, spec):
    result = PipelineResult(kind="bug", reproduced=True, fixed=False, message="上限")
    calls = _run(db, ticket, kind="bug", result=result, spec=spec)
    assert ticket.state == TicketState.ESCALATED.name
    assert calls["pr"] == []
