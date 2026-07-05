"""本番のパイプライン組み立て(統合層)。

クローン取得・sandbox 実行・PR 作成の実装を束ね、process_event に渡す stage
ハンドラを作る。各クライアント(git / GCS / Cloud Run / GitHub)は実環境でのみ
動くため、この層はローカル単体テスト対象外(各部品は seam 越しに個別テスト済み)。
"""
import json
import os
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.feature import file_feature_issue
from app.agents.fix_stage import run_full_pipeline_for_ticket, run_refix_for_ticket
from app.agents.github_app import github_token
from app.agents.github_pr import GitHubClient, create_fix_pr
from app.agents.llm import AgentLLM
from app.agents.pipeline import reproduce_and_fix
from app.agents.repo_ops import GitRepoOps
from app.agents.sandbox import CloudRunJobExecutor, GcsBundleStore, SandboxRunner
from app.agents.schemas import PipelineResult, TicketInput
from app.models import InboxEvent, Ticket

_SPEC_REL = "docs/仕様書.md"


def _clone_repo(dest: str) -> Path:
    repo = os.environ["GITHUB_REPOSITORY"]
    token = github_token()
    url = f"https://x-access-token:{token}@github.com/{repo}.git"
    subprocess.run(["git", "clone", url, dest], check=True, capture_output=True, text=True)
    return Path(dest)


def _sandbox() -> SandboxRunner:
    bucket = os.environ["SOURCE_BUNDLE_BUCKET"]
    return SandboxRunner(
        bucket=bucket,
        store=GcsBundleStore(bucket),
        executor=CloudRunJobExecutor(
            os.environ["SANDBOX_JOB"],
            os.environ["REGION"],
            os.environ["GOOGLE_CLOUD_PROJECT"],
        ),
    )


def _reproduce_fix(ticket: Ticket, llm: AgentLLM) -> PipelineResult:
    clone = _clone_repo(tempfile.mkdtemp())
    spec = (clone / _SPEC_REL).read_text(encoding="utf-8")
    sandbox = _sandbox()
    return reproduce_and_fix(
        TicketInput(
            title=ticket.title, steps=ticket.steps, tobe=ticket.tobe, asis=ticket.asis
        ),
        ticket_id=ticket.id,
        llm=llm,
        spec=spec,
        workspace_root=Path(tempfile.mkdtemp()) / "ws",
        source_root=clone,
        run_tests=lambda ws, target: sandbox.run(files=ws.snapshot(), target=target),
    )


def _create_pr(ticket: Ticket, result: PipelineResult) -> str:
    # PR の作成先(ブランチを切る base かつ PR の target)。既定は main、
    # デモ運用では PR_BASE_BRANCH=demo で demo ブランチへ向ける。
    base = os.environ.get("PR_BASE_BRANCH", "main")
    clone = _clone_repo(tempfile.mkdtemp())
    return create_fix_pr(
        ticket, result, repo=GitRepoOps(clone, base=base), github=GitHubClient(), base=base
    )


def _file_issue(ticket: Ticket, llm: AgentLLM) -> str:
    clone = _clone_repo(tempfile.mkdtemp())
    spec = (clone / _SPEC_REL).read_text(encoding="utf-8")
    doc = llm.draft_requirement(
        TicketInput(
            title=ticket.title, steps=ticket.steps, tobe=ticket.tobe, asis=ticket.asis
        ),
        spec,
    )
    return file_feature_issue(ticket, doc, github=GitHubClient())


def build_event_handler(
    db: Session, llm: AgentLLM
) -> Callable[[InboxEvent], None]:
    def handler(event: InboxEvent) -> None:
        payload = json.loads(event.payload)
        ticket_id = payload["ticket_id"]
        ticket = db.get(Ticket, ticket_id)
        if ticket is None:
            raise ValueError(f"ticket not found: {ticket_id}")

        if payload.get("action") == "refix":
            run_refix_for_ticket(
                db,
                ticket,
                reproduce_fix=lambda t: _reproduce_fix(t, llm),
                pr_creator=_create_pr,
            )
        else:
            run_full_pipeline_for_ticket(
                db,
                ticket,
                llm=llm,
                reproduce_fix=lambda t: _reproduce_fix(t, llm),
                pr_creator=_create_pr,
                issue_creator=lambda t: _file_issue(t, llm),
            )

    return handler
