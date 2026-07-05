"""修正完了チケットから PR を作成する。

git 操作と GitHub API は seam(repo / github)に分離し、ここでは決定論的な
ブランチ名・PR 本文・最終パスガード・順序のみを扱う。LLM 由来のパッチは PR 作成
直前にも許可パス(app/ tests/, app/agents 除く)を再検証する。
"""
import json
import os
from typing import Protocol

from app.agents.config import sanitize_secret
from app.agents.github_app import github_token
from app.agents.schemas import PipelineResult
from app.agents.workspace import validate_write_paths


class RepoOps(Protocol):
    def commit_and_push(self, *, branch: str, files: dict[str, str], message: str) -> None: ...


class GitHub(Protocol):
    def create_pull_request(self, *, head: str, base: str, title: str, body: str) -> str: ...


def branch_name(ticket_id: int) -> str:
    return f"agent/ticket-{ticket_id}-fix"


def pr_title(ticket) -> str:
    return f"fix: {ticket.title} (ticket #{ticket.id})"


def pr_body(ticket, result: PipelineResult) -> str:
    repro = result.generated_test.filename if result.generated_test else "(なし)"
    return (
        f"## 元の報告 (ticket #{ticket.id})\n"
        f"- タイトル: {ticket.title}\n"
        f"- 操作手順: {ticket.steps}\n"
        f"- 期待 (TOBE): {ticket.tobe}\n"
        f"- 実際 (ASIS): {ticket.asis}\n\n"
        f"## 原因分析\n{result.rationale or '(なし)'}\n\n"
        f"## 再現テスト\n`{repro}`\n\n"
        f"## 修正方針\n{result.message}(試行 {result.attempts} 回)\n"
    )


def create_fix_pr(
    ticket,
    result: PipelineResult,
    *,
    repo: RepoOps,
    github: GitHub,
    base: str = "main",
) -> str:
    """修正成功時のみ、パッチ+再現テストをブランチに積んで PR を作成し URL を返す。"""
    if not result.fixed or result.patch is None or result.generated_test is None:
        raise ValueError("修正成功時のみ PR を作成できます")

    files = dict(result.patch.files)
    files[result.generated_test.filename] = result.generated_test.code
    validate_write_paths(files.keys())  # PR 直前の最終ガード

    branch = branch_name(ticket.id)
    repo.commit_and_push(
        branch=branch, files=files, message=f"fix: ticket #{ticket.id} {ticket.title}"
    )
    return github.create_pull_request(
        head=branch, base=base, title=pr_title(ticket), body=pr_body(ticket, result)
    )


class GitHubClient:
    """GitHub REST API で PR を作成する(GitHub App の installation token を使用)。"""

    def __init__(
        self,
        repository: str | None = None,
        token: str | None = None,
        reviewers: list[str] | None = None,
    ):
        self._repository = repository or os.environ["GITHUB_REPOSITORY"]
        self._token = sanitize_secret(token) if token is not None else github_token()
        # PR に付けるレビュアー(カンマ区切り env。未設定なら付けない)。
        self._reviewers = (
            reviewers
            if reviewers is not None
            else [r.strip() for r in os.environ.get("PR_REVIEWERS", "").split(",") if r.strip()]
        )

    def _post(self, path: str, payload: dict) -> dict:
        import httpx

        resp = httpx.post(
            f"https://api.github.com/repos/{self._repository}/{path}",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
            },
            content=json.dumps(payload),
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    def create_pull_request(self, *, head: str, base: str, title: str, body: str) -> str:
        pr = self._post("pulls", {"head": head, "base": base, "title": title, "body": body})
        if self._reviewers:
            # レビュー依頼は付帯処理: 失敗しても PR 自体は成立させる。
            try:
                self._post(
                    f"pulls/{pr['number']}/requested_reviewers",
                    {"reviewers": self._reviewers},
                )
            except Exception as exc:  # noqa: BLE001
                print(f"レビュアー依頼に失敗しました({self._reviewers}): {exc}")
        return pr["html_url"]

    def create_issue(self, *, title: str, body: str, labels: list[str]) -> str:
        return self._post("issues", {"title": title, "body": body, "labels": labels})["html_url"]
