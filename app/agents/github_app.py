"""GitHub App の installation access token を発行する。

App ID + 秘密鍵(PEM)から App JWT を作り、installation access token(約1時間有効)を
取得する。これにより個人 PAT なしで Organization リポジトリへ push / PR / Issue できる。
GITHUB_APP_ID が未設定の環境(ローカル等)では従来の PAT にフォールバックする。
"""
import os
import time

from app.agents.config import sanitize_secret


def _app_jwt(app_id: str, private_key: str) -> str:
    import jwt

    now = int(time.time())
    # iat は時計ずれ対策で 60 秒手前、exp は上限 10 分未満に収める。
    return jwt.encode(
        {"iat": now - 60, "exp": now + 540, "iss": app_id},
        private_key,
        algorithm="RS256",
    )


def installation_token(app_id: str, private_key: str, installation_id: str) -> str:
    """installation access token を取得して返す。"""
    import httpx

    resp = httpx.post(
        f"https://api.github.com/app/installations/{installation_id}/access_tokens",
        headers={
            "Authorization": f"Bearer {_app_jwt(app_id, private_key)}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def github_token() -> str:
    """App が設定されていれば installation token、なければ PAT を返す。"""
    app_id = os.environ.get("GITHUB_APP_ID")
    if app_id:
        return installation_token(
            app_id,
            sanitize_secret(os.environ["GITHUB_APP_PRIVATE_KEY"]),
            os.environ["GITHUB_APP_INSTALLATION_ID"],
        )
    return sanitize_secret(os.environ["GITHUB_TOKEN"])
