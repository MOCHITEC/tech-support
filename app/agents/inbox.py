"""inbox: イベント受付の冪等化。

event_id の UNIQUE 制約に依存して「先に INSERT、衝突したら破棄」で冪等性を
保証する(チェックしてから INSERT する方式は競合に弱いため採らない)。
"""
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InboxEvent


def record_event(db: Session, *, event_id: str, payload: str) -> bool:
    """イベントを pending で記録する。新規なら True、再配信なら False。"""
    db.add(InboxEvent(event_id=event_id, payload=payload, state="pending"))
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
