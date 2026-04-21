"""Auth routes — register, login, current user info."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.mysql import get_db

from app.api_routes.deps import CurrentUser, DBSession
from app.core.exceptions import BizError
from app.core.response import R
from app.core.security import create_access_token, hash_password, verify_password
from app.crud.user import user_crud
from app.schema_defs.user import TokenOut, UserLogin, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=R[TokenOut], summary="注册")
async def register(body: UserRegister, db: DBSession):
    # Check duplicates
    if await user_crud.get_by_username(db, username=body.username):
        raise BizError(code=40001, message="用户名已存在")
    if await user_crud.get_by_email(db, email=body.email):
        raise BizError(code=40002, message="邮箱已被注册")

    hashed = hash_password(body.password)
    user = await user_crud.create_user(db, obj_in=body, hashed_password=hashed)

    token = create_access_token(user_id=user.id)
    return R.ok(
        data=TokenOut(
            access_token=token,
            user=UserOut.model_validate(user),
        )
    )

# 调用 /auth/login 获取 token
@router.post("/login", response_model=R[TokenOut], summary="登录")
async def login(body: UserLogin, db: DBSession):
    user = await user_crud.get_by_username(db, username=body.username)
    if user is None or not verify_password(body.password, user.hashed_password):
        raise BizError(code=40100, message="用户名或密码错误", status_code=401)

    token = create_access_token(user_id=user.id)
    return R.ok(
        data=TokenOut(
            access_token=token,
            user=UserOut.model_validate(user),
        )
    )

#  进入 Authorize 弹窗 ，并填入用户名、token后，点击 Authorize 确认，调用
# 后续每个需要认证的请求，Swagger UI 自动在请求头加上：Authorization: Bearer xxx
# 后端走：oauth2_scheme 从 Header 提取 token，get_current_user() 验证 token、查用户，注入 CurrentUser 到路由函数
@router.post("/token", summary="Swagger认证专用", include_in_schema=False)
async def swagger_token(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    user = await user_crud.get_by_username(db, username=form.username)
    if user is None or not verify_password(form.password, user.hashed_password):
        raise BizError(code=40100, message="用户名或密码错误", status_code=401)

    token = create_access_token(user_id=user.id)
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=R[UserOut], summary="当前用户信息")
async def get_me(user: CurrentUser):
    return R.ok(data=UserOut.model_validate(user))


