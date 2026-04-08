import asyncio
from datetime import datetime, timedelta

import pytz
from croniter import croniter

from ..config import settings
from ..models.dtos import ReminderCreateDTO, ReminderDTO, ReminderUpdateDTO
from ..models.entities import ReminderStatus
from ..repositories.reminder_repository import ReminderRepository
from ..utils.database import get_async_session
from ..utils.exceptions import DatabaseException, ValidationException
from ..utils.logging import get_logger
from ..utils.transformers import entity_to_reminder_dto, reminder_create_dto_to_entity

logger = get_logger()

WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


class ReminderService:
    def __init__(self, reminder_repo: ReminderRepository = None):
        self.reminder_repo = reminder_repo
        self._repo_lock = asyncio.Lock()

    async def create_reminder(self, reminder_data: ReminderCreateDTO) -> ReminderDTO:
        try:
            entity = reminder_create_dto_to_entity(reminder_data)

            user_tz = pytz.UTC
            try:
                from ..services.user_service import UserService

                user_service = UserService(None)
                user_tz = await user_service.get_user_timezone(reminder_data.user_id)
            except Exception:
                pass

            next_notification_time = self._calculate_next_notification_time(
                reminder_data.schedule_time,
                reminder_data.interval_days,
                user_tz,
                reminder_data.weekday,
                reminder_data.cron_expression,
            )
            entity.next_notification = next_notification_time

            if self.reminder_repo is None:
                async with get_async_session() as session:
                    reminder_repo = ReminderRepository(session)
                    created_entity = await reminder_repo.create(entity)
                    result = entity_to_reminder_dto(created_entity)
            else:
                async with self._repo_lock:
                    created_entity = await self.reminder_repo.create(entity)
                    result = entity_to_reminder_dto(created_entity)

            logger.info(
                "reminder_created",
                reminder_id=result.id,
                user_id=result.user_id,
                schedule_time=result.schedule_time,
            )

            return result

        except Exception as e:
            logger.error(
                "reminder_creation_failed", error=str(e), user_id=reminder_data.user_id
            )
            raise ValidationException(f"Failed to create reminder: {e}")

    async def get_user_reminders(self, user_id: int) -> list[ReminderDTO]:
        try:
            if self.reminder_repo is None:
                from ..repositories.reminder_repository import ReminderRepository
                from ..utils.database import get_async_session

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

    async def get_reminder_by_id(self, reminder_id: int) -> ReminderDTO | None:
        try:
            if self.reminder_repo is None:
                async with get_async_session() as session:
                    reminder_repo = ReminderRepository(session)
                    entity = await reminder_repo.get_by_id(reminder_id)
                    return entity_to_reminder_dto(entity) if entity else None
            else:
                entity = await self.reminder_repo.get_by_id(reminder_id)
                return entity_to_reminder_dto(entity) if entity else None
        except Exception as e:
            logger.error("get_reminder_failed", error=str(e), reminder_id=reminder_id)
            raise DatabaseException(f"Failed to get reminder: {e}")

    async def update_reminder(
        self, reminder_id: int, user_id: int, update_data: ReminderUpdateDTO
    ) -> ReminderDTO | None:
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
                    if update_data.interval_days is not None:
                        entity.interval_days = update_data.interval_days
                    if update_data.weekday is not None:
                        entity.weekday = update_data.weekday
                    if update_data.cron_expression is not None:
                        entity.cron_expression = update_data.cron_expression
                    if update_data.notification_interval_minutes is not None:
                        entity.notification_interval_minutes = (
                            update_data.notification_interval_minutes
                        )
                    if update_data.max_notifications is not None:
                        entity.max_notifications = update_data.max_notifications
                    if update_data.status is not None:
                        entity.status = update_data.status.value

                    if any(
                        [
                            update_data.schedule_time is not None,
                            update_data.interval_days is not None,
                            update_data.weekday is not None,
                            update_data.cron_expression is not None,
                        ]
                    ):
                        user_tz = pytz.UTC
                        try:
                            from ..services.user_service import UserService

                            user_service = UserService(None)
                            user_tz = await user_service.get_user_timezone(user_id)
                        except Exception:
                            pass
                        entity.next_notification = (
                            self._calculate_next_notification_time(
                                entity.schedule_time,
                                entity.interval_days,
                                user_tz,
                                entity.weekday,
                                entity.cron_expression,
                            )
                        )

                    entity.updated_at = datetime.utcnow()
                    updated_entity = await reminder_repo.update(entity)

                    logger.info(
                        "reminder_updated", reminder_id=reminder_id, user_id=user_id
                    )
                    return entity_to_reminder_dto(updated_entity)
            else:
                entity = await self.reminder_repo.get_by_id(reminder_id)
                if not entity or entity.user_id != user_id:
                    return None

                if update_data.text is not None:
                    entity.text = update_data.text
                if update_data.schedule_time is not None:
                    entity.schedule_time = update_data.schedule_time
                if update_data.interval_days is not None:
                    entity.interval_days = update_data.interval_days
                if update_data.weekday is not None:
                    entity.weekday = update_data.weekday
                if update_data.cron_expression is not None:
                    entity.cron_expression = update_data.cron_expression
                if update_data.notification_interval_minutes is not None:
                    entity.notification_interval_minutes = (
                        update_data.notification_interval_minutes
                    )
                if update_data.max_notifications is not None:
                    entity.max_notifications = update_data.max_notifications
                if update_data.status is not None:
                    entity.status = update_data.status.value

                if any(
                    [
                        update_data.schedule_time is not None,
                        update_data.interval_days is not None,
                        update_data.weekday is not None,
                        update_data.cron_expression is not None,
                    ]
                ):
                    user_tz = pytz.UTC
                    try:
                        from ..services.user_service import UserService

                        user_service = UserService(None)
                        user_tz = await user_service.get_user_timezone(user_id)
                    except Exception:
                        pass
                    entity.next_notification = self._calculate_next_notification_time(
                        entity.schedule_time,
                        entity.interval_days,
                        user_tz,
                        entity.weekday,
                        entity.cron_expression,
                    )

                entity.updated_at = datetime.utcnow()
                updated_entity = await self.reminder_repo.update(entity)

                logger.info(
                    "reminder_updated", reminder_id=reminder_id, user_id=user_id
                )
                return entity_to_reminder_dto(updated_entity)

        except Exception as e:
            logger.error(
                "reminder_update_failed", error=str(e), reminder_id=reminder_id
            )
            raise DatabaseException(f"Failed to update reminder: {e}")

    async def confirm_reminder(
        self, reminder_id: int, user_id: int, job_scheduler=None
    ) -> bool:
        try:
            if self.reminder_repo is None:
                async with get_async_session() as session:
                    reminder_repo = ReminderRepository(session)
                    entity = await reminder_repo.get_by_id(reminder_id)
                    if not entity or entity.user_id != user_id:
                        return False

                    return await self._process_confirmation(
                        entity, reminder_id, user_id, job_scheduler, reminder_repo
                    )
            else:
                entity = await self.reminder_repo.get_by_id(reminder_id)
                if not entity or entity.user_id != user_id:
                    return False

                return await self._process_confirmation(
                    entity, reminder_id, user_id, job_scheduler, self.reminder_repo
                )

        except Exception as e:
            logger.error(
                "reminder_confirmation_failed", error=str(e), reminder_id=reminder_id
            )
            raise DatabaseException(f"Failed to confirm reminder: {e}")

        return False

    async def _process_confirmation(
        self, entity, reminder_id: int, user_id: int, job_scheduler, reminder_repo
    ) -> bool:
        if entity.status != ReminderStatus.ACTIVE.value:
            return False

        if entity.interval_days == 0 and entity.cron_expression is None:
            if job_scheduler:
                await job_scheduler.cancel_reminder(reminder_id)
                await job_scheduler.cancel_notification_jobs(reminder_id)
            await reminder_repo.update_status(reminder_id, ReminderStatus.COMPLETED)
            logger.info("one_time_reminder_completed", reminder_id=reminder_id)
            return True

        if job_scheduler:
            await job_scheduler.cancel_reminder(reminder_id)
            await job_scheduler.cancel_notification_jobs(reminder_id)

        user_tz = pytz.UTC
        try:
            from ..services.user_service import UserService

            user_service = UserService(None)
            user_tz = await user_service.get_user_timezone(user_id)
        except Exception:
            pass

        base_time = entity.next_notification or datetime.now(pytz.UTC).replace(
            tzinfo=None
        )
        base_time_local = pytz.UTC.localize(base_time).astimezone(user_tz)

        if entity.cron_expression:
            next_notification = self._calculate_next_from_cron(
                entity.cron_expression, user_tz, base_time_local
            )
        elif entity.weekday is not None:
            hour, minute = map(int, entity.schedule_time.split(":"))
            days_ahead = entity.weekday - base_time_local.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            next_local = base_time_local + timedelta(days=days_ahead)
            next_local = next_local.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            next_notification = next_local.astimezone(pytz.UTC).replace(tzinfo=None)
        else:
            hour, minute = map(int, entity.schedule_time.split(":"))
            next_local = base_time_local + timedelta(days=entity.interval_days)
            next_local = next_local.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            next_notification = next_local.astimezone(pytz.UTC).replace(tzinfo=None)

        entity.notification_count = 0
        entity.next_notification = next_notification
        entity.last_message_id = None
        await reminder_repo.update(entity)

        if job_scheduler:
            from ..utils.transformers import entity_to_reminder_dto

            reminder_dto = entity_to_reminder_dto(entity)
            await job_scheduler.schedule_reminder(reminder_dto)

        logger.info(
            "recurring_reminder_reset",
            reminder_id=reminder_id,
            next_notification=next_notification,
        )

        return True

    async def snooze_reminder(self, reminder_id: int, minutes: int) -> bool:
        try:
            snooze_time = datetime.utcnow() + timedelta(minutes=minutes)

            if self.reminder_repo is None:
                async with get_async_session() as session:
                    reminder_repo = ReminderRepository(session)
                    success = await reminder_repo.update_next_notification(
                        reminder_id, snooze_time
                    )

                    if success:
                        logger.info(
                            "reminder_snoozed",
                            reminder_id=reminder_id,
                            snooze_minutes=minutes,
                        )

                    return success
            else:
                success = await self.reminder_repo.update_next_notification(
                    reminder_id, snooze_time
                )

                if success:
                    logger.info(
                        "reminder_snoozed",
                        reminder_id=reminder_id,
                        snooze_minutes=minutes,
                    )

                return success

        except Exception as e:
            logger.error(
                "reminder_snooze_failed", error=str(e), reminder_id=reminder_id
            )
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
                        logger.info(
                            "reminder_deleted", reminder_id=reminder_id, user_id=user_id
                        )

                    return success
            else:
                entity = await self.reminder_repo.get_by_id(reminder_id)
                if not entity or entity.user_id != user_id:
                    return False

                success = await self.reminder_repo.delete(reminder_id)
                if success:
                    logger.info(
                        "reminder_deleted", reminder_id=reminder_id, user_id=user_id
                    )

                return success

        except Exception as e:
            logger.error(
                "reminder_deletion_failed", error=str(e), reminder_id=reminder_id
            )
            raise DatabaseException(f"Failed to delete reminder: {e}")

    async def get_active_reminders(self) -> list[ReminderDTO]:
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

    def _calculate_next_notification_time(
        self,
        schedule_time: str,
        interval_days: int,
        user_timezone: pytz.BaseTzInfo | None = None,
        weekday: int | None = None,
        cron_expression: str | None = None,
    ) -> datetime:
        tz = user_timezone or pytz.timezone(settings.timezone)
        now_local = datetime.now(tz)

        if cron_expression:
            return self._calculate_next_from_cron(cron_expression, tz, now_local)

        hour, minute = map(int, schedule_time.split(":"))
        next_time_local = now_local.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )

        if weekday is not None:
            days_ahead = weekday - now_local.weekday()
            if days_ahead < 0 or (days_ahead == 0 and next_time_local <= now_local):
                days_ahead += 7
            next_time_local = now_local + timedelta(days=days_ahead)
            next_time_local = next_time_local.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
        elif next_time_local <= now_local:
            next_time_local += timedelta(days=interval_days if interval_days > 0 else 1)

        return next_time_local.astimezone(pytz.UTC).replace(tzinfo=None)

    def _calculate_next_from_cron(
        self, cron_expression: str, tz: pytz.BaseTzInfo, now_local: datetime
    ) -> datetime:
        try:
            itr = croniter(cron_expression, now_local)
            next_local = itr.get_next(datetime)
            return next_local.astimezone(pytz.UTC).replace(tzinfo=None)
        except Exception:
            hour, minute = 9, 0
            next_time = now_local.replace(
                hour=hour, minute=minute, second=0, microsecond=0
            )
            if next_time <= now_local:
                next_time += timedelta(days=1)
            return next_time.astimezone(pytz.UTC).replace(tzinfo=None)

    async def recompute_reminders_for_timezone_change(
        self, user_id: int, user_timezone: pytz.BaseTzInfo, job_scheduler=None
    ) -> int:
        try:
            user_reminders = await self.get_user_reminders(user_id)
            active_reminders = [r for r in user_reminders if r.status.value == "active"]

            updated_count = 0
            for reminder in active_reminders:
                new_next_notification = self._calculate_next_notification_time(
                    reminder.schedule_time,
                    reminder.interval_days,
                    user_timezone,
                    reminder.weekday,
                    reminder.cron_expression,
                )

                if self.reminder_repo is None:
                    async with get_async_session() as session:
                        reminder_repo = ReminderRepository(session)
                        entity = await reminder_repo.get_by_id(reminder.id)
                        if entity:
                            entity.next_notification = new_next_notification
                            entity.updated_at = datetime.utcnow()
                            await reminder_repo.update(entity)
                else:
                    entity = await self.reminder_repo.get_by_id(reminder.id)
                    if entity:
                        entity.next_notification = new_next_notification
                        entity.updated_at = datetime.utcnow()
                        await self.reminder_repo.update(entity)

                if job_scheduler:
                    await job_scheduler.cancel_reminder(reminder.id)
                    await job_scheduler.cancel_notification_jobs(reminder.id)
                    from ..utils.transformers import entity_to_reminder_dto

                    if entity:
                        updated_reminder = entity_to_reminder_dto(entity)
                        await job_scheduler.schedule_reminder(updated_reminder)

                updated_count += 1

            logger.info(
                "reminders_recomputed_for_timezone_change",
                user_id=user_id,
                updated_count=updated_count,
            )
            return updated_count

        except Exception as e:
            logger.error("recompute_reminders_failed", error=str(e), user_id=user_id)
            raise DatabaseException(f"Failed to recompute reminders: {e}")
