"""疑似ログイン。セッション開始時に専用デモユーザを自動割当する(ユーザ選択画面なし)。"""
import uuid

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """セッションに紐づくデモユーザを返す。無ければ新規作成して割り当てる。"""
    user_id = request.session.get("user_id")
    if user_id is not None:
        user = db.get(User, user_id)
        if user is not None:
            return user

    user = User(name=f"demo-{uuid.uuid4().hex[:6]}")
    db.add(user)
    db.commit()
    db.refresh(user)
    request.session["user_id"] = user.id
    return user
