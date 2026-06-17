"""エージェント間でやり取りする構造化データ。LLM 出力はこれで検証する。"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

TriageKind = Literal["bug", "feature", "needs_info", "duplicate"]


class TicketInput(BaseModel):
    title: str
    steps: str
    tobe: str
    asis: str


class TriageResult(BaseModel):
    kind: TriageKind
    rationale: str
    spec_citation: str = ""
    confidence: float = 0.0


class GeneratedTest(BaseModel):
    filename: str  # 例: tests/test_repro_ticket_1.py
    code: str


class CodePatch(BaseModel):
    files: dict[str, str]  # 相対パス -> 新しい全文


class PipelineResult(BaseModel):
    kind: str
    reproduced: bool | None = None
    fixed: bool | None = None
    attempts: int = 0
    generated_test: GeneratedTest | None = None
    patch: CodePatch | None = None
    rationale: str = ""
    spec_citation: str = ""
    requirement_doc: str | None = None
    escalated: bool = False
    message: str = ""
