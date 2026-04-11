"""Security utilities — JWT token management and password hashing.

Usage:
    hashed = hash_password("my_secret")
    assert verify_password("my_secret", hashed)

    token = create_access_token(user_id="abc123")
    payload = decode_access_token(token)  # {"sub": "abc123", "exp": ...}
"""
# 登陆流程
# 用户输入密码
# bcrypt 校验密码
# 登陆成功就用JWT生成token
# 前端保存token
# 请求接口时带 token

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt # 密码加密（hash） & 校验（verify）
import jwt # JSON Web Token

from app.config import get_settings


# ── Password ─────────────────────────────────────────────────
# 直接用 bcrypt 库，不再依赖 passlib（passlib 与 bcrypt>=4.1 不兼容）


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ── JWT ──────────────────────────────────────────────────────


def create_access_token(
    user_id: str,
    extra: dict | None = None,
    expires_minutes: int | None = None,
) -> str:
    """Create a signed JWT token."""
    settings = get_settings()
    exp = expires_minutes or settings.jwt_expire_minutes
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=exp),
        "iat": datetime.now(timezone.utc),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT token. Raises jwt.PyJWTError on failure."""
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])