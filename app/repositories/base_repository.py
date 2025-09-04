from typing import Annotated, Generic, TypeVar

from fastapi import Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from app.core.database import get_session

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    def __init__(
        self,
        model: type[ModelType],
        session: Annotated[AsyncSession, Depends(get_session)],
    ):
        self.model = model
        self._session = session

    async def create(self, obj_in: ModelType) -> ModelType:
        db_obj = self.model.model_validate(obj_in)
        self._session.add(db_obj)
        await self._session.commit()
        await self._session.refresh(db_obj)
        return db_obj

    async def get(self, id: int) -> ModelType | None:
        statement = select(self.model).where(self.model.id == id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        statement = select(self.model).offset(skip).limit(limit)
        result = await self._session.execute(statement)
        return result.scalars().all()

    async def update(self, id: int, obj_in: dict) -> ModelType | None:
        # Получаем объект и обновляем его напрямую
        result = await self._session.execute(
            select(self.model).where(self.model.id == id)
        )
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return None

        for key, value in obj_in.items():
            setattr(db_obj, key, value)

        await self._session.commit()
        await self._session.refresh(db_obj)
        return db_obj

    async def delete(self, id: int) -> bool:
        statement = delete(self.model).where(self.model.id == id)
        result = await self._session.execute(statement)
        await self._session.commit()
        return result.rowcount > 0
