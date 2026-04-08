from datetime import datetime, timedelta

import pytz
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from croniter import croniter

from ..models.dtos import ReminderDTO
from ..models.entities import ReminderStatus
from ..repositories.reminder_repository import ReminderRepository
from ..services.notification_service import NotificationService
from ..utils.exceptions import SchedulingException
from ..utils.logging import get_logger

logger = get_logger()


class JobScheduler:
    def __init__(
        self,
        notification_service: NotificationService,
        reminder_repo: ReminderRepository = None,
    ):
        self.notification_service = notification_service
        self.reminder_repo = reminder_repo

        jobstores = {
            "default": MemoryJobStore(),
        }

        executors = {
            "default": AsyncIOExecutor(),
        }

        job_defaults = {
            "coalesce": False,
            "max_instances": 3,
            "misfire_grace_time": 300,
        }

        self.scheduler = AsyncIOScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="UTC",
        )

        self.scheduler.add_listener(
            self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

    async def start(self) -> None:
        try:
            self.scheduler.start()
            logger.info("scheduler_started")
        except Exception as e:
            logger.error("scheduler_start_failed", error=str(e))
            raise SchedulingException(f"Failed to start scheduler: {e}")

    async def shutdown(self) -> None:
        try:
            self.scheduler.shutdown(wait=False)
            logger.info("scheduler_shutdown")
        except Exception as e:
            logger.error("scheduler_shutdown_failed", error=str(e))

    async def schedule_reminder(self, reminder: ReminderDTO) -> str:
        try:
            job_id = f"reminder_{reminder.id}"

            self.scheduler.add_job(
                self._send_reminder_job,
                trigger="date",
                run_date=reminder.next_notification,
                args=[reminder.id],
                id=job_id,
                replace_existing=True,
            )

            logger.info(
                "reminder_scheduled",
                reminder_id=reminder.id,
                job_id=job_id,
                run_date=reminder.next_notification.isoformat(),
            )

            return job_id

        except Exception as e:
            logger.error(
                "reminder_scheduling_failed", reminder_id=reminder.id, error=str(e)
            )
            raise SchedulingException(f"Failed to schedule reminder: {e}")

    async def reschedule_reminder(
        self, reminder: ReminderDTO, new_time: datetime
    ) -> str:
        try:
            job_id = f"reminder_{reminder.id}"

            try:
                self.scheduler.remove_job(job_id)
            except:
                pass

            self.scheduler.add_job(
                self._send_reminder_job,
                trigger="date",
                run_date=new_time,
                args=[reminder.id],
                id=job_id,
                replace_existing=True,
            )

            logger.info(
                "reminder_rescheduled",
                reminder_id=reminder.id,
                job_id=job_id,
                new_run_date=new_time.isoformat(),
            )

            return job_id

        except Exception as e:
            logger.error(
                "reminder_rescheduling_failed", reminder_id=reminder.id, error=str(e)
            )
            raise SchedulingException(f"Failed to reschedule reminder: {e}")

    async def cancel_reminder(self, reminder_id: int) -> bool:
        try:
            job_id = f"reminder_{reminder_id}"

            try:
                self.scheduler.remove_job(job_id)
                logger.info(
                    "reminder_job_cancelled", reminder_id=reminder_id, job_id=job_id
                )
                return True
            except:
                logger.warning(
                    "reminder_job_not_found", reminder_id=reminder_id, job_id=job_id
                )
                return False

        except Exception as e:
            logger.error(
                "reminder_cancellation_failed", reminder_id=reminder_id, error=str(e)
            )
            return False

    async def cancel_notification_jobs(self, reminder_id: int) -> int:
        cancelled_count = 0
        try:
            for job in self.scheduler.get_jobs():
                if job.id.startswith(f"notification_{reminder_id}_"):
                    try:
                        self.scheduler.remove_job(job.id)
                        cancelled_count += 1
                        logger.info(
                            "cancelled_notification_job",
                            job_id=job.id,
                            reminder_id=reminder_id,
                        )
                    except Exception as e:
                        logger.warning(
                            "failed_to_cancel_notification_job",
                            job_id=job.id,
                            reminder_id=reminder_id,
                            error=str(e),
                        )
            logger.info(
                "notification_jobs_cancelled",
                reminder_id=reminder_id,
                count=cancelled_count,
            )
        except Exception as e:
            logger.error(
                "cancel_notification_jobs_failed",
                reminder_id=reminder_id,
                error=str(e),
            )
        return cancelled_count

    async def _send_reminder_job(self, reminder_id: int) -> None:
        from ..repositories.reminder_repository import ReminderRepository
        from ..services.notification_service import NotificationService
        from ..utils.database import get_async_session

        try:
            async with get_async_session() as session:
                reminder_repo = ReminderRepository(session)
                notification_service = NotificationService(
                    self.notification_service.bot,
                    reminder_repo,
                    self.notification_service.user_service,
                )

                reminder_entity = await reminder_repo.get_by_id(reminder_id)
                if (
                    not reminder_entity
                    or reminder_entity.status != ReminderStatus.ACTIVE.value
                ):
                    logger.warning(
                        "reminder_job_skipped",
                        reminder_id=reminder_id,
                        status=reminder_entity.status
                        if reminder_entity
                        else "not_found",
                    )
                    return

                from ..utils.transformers import entity_to_reminder_dto

                reminder = entity_to_reminder_dto(reminder_entity)

                result = await notification_service.send_reminder_notification(reminder)

                if result.success:
                    await reminder_repo.increment_notification_count(reminder_id)

                    if reminder.notification_count < reminder.max_notifications - 1:
                        interval = (
                            notification_service.calculate_next_notification_interval(
                                reminder.notification_count,
                                reminder.notification_interval_minutes,
                            )
                        )
                        now_utc = datetime.now(pytz.UTC).replace(tzinfo=None)
                        next_time = now_utc + timedelta(minutes=interval)
                        await self.schedule_next_notification(reminder, next_time)
                    else:
                        await notification_service.send_escalation_warning(reminder)
                        await self._reset_and_reschedule_reminder(
                            reminder_repo, reminder
                        )
                elif result.error and result.error.startswith("blocked:"):
                    logger.info(
                        "skipping_reschedule_user_blocked", reminder_id=reminder_id
                    )
                else:
                    logger.error(
                        "reminder_notification_failed", reminder_id=reminder_id
                    )

        except Exception as e:
            logger.error(
                "reminder_job_failed",
                reminder_id=reminder_id,
                error=str(e),
                exc_info=True,
            )

    async def _reset_and_reschedule_reminder(
        self, reminder_repo: ReminderRepository, reminder: ReminderDTO
    ) -> None:
        try:
            from ..services.user_service import UserService
            from ..utils.database import get_async_session
            from ..utils.transformers import entity_to_reminder_dto

            async with get_async_session():
                user_service = UserService(None)
                user_tz = await user_service.get_user_timezone(reminder.user_id)

            now_local = datetime.now(user_tz)
            hour, minute = map(int, reminder.schedule_time.split(":"))

            if reminder.cron_expression:
                try:
                    base_time = datetime.now(pytz.UTC).replace(tzinfo=None)
                    base_local = pytz.UTC.localize(base_time).astimezone(user_tz)
                    itr = croniter(reminder.cron_expression, base_local)
                    next_local = itr.get_next(datetime)
                except Exception:
                    next_local = now_local.replace(
                        hour=hour, minute=minute, second=0, microsecond=0
                    )
                    if next_local <= now_local:
                        next_local += timedelta(days=1)
            elif reminder.weekday is not None:
                days_ahead = reminder.weekday - now_local.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                next_local = now_local + timedelta(days=days_ahead)
                next_local = next_local.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
            else:
                next_local = now_local.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                days_to_add = (
                    reminder.interval_days if reminder.interval_days > 0 else 1
                )
                if next_local <= now_local:
                    next_local += timedelta(days=days_to_add)

            next_utc = next_local.astimezone(pytz.UTC).replace(tzinfo=None)

            reminder_entity = await reminder_repo.get_by_id(reminder.id)
            if reminder_entity:
                reminder_entity.notification_count = 0
                reminder_entity.next_notification = next_utc
                reminder_entity.updated_at = datetime.now(pytz.UTC).replace(tzinfo=None)
                await reminder_repo.update(reminder_entity)

                updated_reminder = entity_to_reminder_dto(reminder_entity)
                await self.schedule_reminder(updated_reminder)

                logger.info(
                    "reminder_reset_and_rescheduled",
                    reminder_id=reminder.id,
                    next_notification=next_utc.isoformat(),
                    interval_days=reminder.interval_days,
                )

        except Exception as e:
            logger.error(
                "reset_reschedule_failed", reminder_id=reminder.id, error=str(e)
            )

    async def schedule_next_notification(
        self, reminder: ReminderDTO, next_time: datetime
    ) -> None:
        try:
            job_id = f"notification_{reminder.id}_{int(next_time.timestamp())}"

            self.scheduler.add_job(
                self._send_reminder_job,
                trigger="date",
                run_date=next_time,
                args=[reminder.id],
                id=job_id,
            )

            logger.info(
                "next_notification_scheduled",
                reminder_id=reminder.id,
                next_time=next_time.isoformat(),
            )

        except Exception as e:
            logger.error(
                "next_notification_scheduling_failed",
                reminder_id=reminder.id,
                error=str(e),
            )

    async def recover_jobs_from_database(self) -> None:
        from ..repositories.reminder_repository import ReminderRepository
        from ..utils.database import get_async_session

        try:
            async with get_async_session() as session:
                reminder_repo = ReminderRepository(session)
                active_reminders = await reminder_repo.get_active_reminders()
                recovered_count = 0

                for reminder_entity in active_reminders:
                    try:
                        from ..utils.transformers import entity_to_reminder_dto

                        reminder = entity_to_reminder_dto(reminder_entity)

                        now_utc = datetime.now(pytz.UTC).replace(tzinfo=None)
                        if reminder.next_notification > now_utc:
                            job_id = f"reminder_{reminder.id}"
                            existing_job = self.scheduler.get_job(job_id)
                            if not existing_job:
                                await self.schedule_reminder(reminder)
                                recovered_count += 1
                            else:
                                logger.info(
                                    "reminder_job_already_exists",
                                    reminder_id=reminder.id,
                                    job_id=job_id,
                                )
                        else:
                            overdue_minutes = int(
                                (now_utc - reminder.next_notification).total_seconds()
                                / 60
                            )
                            if overdue_minutes <= 60:
                                immediate_time = now_utc + timedelta(seconds=30)
                                await self.reschedule_reminder(reminder, immediate_time)
                                recovered_count += 1
                            else:
                                logger.warning(
                                    "reminder_too_overdue_skipped",
                                    reminder_id=reminder.id,
                                    overdue_minutes=overdue_minutes,
                                )

                    except Exception as e:
                        logger.error(
                            "reminder_recovery_failed",
                            reminder_id=reminder_entity.id,
                            error=str(e),
                        )

                logger.info(
                    "jobs_recovery_completed",
                    total_reminders=len(active_reminders),
                    recovered_jobs=recovered_count,
                )

        except Exception as e:
            logger.error("jobs_recovery_failed", error=str(e))
            raise SchedulingException(f"Failed to recover jobs from database: {e}")

    def _job_listener(self, event) -> None:
        if event.exception:
            logger.error(
                "scheduled_job_failed",
                job_id=event.job_id,
                error=str(event.exception),
                traceback=event.traceback,
            )
        else:
            logger.debug("scheduled_job_completed", job_id=event.job_id)
