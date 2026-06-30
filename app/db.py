"""データベース接続。本番は Cloud SQL(PostgreSQL)、テスト/ローカルは SQLite。

接続先の決定: ①DATABASE_URL が明示されていればそれを使う ②Cloud SQL の
INSTANCE_CONNECTION_NAME があれば /cloudsql ソケット経由の PostgreSQL URL を
組み立てる ③いずれもなければローカル SQLite。
"""
import os
from collections.abc import Mapping
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def database_url(env: Mapping[str, str]) -> str:
    """環境変数から SQLAlchemy 接続 URL を決定する。"""
    if env.get("DATABASE_URL"):
        return env["DATABASE_URL"]

    instance = env.get("INSTANCE_CONNECTION_NAME")
    if instance:
        user = quote_plus(env.get("DB_USER", ""))
        password = quote_plus(env.get("DB_PASSWORD", ""))
        name = env.get("DB_NAME", "")
        return (
            f"postgresql+psycopg2://{user}:{password}@/{name}"
            f"?host=/cloudsql/{instance}"
        )

    return "sqlite:///./local.db"


DATABASE_URL = database_url(os.environ)

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
