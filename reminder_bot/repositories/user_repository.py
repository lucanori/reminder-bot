from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from .base import BaseRepository
from ..models.entities import UserEntity
from ..utils.exceptions import DatabaseException


class UserRepository(BaseRepository[UserEntity, int]):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(self, entity: UserEntity) -> UserEntity:
        try:
            self.session.add(entity)
            await self.session.flush()
            await self.session.refresh(entity)
            return entity
        except Exception as e:
            raise DatabaseException(f"Failed to create user: {e}")

    async def get_by_id(self, entity_id: int) -> Optional[UserEntity]:
        try:
            result = await self.session.execute(
                select(UserEntity).where(UserEntity.telegram_id == entity_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseException(f"Failed to get user by id: {e}")

    async def update(self, entity: UserEntity) -> UserEntity:
        try:
            await self.session.merge(entity)
            await self.session.flush()
            await self.session.refresh(entity)
            return entity
        except Exception as e:
            raise DatabaseException(f"Failed to update user: {e}")

    async def delete(self, entity_id: int) -> bool:
        try:
            result = await self.session.execute(
                select(UserEntity).where(UserEntity.telegram_id == entity_id)
            )
            user = result.scalar_one_or_none()
            if user:
                await self.session.delete(user)
                return True
            return False
        except Exception as e:
            raise DatabaseException(f"Failed to delete user: {e}")

    async def get_all(self) -> List[UserEntity]:
        try:
            result = await self.session.execute(select(UserEntity))
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseException(f"Failed to get all users: {e}")

    async def update_blocked_status(self, telegram_id: int, is_blocked: bool) -> bool:
        try:
            result = await self.session.execute(
                update(UserEntity)
                .where(UserEntity.telegram_id == telegram_id)
                .values(is_blocked=is_blocked)
            )
            return result.rowcount > 0
        except Exception as e:
            raise DatabaseException(f"Failed to update user blocked status: {e}")

    async def update_whitelisted_status(self, telegram_id: int, is_whitelisted: bool) -> bool:
        try:
            result = await self.session.execute(
                update(UserEntity)
                .where(UserEntity.telegram_id == telegram_id)
                .values(is_whitelisted=is_whitelisted)
            )
            return result.rowcount > 0
        except Exception as e:
            raise DatabaseException(f"Failed to update user whitelisted status: {e}")