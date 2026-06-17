"""フィードバックチケットの業務ロジック。状態遷移は状態機械で検証する。"""
from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.models import Ticket, TicketHistory
from app.state_machine import TERMINAL_STATES, TicketState, validate_transition

MAX_OPEN_TICKETS = 3


def create_ticket(
    db: Session,
    *,
    user_id: int,
    title: str,
    steps: str,
    tobe: str,
    asis: str,
    screenshot_path: str | None = None,
    base_commit_sha: str | None = None,
) -> Ticket:
    """RECEIVED 状態でチケットを作成し、初期履歴を記録する。"""
    ticket = Ticket(
        user_id=user_id,
        title=title,
        steps=steps,
        tobe=tobe,
        asis=asis,
        screenshot_path=screenshot_path,
        base_commit_sha=base_commit_sha,
        state=TicketState.RECEIVED.name,
    )
    ticket.history.append(
        TicketHistory(state=TicketState.RECEIVED.name, note="報告を受け付けました")
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def get_user_ticket(db: Session, *, ticket_id: int, user_id: int) -> Ticket:
    """所有者本人のチケットのみ返す。他人・不存在は ValueError(IDOR 対策)。"""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or ticket.user_id != user_id:
        raise ValueError("チケットが見つかりません")
    return ticket


def list_user_tickets(db: Session, *, user_id: int) -> list[Ticket]:
    """本人のチケットを新しい順に返す。"""
    return (
        db.query(Ticket)
        .filter(Ticket.user_id == user_id)
        .order_by(Ticket.created_at.desc())
        .all()
    )


def count_open_tickets(db: Session, *, user_id: int) -> int:
    """終了していないチケット数を返す。"""
    terminal = [s.name for s in TERMINAL_STATES]
    return (
        db.query(Ticket)
        .filter(Ticket.user_id == user_id, Ticket.state.notin_(terminal))
        .count()
    )


def transition_ticket(
    db: Session, ticket: Ticket, to_state: TicketState, note: str = ""
) -> Ticket:
    """状態機械で許可された遷移のみ適用し、履歴を追加する。"""
    validate_transition(TicketState[ticket.state], to_state)

    ticket.state = to_state.name
    ticket.updated_at = dt.datetime.now(dt.timezone.utc)
    ticket.history.append(TicketHistory(state=to_state.name, note=note))
    db.commit()
    db.refresh(ticket)
    return ticket
