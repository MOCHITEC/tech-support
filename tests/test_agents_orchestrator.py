"""push → record → process → full pipeline のエンドツーエンド接続。

本番の処理(クローン/sandbox/PR)はローカルで動かせないため、get_event_processor を
差し替え、run_full_pipeline_for_ticket を FakeLLM + フェイク再現修正/PR で実行する。
HTTP push が record→process→パイプラインを駆動し、チケットが AWAITING_REVIEW へ
進み、inbox イベントが completed になることを検証する。
"""
import base64
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.fake_llm import FakeLLM
from app.agents.fix_stage import run_full_pipeline_for_ticket
from app.agents.processor import process_event
from app.agents.schemas import PipelineResult
from app.agents.server import get_event_processor, orchestrator
from app.db import Base, get_db
from app.models import InboxEvent, Ticket, User
from app.state_machine import TicketState


@pytest.fixture
def env(tmp_path):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    spec = tmp_path / "spec.md"
    spec.write_text("dummy", encoding="utf-8")

    def fake_processor():
        def process(event_id: str) -> None:
            session = Session()
            try:
                def handler(event: InboxEvent) -> None:
                    ticket_id = json.loads(event.payload)["ticket_id"]
                    ticket = session.get(Ticket, ticket_id)
                    run_full_pipeline_for_ticket(
                        session,
                        ticket,
                        llm=FakeLLM(),
                        reproduce_fix=lambda t: PipelineResult(
                            kind="bug", reproduced=True, fixed=True, message="ok"
                        ),
                        pr_creator=lambda t, r: "https://github.com/o/r/pull/1",
                        spec_path=spec,
                    )

                process_event(session, event_id=event_id, handler=handler)
            finally:
                session.close()

        return process

    orchestrator.dependency_overrides[get_db] = override_get_db
    orchestrator.dependency_overrides[get_event_processor] = fake_processor

    seed = Session()
    user = User(name="デモ太郎")
    seed.add(user)
    seed.commit()
    ticket = Ticket(
        user_id=user.id,
        title="二重予約ができてしまう",
        steps="1. 予約 2. 同じ枠で再予約",
        tobe="エラーになるべき",
        asis="両方とも成立してしまう",
        state=TicketState.RECEIVED.name,
    )
    seed.add(ticket)
    seed.commit()
    ticket_id = ticket.id
    seed.close()

    with TestClient(orchestrator) as c:
        yield c, Session, ticket_id
    orchestrator.dependency_overrides.clear()


def _envelope(event_id: str, payload: str) -> dict:
    return {
        "message": {
            "messageId": event_id,
            "data": base64.b64encode(payload.encode()).decode(),
        }
    }


def test_push_drives_ticket_through_full_pipeline(env):
    client, Session, ticket_id = env
    resp = client.post(
        "/pubsub/push", json=_envelope("evt-tri", json.dumps({"ticket_id": ticket_id}))
    )
    assert resp.status_code == 204

    session = Session()
    ticket = session.get(Ticket, ticket_id)
    event = session.query(InboxEvent).filter_by(event_id="evt-tri").one()
    session.close()
    assert ticket.state == TicketState.AWAITING_REVIEW.name
    assert event.state == "completed"
