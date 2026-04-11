"""User CRUD — extends base with auth-specific queries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.user import User
from app.schemas.user import UserRegister, UserUpdate


class UserCRUD(CRUDBase[User, UserRegister, UserUpdate]):

    async def get_by_username(self, db: AsyncSession, *, username: str) -> User | None:  # * 后面的所有参数，必须用“关键字方式”传入，不能用位置参数
        stmt = select(User).where(
            User.username == username,
            User.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, *, email: str) -> User | None:
        stmt = select(User).where(
            User.email == email,
            User.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(
        self, db: AsyncSession, *, obj_in: UserRegister, hashed_password: str
    ) -> User:
        """Create user with pre-hashed password."""
        user = User(
            username=obj_in.username,
            email=obj_in.email,
            hashed_password=hashed_password,
            nickname=obj_in.nickname or obj_in.username,
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)
        return user


user_crud = UserCRUD(User)