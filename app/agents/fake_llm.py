"""決定論的なフェイク LLM。ローカルでパイプラインを動かし、TDD で検証するため。

本物の Gemini クライアントと同じ AgentLLM インターフェースを満たす。判定や生成は
キーワードと文字列操作で決定論的に行い、二重予約バグ(仕込みバグ①)を題材に
「報告 → トリアージ → 再現テスト → 修正」までを再現する。
"""
from __future__ import annotations

from app.agents.schemas import CodePatch, GeneratedTest, TicketInput, TriageResult

_OVERLAP_CHECK = '''    overlap = (
        db.query(Reservation)
        .filter(
            Reservation.room_id == room_id,
            Reservation.status == "active",
            Reservation.start_time < end,
            start < Reservation.end_time,
        )
        .first()
    )
    if overlap is not None:
        raise ValueError("同一会議室で時間帯が重複する予約はできません")

'''

_ANCHOR = "    res = Reservation("


class FakeLLM:
    """二重予約シナリオに対応した決定論的フェイク。"""

    def triage(self, ticket: TicketInput, spec: str) -> TriageResult:
        text = f"{ticket.title} {ticket.steps} {ticket.asis}"
        if "二重" in text or "重複" in text:
            return TriageResult(
                kind="bug",
                rationale="仕様では二重予約は禁止だが、実際には作成できている。",
                spec_citation="仕様書 §3 予約作成(二重予約の禁止)",
                confidence=0.9,
            )
        return TriageResult(
            kind="feature",
            rationale="仕様書に該当する記述がなく、新しい振る舞いを求めている。",
            spec_citation="",
            confidence=0.7,
        )

    def generate_repro_test(
        self, ticket: TicketInput, spec: str, ticket_id: int
    ) -> GeneratedTest:
        code = (
            "import datetime as dt\n\n"
            "import pytest\n\n"
            "from app.services import create_reservation\n\n\n"
            "def test_double_booking_is_rejected(db, room, user):\n"
            "    create_reservation(\n"
            "        db, room_id=room.id, user_id=user.id,\n"
            "        start=dt.datetime(2026, 6, 18, 10, 0),\n"
            "        end=dt.datetime(2026, 6, 18, 11, 0),\n"
            "    )\n"
            "    with pytest.raises(ValueError):\n"
            "        create_reservation(\n"
            "            db, room_id=room.id, user_id=user.id,\n"
            "            start=dt.datetime(2026, 6, 18, 10, 30),\n"
            "            end=dt.datetime(2026, 6, 18, 11, 30),\n"
            "        )\n"
        )
        return GeneratedTest(filename=f"tests/test_repro_ticket_{ticket_id}.py", code=code)

    def propose_fix(
        self,
        ticket: TicketInput,
        spec: str,
        sources: dict[str, str],
        failing_test: GeneratedTest,
        prior_error: str | None,
    ) -> CodePatch:
        services = sources["app/services.py"]
        if _ANCHOR not in services:
            raise ValueError("修正対象のアンカーが見つかりません")
        fixed = services.replace(_ANCHOR, _OVERLAP_CHECK + _ANCHOR, 1)
        return CodePatch(files={"app/services.py": fixed})

    def draft_requirement(self, ticket: TicketInput, spec: str) -> str:
        return (
            f"# 要件定義書(自動生成): {ticket.title}\n\n"
            f"## 背景 / ユーザの声\n{ticket.steps}\n\n"
            f"## 要求事項\n想定: {ticket.tobe} / 現状: {ticket.asis}\n\n"
            "## 受入条件(案)\n- 要求された振る舞いが満たされること\n\n"
            "## 判定根拠\n仕様書に該当記述がないため機能要望と判定。"
        )
