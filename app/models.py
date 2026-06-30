"""ORM モデル。会議室・利用者・予約。"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    hourly_rate: Mapped[int] = mapped_column(Integer, nullable=False)


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    start_time: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )

    room: Mapped[Room] = relationship()
    user: Mapped[User] = relationship()


class Ticket(Base):
    """ユーザのフィードバック報告(構造化テンプレート)。"""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    steps: Mapped[str] = mapped_column(String(4000), nullable=False)  # 操作手順一覧
    tobe: Mapped[str] = mapped_column(String(2000), nullable=False)  # 想定結果
    asis: Mapped[str] = mapped_column(String(2000), nullable=False)  # 実際の結果
    screenshot_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    state: Mapped[str] = mapped_column(String(40), nullable=False, default="RECEIVED")
    base_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )

    user: Mapped[User] = relationship()
    history: Mapped[list[TicketHistory]] = relationship(
        back_populates="ticket", order_by="TicketHistory.created_at"
    )


class InboxEvent(Base):
    """Pub/Sub から受信したイベントの冪等受付台帳。

    event_id(Pub/Sub message ID / GitHub delivery ID)を UNIQUE にし、
    再配信を重複なく扱う。state は pending / processing(lease 付き)/ completed。
    """

    __tablename__ = "inbox_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    payload: Mapped[str] = mapped_column(String(8000), nullable=False, default="")
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    lease_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )


class TicketHistory(Base):
    """チケットの状態遷移履歴(ステータスページのタイムライン)。"""

    __tablename__ = "ticket_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), nullable=False)
    state: Mapped[str] = mapped_column(String(40), nullable=False)
    note: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: dt.datetime.now(dt.timezone.utc)
    )

    ticket: Mapped[Ticket] = relationship(back_populates="history")
