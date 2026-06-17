"""ローカル/デモ用の初期データ投入。会議室を用意する。

実行: python -m app.seed
"""
from app.db import Base, SessionLocal, engine
from app.models import Room

ROOMS = [
    ("会議室A", 1000),
    ("会議室B", 1500),
    ("大会議室", 3000),
]


def seed() -> None:
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if db.query(Room).count() == 0:
            db.add_all(Room(name=name, hourly_rate=rate) for name, rate in ROOMS)
            db.commit()
            print(f"会議室を {len(ROOMS)} 件投入しました。")
        else:
            print("会議室は既に存在します。スキップしました。")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
