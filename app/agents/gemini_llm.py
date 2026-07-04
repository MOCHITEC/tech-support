"""Gemini を使う AgentLLM 実装。

生成は2つの seam に集約: json_generate(構造化スキーマで JSON 文字列を返す)と
text_generate(自由文を返す)。既定では google-genai クライアントを使い、テストは
これらを注入してプロンプト構築とパースだけを検証する。LLM 出力は必ず Pydantic で
検証する(不正な出力は ValidationError)。
"""
from collections.abc import Callable

from pydantic import BaseModel

from app.agents.config import sanitize_secret
from app.agents.schemas import CodePatch, GeneratedTest, TicketInput, TriageResult

_DEFAULT_MODEL = "gemini-2.5-flash"


def _ticket_block(ticket: TicketInput) -> str:
    return (
        f"タイトル: {ticket.title}\n"
        f"操作手順: {ticket.steps}\n"
        f"期待(TOBE): {ticket.tobe}\n"
        f"実際(ASIS): {ticket.asis}\n"
    )


class GeminiLLM:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = _DEFAULT_MODEL,
        *,
        use_vertex: bool = False,
        project: str | None = None,
        location: str | None = None,
        json_generate: Callable[[str, type[BaseModel]], str] | None = None,
        text_generate: Callable[[str], str] | None = None,
    ):
        if json_generate is not None and text_generate is not None:
            self._json_generate = json_generate
            self._text_generate = text_generate
        else:
            from google import genai
            from google.genai import types

            if use_vertex:
                # Vertex AI 経由(ADC 認証・API キー不要・GCP クレジットで課金)。
                client = genai.Client(
                    vertexai=True, project=project, location=location
                )
            else:
                client = genai.Client(api_key=sanitize_secret(api_key or ""))

            def _json(prompt: str, schema: type[BaseModel]) -> str:
                return client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                    ),
                ).text

            def _text(prompt: str) -> str:
                return client.models.generate_content(
                    model=model, contents=prompt
                ).text

            self._json_generate = _json
            self._text_generate = _text

    def triage(self, ticket: TicketInput, spec: str) -> TriageResult:
        prompt = (
            "あなたは不具合トリアージ担当です。固定リビジョンの仕様書と利用者の報告を"
            "突き合わせ、bug(仕様との乖離)/ feature(仕様にない要望)/ needs_info"
            "(情報不足)/ duplicate(重複候補)を判定し、根拠と該当箇所を示してください。\n\n"
            f"# 仕様書\n{spec}\n\n# 報告\n{_ticket_block(ticket)}"
        )
        return TriageResult.model_validate_json(self._json_generate(prompt, TriageResult))

    def generate_repro_test(
        self, ticket: TicketInput, spec: str, ticket_id: int
    ) -> GeneratedTest:
        prompt = (
            "報告を再現する、現状コードで失敗する pytest を1つ生成してください。"
            "assertion は仕様書から導出し、FastAPI TestClient を用います。"
            f"ファイル名は tests/test_repro_ticket_{ticket_id}.py としてください。\n\n"
            f"# 仕様書\n{spec}\n\n# 報告\n{_ticket_block(ticket)}"
        )
        return GeneratedTest.model_validate_json(
            self._json_generate(prompt, GeneratedTest)
        )

    def propose_fix(
        self,
        ticket: TicketInput,
        spec: str,
        sources: dict[str, str],
        failing_test: GeneratedTest,
        prior_error: str | None,
    ) -> CodePatch:
        source_block = "\n".join(
            f"## {path}\n{content}" for path, content in sources.items()
        )
        prompt = (
            "失敗するテストを通すための最小修正を提案してください。変更するファイルは"
            "相対パス→新しい全文の辞書で返します。app/ 以外は変更しないでください。\n\n"
            f"# 仕様書\n{spec}\n\n# 報告\n{_ticket_block(ticket)}\n"
            f"# 失敗テスト ({failing_test.filename})\n{failing_test.code}\n\n"
            f"# 直近のエラー\n{prior_error or '(なし)'}\n\n"
            f"# 現在のソース\n{source_block}\n"
        )
        return CodePatch.model_validate_json(self._json_generate(prompt, CodePatch))

    def draft_requirement(self, ticket: TicketInput, spec: str) -> str:
        prompt = (
            "次の要望から要件定義書(背景 / ユーザの声 / 要求事項 / 受入条件案 / "
            "仕様書該当箇所)を Markdown で作成してください。\n\n"
            f"# 仕様書\n{spec}\n\n# 報告\n{_ticket_block(ticket)}"
        )
        return self._text_generate(prompt)
