from typing import List, Optional
from datetime import datetime, timedelta
import pytz
from ..repositories.reminder_repository import ReminderRepository
from ..utils.database import get_async_session
from ..config import settings
from ..models.dtos import ReminderCreateDTO, ReminderDTO, ReminderUpdateDTO
from ..models.entities import ReminderStatus
from ..utils.transformers import reminder_create_dto_to_entity, entity_to_reminder_dto
from ..utils.logging import get_logger
from ..utils.exceptions import ValidationException, DatabaseException

logger = get_logger()


class ReminderService:
    def __init__(self, reminder_repo: ReminderRepository = None):
        self.reminder_repo = reminder_repo

    async def create_reminder(self, reminder_data: ReminderCreateDTO) -> ReminderDTO:
        try:
            entity = reminder_create_dto_to_entity(reminder_data)
            
            next_notification_time = self._calculate_next_notification_time(
                reminder_data.schedule_time, reminder_data.interval_days
            )
            entity.next_notification = next_notification_time
            
            async with get_async_session() as session:
                reminder_repo = ReminderRepository(session)
                created_entity = await reminder_repo.create(entity)
                result = entity_to_reminder_dto(created_entity)
            
            logger.info(
                "reminder_created",
                reminder_id=result.id,
                user_id=result.user_id,
                schedule_time=result.schedule_time
            )
            
            return result
            
        except Exception as e:
            logger.error("reminder_creation_failed", error=str(e), user_id=reminder_data.user_id)
            raise ValidationException(f"Failed to create reminder: {e}")

    async def get_user_reminders(self, user_id: int) -> List[ReminderDTO]:
        try:
            if self.reminder_repo is None:
                from ..utils.database import get_async_session
                from ..repositories.reminder_repository import ReminderRepository
                
                async with get_async_session() as session:
                    reminder_repo = ReminderRepository(session)
                    entities = await reminder_repo.get_by_user_id(user_id)
                    return [entity_to_reminder_dto(entity) for entity in entities]
            else:
                entities = await self.reminder_repo.get_by_user_id(user_id)
                return [entity_to_reminder_dto(entity) for entity in entities]
        except Exception as e:
            logger.error("get_user_reminders_failed", error=str(e), user_id=user_id)
            raise DatabaseException(f"Failed to get user reminders: {e}")

    async def get_reminder_by_id(self, reminder_id: int) -> Optional[ReminderDTO]:
        try:
            async with get_async_session() as session:
                reminder_repo = ReminderRepository(session)
                entity = await reminder_repo.get_by_id(reminder_id)
                return entity_to_reminder_dto(entity) if entity else None
        except Exception as e:
            logger.error("get_reminder_failed", error=str(e), reminder_id=reminder_id)
            raise DatabaseException(f"Failed to get reminder: {e}")

    async def update_reminder(self, reminder_id: int, user_id: int, update_data: ReminderUpdateDTO) -> Optional[ReminderDTO]:
        try:
            if self.reminder_repo is None:
                async with get_async_session() as session:
                    reminder_repo = ReminderRepository(session)
                    entity = await reminder_repo.get_by_id(reminder_id)
                    if not entity or entity.user_id != user_id:
                        return None

                    if update_data.text is not None:
                        entity.text = update_data.text
                    if update_data.schedule_time is not None:
                        entity.schedule_time = update_data.schedule_time
                        entity.next_notification = self._calculate_next_notification_time(
                            update_data.schedule_time, entity.interval_days
                        )
                    if update_data.interval_days is not None:
                        entity.interval_days = update_data.interval_days
                        entity.next_notification = self._calculate_next_notification_time(
                            entity.schedule_time, update_data.interval_days
                        )
                    if update_data.notification_interval_minutes is not None:
                        entity.notification_interval_minutes = update_data.notification_interval_minutes
                    if update_data.max_notifications is not None:
                        entity.max_notifications = update_data.max_notifications
                    if update_data.status is not None:
                        entity.status = update_data.status.value

                    entity.updated_at = datetime.utcnow()
                    updated_entity = await reminder_repo.update(entity)
                    
                    logger.info("reminder_updated", reminder_id=reminder_id, user_id=user_id)
                    return entity_to_reminder_dto(updated_entity)
            else:
                entity = await self.reminder_repo.get_by_id(reminder_id)
                if not entity or entity.user_id != user_id:
                    return None

                if update_data.text is not None:
                    entity.text = update_data.text
                if update_data.schedule_time is not None:
                    entity.schedule_time = update_data.schedule_time
                    entity.next_notification = self._calculate_next_notification_time(
                        update_data.schedule_time, entity.interval_days
                    )
                if update_data.interval_days is not None:
                    entity.interval_days = update_data.interval_days
                    entity.next_notification = self._calculate_next_notification_time(
                        entity.schedule_time, update_data.interval_days
                    )
                if update_data.notification_interval_minutes is not None:
                    entity.notification_interval_minutes = update_data.notification_interval_minutes
                if update_data.max_notifications is not None:
                    entity.max_notifications = update_data.max_notifications
                if update_data.status is not None:
                    entity.status = update_data.status.value

                entity.updated_at = datetime.utcnow()
                updated_entity = await self.reminder_repo.update(entity)
                
                logger.info("reminder_updated", reminder_id=reminder_id, user_id=user_id)
                return entity_to_reminder_dto(updated_entity)
            
        except Exception as e:
            logger.error("reminder_update_failed", error=str(e), reminder_id=reminder_id)
            raise DatabaseException(f"Failed to update reminder: {e}")

    async def confirm_reminder(self, reminder_id: int, user_id: int, job_scheduler=None) -> bool:
        try:
            if self.reminder_repo is None:
                async with get_async_session() as session:
                    reminder_repo = ReminderRepository(session)
                    entity = await reminder_repo.get_by_id(reminder_id)
                    if not entity or entity.user_id != user_id:
                        return False

                    if entity.status == ReminderStatus.ACTIVE.value:
                        if entity.interval_days == 0:
                            await reminder_repo.update_status(reminder_id, ReminderStatus.COMPLETED)
                            logger.info("one_time_reminder_completed", reminder_id=reminder_id)
                        else:
                            if job_scheduler:
                                await job_scheduler.cancel_reminder(reminder_id)
                                try:
                                    for job in job_scheduler.scheduler.get_jobs():
                                        if job.id.startswith(f"notification_{reminder_id}_"):
                                            job_scheduler.scheduler.remove_job(job.id)
                                            logger.info("cancelled_notification_job", job_id=job.id, reminder_id=reminder_id)
                                except Exception as e:
                                    logger.warning("failed_to_cancel_notification_jobs", reminder_id=reminder_id, error=str(e))
                            
                            next_notification = self._calculate_next_notification_time(
                                entity.schedule_time, entity.interval_days
                            )
                            entity.notification_count = 0
                            entity.next_notification = next_notification
                            entity.last_message_id = None
                            await reminder_repo.update(entity)
                            
                            if job_scheduler:
                                from ..utils.transformers import entity_to_reminder_dto
                                reminder_dto = entity_to_reminder_dto(entity)
                                await job_scheduler.schedule_reminder(reminder_dto)
                            
                            logger.info("recurring_reminder_reset", reminder_id=reminder_id, next_notification=next_notification)
                        
                        return True
            else:
                entity = await self.reminder_repo.get_by_id(reminder_id)
                if not entity or entity.user_id != user_id:
                    return False

                if entity.status == ReminderStatus.ACTIVE.value:
                    if entity.interval_days == 0:
                        await self.reminder_repo.update_status(reminder_id, ReminderStatus.COMPLETED)
                        logger.info("one_time_reminder_completed", reminder_id=reminder_id)
                    else:
                        if job_scheduler:
                            await job_scheduler.cancel_reminder(reminder_id)
                            try:
                                for job in job_scheduler.scheduler.get_jobs():
                                    if job.id.startswith(f"notification_{reminder_id}_"):
                                        job_scheduler.scheduler.remove_job(job.id)
                                        logger.info("cancelled_notification_job", job_id=job.id, reminder_id=reminder_id)
                            except Exception as e:
                                logger.warning("failed_to_cancel_notification_jobs", reminder_id=reminder_id, error=str(e))
                        
                        next_notification = self._calculate_next_notification_time(
                            entity.schedule_time, entity.interval_days
                        )
                        entity.notification_count = 0
                        entity.next_notification = next_notification
                        entity.last_message_id = None
                        await self.reminder_repo.update(entity)
                        
                        if job_scheduler:
                            from ..utils.transformers import entity_to_reminder_dto
                            reminder_dto = entity_to_reminder_dto(entity)
                            await job_scheduler.schedule_reminder(reminder_dto)
                        
                        logger.info("recurring_reminder_reset", reminder_id=reminder_id, next_notification=next_notification)
                    
                    return True
                
        except Exception as e:
            logger.error("reminder_confirmation_failed", error=str(e), reminder_id=reminder_id)
            raise DatabaseException(f"Failed to confirm reminder: {e}")

        return False

    async def snooze_reminder(self, reminder_id: int, minutes: int) -> bool:
        try:
            snooze_time = datetime.utcnow() + timedelta(minutes=minutes)
            
            if self.reminder_repo is None:
                async with get_async_session() as session:
                    reminder_repo = ReminderRepository(session)
                    success = await reminder_repo.update_next_notification(reminder_id, snooze_time)
                    
                    if success:
                        logger.info("reminder_snoozed", reminder_id=reminder_id, snooze_minutes=minutes)
                        
                    return success
            else:
                success = await self.reminder_repo.update_next_notification(reminder_id, snooze_time)
                
                if success:
                    logger.info("reminder_snoozed", reminder_id=reminder_id, snooze_minutes=minutes)
                    
                return success
            
        except Exception as e:
            logger.error("reminder_snooze_failed", error=str(e), reminder_id=reminder_id)
            raise DatabaseException(f"Failed to snooze reminder: {e}")

    async def delete_reminder(self, reminder_id: int, user_id: int) -> bool:
        try:
            if self.reminder_repo is None:
                async with get_async_session() as session:
                    reminder_repo = ReminderRepository(session)
                    entity = await reminder_repo.get_by_id(reminder_id)
                    if not entity or entity.user_id != user_id:
                        return False

                    success = await reminder_repo.delete(reminder_id)
                    if success:
                        logger.info("reminder_deleted", reminder_id=reminder_id, user_id=user_id)
                        
                    return success
            else:
                entity = await self.reminder_repo.get_by_id(reminder_id)
                if not entity or entity.user_id != user_id:
                    return False

                success = await self.reminder_repo.delete(reminder_id)
                if success:
                    logger.info("reminder_deleted", reminder_id=reminder_id, user_id=user_id)
                    
                return success
            
        except Exception as e:
            logger.error("reminder_deletion_failed", error=str(e), reminder_id=reminder_id)
            raise DatabaseException(f"Failed to delete reminder: {e}")

    async def get_active_reminders(self) -> List[ReminderDTO]:
        try:
            if self.reminder_repo is None:
                async with get_async_session() as session:
                    reminder_repo = ReminderRepository(session)
                    entities = await reminder_repo.get_active_reminders()
                    return [entity_to_reminder_dto(entity) for entity in entities]
            else:
                entities = await self.reminder_repo.get_active_reminders()
                return [entity_to_reminder_dto(entity) for entity in entities]
        except Exception as e:
            logger.error("get_active_reminders_failed", error=str(e))
            raise DatabaseException(f"Failed to get active reminders: {e}")

    def _calculate_next_notification_time(self, schedule_time: str, interval_days: int) -> datetime:
        tz = pytz.timezone(settings.timezone)
        now_local = datetime.now(tz)
        hour, minute = map(int, schedule_time.split(':'))
        
        next_time_local = now_local.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if next_time_local <= now_local:
            next_time_local += timedelta(days=interval_days if interval_days > 0 else 1)
        
        return next_time_local.astimezone(pytz.UTC).replace(tzinfo=None)