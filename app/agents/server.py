"""オーケストレータ(agents サービス)の ASGI アプリ。

公開アプリ(app.main)とは分離した内部サービス。Pub/Sub push を受け、
イベントを inbox に保存して即 2xx を返す(ack deadline 内で長時間処理しない)。
段階処理は別メッセージとして後続キューに投入する設計(PLAN §7)。
"""
import base64
import binascii

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.agents.inbox import record_event
from app.db import get_db

orchestrator = FastAPI(title="tech-support orchestrator")


@orchestrator.post("/pubsub/push")
async def pubsub_push(request: Request, db: Session = Depends(get_db)) -> Response:
    envelope = await request.json()
    message = envelope.get("message") if isinstance(envelope, dict) else None
    if not isinstance(message, dict) or "messageId" not in message:
        raise HTTPException(status_code=400, detail="invalid push envelope")

    data = message.get("data")
    try:
        payload = base64.b64decode(data).decode() if data else ""
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=400, detail="invalid message data") from exc

    record_event(db, event_id=message["messageId"], payload=payload)
    # 新規・再配信いずれも ack(2xx)。再配信は record_event 側で破棄済み。
    return Response(status_code=204)
