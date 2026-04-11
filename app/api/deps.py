"""Shared FastAPI dependencies — injected via Depends().

Usage in routes:
    @router.get("/projects")
    async def list_projects(
        db: AsyncSession = Depends(get_db),
        user: User = Depends(get_current_user),
        paging: PagingParams = Depends(),
    ):
        ...
"""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, Header, Query
from fastapi.security import OAuth2PasswordBearer

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthError
from app.core.security import decode_access_token
from app.crud.user import user_crud
from app.db.mysql import get_db as _get_db
from app.models.user import User


# ── Database Session ─────────────────────────────────────────

# Re-export so routes import from one place
get_db = _get_db
DBSession = Annotated[AsyncSession, Depends(_get_db)]

# ── ⭐ Swagger 认证入口（关键新增） ──────────────────────────


from app.config import get_settings
settings = get_settings()
# 存储 tokenUrl，用于生成 /docs 的 OpenAPI schema（让 Swagger UI 知道 Authorize 按钮往哪发请求）
# 作为依赖函数，每次请求进来时从 Authorization: Bearer xxx 头里提取 token 字符串
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.api_v1_prefix}/auth/token") 

# ── Authentication ───────────────────────────────────────────

# 任何用了 CurrentUser 的路由 每次请求进来都会调用
async def get_current_user(
    db: DBSession,
     token: str = Depends(oauth2_scheme),   # ⭐ FastAPI 提供的依赖注入机制
) -> User:
    """Extract and validate JWT from Authorization header."""

    if not token:
        raise AuthError("token 为空")

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise AuthError("token 已过期，请重新登录")
    except jwt.PyJWTError:
        raise AuthError("token 无效")

    user_id: str = payload.get("sub", "")
    if not user_id:
        raise AuthError("token 中缺少用户标识")

    user = await user_crud.get(db, id=user_id)
    if user is None:
        raise AuthError("用户不存在或已被禁用")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ── Optional Auth (for public + auth-enhanced endpoints) ─────


async def get_optional_user(
    db: DBSession,
    authorization: str | None = Header(default=None),
) -> User | None:
    """Returns User if valid token present, None otherwise."""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    try:
        return await get_current_user(db, authorization)
    except AuthError:
        return None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


# ── Admin Guard ──────────────────────────────────────────────


async def require_admin(user: CurrentUser) -> User:
    if user.role < 1:
        raise AuthError("需要管理员权限")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


# ── Pagination ───────────────────────────────────────────────


class PagingParams:
    """Common pagination query parameters."""

    def __init__(
        self,
        page: int = Query(default=1, ge=1, description="Page number"),
        page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    ):
        self.page = page
        self.page_size = page_size


Paging = Annotated[PagingParams, Depends()]