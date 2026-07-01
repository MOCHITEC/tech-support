"""feature 判定時の要件定義 Issue 起票。

triage が feature と判定した場合、生成した要件定義書を GitHub Issue として起票する
(feature-request ラベル、元チケットへの参照つき)。GitHub 呼び出しは seam。
"""
from typing import Protocol


class IssueOpener(Protocol):
    def create_issue(self, *, title: str, body: str, labels: list[str]) -> str: ...


def file_feature_issue(ticket, requirement_doc: str, *, github: IssueOpener) -> str:
    """要件定義書から feature-request Issue を作成し、その URL を返す。"""
    title = f"[Feature] {ticket.title} (ticket #{ticket.id})"
    body = f"{requirement_doc}\n\n---\n元の報告(ticket id: {ticket.id})"
    return github.create_issue(title=title, body=body, labels=["feature-request"])
