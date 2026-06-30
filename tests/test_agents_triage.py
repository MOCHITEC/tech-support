"""トリアージ段階: チケットを TRIAGING 経由で判定結果の状態へ遷移させる。

LLM はスタブ。状態機械の許可遷移(RECEIVED→TRIAGING→{REPRODUCING/
FEATURE_REQUEST/DUPLICATE/ESCALATED})に従うことを検証する。
"""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.schemas import TicketInput, TriageResult
from app.agents.triage import run_triage, triage_handler
from app.db import Base
from app.models import Ticket, User
from app.state_machine import TicketState


class StubLLM:
    def __init__(self, result: TriageResult):
        self.result = result
        self.seen: TicketInput | None = None

    def triage(self, ticket: TicketInput, spec: str) -> TriageResult:
        self.seen = ticket
        return self.result


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
    p.write_text("dummy spec", encoding="utf-8")
    return p


@pytest.fixture
def ticket(db):
    user = User(name="デモ太郎")
    db.add(user)
    db.commit()
    t = Ticket(
        user_id=user.id,
        title="二重予約できる",
        steps="1. 予約 2. 同じ枠で再予約",
        tobe="エラーになる",
        asis="両方成立する",
        state=TicketState.RECEIVED.name,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def _result(kind):
    return TriageResult(kind=kind, rationale=f"{kind} と判定", confidence=0.9)


def test_bug_moves_to_reproducing(db, ticket, spec):
    run_triage(db, ticket=ticket, llm=StubLLM(_result("bug")), spec_path=spec)
    assert ticket.state == TicketState.REPRODUCING.name
    states = [h.state for h in ticket.history]
    assert states == [TicketState.TRIAGING.name, TicketState.REPRODUCING.name]


def test_feature_moves_to_feature_request(db, ticket, spec):
    run_triage(db, ticket=ticket, llm=StubLLM(_result("feature")), spec_path=spec)
    assert ticket.state == TicketState.FEATURE_REQUEST.name


def test_duplicate_moves_to_duplicate(db, ticket, spec):
    run_triage(db, ticket=ticket, llm=StubLLM(_result("duplicate")), spec_path=spec)
    assert ticket.state == TicketState.DUPLICATE.name


def test_needs_info_escalates(db, ticket, spec):
    run_triage(db, ticket=ticket, llm=StubLLM(_result("needs_info")), spec_path=spec)
    assert ticket.state == TicketState.ESCALATED.name


def test_triage_passes_ticket_fields_to_llm(db, ticket, spec):
    llm = StubLLM(_result("bug"))
    run_triage(db, ticket=ticket, llm=llm, spec_path=spec)
    assert llm.seen.title == "二重予約できる"
    assert llm.seen.asis == "両方成立する"


def test_handler_parses_payload_and_runs(db, ticket, spec):
    from app.models import InboxEvent

    handler = triage_handler(db, StubLLM(_result("bug")), spec_path=spec)
    handler(InboxEvent(event_id="e", payload=json.dumps({"ticket_id": ticket.id})))
    assert ticket.state == TicketState.REPRODUCING.name


def test_handler_missing_ticket_raises(db, spec):
    from app.models import InboxEvent

    handler = triage_handler(db, StubLLM(_result("bug")), spec_path=spec)
    with pytest.raises(ValueError):
        handler(InboxEvent(event_id="e", payload=json.dumps({"ticket_id": 999})))
