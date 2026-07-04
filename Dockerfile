# 予約アプリ / エージェントのコンテナイメージ。Cloud Run は $PORT を注入する。
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# オーケストレータはリポジトリの clone / branch / push に git を使う。
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY app/ ./app/
# 仕様書はトリアージの判定基準(run_triage が既定で /app/docs/仕様書.md を読む)。
COPY docs/ ./docs/

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
