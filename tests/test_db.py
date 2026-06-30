"""DATABASE_URL の決定ロジック(明示指定 / Cloud SQL ソケット / ローカル SQLite)。"""
from app.db import database_url


def test_explicit_database_url_takes_precedence():
    env = {"DATABASE_URL": "postgresql+psycopg2://u:p@host/db"}
    assert database_url(env) == "postgresql+psycopg2://u:p@host/db"


def test_builds_cloud_sql_socket_url_from_components():
    env = {
        "DB_USER": "app",
        "DB_PASSWORD": "secret",
        "DB_NAME": "appdb",
        "INSTANCE_CONNECTION_NAME": "proj:asia-northeast1:pg",
    }
    assert database_url(env) == (
        "postgresql+psycopg2://app:secret@/appdb"
        "?host=/cloudsql/proj:asia-northeast1:pg"
    )


def test_url_encodes_password_special_characters():
    env = {
        "DB_USER": "app",
        "DB_PASSWORD": "p@ss/w:rd",
        "DB_NAME": "appdb",
        "INSTANCE_CONNECTION_NAME": "proj:r:pg",
    }
    assert database_url(env) == (
        "postgresql+psycopg2://app:p%40ss%2Fw%3Ard@/appdb"
        "?host=/cloudsql/proj:r:pg"
    )


def test_defaults_to_local_sqlite_when_nothing_set():
    assert database_url({}) == "sqlite:///./local.db"
