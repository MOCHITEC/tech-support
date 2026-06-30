"""GeminiLLM のプロンプト構築と構造化出力(Pydantic)検証。

実 API は叩かず、生成関数(json/text)を注入してプロンプト内容とパースを検証する。
"""
import pytest
from pydantic import ValidationError

from app.agents.gemini_llm import GeminiLLM
from app.agents.schemas import CodePatch, GeneratedTest, TicketInput, TriageResult


class FakeGen:
    """json/text 生成のフェイク。最後のプロンプトと schema を記録する。"""

    def __init__(self, json_text="", text=""):
        self.json_text = json_text
        self.text = text
        self.json_prompt = None
        self.json_schema = None
        self.text_prompt = None

    def json_generate(self, prompt, schema):
        self.json_prompt = prompt
        self.json_schema = schema
        return self.json_text

    def text_generate(self, prompt):
        self.text_prompt = prompt
        return self.text


def _llm(gen):
    return GeminiLLM(json_generate=gen.json_generate, text_generate=gen.text_generate)


TICKET = TicketInput(
    title="二重予約できる", steps="1. 予約 2. 再予約", tobe="エラー", asis="成立"
)


def test_triage_builds_prompt_and_parses():
    gen = FakeGen(
        json_text='{"kind":"bug","rationale":"乖離あり","spec_citation":"§3","confidence":0.9}'
    )
    result = _llm(gen).triage(TICKET, spec="SPEC-TEXT")

    assert isinstance(result, TriageResult)
    assert result.kind == "bug"
    assert gen.json_schema is TriageResult
    assert "二重予約できる" in gen.json_prompt
    assert "SPEC-TEXT" in gen.json_prompt


def test_generate_repro_test_parses():
    gen = FakeGen(
        json_text='{"filename":"tests/test_repro_ticket_1.py","code":"def test_x():\\n    assert False"}'
    )
    test = _llm(gen).generate_repro_test(TICKET, spec="S", ticket_id=1)

    assert isinstance(test, GeneratedTest)
    assert test.filename == "tests/test_repro_ticket_1.py"
    assert gen.json_schema is GeneratedTest


def test_propose_fix_parses_and_includes_context():
    gen = FakeGen(json_text='{"files":{"app/services.py":"# fixed"}}')
    failing = GeneratedTest(filename="tests/test_repro.py", code="assert False")
    patch = _llm(gen).propose_fix(
        TICKET,
        spec="S",
        sources={"app/services.py": "# original"},
        failing_test=failing,
        prior_error="AssertionError",
    )

    assert isinstance(patch, CodePatch)
    assert patch.files == {"app/services.py": "# fixed"}
    assert "app/services.py" in gen.json_prompt
    assert "AssertionError" in gen.json_prompt


def test_draft_requirement_uses_text_generate():
    gen = FakeGen(text="# 要件定義書\n...")
    out = _llm(gen).draft_requirement(TICKET, spec="S")

    assert out == "# 要件定義書\n..."
    assert "二重予約できる" in gen.text_prompt


def test_invalid_json_raises():
    gen = FakeGen(json_text='{"kind":"not-a-kind"}')
    with pytest.raises(ValidationError):
        _llm(gen).triage(TICKET, spec="S")


def test_get_llm_defaults_to_fake_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from app.agents.fake_llm import FakeLLM
    from app.agents.server import get_llm

    assert isinstance(get_llm(), FakeLLM)
