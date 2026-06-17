"""データベース接続。本番は Cloud SQL(PostgreSQL)、テスト/ローカルは SQLite。

接続先は環境変数 DATABASE_URL で切り替える。未設定時はローカル SQLite。
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./local.db")

# SQLite はスレッド制約があるため接続引数を分岐する。
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    """リクエストスコープの DB セッションを供給する FastAPI 依存。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
