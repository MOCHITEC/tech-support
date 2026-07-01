"""@agent fix レビューコマンドの検証。

PLAN §7: 実行前に「PR 上のコメント・投稿者が write 権限相当・コマンド形式・
ボット作成 PR」を全て検証する。ボット PR かどうかは PR タイトルの "ticket #N"
形式(create_fix_pr が付与)で判定する。
"""
import re

# コメント本文の author_association。write 相当のみ許可する。
_WRITE_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
_FIX_CMD = re.compile(r"(^|\s)@agent\s+fix(\s|$)", re.IGNORECASE)
_TICKET_RE = re.compile(r"ticket #(\d+)")


def is_fix_command(body: str) -> bool:
    return bool(_FIX_CMD.search(body or ""))


def fix_request_ticket_id(payload: dict) -> int | None:
    """issue_comment ペイロードが有効な @agent fix なら ticket_id を返す。"""
    if payload.get("action") != "created":
        return None

    issue = payload.get("issue", {})
    if "pull_request" not in issue:  # PR 上のコメントに限る。
        return None

    comment = payload.get("comment", {})
    if comment.get("author_association") not in _WRITE_ASSOCIATIONS:
        return None
    if not is_fix_command(comment.get("body", "")):
        return None

    match = _TICKET_RE.search(issue.get("title", ""))
    return int(match.group(1)) if match else None
