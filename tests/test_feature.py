"""feature 判定時の GitHub Issue 起票。"""
from types import SimpleNamespace

from app.agents.feature import file_feature_issue


class FakeGitHub:
    def __init__(self, url="https://github.com/o/r/issues/9"):
        self.url = url
        self.calls = []

    def create_issue(self, *, title, body, labels):
        self.calls.append({"title": title, "body": body, "labels": labels})
        return self.url


def _ticket():
    return SimpleNamespace(id=7, title="繰り返し予約がほしい")


def test_file_feature_issue_builds_and_creates():
    github = FakeGitHub()
    url = file_feature_issue(_ticket(), "# 要件定義書\n背景...", github=github)

    assert url == "https://github.com/o/r/issues/9"
    call = github.calls[0]
    assert "繰り返し予約がほしい" in call["title"]
    assert "# 要件定義書" in call["body"]
    assert "7" in call["body"]  # 元チケット参照
    assert "feature-request" in call["labels"]
