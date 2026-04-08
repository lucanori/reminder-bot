from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytz
from freezegun import freeze_time
from reminder_bot.models.dtos import ReminderDTO
from reminder_bot.models.entities import ReminderEntity, ReminderStatus
from reminder_bot.utils.scheduler import JobScheduler


@pytest.mark.asyncio
async def test_job_scheduler_initialization(mock_bot, reminder_repository):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)

    assert scheduler.notification_service == notification_service
    assert scheduler.reminder_repo == reminder_repository
    assert scheduler.scheduler is not None


@pytest.mark.asyncio
async def test_job_scheduler_start_shutdown(mock_bot, reminder_repository):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)

    await scheduler.start()
    assert scheduler.scheduler.running is True

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_schedule_reminder(mock_bot, reminder_repository, sample_reminder):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    reminder_dto = ReminderDTO(
        id=sample_reminder.id or 1,
        user_id=sample_reminder.user_id,
        chat_id=sample_reminder.chat_id,
        text=sample_reminder.text,
        schedule_time=sample_reminder.schedule_time,
        interval_days=sample_reminder.interval_days,
        weekday=sample_reminder.weekday,
        cron_expression=sample_reminder.cron_expression,
        status=ReminderStatus.ACTIVE,
        next_notification=datetime.now(pytz.UTC).replace(tzinfo=None)
        + timedelta(hours=1),
        notification_count=sample_reminder.notification_count,
        max_notifications=sample_reminder.max_notifications,
        notification_interval_minutes=sample_reminder.notification_interval_minutes,
        last_message_id=sample_reminder.last_message_id,
        job_id=sample_reminder.job_id,
        created_at=sample_reminder.created_at,
        updated_at=sample_reminder.updated_at,
    )

    job_id = await scheduler.schedule_reminder(reminder_dto)

    assert job_id == f"reminder_{reminder_dto.id}"
    assert scheduler.scheduler.get_job(job_id) is not None

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_reschedule_reminder(mock_bot, reminder_repository, sample_reminder):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    reminder_dto = ReminderDTO(
        id=sample_reminder.id or 1,
        user_id=sample_reminder.user_id,
        chat_id=sample_reminder.chat_id,
        text=sample_reminder.text,
        schedule_time=sample_reminder.schedule_time,
        interval_days=sample_reminder.interval_days,
        weekday=sample_reminder.weekday,
        cron_expression=sample_reminder.cron_expression,
        status=ReminderStatus.ACTIVE,
        next_notification=datetime.now(pytz.UTC).replace(tzinfo=None)
        + timedelta(hours=1),
        notification_count=sample_reminder.notification_count,
        max_notifications=sample_reminder.max_notifications,
        notification_interval_minutes=sample_reminder.notification_interval_minutes,
        last_message_id=sample_reminder.last_message_id,
        job_id=sample_reminder.job_id,
        created_at=sample_reminder.created_at,
        updated_at=sample_reminder.updated_at,
    )

    await scheduler.schedule_reminder(reminder_dto)

    new_time = datetime.now(pytz.UTC).replace(tzinfo=None) + timedelta(hours=2)
    job_id = await scheduler.reschedule_reminder(reminder_dto, new_time)

    assert job_id == f"reminder_{reminder_dto.id}"
    job = scheduler.scheduler.get_job(job_id)
    assert job is not None

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_cancel_reminder(mock_bot, reminder_repository, sample_reminder):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    reminder_dto = ReminderDTO(
        id=sample_reminder.id or 1,
        user_id=sample_reminder.user_id,
        chat_id=sample_reminder.chat_id,
        text=sample_reminder.text,
        schedule_time=sample_reminder.schedule_time,
        interval_days=sample_reminder.interval_days,
        weekday=sample_reminder.weekday,
        cron_expression=sample_reminder.cron_expression,
        status=ReminderStatus.ACTIVE,
        next_notification=datetime.now(pytz.UTC).replace(tzinfo=None)
        + timedelta(hours=1),
        notification_count=sample_reminder.notification_count,
        max_notifications=sample_reminder.max_notifications,
        notification_interval_minutes=sample_reminder.notification_interval_minutes,
        last_message_id=sample_reminder.last_message_id,
        job_id=sample_reminder.job_id,
        created_at=sample_reminder.created_at,
        updated_at=sample_reminder.updated_at,
    )

    await scheduler.schedule_reminder(reminder_dto)

    success = await scheduler.cancel_reminder(reminder_dto.id)
    assert success is True

    success = await scheduler.cancel_reminder(99999)
    assert success is False

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_recover_jobs_from_database_future_jobs(
    mock_bot, reminder_repository, sample_user, sample_reminder
):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    with freeze_time("2024-01-01 12:00:00"):
        sample_reminder.next_notification = datetime(2024, 1, 1, 14, 0, 0)
        sample_reminder.status = ReminderStatus.ACTIVE.value

        async def mock_get_active():
            return [sample_reminder]

        reminder_repository.get_active_reminders = mock_get_active

        await scheduler.recover_jobs_from_database()

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_recover_jobs_from_database_overdue_jobs(
    mock_bot, reminder_repository, sample_user, sample_reminder
):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    with freeze_time("2024-01-01 12:00:00"):
        sample_reminder.next_notification = datetime(2024, 1, 1, 11, 30, 0)
        sample_reminder.status = ReminderStatus.ACTIVE.value

        async def mock_get_active():
            return [sample_reminder]

        reminder_repository.get_active_reminders = mock_get_active

        await scheduler.recover_jobs_from_database()

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_recover_jobs_from_database_too_overdue(
    mock_bot, reminder_repository, sample_user, sample_reminder
):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    with freeze_time("2024-01-01 14:00:00"):
        sample_reminder.next_notification = datetime(2024, 1, 1, 11, 0, 0)
        sample_reminder.status = ReminderStatus.ACTIVE.value

        async def mock_get_active():
            return [sample_reminder]

        reminder_repository.get_active_reminders = mock_get_active

        await scheduler.recover_jobs_from_database()

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_schedule_next_notification(
    mock_bot, reminder_repository, sample_reminder
):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    reminder_dto = ReminderDTO(
        id=sample_reminder.id or 1,
        user_id=sample_reminder.user_id,
        chat_id=sample_reminder.chat_id,
        text=sample_reminder.text,
        schedule_time=sample_reminder.schedule_time,
        interval_days=sample_reminder.interval_days,
        weekday=sample_reminder.weekday,
        cron_expression=sample_reminder.cron_expression,
        status=ReminderStatus.ACTIVE,
        next_notification=datetime.now(pytz.UTC).replace(tzinfo=None)
        + timedelta(hours=1),
        notification_count=sample_reminder.notification_count,
        max_notifications=sample_reminder.max_notifications,
        notification_interval_minutes=sample_reminder.notification_interval_minutes,
        last_message_id=sample_reminder.last_message_id,
        job_id=sample_reminder.job_id,
        created_at=sample_reminder.created_at,
        updated_at=sample_reminder.updated_at,
    )

    next_time = datetime.now(pytz.UTC).replace(tzinfo=None) + timedelta(minutes=5)
    await scheduler.schedule_next_notification(reminder_dto, next_time)

    job_id = f"notification_{reminder_dto.id}_{int(next_time.timestamp())}"
    job = scheduler.scheduler.get_job(job_id)
    assert job is not None

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_reset_and_reschedule_reminder_weekday(
    mock_bot, reminder_repository, sample_reminder, sample_user
):
    notification_service = MagicMock()
    notification_service.bot = mock_bot
    notification_service.user_service = MagicMock()
    notification_service.user_service.get_user_timezone = AsyncMock(
        return_value=pytz.timezone("UTC")
    )

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    sample_reminder.weekday = 0
    sample_reminder.interval_days = 7
    sample_reminder.schedule_time = "09:00"

    reminder_dto = ReminderDTO(
        id=1,
        user_id=sample_user.telegram_id,
        chat_id=sample_user.telegram_id,
        text=sample_reminder.text,
        schedule_time="09:00",
        interval_days=7,
        weekday=0,
        cron_expression=None,
        status=ReminderStatus.ACTIVE,
        next_notification=datetime.now(pytz.UTC).replace(tzinfo=None),
        notification_count=5,
        max_notifications=10,
        notification_interval_minutes=5,
        last_message_id=None,
        job_id=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    async def mock_get_by_id(reminder_id):
        entity = ReminderEntity(
            id=reminder_id,
            user_id=sample_user.telegram_id,
            chat_id=sample_user.telegram_id,
            text="Test",
            schedule_time="09:00",
            interval_days=7,
            weekday=0,
            cron_expression=None,
            status=ReminderStatus.ACTIVE.value,
            next_notification=datetime.utcnow(),
            notification_count=5,
            max_notifications=10,
            notification_interval_minutes=5,
        )
        return entity

    reminder_repository.get_by_id = mock_get_by_id
    reminder_repository.update = AsyncMock(return_value=None)

    await scheduler._reset_and_reschedule_reminder(reminder_repository, reminder_dto)

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_reset_and_reschedule_reminder_cron(
    mock_bot, reminder_repository, sample_reminder, sample_user
):
    notification_service = MagicMock()
    notification_service.bot = mock_bot
    notification_service.user_service = MagicMock()
    notification_service.user_service.get_user_timezone = AsyncMock(
        return_value=pytz.timezone("UTC")
    )

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    reminder_dto = ReminderDTO(
        id=1,
        user_id=sample_user.telegram_id,
        chat_id=sample_user.telegram_id,
        text=sample_reminder.text,
        schedule_time="09:00",
        interval_days=0,
        weekday=None,
        cron_expression="0 9 * * *",
        status=ReminderStatus.ACTIVE,
        next_notification=datetime.now(pytz.UTC).replace(tzinfo=None),
        notification_count=5,
        max_notifications=10,
        notification_interval_minutes=5,
        last_message_id=None,
        job_id=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    async def mock_get_by_id(reminder_id):
        entity = ReminderEntity(
            id=reminder_id,
            user_id=sample_user.telegram_id,
            chat_id=sample_user.telegram_id,
            text="Test",
            schedule_time="09:00",
            interval_days=0,
            weekday=None,
            cron_expression="0 9 * * *",
            status=ReminderStatus.ACTIVE.value,
            next_notification=datetime.utcnow(),
            notification_count=5,
            max_notifications=10,
            notification_interval_minutes=5,
        )
        return entity

    reminder_repository.get_by_id = mock_get_by_id
    reminder_repository.update = AsyncMock(return_value=None)

    await scheduler._reset_and_reschedule_reminder(reminder_repository, reminder_dto)

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_job_listener_success(mock_bot, reminder_repository):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)

    mock_event = MagicMock()
    mock_event.exception = None
    mock_event.job_id = "test_job_123"

    scheduler._job_listener(mock_event)


@pytest.mark.asyncio
async def test_job_listener_error(mock_bot, reminder_repository):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)

    mock_event = MagicMock()
    mock_event.exception = Exception("Test error")
    mock_event.job_id = "test_job_123"
    mock_event.traceback = "Traceback line 1\nTraceback line 2"

    scheduler._job_listener(mock_event)


@pytest.mark.asyncio
async def test_cancel_notification_jobs(mock_bot, reminder_repository, sample_reminder):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    reminder_id = 1

    next_time1 = datetime.now(pytz.UTC).replace(tzinfo=None) + timedelta(minutes=5)
    next_time2 = datetime.now(pytz.UTC).replace(tzinfo=None) + timedelta(minutes=10)

    job_id1 = f"notification_{reminder_id}_{int(next_time1.timestamp())}"
    job_id2 = f"notification_{reminder_id}_{int(next_time2.timestamp())}"

    scheduler.scheduler.add_job(
        lambda: None,
        trigger="date",
        run_date=next_time1,
        id=job_id1,
    )
    scheduler.scheduler.add_job(
        lambda: None,
        trigger="date",
        run_date=next_time2,
        id=job_id2,
    )

    assert scheduler.scheduler.get_job(job_id1) is not None
    assert scheduler.scheduler.get_job(job_id2) is not None

    cancelled_count = await scheduler.cancel_notification_jobs(reminder_id)

    assert cancelled_count == 2
    assert scheduler.scheduler.get_job(job_id1) is None
    assert scheduler.scheduler.get_job(job_id2) is None

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_cancel_notification_jobs_only_target_reminder(
    mock_bot, reminder_repository, sample_reminder
):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    reminder_id_1 = 1
    reminder_id_2 = 2

    next_time = datetime.now(pytz.UTC).replace(tzinfo=None) + timedelta(minutes=5)

    job_id_1 = f"notification_{reminder_id_1}_{int(next_time.timestamp())}"
    job_id_2 = f"notification_{reminder_id_2}_{int(next_time.timestamp())}"

    scheduler.scheduler.add_job(
        lambda: None,
        trigger="date",
        run_date=next_time,
        id=job_id_1,
    )
    scheduler.scheduler.add_job(
        lambda: None,
        trigger="date",
        run_date=next_time,
        id=job_id_2,
    )

    cancelled_count = await scheduler.cancel_notification_jobs(reminder_id_1)

    assert cancelled_count == 1
    assert scheduler.scheduler.get_job(job_id_1) is None
    assert scheduler.scheduler.get_job(job_id_2) is not None

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_send_reminder_job_cancels_retries_on_confirmation(
    mock_bot, reminder_repository, sample_user, sample_reminder, monkeypatch
):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service, reminder_repository)
    await scheduler.start()

    reminder_id = 1

    next_time = datetime.now(pytz.UTC).replace(tzinfo=None) + timedelta(minutes=5)
    job_id = f"notification_{reminder_id}_{int(next_time.timestamp())}"

    scheduler.scheduler.add_job(
        lambda: None,
        trigger="date",
        run_date=next_time,
        id=job_id,
    )

    assert scheduler.scheduler.get_job(job_id) is not None

    cancelled_count = await scheduler.cancel_notification_jobs(reminder_id)
    assert cancelled_count == 1
    assert scheduler.scheduler.get_job(job_id) is None

    await scheduler.shutdown()
