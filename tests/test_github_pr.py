"""修正完了チケットからの PR 作成。

git/GitHub はフェイクに差し替え、ブランチ名・PR 本文・最終パスガード・
オーケストレーションを検証する(実際の push/API 呼び出しは結合部)。
"""
import json
from types import SimpleNamespace

import pytest

from app.agents.github_pr import branch_name, create_fix_pr, pr_body
from app.agents.schemas import CodePatch, GeneratedTest, PipelineResult


class FakeRepo:
    def __init__(self):
        self.calls = []

    def commit_and_push(self, *, branch, files, message):
        self.calls.append({"branch": branch, "files": files, "message": message})


class FakeGitHub:
    def __init__(self, url="https://github.com/o/r/pull/1"):
        self.url = url
        self.calls = []

    def create_pull_request(self, *, head, base, title, body):
        self.calls.append({"head": head, "base": base, "title": title, "body": body})
        return self.url


def _ticket():
    return SimpleNamespace(
        id=7, title="二重予約できる", steps="1. 予約 2. 再予約", tobe="エラー", asis="成立"
    )


def _fixed_result():
    return PipelineResult(
        kind="bug",
        reproduced=True,
        fixed=True,
        attempts=2,
        rationale="仕様では二重予約禁止",
        generated_test=GeneratedTest(
            filename="tests/test_repro_ticket_7.py", code="def test():\n    assert False"
        ),
        patch=CodePatch(files={"app/services.py": "# fixed"}),
        message="修正完了",
    )


def test_branch_name():
    assert branch_name(7) == "agent/ticket-7-fix"


def test_pr_body_includes_report_cause_and_repro():
    body = pr_body(_ticket(), _fixed_result())
    assert "成立" in body  # ASIS（報告された実際の挙動）
    assert "仕様では二重予約禁止" in body  # 原因/根拠
    assert "tests/test_repro_ticket_7.py" in body  # 再現テスト
    assert "#7" in body or "ticket-7" in body  # チケット参照


def test_create_fix_pr_pushes_and_opens_pr():
    repo, github = FakeRepo(), FakeGitHub()
    url = create_fix_pr(_ticket(), _fixed_result(), repo=repo, github=github)

    assert url == "https://github.com/o/r/pull/1"
    pushed = repo.calls[0]
    assert pushed["branch"] == "agent/ticket-7-fix"
    # パッチ + 再現テストの両方を含める。
    assert "app/services.py" in pushed["files"]
    assert "tests/test_repro_ticket_7.py" in pushed["files"]
    assert github.calls[0]["head"] == "agent/ticket-7-fix"
    assert github.calls[0]["base"] == "main"


def test_create_fix_pr_targets_given_base():
    # base はブランチを切る元かつ PR の target。demo を渡すと demo へ向く。
    repo, github = FakeRepo(), FakeGitHub()
    create_fix_pr(_ticket(), _fixed_result(), repo=repo, github=github, base="demo")
    assert github.calls[0]["base"] == "demo"


def test_create_fix_pr_rejects_disallowed_paths():
    result = _fixed_result()
    result.patch.files["infra/secrets.tf"] = "evil"
    repo, github = FakeRepo(), FakeGitHub()
    with pytest.raises(ValueError):
        create_fix_pr(_ticket(), result, repo=repo, github=github)
    assert repo.calls == []
    assert github.calls == []


def test_create_fix_pr_requires_fixed_result():
    result = _fixed_result()
    result.fixed = False
    with pytest.raises(ValueError):
        create_fix_pr(_ticket(), result, repo=FakeRepo(), github=FakeGitHub())


def test_github_client_requests_reviewers(monkeypatch):
    import httpx

    from app.agents.github_pr import GitHubClient

    posts = []

    class _Resp:
        def __init__(self, path):
            self._path = path

        def raise_for_status(self):
            pass

        def json(self):
            return {"html_url": "https://github.com/o/r/pull/9", "number": 9}

    def fake_post(url, **kwargs):
        posts.append((url, json.loads(kwargs["content"])))
        return _Resp(url)

    monkeypatch.setattr(httpx, "post", fake_post)
    client = GitHubClient(repository="o/r", token="t", reviewers=["EndoRai88"])
    url = client.create_pull_request(head="b", base="main", title="t", body="x")

    assert url == "https://github.com/o/r/pull/9"
    assert posts[0][0].endswith("/repos/o/r/pulls")
    assert posts[1][0].endswith("/repos/o/r/pulls/9/requested_reviewers")
    assert posts[1][1] == {"reviewers": ["EndoRai88"]}


def test_github_client_skips_reviewers_when_none(monkeypatch):
    import httpx

    from app.agents.github_pr import GitHubClient

    posts = []

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"html_url": "https://github.com/o/r/pull/9", "number": 9}

    monkeypatch.setattr(
        httpx, "post", lambda url, **kw: (posts.append(url), _Resp())[1]
    )
    client = GitHubClient(repository="o/r", token="t", reviewers=[])
    client.create_pull_request(head="b", base="main", title="t", body="x")

    assert posts == ["https://api.github.com/repos/o/r/pulls"]
