"""Alembic マイグレーションがモデル定義どおりのスキーマを作ることを検証する。"""
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.db import Base


def _config(url: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


def test_upgrade_head_creates_all_model_tables(tmp_path):
    url = f"sqlite:///{tmp_path / 'm.db'}"
    command.upgrade(_config(url), "head")

    insp = inspect(create_engine(url))
    tables = set(insp.get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables.keys())
