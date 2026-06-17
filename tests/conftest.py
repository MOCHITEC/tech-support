"""テスト用フィクスチャ。インメモリ SQLite に毎回新しいスキーマを作る。"""
import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Room, User


@pytest.fixture
def client():
    """SessionMiddleware 込みの TestClient。インメモリ DB に会議室を1件投入する。"""
    from fastapi.testclient import TestClient

    from app.main import app, get_db

    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    seed = TestingSession()
    seed.add(Room(name="会議室A", hourly_rate=1000))
    seed.commit()
    seed.close()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def room(db):
    r = Room(name="会議室A", hourly_rate=1000)
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture
def user(db):
    u = User(name="デモ太郎")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def now():
    return dt.datetime(2026, 6, 17, 10, 0, 0)
