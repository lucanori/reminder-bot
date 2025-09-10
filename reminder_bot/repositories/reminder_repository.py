from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from .base import BaseRepository
from ..models.entities import ReminderEntity, ReminderStatus
from ..utils.exceptions import DatabaseException


class ReminderRepository(BaseRepository[ReminderEntity, int]):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create(self, entity: ReminderEntity) -> ReminderEntity:
        try:
            self.session.add(entity)
            await self.session.flush()
            await self.session.refresh(entity)
            return entity
        except Exception as e:
            raise DatabaseException(f"Failed to create reminder: {e}")

    async def get_by_id(self, entity_id: int) -> Optional[ReminderEntity]:
        try:
            result = await self.session.execute(
                select(ReminderEntity).where(ReminderEntity.id == entity_id)
            )
            return result.scalar_one_or_none()
        except Exception as e:
            raise DatabaseException(f"Failed to get reminder by id: {e}")

    async def update(self, entity: ReminderEntity) -> ReminderEntity:
        try:
            await self.session.merge(entity)
            await self.session.flush()
            await self.session.refresh(entity)
            return entity
        except Exception as e:
            raise DatabaseException(f"Failed to update reminder: {e}")

    async def delete(self, entity_id: int) -> bool:
        try:
            result = await self.session.execute(
                select(ReminderEntity).where(ReminderEntity.id == entity_id)
            )
            reminder = result.scalar_one_or_none()
            if reminder:
                await self.session.delete(reminder)
                return True
            return False
        except Exception as e:
            raise DatabaseException(f"Failed to delete reminder: {e}")

    async def get_all(self) -> List[ReminderEntity]:
        try:
            result = await self.session.execute(select(ReminderEntity))
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseException(f"Failed to get all reminders: {e}")

    async def get_all_reminders(self) -> List[ReminderEntity]:
        return await self.get_all()

    async def get_by_user_id(self, user_id: int) -> List[ReminderEntity]:
        try:
            result = await self.session.execute(
                select(ReminderEntity).where(ReminderEntity.user_id == user_id)
            )
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseException(f"Failed to get reminders by user id: {e}")

    async def get_active_reminders(self) -> List[ReminderEntity]:
        try:
            result = await self.session.execute(
                select(ReminderEntity).where(ReminderEntity.status == ReminderStatus.ACTIVE.value)
            )
            return list(result.scalars().all())
        except Exception as e:
            raise DatabaseException(f"Failed to get active reminders: {e}")

    async def update_status(self, reminder_id: int, status: ReminderStatus) -> bool:
        try:
            result = await self.session.execute(
                update(ReminderEntity)
                .where(ReminderEntity.id == reminder_id)
                .values(status=status.value, updated_at=datetime.utcnow())
            )
            return result.rowcount > 0
        except Exception as e:
            raise DatabaseException(f"Failed to update reminder status: {e}")

    async def update_message_id(self, reminder_id: int, message_id: int) -> bool:
        try:
            result = await self.session.execute(
                update(ReminderEntity)
                .where(ReminderEntity.id == reminder_id)
                .values(last_message_id=message_id, updated_at=datetime.utcnow())
            )
            return result.rowcount > 0
        except Exception as e:
            raise DatabaseException(f"Failed to update reminder message id: {e}")

    async def increment_notification_count(self, reminder_id: int) -> bool:
        try:
            reminder = await self.get_by_id(reminder_id)
            if reminder:
                reminder.notification_count += 1
                reminder.updated_at = datetime.utcnow()
                await self.session.flush()
                return True
            return False
        except Exception as e:
            raise DatabaseException(f"Failed to increment notification count: {e}")

    async def update_next_notification(self, reminder_id: int, next_notification: datetime) -> bool:
        try:
            result = await self.session.execute(
                update(ReminderEntity)
                .where(ReminderEntity.id == reminder_id)
                .values(next_notification=next_notification, updated_at=datetime.utcnow())
            )
            return result.rowcount > 0
        except Exception as e:
            raise DatabaseException(f"Failed to update next notification time: {e}")