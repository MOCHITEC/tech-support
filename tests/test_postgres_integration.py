"""PostgreSQL 統合テスト(CI のサービスコンテナで実行)。

SQLite では拾えない本番 DB 固有の問題(マイグレーション DDL・psycopg2・日時型)を
検証する。TEST_DATABASE_URL 未設定時はスキップ(ローカルの素の pytest を妨げない)。
"""
import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Room

pytestmark = pytest.mark.integration

_URL = os.environ.get("TEST_DATABASE_URL")
pytest.importorskip("psycopg2")
if not _URL:
    pytest.skip("TEST_DATABASE_URL 未設定", allow_module_level=True)


@pytest.fixture
def pg_client():
    engine = create_engine(_URL)
    # 各テストを再現可能にするためスキーマを作り直す。
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", _URL)
    command.upgrade(cfg, "head")  # 本番と同じくマイグレーションでスキーマ構築。

    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    from app.main import app, get_db

    def override_get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    seed = Session()
    seed.add(Room(name="会議室A", hourly_rate=1000))
    seed.commit()
    seed.close()

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()


def test_reservation_roundtrip_on_postgres(pg_client):
    resp = pg_client.post(
        "/reservations",
        data={"room_id": 1, "start": "2026-12-01T10:00", "end": "2026-12-01T11:00"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    my = pg_client.get("/my")
    assert my.status_code == 200
    assert "会議室A" in my.text
