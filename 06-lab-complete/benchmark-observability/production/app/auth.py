"""
JWT auth cho stack benchmark.

Luồng:
  POST /auth/token {username, password}  ──▶  {access_token, token_type, expires_in}
  POST /ask  + Authorization: Bearer <token>

- Token ký HS256, claim: sub, iat, exp. Khi kiểm tra chỉ nhận HS256 và bắt buộc đủ 3 claim.
- Mọi lỗi token (thiếu / sai / hết hạn) → 401 + WWW-Authenticate: Bearer (RFC 6750).
  Cố ý khác Part 4 (04-api-gateway trả 403 cho token sai): 403 là "đã xác thực nhưng
  không có quyền", mà stack này không có phân quyền.
- Cấu hình đọc trong lifespan (load_auth_config), không phải lúc import:
  thiếu secret / tài khoản hoặc secret < 32 byte → agent không khởi động.
- Không log mật khẩu hay token.
"""
import hmac
import os
import time
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

ALGORITHM = "HS256"
MIN_SECRET_BYTES = 32
REQUIRED_CLAIMS = ["sub", "iat", "exp"]


@dataclass(frozen=True)
class AuthConfig:
    secret: str
    username: str
    password: str
    expire_minutes: int


def load_auth_config() -> AuthConfig:
    """Đọc và kiểm tra cấu hình auth từ env. Lỗi → RuntimeError (agent không khởi động)."""
    missing = [name for name in ("JWT_SECRET", "AUTH_USERNAME", "AUTH_PASSWORD")
               if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Thiếu biến môi trường bắt buộc cho auth: {', '.join(missing)}")

    secret = os.environ["JWT_SECRET"]
    if len(secret.encode()) < MIN_SECRET_BYTES:
        raise RuntimeError(f"JWT_SECRET phải dài ít nhất {MIN_SECRET_BYTES} byte")

    expire_minutes = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    if expire_minutes <= 0:
        raise RuntimeError("JWT_EXPIRE_MINUTES phải > 0")

    return AuthConfig(secret=secret, username=os.environ["AUTH_USERNAME"],
                      password=os.environ["AUTH_PASSWORD"], expire_minutes=expire_minutes)


def get_auth_config(request: Request) -> AuthConfig:
    return request.app.state.auth


# ─────────────────────────────────────────────────────────
# Login
# ─────────────────────────────────────────────────────────
class TokenRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def issue_token(body: TokenRequest, cfg: AuthConfig = Depends(get_auth_config)) -> TokenResponse:
    # So sánh cả hai (không dừng sớm) để thời gian phản hồi không lộ username nào đúng.
    user_ok = _same(body.username, cfg.username)
    pass_ok = _same(body.password, cfg.password)
    if not (user_ok and pass_ok):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Sai username hoặc password")

    now = int(time.time())
    expires_in = cfg.expire_minutes * 60
    token = jwt.encode({"sub": cfg.username, "iat": now, "exp": now + expires_in},
                       cfg.secret, algorithm=ALGORITHM)
    return TokenResponse(access_token=token, expires_in=expires_in)


# ─────────────────────────────────────────────────────────
# Kiểm tra token cho /ask
# ─────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail,
                         headers={"WWW-Authenticate": "Bearer"})


def require_token(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    cfg: AuthConfig = Depends(get_auth_config),
) -> str:
    """Trả về `sub` của token hợp lệ; mọi lỗi → 401."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized("Thiếu header Authorization: Bearer <token>")
    try:
        claims = jwt.decode(creds.credentials, cfg.secret, algorithms=[ALGORITHM],
                            options={"require": REQUIRED_CLAIMS})
    except jwt.ExpiredSignatureError:
        raise _unauthorized("Token đã hết hạn")
    except jwt.InvalidTokenError:
        raise _unauthorized("Token không hợp lệ")
    return claims["sub"]
