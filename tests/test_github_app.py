"""GitHub App の installation token 発行とトークン選択のテスト。"""
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.agents import github_app


@pytest.fixture
def rsa_pem():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return priv, pub


def test_app_jwt_is_signed_and_claims_set(rsa_pem):
    priv, pub = rsa_pem
    token = github_app._app_jwt("4218791", priv)
    decoded = jwt.decode(token, pub, algorithms=["RS256"])
    assert decoded["iss"] == "4218791"
    assert decoded["exp"] > decoded["iat"]


def test_github_token_uses_pat_when_app_not_configured(monkeypatch):
    monkeypatch.delenv("GITHUB_APP_ID", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "﻿ ghp_pat \n")
    assert github_app.github_token() == "ghp_pat"


def test_github_token_mints_installation_token_when_app_configured(monkeypatch, rsa_pem):
    priv, _ = rsa_pem
    monkeypatch.setenv("GITHUB_APP_ID", "4218791")
    monkeypatch.setenv("GITHUB_APP_INSTALLATION_ID", "144466688")
    monkeypatch.setenv("GITHUB_APP_PRIVATE_KEY", priv)

    seen = {}

    def fake_mint(app_id, private_key, installation_id):
        seen.update(app_id=app_id, installation_id=installation_id)
        return "ghs_installation"

    monkeypatch.setattr(github_app, "installation_token", fake_mint)
    assert github_app.github_token() == "ghs_installation"
    assert seen == {"app_id": "4218791", "installation_id": "144466688"}
