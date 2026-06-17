"""入口の防御。CSRF トークン・Origin 検証・レート制限。

レート制限はローカル/デモ用にプロセス内メモリで保持する(本番では共有ストアに置換)。
"""
import secrets
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from fastapi import Request

RATE_LIMIT_MAX = 5  # ウィンドウ内で許可する送信数
RATE_LIMIT_WINDOW = 60.0  # 秒

_recent: dict[str, deque[float]] = defaultdict(deque)


def issue_csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def verify_csrf(request: Request, submitted: str | None) -> None:
    """CSRF トークンと Origin を検証する。不正なら PermissionError。"""
    expected = request.session.get("csrf_token")
    if not expected or not submitted or not secrets.compare_digest(expected, submitted):
        raise PermissionError("CSRF トークンが無効です")

    origin = request.headers.get("origin")
    if origin is not None and urlparse(origin).netloc != request.url.netloc:
        raise PermissionError("Origin が一致しません")


def check_rate_limit(key: str) -> None:
    """直近ウィンドウの送信回数が上限を超えていれば PermissionError。"""
    now = time.monotonic()
    bucket = _recent[key]
    while bucket and now - bucket[0] > RATE_LIMIT_WINDOW:
        bucket.popleft()
    if len(bucket) >= RATE_LIMIT_MAX:
        raise PermissionError("短時間に送信しすぎです。しばらく待ってください")
    bucket.append(now)
