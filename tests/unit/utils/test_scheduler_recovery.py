from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytz
from freezegun import freeze_time
from reminder_bot.models.dtos import ReminderDTO
from reminder_bot.models.entities import ReminderEntity, ReminderStatus
from reminder_bot.utils.scheduler import JobScheduler


def _make_session_cm():
    mock_session = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm, mock_session


def _setup_recovery_mocks(monkeypatch, sample_reminder, session_cm):
    from reminder_bot.repositories.reminder_repository import ReminderRepository
    from reminder_bot.utils import database as db_module

    async def mock_get_active(self):
        return [sample_reminder]

    async def mock_update_next(self, reminder_id, next_time):
        return True

    monkeypatch.setattr(db_module, "get_async_session", lambda: session_cm)
    monkeypatch.setattr(ReminderRepository, "get_active_reminders", mock_get_active)
    monkeypatch.setattr(
        ReminderRepository, "update_next_notification", mock_update_next
    )


@pytest.mark.asyncio
async def test_recover_jobs_from_database_future_jobs(
    mock_bot, sample_user, sample_reminder, monkeypatch
):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service)
    session_cm, _ = _make_session_cm()

    with freeze_time("2024-01-01 12:00:00"):
        sample_reminder.id = 1
        sample_reminder.next_notification = datetime(2024, 1, 1, 14, 0, 0)
        sample_reminder.status = ReminderStatus.ACTIVE.value
        _setup_recovery_mocks(monkeypatch, sample_reminder, session_cm)

        await scheduler.recover_jobs_from_database()
        await scheduler.start()

        job = scheduler.scheduler.get_job(f"reminder_{sample_reminder.id}")
        assert job is not None

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_recover_jobs_from_database_overdue_jobs(
    mock_bot, sample_user, sample_reminder, monkeypatch
):
    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service)
    session_cm, _ = _make_session_cm()

    with freeze_time("2024-01-01 12:00:00"):
        sample_reminder.id = 1
        sample_reminder.next_notification = datetime(2024, 1, 1, 11, 30, 0)
        sample_reminder.status = ReminderStatus.ACTIVE.value
        _setup_recovery_mocks(monkeypatch, sample_reminder, session_cm)

        await scheduler.recover_jobs_from_database()
        await scheduler.start()

        job = scheduler.scheduler.get_job(f"reminder_{sample_reminder.id}")
        assert job is not None

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_recover_jobs_from_database_hours_overdue(
    mock_bot, sample_user, sample_reminder, monkeypatch
):
    from reminder_bot.repositories.reminder_repository import ReminderRepository

    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service)
    session_cm, _ = _make_session_cm()

    with freeze_time("2024-01-01 14:00:00"):
        sample_reminder.id = 1
        sample_reminder.next_notification = datetime(2024, 1, 1, 11, 0, 0)
        sample_reminder.status = ReminderStatus.ACTIVE.value

        update_next_mock = AsyncMock(return_value=True)
        _setup_recovery_mocks(monkeypatch, sample_reminder, session_cm)
        monkeypatch.setattr(
            ReminderRepository, "update_next_notification", update_next_mock
        )

        await scheduler.recover_jobs_from_database()
        await scheduler.start()

        job = scheduler.scheduler.get_job(f"reminder_{sample_reminder.id}")
        assert job is not None

        expected_run = datetime(2024, 1, 1, 14, 0, 30)
        assert job.next_run_time.replace(tzinfo=None) == expected_run

        update_next_mock.assert_called_once()
        call_time = update_next_mock.call_args[0][1]
        assert call_time == expected_run

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_recover_overdue_skips_failed_persist(
    mock_bot, sample_user, sample_reminder, monkeypatch
):
    from reminder_bot.repositories.reminder_repository import ReminderRepository
    from reminder_bot.utils import database as db_module

    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service)
    session_cm, _ = _make_session_cm()

    entity_a = ReminderEntity(
        id=1,
        user_id=sample_user.telegram_id,
        chat_id=12345,
        text="A",
        schedule_time="08:00",
        interval_days=1,
        status=ReminderStatus.ACTIVE.value,
        next_notification=datetime(2024, 1, 1, 11, 0, 0),
        notification_count=0,
        max_notifications=5,
        notification_interval_minutes=5,
        created_at=datetime(2024, 1, 1, 10, 0, 0),
        updated_at=datetime(2024, 1, 1, 10, 0, 0),
    )
    entity_b = ReminderEntity(
        id=2,
        user_id=sample_user.telegram_id,
        chat_id=12345,
        text="B",
        schedule_time="08:00",
        interval_days=1,
        status=ReminderStatus.ACTIVE.value,
        next_notification=datetime(2024, 1, 1, 11, 0, 0),
        notification_count=0,
        max_notifications=5,
        notification_interval_minutes=5,
        created_at=datetime(2024, 1, 1, 10, 0, 0),
        updated_at=datetime(2024, 1, 1, 10, 0, 0),
    )

    with freeze_time("2024-01-01 14:00:00"):

        async def mock_get_active(self):
            return [entity_a, entity_b]

        call_count = [0]

        async def mock_update_next(self, reminder_id, next_time):
            call_count[0] += 1
            return call_count[0] != 1

        monkeypatch.setattr(db_module, "get_async_session", lambda: session_cm)
        monkeypatch.setattr(ReminderRepository, "get_active_reminders", mock_get_active)
        monkeypatch.setattr(
            ReminderRepository, "update_next_notification", mock_update_next
        )

        await scheduler.recover_jobs_from_database()
        await scheduler.start()

        job_a = scheduler.scheduler.get_job("reminder_1")
        job_b = scheduler.scheduler.get_job("reminder_2")
        assert job_a is None
        assert job_b is not None

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_schedule_next_notification_idempotent(
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
    await scheduler.schedule_next_notification(reminder_dto, next_time)

    job_id = f"notification_{reminder_dto.id}_{int(next_time.timestamp())}"
    job = scheduler.scheduler.get_job(job_id)
    assert job is not None

    notification_jobs = [
        j
        for j in scheduler.scheduler.get_jobs()
        if j.id.startswith(f"notification_{reminder_dto.id}_")
    ]
    assert len(notification_jobs) == 1

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_send_reminder_job_persists_next_before_escalation(
    mock_bot, sample_reminder, monkeypatch
):
    from reminder_bot.models.dtos import NotificationResult
    from reminder_bot.repositories.reminder_repository import ReminderRepository
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.utils import database as db_module
    from reminder_bot.utils import transformers as transformers_module

    notification_service = MagicMock()
    notification_service.bot = mock_bot
    notification_service.user_service = MagicMock()

    scheduler_obj = JobScheduler(notification_service)
    await scheduler_obj.start()

    reminder_dto = ReminderDTO(
        id=1,
        user_id=12345,
        chat_id=12345,
        text="Test",
        schedule_time="08:00",
        interval_days=1,
        weekday=None,
        cron_expression=None,
        status=ReminderStatus.ACTIVE,
        next_notification=datetime.now(pytz.UTC).replace(tzinfo=None),
        notification_count=0,
        max_notifications=3,
        notification_interval_minutes=5,
        last_message_id=None,
        job_id=None,
        created_at=datetime.now(pytz.UTC).replace(tzinfo=None),
        updated_at=datetime.now(pytz.UTC).replace(tzinfo=None),
    )

    session_cm, _ = _make_session_cm()

    entity = ReminderEntity(
        id=1,
        user_id=12345,
        chat_id=12345,
        text="Test",
        schedule_time="08:00",
        interval_days=1,
        status=ReminderStatus.ACTIVE.value,
        next_notification=datetime.now(pytz.UTC).replace(tzinfo=None),
        notification_count=0,
        max_notifications=3,
        notification_interval_minutes=5,
    )

    call_order = []

    async def update_next_with_order(self, reminder_id, next_time):
        call_order.append("persist")
        return True

    get_by_id_mock = AsyncMock(return_value=entity)
    increment_mock = AsyncMock(return_value=True)
    send_notification_mock = AsyncMock(
        return_value=NotificationResult(
            message_id=1,
            sent_at=datetime.now(pytz.UTC).replace(tzinfo=None),
            success=True,
        )
    )
    calculate_interval_mock = MagicMock(return_value=5)

    async def schedule_next_with_order(reminder, next_time):
        call_order.append("schedule")

    monkeypatch.setattr(ReminderRepository, "get_by_id", get_by_id_mock)
    monkeypatch.setattr(
        ReminderRepository, "increment_notification_count", increment_mock
    )
    monkeypatch.setattr(
        ReminderRepository, "update_next_notification", update_next_with_order
    )
    monkeypatch.setattr(
        NotificationService, "send_reminder_notification", send_notification_mock
    )
    monkeypatch.setattr(
        NotificationService,
        "calculate_next_notification_interval",
        calculate_interval_mock,
    )
    monkeypatch.setattr(db_module, "get_async_session", lambda: session_cm)
    monkeypatch.setattr(
        transformers_module, "entity_to_reminder_dto", lambda e: reminder_dto
    )
    monkeypatch.setattr(
        scheduler_obj, "schedule_next_notification", schedule_next_with_order
    )

    await scheduler_obj._send_reminder_job(1)

    assert call_order == ["persist", "schedule"]

    call_order.clear()
    update_next_fail = AsyncMock(return_value=False)
    monkeypatch.setattr(
        ReminderRepository, "update_next_notification", update_next_fail
    )
    fail_schedule_mock = AsyncMock()
    monkeypatch.setattr(scheduler_obj, "schedule_next_notification", fail_schedule_mock)

    await scheduler_obj._send_reminder_job(1)

    update_next_fail.assert_called_once()
    fail_schedule_mock.assert_not_called()

    await scheduler_obj.shutdown()
