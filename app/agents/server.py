"""オーケストレータ(agents サービス)の ASGI アプリ。

公開アプリ(app.main)とは分離した内部サービス。Pub/Sub push を受け、
イベントを inbox に保存(冪等)し、新規イベントなら段階処理(現状トリアージ)を
実行する。段階処理は process_event の lease で二重処理を防ぐ。
"""
import base64
import binascii
import os
from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.agents.inbox import record_event
from app.agents.llm import AgentLLM
from app.agents.processor import process_event
from app.agents.runtime import build_event_handler
from app.db import get_db

orchestrator = FastAPI(title="tech-support orchestrator")


def get_llm() -> AgentLLM:
    """Vertex AI(GCP クレジット)> API キー > ローカル FakeLLM の順で選ぶ。"""
    if os.environ.get("GEMINI_USE_VERTEX", "").lower() == "true":
        from app.agents.gemini_llm import GeminiLLM

        return GeminiLLM(
            use_vertex=True,
            project=os.environ.get("GOOGLE_CLOUD_PROJECT"),
            location=os.environ.get("GEMINI_LOCATION", "us-central1"),
            model=os.environ.get("GEMINI_MODEL", "gemini-2.5-flash"),
        )

    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        from app.agents.gemini_llm import GeminiLLM

        return GeminiLLM(api_key=api_key)

    from app.agents.fake_llm import FakeLLM

    return FakeLLM()


def get_event_processor(
    db: Session = Depends(get_db), llm: AgentLLM = Depends(get_llm)
) -> Callable[[str], None]:
    handler = build_event_handler(db, llm)

    def process(event_id: str) -> None:
        process_event(db, event_id=event_id, handler=handler)

    return process


@orchestrator.post("/pubsub/push")
async def pubsub_push(
    request: Request,
    db: Session = Depends(get_db),
    process: Callable[[str], None] = Depends(get_event_processor),
) -> Response:
    envelope = await request.json()
    message = envelope.get("message") if isinstance(envelope, dict) else None
    if not isinstance(message, dict) or "messageId" not in message:
        raise HTTPException(status_code=400, detail="invalid push envelope")

    data = message.get("data")
    try:
        payload = base64.b64decode(data).decode() if data else ""
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid message data") from exc

    # 新規受付なら処理する。再配信(record_event=False)は ack のみ。
    if record_event(db, event_id=message["messageId"], payload=payload):
        process(message["messageId"])
    return Response(status_code=204)
