"""inbox イベントの処理ライフサイクル。

claim_event で pending(または lease 切れの processing)を processing へ遷移させ
lease を更新する。complete_event で completed にする。process_event は
claim → stage ハンドラ実行 → complete を束ねる。lease 有効中の event は
再取得されないため、同一イベントの二重処理を防ぐ(クラッシュ時は lease 切れで再開)。
"""
import datetime as dt
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.models import InboxEvent

_DEFAULT_LEASE_SECONDS = 600


def _now(now: dt.datetime | None) -> dt.datetime:
    return now if now is not None else dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def claim_event(
    db: Session,
    *,
    event_id: str,
    now: dt.datetime | None = None,
    lease_seconds: int = _DEFAULT_LEASE_SECONDS,
) -> InboxEvent | None:
    """処理権を取得する。取得できれば event を、できなければ None を返す。"""
    now = _now(now)
    event = db.query(InboxEvent).filter_by(event_id=event_id).first()
    if event is None or event.state == "completed":
        return None
    if (
        event.state == "processing"
        and event.lease_expires_at is not None
        and event.lease_expires_at > now
    ):
        return None

    event.state = "processing"
    event.lease_expires_at = now + dt.timedelta(seconds=lease_seconds)
    db.commit()
    return event


def complete_event(db: Session, *, event_id: str) -> None:
    event = db.query(InboxEvent).filter_by(event_id=event_id).first()
    if event is not None:
        event.state = "completed"
        db.commit()


def process_event(
    db: Session,
    *,
    event_id: str,
    handler: Callable[[InboxEvent], None],
    now: dt.datetime | None = None,
    lease_seconds: int = _DEFAULT_LEASE_SECONDS,
) -> bool:
    """claim できれば handler を実行して complete し True を返す。"""
    event = claim_event(db, event_id=event_id, now=now, lease_seconds=lease_seconds)
    if event is None:
        return False
    handler(event)
    complete_event(db, event_id=event_id)
    return True
