"""エージェントのオーケストレーション本体。

報告 → トリアージ → (バグなら)再現テスト生成 → サンドボックスで再現確認 →
修正の自己ループ、までを決定論的に進める。LLM は判定と生成のみを担い、ファイル
書き込み・テスト実行・パスガードはこのコードが行う。
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from app.agents.llm import AgentLLM
from app.agents.schemas import PipelineResult, TicketInput
from app.agents.workspace import Workspace, validate_write_paths

# テスト実行 seam: (workspace, target) -> (全て成功したか, 出力)
RunTests = Callable[[Workspace, str], tuple[bool, str]]

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_SPEC = _REPO_ROOT / "docs" / "仕様書.md"
# LLM に編集候補として渡すソース(これ以外は触らせない)。
_EDITABLE_SOURCES = ("app/services.py", "app/pricing.py", "app/models.py")
_MAX_ATTEMPTS = 5


def run_pipeline(
    ticket: TicketInput,
    *,
    ticket_id: int,
    llm: AgentLLM,
    workspace_root: Path,
    spec_path: Path | None = None,
    source_root: Path | None = None,
    max_attempts: int = _MAX_ATTEMPTS,
) -> PipelineResult:
    spec = (spec_path or _DEFAULT_SPEC).read_text(encoding="utf-8")

    triage = llm.triage(ticket, spec)

    if triage.kind == "feature":
        return PipelineResult(
            kind="feature",
            rationale=triage.rationale,
            spec_citation=triage.spec_citation,
            requirement_doc=llm.draft_requirement(ticket, spec),
            message="機能要望として要件定義書を生成しました。",
        )
    if triage.kind in ("needs_info", "duplicate"):
        return PipelineResult(
            kind=triage.kind,
            rationale=triage.rationale,
            spec_citation=triage.spec_citation,
            escalated=(triage.kind == "duplicate"),
            message="人間の確認が必要です。",
        )

    return reproduce_and_fix(
        ticket,
        ticket_id=ticket_id,
        llm=llm,
        spec=spec,
        workspace_root=workspace_root,
        rationale=triage.rationale,
        spec_citation=triage.spec_citation,
        max_attempts=max_attempts,
        source_root=source_root,
    )


def reproduce_and_fix(
    ticket: TicketInput,
    *,
    ticket_id: int,
    llm: AgentLLM,
    spec: str,
    workspace_root: Path,
    rationale: str = "",
    spec_citation: str = "",
    max_attempts: int = _MAX_ATTEMPTS,
    run_tests: "RunTests | None" = None,
    source_root: Path | None = None,
) -> PipelineResult:
    """バグの再現テスト生成→実行→修正の自己ループ。トリアージ済みを前提とする。

    テスト実行は run_tests seam に委譲する(既定はローカル、本番は sandbox 経由)。
    source_root は作業領域の複製元(既定はリポジトリルート、本番はクローン)。
    """
    run_tests = run_tests or (lambda ws, target: ws.run_tests(target))
    # 再現テスト生成に実コードと conftest フィクスチャを渡し、実 API を import した
    # テストを書かせる(独自アプリを捏造すると修正しても通らないため)。
    src_root = source_root or _REPO_ROOT
    repro_sources = {
        rel: (src_root / rel).read_text(encoding="utf-8")
        for rel in _EDITABLE_SOURCES
        if (src_root / rel).exists()
    }
    conftest = src_root / "tests" / "conftest.py"
    fixtures = conftest.read_text(encoding="utf-8") if conftest.exists() else ""
    test = llm.generate_repro_test(
        ticket, spec, ticket_id, sources=repro_sources, fixtures=fixtures
    )
    validate_write_paths([test.filename])

    ws = Workspace.materialize(workspace_root, source_root)
    ws.write_files({test.filename: test.code})

    test_passes, repro_output = run_tests(ws, test.filename)
    if test_passes:
        # バグ向けテストが現状コードで通る = 再現できない。
        return PipelineResult(
            kind="bug",
            reproduced=False,
            generated_test=test,
            rationale=rationale,
            spec_citation=spec_citation,
            escalated=True,
            message="報告内容を再現できませんでした。追加情報が必要です。",
        )

    prior_error: str | None = repro_output
    for attempt in range(1, max_attempts + 1):
        sources = {
            rel: ws.read(rel) for rel in _EDITABLE_SOURCES if (ws.root / rel).exists()
        }
        try:
            patch = llm.propose_fix(ticket, spec, sources, test, prior_error)
            validate_write_paths(patch.files.keys())
        except Exception as exc:  # noqa: BLE001
            # LLM 出力境界: 空応答(.text=None)や不正パス等は致命エラーにせず、
            # エラーを次の試行に渡して作り直す(1回の空応答でループ全体を落とさない)。
            prior_error = f"修正生成に失敗しました(再試行します): {exc}"
            continue
        ws.write_files(patch.files)

        passed, output = run_tests(ws, test.filename)
        if passed:
            return PipelineResult(
                kind="bug",
                reproduced=True,
                fixed=True,
                attempts=attempt,
                generated_test=test,
                patch=patch,
                rationale=rationale,
                spec_citation=spec_citation,
                message="再現テストを修正で解消しました。レビュー待ちです。",
            )
        prior_error = output

    return PipelineResult(
        kind="bug",
        reproduced=True,
        fixed=False,
        attempts=max_attempts,
        generated_test=test,
        rationale=rationale,
        spec_citation=spec_citation,
        escalated=True,
        message="上限内で修正できませんでした。人間へエスカレーションします。",
    )
