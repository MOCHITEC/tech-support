"""GitHub webhook による状態同期。

署名検証・ブランチからの ticket 特定・PR クローズ→状態遷移(merged→RELEASED /
未マージ→PR_REJECTED)を検証する。
"""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.webhook import apply_pr_event, ticket_id_from_ref, verify_signature
from app.db import Base, get_db
from app.models import Ticket, User
from app.state_machine import TicketState

_SECRET = "shh"


def _sign(body: bytes) -> str:
    return "sha256=" + hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()


def test_verify_signature_accepts_valid_and_rejects_invalid():
    body = b'{"a":1}'
    assert verify_signature(_SECRET, body, _sign(body)) is True
    assert verify_signature(_SECRET, body, "sha256=deadbeef") is False
    assert verify_signature(_SECRET, body, "") is False


def test_ticket_id_from_ref():
    assert ticket_id_from_ref("agent/ticket-7-fix") == 7
    assert ticket_id_from_ref("feature/other") is None


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    session.info["factory"] = Session
    try:
        yield session
    finally:
        session.close()


def _ticket(db, state=TicketState.AWAITING_REVIEW):
    user = User(name="デモ太郎")
    db.add(user)
    db.commit()
    t = Ticket(
        user_id=user.id, title="二重予約", steps="s", tobe="t", asis="a", state=state.name
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def test_merged_pr_releases_ticket(db):
    t = _ticket(db)
    apply_pr_event(db, action="closed", merged=True, head_ref=f"agent/ticket-{t.id}-fix")
    assert t.state == TicketState.RELEASED.name


def test_closed_unmerged_pr_rejects_ticket(db):
    t = _ticket(db)
    apply_pr_event(db, action="closed", merged=False, head_ref=f"agent/ticket-{t.id}-fix")
    assert t.state == TicketState.PR_REJECTED.name


def test_non_close_action_is_noop(db):
    t = _ticket(db)
    apply_pr_event(db, action="opened", merged=False, head_ref=f"agent/ticket-{t.id}-fix")
    assert t.state == TicketState.AWAITING_REVIEW.name


def test_disallowed_transition_is_skipped(db):
    t = _ticket(db, state=TicketState.RELEASED)  # 終了状態
    apply_pr_event(db, action="closed", merged=False, head_ref=f"agent/ticket-{t.id}-fix")
    assert t.state == TicketState.RELEASED.name


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", _SECRET)
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    from app.main import app

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.session_factory = Session
        yield c
    app.dependency_overrides.clear()


def _pr_payload(ticket_id, merged):
    return {
        "action": "closed",
        "pull_request": {"merged": merged, "head": {"ref": f"agent/ticket-{ticket_id}-fix"}},
    }


def test_webhook_endpoint_releases_on_merge(client):
    session = client.session_factory()
    t = _ticket(session)
    tid = t.id
    session.close()

    body = json.dumps(_pr_payload(tid, True)).encode()
    resp = client.post(
        "/webhook/github",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": _sign(body)},
    )
    assert resp.status_code == 204

    session = client.session_factory()
    state = session.get(Ticket, tid).state
    session.close()
    assert state == TicketState.RELEASED.name


def test_webhook_endpoint_rejects_bad_signature(client):
    body = json.dumps(_pr_payload(1, True)).encode()
    resp = client.post(
        "/webhook/github",
        content=body,
        headers={"X-GitHub-Event": "pull_request", "X-Hub-Signature-256": "sha256=bad"},
    )
    assert resp.status_code == 401
