"""inbox イベントの処理ライフサイクル(claim → 処理 → complete)。

クラッシュ耐性: lease 有効中の processing は再取得させず、lease 切れは再開する。
"""
import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.processor import claim_event, complete_event, process_event
from app.db import Base
from app.models import InboxEvent

T0 = dt.datetime(2026, 6, 30, 12, 0, 0)


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _add(db, event_id, state="pending", lease=None, payload=""):
    db.add(
        InboxEvent(
            event_id=event_id, payload=payload, state=state, lease_expires_at=lease
        )
    )
    db.commit()


def test_claim_pending_sets_processing_with_lease(db):
    _add(db, "e1")
    ev = claim_event(db, event_id="e1", now=T0, lease_seconds=600)
    assert ev is not None
    assert ev.state == "processing"
    assert ev.lease_expires_at == T0 + dt.timedelta(seconds=600)


def test_claim_completed_returns_none(db):
    _add(db, "e2", state="completed")
    assert claim_event(db, event_id="e2", now=T0) is None


def test_claim_actively_leased_returns_none(db):
    _add(db, "e3", state="processing", lease=T0 + dt.timedelta(seconds=300))
    assert claim_event(db, event_id="e3", now=T0) is None


def test_claim_expired_lease_reclaims(db):
    _add(db, "e4", state="processing", lease=T0 - dt.timedelta(seconds=1))
    ev = claim_event(db, event_id="e4", now=T0, lease_seconds=600)
    assert ev is not None
    assert ev.lease_expires_at == T0 + dt.timedelta(seconds=600)


def test_complete_sets_completed(db):
    _add(db, "e5", state="processing", lease=T0 + dt.timedelta(seconds=10))
    complete_event(db, event_id="e5")
    assert db.query(InboxEvent).filter_by(event_id="e5").one().state == "completed"


def test_process_event_runs_handler_then_completes(db):
    _add(db, "e6", payload='{"ticket_id": 7}')
    seen = []
    assert process_event(db, event_id="e6", handler=lambda ev: seen.append(ev.payload), now=T0) is True
    assert seen == ['{"ticket_id": 7}']
    assert db.query(InboxEvent).filter_by(event_id="e6").one().state == "completed"


def test_process_event_skips_when_unclaimable(db):
    _add(db, "e7", state="completed")
    calls = []
    assert process_event(db, event_id="e7", handler=lambda ev: calls.append(ev), now=T0) is False
    assert calls == []
