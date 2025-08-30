from typing import TypeVar, Generic, Optional, List, Type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlmodel import SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session

    async def create(self, obj_in: ModelType) -> ModelType:
        db_obj = self.model.model_validate(obj_in)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def get(self, id: int) -> Optional[ModelType]:
        statement = select(self.model).where(self.model.id == id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        statement = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(statement)
        return result.scalars().all()

    async def update(self, id: int, obj_in: dict) -> Optional[ModelType]:
        statement = (
            update(self.model)
            .where(self.model.id == id)
            .values(**obj_in)
            .returning(self.model)
        )
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()
        if db_obj:
            await self.session.commit()
            await self.session.refresh(db_obj)
        return db_obj

    async def delete(self, id: int) -> bool:
        statement = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(statement)
        await self.session.commit()
        return result.rowcount > 0