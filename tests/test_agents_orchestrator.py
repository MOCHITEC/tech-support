"""push → record → process → triage のエンドツーエンド接続。

有効な ticket を指す push を受けると、その ticket がトリアージを通って遷移し、
inbox イベントが completed になることを検証する(LLM は既定の FakeLLM)。
"""
import base64
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.server import orchestrator
from app.db import Base, get_db
from app.models import InboxEvent, Ticket, User
from app.state_machine import TicketState


@pytest.fixture
def env():
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

    orchestrator.dependency_overrides[get_db] = override_get_db

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


def test_push_drives_ticket_through_triage(env):
    client, Session, ticket_id = env
    resp = client.post(
        "/pubsub/push", json=_envelope("evt-tri", json.dumps({"ticket_id": ticket_id}))
    )
    assert resp.status_code == 204

    session = Session()
    ticket = session.get(Ticket, ticket_id)
    event = session.query(InboxEvent).filter_by(event_id="evt-tri").one()
    session.close()
    # FakeLLM は二重予約報告を bug 判定 → REPRODUCING へ。
    assert ticket.state == TicketState.REPRODUCING.name
    assert event.state == "completed"
