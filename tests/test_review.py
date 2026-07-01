"""@agent fix レビューコマンドの検証ロジック。

実行前に全条件を検証する(PLAN §7): action=created / PR 上のコメント /
投稿者が write 権限相当 / コマンド形式が正しい / ボット PR(タイトルに ticket #N)。
"""
from app.agents.review import fix_request_ticket_id, is_fix_command


def test_is_fix_command():
    assert is_fix_command("@agent fix") is True
    assert is_fix_command("please @agent fix this") is True
    assert is_fix_command("@agent  fix") is True
    assert is_fix_command("agent fix") is False  # @ が無い
    assert is_fix_command("@agent fixture") is False  # 別語
    assert is_fix_command("@agentfix") is False
    assert is_fix_command("") is False


def _payload(
    *,
    action="created",
    is_pr=True,
    assoc="MEMBER",
    body="@agent fix",
    title="fix: 二重予約 (ticket #7)",
):
    issue = {"title": title}
    if is_pr:
        issue["pull_request"] = {"url": "https://api.github.com/.../pulls/3"}
    return {
        "action": action,
        "issue": issue,
        "comment": {"body": body, "author_association": assoc},
    }


def test_valid_command_returns_ticket_id():
    assert fix_request_ticket_id(_payload()) == 7


def test_rejects_non_created_action():
    assert fix_request_ticket_id(_payload(action="edited")) is None


def test_rejects_comment_not_on_pr():
    assert fix_request_ticket_id(_payload(is_pr=False)) is None


def test_rejects_insufficient_permission():
    assert fix_request_ticket_id(_payload(assoc="NONE")) is None
    assert fix_request_ticket_id(_payload(assoc="CONTRIBUTOR")) is None


def test_rejects_without_command():
    assert fix_request_ticket_id(_payload(body="looks good, merging")) is None


def test_rejects_without_ticket_reference():
    assert fix_request_ticket_id(_payload(title="random PR title")) is None
