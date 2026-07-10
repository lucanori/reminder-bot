import asyncio
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


def _dto(id=1):
    return ReminderDTO(
        id=id,
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


def _entity(**overrides):
    defaults = {
        "id": 1,
        "user_id": 12345,
        "chat_id": 12345,
        "text": "Test",
        "schedule_time": "08:00",
        "interval_days": 1,
        "status": ReminderStatus.ACTIVE.value,
        "next_notification": datetime.now(pytz.UTC).replace(tzinfo=None),
        "notification_count": 0,
        "max_notifications": 3,
        "notification_interval_minutes": 5,
        "created_at": datetime.now(pytz.UTC).replace(tzinfo=None),
        "updated_at": datetime.now(pytz.UTC).replace(tzinfo=None),
    }
    defaults.update(overrides)
    return ReminderEntity(**defaults)


@pytest.mark.asyncio
async def test_escalation_persist_commit_then_schedule(
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

    reminder_dto = _dto()
    session_cm, mock_session = _make_session_cm()
    entity = _entity()

    call_order = []

    async def update_next_with_order(self, reminder_id, next_time):
        call_order.append("persist")
        return True

    async def commit_with_order():
        call_order.append("commit")

    async def schedule_next_with_order(reminder, next_time):
        call_order.append("schedule")

    mock_session.commit = commit_with_order

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

    assert call_order == ["persist", "commit", "schedule"]

    await scheduler_obj.shutdown()


@pytest.mark.asyncio
async def test_escalation_commit_failure_no_schedule(
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

    reminder_dto = _dto()
    session_cm, mock_session = _make_session_cm()
    mock_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))
    entity = _entity()

    get_by_id_mock = AsyncMock(return_value=entity)
    increment_mock = AsyncMock(return_value=True)
    update_next_mock = AsyncMock(return_value=True)
    send_notification_mock = AsyncMock(
        return_value=NotificationResult(
            message_id=1,
            sent_at=datetime.now(pytz.UTC).replace(tzinfo=None),
            success=True,
        )
    )
    calculate_interval_mock = MagicMock(return_value=5)
    schedule_next_mock = AsyncMock()

    monkeypatch.setattr(ReminderRepository, "get_by_id", get_by_id_mock)
    monkeypatch.setattr(
        ReminderRepository, "increment_notification_count", increment_mock
    )
    monkeypatch.setattr(
        ReminderRepository, "update_next_notification", update_next_mock
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
    monkeypatch.setattr(scheduler_obj, "schedule_next_notification", schedule_next_mock)

    await scheduler_obj._send_reminder_job(1)

    schedule_next_mock.assert_not_called()

    await scheduler_obj.shutdown()


@pytest.mark.asyncio
async def test_recovery_commit_before_any_add_job(
    mock_bot, sample_user, sample_reminder, monkeypatch
):
    from reminder_bot.repositories.reminder_repository import ReminderRepository
    from reminder_bot.utils import database as db_module

    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service)
    session_cm, mock_session = _make_session_cm()

    events = []

    async def record_commit():
        events.append("commit")

    mock_session.commit = record_commit

    with freeze_time("2024-01-01 14:00:00"):
        sample_reminder.id = 1
        sample_reminder.next_notification = datetime(2024, 1, 1, 11, 0, 0)
        sample_reminder.status = ReminderStatus.ACTIVE.value

        async def mock_get_active(self):
            return [sample_reminder]

        async def mock_update_next(self, reminder_id, next_time):
            events.append("persist")
            return True

        monkeypatch.setattr(db_module, "get_async_session", lambda: session_cm)
        monkeypatch.setattr(ReminderRepository, "get_active_reminders", mock_get_active)
        monkeypatch.setattr(
            ReminderRepository, "update_next_notification", mock_update_next
        )

        initial_job_count = len(scheduler.scheduler.get_jobs())

        await scheduler.recover_jobs_from_database()

        assert events[0] == "persist"
        assert events[1] == "commit"

        final_job_count = len(scheduler.scheduler.get_jobs())
        assert final_job_count > initial_job_count

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_recovery_commit_failure_no_jobs(
    mock_bot, sample_user, sample_reminder, monkeypatch
):
    from reminder_bot.repositories.reminder_repository import ReminderRepository
    from reminder_bot.utils import database as db_module
    from reminder_bot.utils.exceptions import SchedulingException

    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service)
    session_cm, mock_session = _make_session_cm()
    mock_session.commit = AsyncMock(side_effect=RuntimeError("commit failed"))

    with freeze_time("2024-01-01 14:00:00"):
        sample_reminder.id = 1
        sample_reminder.next_notification = datetime(2024, 1, 1, 11, 0, 0)
        sample_reminder.status = ReminderStatus.ACTIVE.value

        async def mock_get_active(self):
            return [sample_reminder]

        async def mock_update_next(self, reminder_id, next_time):
            return True

        monkeypatch.setattr(db_module, "get_async_session", lambda: session_cm)
        monkeypatch.setattr(ReminderRepository, "get_active_reminders", mock_get_active)
        monkeypatch.setattr(
            ReminderRepository, "update_next_notification", mock_update_next
        )

        initial_job_count = len(scheduler.scheduler.get_jobs())

        with pytest.raises(SchedulingException):
            await scheduler.recover_jobs_from_database()

        assert len(scheduler.scheduler.get_jobs()) == initial_job_count

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_recovery_overdue_stagger(mock_bot, sample_user, monkeypatch):
    from reminder_bot.repositories.reminder_repository import ReminderRepository
    from reminder_bot.utils import database as db_module

    notification_service = MagicMock()
    notification_service.bot = mock_bot

    scheduler = JobScheduler(notification_service)
    session_cm, _ = _make_session_cm()

    entities = [
        ReminderEntity(
            id=i,
            user_id=sample_user.telegram_id,
            chat_id=12345,
            text=f"R{i}",
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
        for i in range(1, 4)
    ]

    with freeze_time("2024-01-01 14:00:00"):

        async def mock_get_active(self):
            return entities

        async def mock_update_next(self, reminder_id, next_time):
            return True

        monkeypatch.setattr(db_module, "get_async_session", lambda: session_cm)
        monkeypatch.setattr(ReminderRepository, "get_active_reminders", mock_get_active)
        monkeypatch.setattr(
            ReminderRepository, "update_next_notification", mock_update_next
        )

        await scheduler.recover_jobs_from_database()
        await scheduler.start()

        base = datetime(2024, 1, 1, 14, 0, 0)
        for i in range(1, 4):
            job = scheduler.scheduler.get_job(f"reminder_{i}")
            assert job is not None
            expected = base + timedelta(seconds=30 + (i - 1) * 2)
            assert job.next_run_time.replace(tzinfo=None) == expected

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_recovery_failed_persist_skips_stagger_slot(
    mock_bot, sample_user, monkeypatch
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

        base = datetime(2024, 1, 1, 14, 0, 0)
        expected = base + timedelta(seconds=30)
        assert job_b.next_run_time.replace(tzinfo=None) == expected

    await scheduler.shutdown()


@pytest.mark.asyncio
async def test_semaphore_limits_concurrent_sends(mock_bot, monkeypatch):
    from reminder_bot.repositories.reminder_repository import ReminderRepository
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.utils import database as db_module
    from reminder_bot.utils import transformers as transformers_module

    notification_service = MagicMock()
    notification_service.bot = mock_bot
    notification_service.user_service = MagicMock()

    scheduler_obj = JobScheduler(notification_service)
    await scheduler_obj.start()

    session_cm, _ = _make_session_cm()
    entity = _entity()

    active = [0]
    max_active = [0]

    async def tracked_get_by_id(self, reminder_id):
        active[0] += 1
        if active[0] > max_active[0]:
            max_active[0] = active[0]
        await asyncio.sleep(0.05)
        active[0] -= 1
        return entity

    send_notification_mock = AsyncMock(
        return_value=MagicMock(
            message_id=1,
            sent_at=datetime.now(pytz.UTC).replace(tzinfo=None),
            success=False,
            error="some_error",
        )
    )

    monkeypatch.setattr(ReminderRepository, "get_by_id", tracked_get_by_id)
    monkeypatch.setattr(
        NotificationService,
        "send_reminder_notification",
        send_notification_mock,
    )
    monkeypatch.setattr(db_module, "get_async_session", lambda: session_cm)
    monkeypatch.setattr(transformers_module, "entity_to_reminder_dto", lambda e: _dto())

    tasks = [scheduler_obj._send_reminder_job(1) for _ in range(10)]
    await asyncio.gather(*tasks)

    assert max_active[0] <= 5

    await scheduler_obj.shutdown()
