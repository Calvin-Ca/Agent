"""Generic async CRUD base class.

Usage:
    class UserCRUD(CRUDBase[User, UserCreate, UserUpdate]):
        pass

    user_crud = UserCRUD(User)
    user = await user_crud.get(db, id="xxx")
"""

from __future__ import annotations

# 泛型 = “先不写死类型，而是先占位，等使用时再决定类型”，泛型 = “类型的模板”
# TypeVar 定义“泛型变量”
# Generic 用来创建泛型类
# Type 表示类本身，不是实例
# Sequence 序列类型
from typing import Any, Generic, TypeVar, Type, Sequence

from pydantic import BaseModel
from sqlalchemy import select, update, func # 让 python 直接操作sql的增删查改
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base
 
ModelType = TypeVar("ModelType", bound=Base)  # 受限制的泛型
CreateSchema = TypeVar("CreateSchema", bound=BaseModel)
UpdateSchema = TypeVar("UpdateSchema", bound=BaseModel)

# 通用增删查改（crud）基类，支持 Create（创建）、Read（查询单条/多条）、Update（更新）、Delete（删除）......
class CRUDBase(Generic[ModelType, CreateSchema, UpdateSchema]): # 定义一个“带 3 个泛型参数的通用类，也就是：这个类在使用时，必须同时指定 3种类型
    """Generic CRUD operations with soft-delete support."""

    def __init__(self, model: Type[ModelType]): # model 一张表 对象
        self.model = model

    async def get(self, db: AsyncSession, *, id: str) -> ModelType | None:
        """Get a single record by ID (excludes soft-deleted)."""
        stmt = select(self.model).where(
            self.model.id == id,
            self.model.is_deleted == False,  # noqa: E712
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        db: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        order_by: str = "created_at",
        desc: bool = True,
        filters: dict[str, Any] | None = None,
    ) -> tuple[Sequence[ModelType], int]:
        """Get paginated records. Returns (items, total_count)."""
        stmt = select(self.model).where(self.model.is_deleted == False)  # noqa: E712

        # Apply filters
        if filters:
            for field, value in filters.items():
                if hasattr(self.model, field) and value is not None:
                    stmt = stmt.where(getattr(self.model, field) == value)

        # Count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await db.execute(count_stmt)).scalar() or 0

        # Order
        order_col = getattr(self.model, order_by, self.model.created_at)
        stmt = stmt.order_by(order_col.desc() if desc else order_col.asc())

        # Paginate
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(stmt)
        items = result.scalars().all()
        return items, total

    async def create(self, db: AsyncSession, *, obj_in: CreateSchema, **extra) -> ModelType:
        """Create a new record."""
        data = obj_in.model_dump()
        data.update(extra)
        obj = self.model(**data)
        db.add(obj)
        await db.flush()
        await db.refresh(obj)
        return obj

    async def update(self, db: AsyncSession, *, id: str, obj_in: UpdateSchema) -> ModelType | None:
        """Update a record. Only sets non-None fields."""
        obj = await self.get(db, id=id)
        if obj is None:
            return None

        update_data = obj_in.model_dump(exclude_unset=True)
        if not update_data:
            return obj

        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**update_data)
        )
        await db.execute(stmt)
        await db.refresh(obj)
        return obj

    async def delete(self, db: AsyncSession, *, id: str, hard: bool = False) -> bool:
        """Delete a record. Soft-delete by default."""
        obj = await self.get(db, id=id)
        if obj is None:
            return False

        if hard:
            await db.delete(obj)
        else:
            stmt = (
                update(self.model)
                .where(self.model.id == id)
                .values(is_deleted=True)
            )
            await db.execute(stmt)
        return True

    async def exists(self, db: AsyncSession, **kwargs) -> bool:
        """Check if a record exists matching the given field values."""
        stmt = select(func.count()).select_from(self.model).where(
            self.model.is_deleted == False  # noqa: E712
        )
        for field, value in kwargs.items():
            if hasattr(self.model, field):
                stmt = stmt.where(getattr(self.model, field) == value)
        count = (await db.execute(stmt)).scalar() or 0
        return count > 0