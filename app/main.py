"""会議室予約システム(FastAPI)。"""
import datetime as dt
import os
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app.auth import get_current_user
from app.db import get_db
from app.models import Reservation, Room, User
from app.pricing import calculate_price
from app.services import cancel_reservation, create_reservation

app = FastAPI(title="会議室予約システム")
app.add_middleware(
    SessionMiddleware, secret_key=os.environ.get("SESSION_SECRET", "dev-secret-change-me")
)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


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
