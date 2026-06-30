"""トリアージ段階。

チケットを RECEIVED→TRIAGING に進めてから LLM で判定し、判定種別に応じた
状態へ遷移させる(状態機械の許可遷移のみ)。バグなら REPRODUCING に進め、
後続の再現段階を別メッセージで起動する想定(自己キュー投入は別途)。
"""
import json
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.llm import AgentLLM
from app.agents.schemas import TicketInput, TriageResult
from app.models import InboxEvent, Ticket
from app.state_machine import TicketState
from app.tickets import transition_ticket

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_SPEC = _REPO_ROOT / "docs" / "仕様書.md"

_KIND_TO_STATE: dict[str, TicketState] = {
    "bug": TicketState.REPRODUCING,
    "feature": TicketState.FEATURE_REQUEST,
    "duplicate": TicketState.DUPLICATE,
    "needs_info": TicketState.ESCALATED,
}


def run_triage(
    db: Session,
    *,
    ticket: Ticket,
    llm: AgentLLM,
    spec_path: Path | None = None,
) -> TriageResult:
    spec = (spec_path or _DEFAULT_SPEC).read_text(encoding="utf-8")
    transition_ticket(db, ticket, TicketState.TRIAGING, note="トリアージを開始しました")

    result = llm.triage(
        TicketInput(
            title=ticket.title, steps=ticket.steps, tobe=ticket.tobe, asis=ticket.asis
        ),
        spec,
    )
    transition_ticket(db, ticket, _KIND_TO_STATE[result.kind], note=result.rationale)
    return result


def triage_handler(
    db: Session, llm: AgentLLM, spec_path: Path | None = None
) -> Callable[[InboxEvent], None]:
    """process_event に渡す stage ハンドラ。payload から ticket を解決して実行。"""

    def handler(event: InboxEvent) -> None:
        ticket_id = json.loads(event.payload)["ticket_id"]
        ticket = db.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError(f"ticket not found: {ticket_id}")
        run_triage(db, ticket=ticket, llm=llm, spec_path=spec_path)

    return handler
