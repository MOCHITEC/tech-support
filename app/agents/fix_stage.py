"""再現/修正段階。

REPRODUCING のチケットに対し、再現/修正の結果(PipelineResult)を状態機械の
許可遷移へ写像する。実際の再現テスト生成・実行・修正ループは pipeline の
reproduce_and_fix が担う。
"""
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.llm import AgentLLM
from app.agents.pipeline import reproduce_and_fix
from app.agents.schemas import PipelineResult, TicketInput
from app.models import Ticket
from app.state_machine import TicketState
from app.tickets import transition_ticket

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_SPEC = _REPO_ROOT / "docs" / "仕様書.md"


def apply_pipeline_result(db: Session, ticket: Ticket, result: PipelineResult) -> None:
    """再現/修正結果に応じて REPRODUCING のチケットを遷移させる。"""
    if not result.reproduced:
        transition_ticket(db, ticket, TicketState.AWAITING_INFO, note=result.message)
        return

    transition_ticket(db, ticket, TicketState.FIXING, note="再現を確認しました")
    if result.fixed:
        transition_ticket(db, ticket, TicketState.AWAITING_REVIEW, note=result.message)
    else:
        transition_ticket(db, ticket, TicketState.ESCALATED, note=result.message)


def run_reproduce_fix(
    db: Session,
    *,
    ticket: Ticket,
    llm: AgentLLM,
    workspace_root: Path,
    spec_path: Path | None = None,
) -> PipelineResult:
    """REPRODUCING のチケットの再現/修正を実行し、結果を状態へ反映する。"""
    spec = (spec_path or _DEFAULT_SPEC).read_text(encoding="utf-8")
    result = reproduce_and_fix(
        TicketInput(
            title=ticket.title, steps=ticket.steps, tobe=ticket.tobe, asis=ticket.asis
        ),
        ticket_id=ticket.id,
        llm=llm,
        spec=spec,
        workspace_root=workspace_root,
    )
    apply_pipeline_result(db, ticket, result)
    return result
