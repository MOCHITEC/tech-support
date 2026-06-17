"""チケット状態機械。docs/状態機械.md の正式定義に対応する。"""
from __future__ import annotations

import enum


class TicketState(enum.Enum):
    RECEIVED = "受付"
    TRIAGING = "トリアージ中"
    REPRODUCING = "再現確認中"
    AWAITING_INFO = "追加情報待ち"
    FIXING = "修正中"
    AWAITING_REVIEW = "レビュー待ち"
    RELEASED = "リリース済み"
    FEATURE_REQUEST = "要望としてIT検討中"
    DUPLICATE = "重複候補(IT確認待ち)"
    ESCALATED = "人間へエスカレーション"
    UNFIXABLE = "修正不能"
    PR_REJECTED = "PR却下"
    DEPLOY_FAILED = "デプロイ失敗"


# 許可遷移。終了状態は空集合。
ALLOWED_TRANSITIONS: dict[TicketState, frozenset[TicketState]] = {
    TicketState.RECEIVED: frozenset({TicketState.TRIAGING}),
    TicketState.TRIAGING: frozenset(
        {
            TicketState.REPRODUCING,
            TicketState.FEATURE_REQUEST,
            TicketState.DUPLICATE,
            TicketState.ESCALATED,
        }
    ),
    TicketState.REPRODUCING: frozenset(
        {TicketState.FIXING, TicketState.AWAITING_INFO, TicketState.ESCALATED}
    ),
    TicketState.AWAITING_INFO: frozenset(
        {TicketState.REPRODUCING, TicketState.ESCALATED}
    ),
    TicketState.FIXING: frozenset(
        {TicketState.AWAITING_REVIEW, TicketState.ESCALATED, TicketState.UNFIXABLE}
    ),
    TicketState.AWAITING_REVIEW: frozenset(
        {
            TicketState.FIXING,
            TicketState.RELEASED,
            TicketState.PR_REJECTED,
            TicketState.DEPLOY_FAILED,
        }
    ),
    TicketState.DEPLOY_FAILED: frozenset({TicketState.FIXING, TicketState.ESCALATED}),
    TicketState.RELEASED: frozenset(),
    TicketState.FEATURE_REQUEST: frozenset(),
    TicketState.DUPLICATE: frozenset(),
    TicketState.ESCALATED: frozenset(),
    TicketState.UNFIXABLE: frozenset(),
    TicketState.PR_REJECTED: frozenset(),
}


# 遷移先を持たない状態 = 終了状態(DEPLOY_FAILED は再試行可なので終了ではない)。
TERMINAL_STATES: frozenset[TicketState] = frozenset(
    state for state, allowed in ALLOWED_TRANSITIONS.items() if not allowed
)


def can_transition(src: TicketState, dst: TicketState) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())


def validate_transition(src: TicketState, dst: TicketState) -> None:
    if not can_transition(src, dst):
        raise ValueError(f"不正な状態遷移: {src.name} -> {dst.name}")
