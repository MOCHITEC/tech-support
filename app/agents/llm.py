"""LLM の差し替え可能な seam(インターフェース)。

FakeLLM(テスト/ローカル)と、後で実装する Gemini クライアントがこれを満たす。
LLM は構造化データのみを返し、ファイル操作・テスト実行は決定論的コードが行う。
"""
from __future__ import annotations

from typing import Protocol

from app.agents.schemas import CodePatch, GeneratedTest, TicketInput, TriageResult


class AgentLLM(Protocol):
    def triage(self, ticket: TicketInput, spec: str) -> TriageResult: ...

    def generate_repro_test(
        self,
        ticket: TicketInput,
        spec: str,
        ticket_id: int,
        sources: dict[str, str] | None = None,
        fixtures: str = "",
    ) -> GeneratedTest: ...

    def propose_fix(
        self,
        ticket: TicketInput,
        spec: str,
        sources: dict[str, str],
        failing_test: GeneratedTest,
        prior_error: str | None,
    ) -> CodePatch: ...

    def draft_requirement(self, ticket: TicketInput, spec: str) -> str: ...
