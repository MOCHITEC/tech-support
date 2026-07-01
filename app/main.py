"""会議室予約システム(FastAPI)。"""
import datetime as dt
import json
import os
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import screenshots, security, tickets
from app.auth import get_current_user
from app.agents.review import fix_request_ticket_id
from app.agents.webhook import apply_pr_event, verify_signature
from app.db import get_db
from app.events import Publisher, default_publisher
from app.gitref import current_commit_sha
from app.models import Reservation, Room, User
from app.pricing import calculate_price
from app.services import cancel_reservation, create_reservation
from app.state_machine import TicketState

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "var" / "screenshots"

app = FastAPI(title="会議室予約システム")
app.add_middleware(
    SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "dev-secret-change-me")
)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_publisher: Publisher | None = None


def get_publisher() -> Publisher:
    """イベント発行 publisher を返す(env から一度だけ決定)。"""
    global _publisher
    if _publisher is None:
        _publisher = default_publisher()
    return _publisher


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
    publisher: Publisher = Depends(get_publisher),
) -> Response:
    """GitHub webhook(HMAC 署名検証)。PR クローズをチケット状態へ同期し、
    レビューでの `@agent fix` を検証のうえ再修正イベントとして発行する。

    公開アプリ側に置く(GitHub は IAM 認証できず、非公開の agents サービスには
    到達できないため)。認証は署名のみ。"""
    body = await request.body()
    if not verify_signature(
        os.environ.get("GITHUB_WEBHOOK_SECRET", ""),
        body,
        request.headers.get("X-Hub-Signature-256", ""),
    ):
        raise HTTPException(status_code=401, detail="invalid signature")

    event = request.headers.get("X-GitHub-Event")
    if event == "pull_request":
        payload = json.loads(body)
        pr = payload.get("pull_request", {})
        apply_pr_event(
            db,
            action=payload.get("action", ""),
            merged=bool(pr.get("merged")),
            head_ref=pr.get("head", {}).get("ref", ""),
        )
    elif event == "issue_comment":
        ticket_id = fix_request_ticket_id(json.loads(body))
        if ticket_id is not None:
            publisher.publish_fix_requested(ticket_id)
    return Response(status_code=204)


@app.get("/")
def index(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rooms = db.query(Room).order_by(Room.id).all()
    return templates.TemplateResponse(
        request, "index.html", {"rooms": rooms, "user": user, "error": None}
    )


@app.post("/reservations")
def post_reservation(
    request: Request,
    room_id: int = Form(...),
    start: str = Form(...),
    end: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        create_reservation(
            db,
            room_id=room_id,
            user_id=user.id,
            start=dt.datetime.fromisoformat(start),
            end=dt.datetime.fromisoformat(end),
        )
    except ValueError as exc:
        rooms = db.query(Room).order_by(Room.id).all()
        return templates.TemplateResponse(
            request, "index.html", {"rooms": rooms, "user": user, "error": str(exc)}
        )
    return RedirectResponse("/my", status_code=303)


@app.get("/my")
def my_reservations(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    reservations = (
        db.query(Reservation)
        .filter(Reservation.user_id == user.id)
        .order_by(Reservation.start_time)
        .all()
    )
    rows = [
        {
            "res": r,
            "price": calculate_price(r.room.hourly_rate, r.start_time, r.end_time),
        }
        for r in reservations
    ]
    return templates.TemplateResponse(
        request, "my.html", {"rows": rows, "user": user}
    )


@app.post("/reservations/{reservation_id}/cancel")
def post_cancel(
    reservation_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        cancel_reservation(db, reservation_id=reservation_id, user_id=user.id)
    except ValueError:
        pass
    return RedirectResponse("/my", status_code=303)


# ---- フィードバック(ユーザから見える CI/CD の入口と進捗) ----


@app.get("/feedback")
def feedback_form(
    request: Request,
    user: User = Depends(get_current_user),
    error: str | None = None,
):
    return templates.TemplateResponse(
        request,
        "feedback.html",
        {"user": user, "csrf_token": security.issue_csrf_token(request), "error": error},
    )


@app.post("/feedback")
async def post_feedback(
    request: Request,
    csrf_token: str = Form(""),
    title: str = Form(...),
    steps: str = Form(...),
    tobe: str = Form(...),
    asis: str = Form(...),
    screenshot: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    publisher: Publisher = Depends(get_publisher),
):
    try:
        security.verify_csrf(request, csrf_token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    try:
        security.check_rate_limit(f"feedback:{user.id}")
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc

    if tickets.count_open_tickets(db, user_id=user.id) >= tickets.MAX_OPEN_TICKETS:
        return templates.TemplateResponse(
            request,
            "feedback.html",
            {
                "user": user,
                "csrf_token": security.issue_csrf_token(request),
                "error": "未完了の報告が多すぎます。処理を待ってから送信してください。",
            },
            status_code=400,
        )

    screenshot_path: str | None = None
    if screenshot is not None and screenshot.filename:
        raw = await screenshot.read()
        try:
            clean_png = screenshots.validate_and_process(raw)
        except ValueError as exc:
            return templates.TemplateResponse(
                request,
                "feedback.html",
                {
                    "user": user,
                    "csrf_token": security.issue_csrf_token(request),
                    "error": f"スクリーンショットを受け付けられません: {exc}",
                },
                status_code=400,
            )
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        fname = f"{uuid.uuid4().hex}.png"
        (SCREENSHOT_DIR / fname).write_bytes(clean_png)
        screenshot_path = fname

    ticket = tickets.create_ticket(
        db,
        user_id=user.id,
        title=title,
        steps=steps,
        tobe=tobe,
        asis=asis,
        screenshot_path=screenshot_path,
        base_commit_sha=current_commit_sha(),
    )
    publisher.publish_ticket_created(ticket.id)
    return RedirectResponse("/tickets", status_code=303)


@app.get("/tickets")
def ticket_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = [
        {"ticket": t, "state_label": TicketState[t.state].value}
        for t in tickets.list_user_tickets(db, user_id=user.id)
    ]
    return templates.TemplateResponse(
        request, "tickets.html", {"rows": rows, "user": user}
    )


@app.get("/tickets/{ticket_id}")
def ticket_detail(
    ticket_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        ticket = tickets.get_user_ticket(db, ticket_id=ticket_id, user_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    timeline = [
        {"label": TicketState[h.state].value, "note": h.note, "at": h.created_at}
        for h in ticket.history
    ]
    return templates.TemplateResponse(
        request,
        "ticket_detail.html",
        {
            "ticket": ticket,
            "state_label": TicketState[ticket.state].value,
            "timeline": timeline,
            "user": user,
        },
    )


@app.get("/tickets/{ticket_id}/screenshot")
def ticket_screenshot(
    ticket_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """所有者本人のみがスクリーンショットを取得できる(代理取得・IDOR 対策)。"""
    try:
        ticket = tickets.get_user_ticket(db, ticket_id=ticket_id, user_id=user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not ticket.screenshot_path:
        raise HTTPException(status_code=404, detail="スクリーンショットがありません")

    path = SCREENSHOT_DIR / ticket.screenshot_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="ファイルが見つかりません")
    return FileResponse(path, media_type="image/png")
