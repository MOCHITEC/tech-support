"""オーケストレータの Pub/Sub push ハンドラと冪等 inbox。

push リクエストはイベントを inbox に保存して即 2xx を返す(ack deadline 内で
長時間処理しない)。同一イベントの再配信は重複保存しない(冪等)。
"""
import base64

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.server import orchestrator
from app.db import Base, get_db
from app.models import InboxEvent


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    orchestrator.dependency_overrides[get_db] = override_get_db
    with TestClient(orchestrator) as c:
        c.session_factory = TestingSession
        yield c
    orchestrator.dependency_overrides.clear()


def _envelope(event_id: str, payload: str) -> dict:
    return {
        "message": {
            "messageId": event_id,
            "data": base64.b64encode(payload.encode()).decode(),
        }
    }


def test_push_stores_pending_inbox_event(client):
    resp = client.post("/pubsub/push", json=_envelope("evt-1", '{"ticket_id": 5}'))
    assert resp.status_code == 204

    session = client.session_factory()
    rows = session.query(InboxEvent).all()
    session.close()
    assert len(rows) == 1
    assert rows[0].event_id == "evt-1"
    assert rows[0].state == "pending"
    assert rows[0].payload == '{"ticket_id": 5}'


def test_duplicate_delivery_is_idempotent(client):
    envelope = _envelope("evt-dup", "x")
    assert client.post("/pubsub/push", json=envelope).status_code == 204
    assert client.post("/pubsub/push", json=envelope).status_code == 204

    session = client.session_factory()
    count = session.query(InboxEvent).count()
    session.close()
    assert count == 1


def test_invalid_envelope_returns_400(client):
    assert client.post("/pubsub/push", json={"foo": "bar"}).status_code == 400
