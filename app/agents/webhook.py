"""GitHub webhook による状態同期。

PR のクローズを受け、状態機械の許可遷移に従ってチケットを更新する。ブランチ名
(agent/ticket-{id}-fix)から対象チケットを特定し、merged なら RELEASED、未マージ
クローズなら PR_REJECTED に遷移させる。

注: PLAN §5 は本来デプロイ完了(deployment record 照合)で RELEASED にするが、本実装
はデモ簡略版として PR マージを RELEASED とみなす(デプロイ照合は今後の精緻化点)。
"""
import hashlib
import hmac
import re

from sqlalchemy.orm import Session

from app.models import Ticket
from app.state_machine import TicketState, can_transition
from app.tickets import transition_ticket

_BRANCH_RE = re.compile(r"^agent/ticket-(\d+)-fix$")


def verify_signature(secret: str, body: bytes, header: str) -> bool:
    """X-Hub-Signature-256(sha256=...)を検証する。"""
    if not header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)


def ticket_id_from_ref(ref: str) -> int | None:
    match = _BRANCH_RE.match(ref or "")
    return int(match.group(1)) if match else None


def apply_pr_event(db: Session, *, action: str, merged: bool, head_ref: str) -> None:
    """PR クローズイベントを許可された範囲でチケット状態へ反映する。"""
    if action != "closed":
        return
    ticket_id = ticket_id_from_ref(head_ref)
    if ticket_id is None:
        return
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        return

    target = TicketState.RELEASED if merged else TicketState.PR_REJECTED
    note = "PR がマージされました。" if merged else "PR がクローズされました(未マージ)。"
    if can_transition(TicketState[ticket.state], target):
        transition_ticket(db, ticket, target, note=note)
