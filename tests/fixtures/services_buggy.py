"""再現テスト用に固定した「仕込みバグ①」入り services.py。

デモの本番バグ(同一会議室・同一時間帯の二重予約が通ってしまう)を確実に含む。
test_agent_pipeline はこのソースを source_root に使い、実装(app/services.py)が
修正済みのブランチでも再現→修正のパイプラインを安定して検証する。
実 app/ の他モジュールと互換な API を保つこと(create_reservation のアンカー行含む)。
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.models import Reservation


def create_reservation(
    db: Session, *, room_id: int, user_id: int, start: dt.datetime, end: dt.datetime
) -> Reservation:
    """予約を作成する。"""
    if end <= start:
        raise ValueError("end_time は start_time より後でなければなりません")

    res = Reservation(
        room_id=room_id, user_id=user_id, start_time=start, end_time=end, status="active"
    )
    db.add(res)
    db.commit()
    db.refresh(res)
    return res


def cancel_reservation(db: Session, *, reservation_id: int, user_id: int) -> Reservation:
    """予約をキャンセルする。"""
    res = db.get(Reservation, reservation_id)
    if res is None:
        raise ValueError("予約が見つかりません")
    if res.user_id != user_id:
        raise ValueError("他の利用者の予約はキャンセルできません")
    if res.status != "active":
        raise ValueError("active な予約のみキャンセルできます")

    res.status = "cancelled"
    db.commit()
    db.refresh(res)
    return res
