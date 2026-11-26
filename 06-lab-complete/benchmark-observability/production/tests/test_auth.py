"""Test JWT cho stack benchmark.

Chạy (trong thư mục production/):
  pip install -r requirements-dev.txt
  python -m pytest tests -q
"""
import os
import time

# Phải đặt trước khi import app: settings đọc env lúc import, và không gửi trace khi test.
os.environ["TRACING_ENABLED"] = "false"
os.environ["MOCK_ERROR_RATE"] = "0"
os.environ["MOCK_SLOW_RATE"] = "0"

import jwt  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

SECRET = "test-secret-that-is-at-least-32-bytes-long!"
USER, PASSWORD = "demo", "demo-password"


@pytest.fixture
def auth_env(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)
    monkeypatch.setenv("AUTH_USERNAME", USER)
    monkeypatch.setenv("AUTH_PASSWORD", PASSWORD)
    monkeypatch.delenv("JWT_EXPIRE_MINUTES", raising=False)


@pytest.fixture
def client(auth_env):
    with TestClient(app) as c:
        yield c


def login(client, username=USER, password=PASSWORD):
    return client.post("/auth/token", json={"username": username, "password": password})


def ask(client, headers=None):
    return client.post("/ask", json={"question": "Docker container là gì?"}, headers=headers or {})


def make_token(secret=SECRET, algorithm="HS256", **overrides):
    now = int(time.time())
    claims = {"sub": USER, "iat": now, "exp": now + 600, **overrides}
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, secret, algorithm=algorithm)


# ── Login ────────────────────────────────────────────────
def test_login_ok_returns_bearer_token(client):
    resp = login(client)
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600
    claims = jwt.decode(body["access_token"], SECRET, algorithms=["HS256"])
    assert claims["sub"] == USER
    assert claims["exp"] - claims["iat"] == 3600


@pytest.mark.parametrize("username,password", [(USER, "wrong"), ("other", PASSWORD), ("", "")])
def test_login_wrong_credentials_401(client, username, password):
    assert login(client, username, password).status_code == 401


def test_expire_minutes_configurable(auth_env, monkeypatch):
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "5")
    with TestClient(app) as c:
        assert login(c).json()["expires_in"] == 300


# ── /ask ─────────────────────────────────────────────────
def test_ask_with_valid_token_200(client):
    token = login(client).json()["access_token"]
    resp = ask(client, {"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["answer"]


def test_ask_without_token_401(client):
    resp = ask(client)
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_ask_with_api_key_only_401(client):
    resp = ask(client, {"X-API-Key": "day14-lab-key"})
    assert resp.status_code == 401


@pytest.mark.parametrize("token", [
    "not-a-jwt",
    make_token(secret="another-secret-that-is-also-32-bytes-long"),   # sai chữ ký
    make_token(exp=int(time.time()) - 10),                             # hết hạn
    make_token(sub=None),                                              # thiếu sub
    make_token(iat=None),                                              # thiếu iat
    make_token(exp=None),                                              # thiếu exp
    make_token(algorithm="HS512"),                                     # sai thuật toán
], ids=["garbage", "bad-signature", "expired", "no-sub", "no-iat", "no-exp", "hs512"])
def test_ask_with_bad_token_401(client, token):
    resp = ask(client, {"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"


def test_ask_with_wrong_scheme_401(client):
    token = make_token()
    assert ask(client, {"Authorization": f"Basic {token}"}).status_code == 401


def test_ops_endpoints_need_no_token(client):
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 200
    assert client.get("/metrics").status_code == 200


# ── Cấu hình thiếu → không khởi động ─────────────────────
@pytest.mark.parametrize("missing", ["JWT_SECRET", "AUTH_USERNAME", "AUTH_PASSWORD"])
def test_startup_fails_when_config_missing(auth_env, monkeypatch, missing):
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        with TestClient(app):
            pass


def test_startup_fails_when_secret_too_short(auth_env, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "short")
    with pytest.raises(RuntimeError, match="32"):
        with TestClient(app):
            pass
