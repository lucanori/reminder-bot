from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytz
from freezegun import freeze_time
from reminder_bot.models.dtos import ReminderCreateDTO, ReminderUpdateDTO
from reminder_bot.models.entities import ReminderStatus


@pytest.mark.asyncio
async def test_reminder_service_create_with_cron(reminder_service, populated_database):
    user = populated_database["user"]

    reminder_data = ReminderCreateDTO(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
        text="Cron reminder",
        schedule_time="09:00",
        interval_days=0,
        cron_expression="0 9 * * *",
    )

    reminder_dto = await reminder_service.create_reminder(reminder_data)

    assert reminder_dto.text == "Cron reminder"
    assert reminder_dto.cron_expression == "0 9 * * *"
    assert reminder_dto.status == ReminderStatus.ACTIVE


@pytest.mark.asyncio
async def test_reminder_service_create_with_weekday(
    reminder_service, populated_database
):
    user = populated_database["user"]

    reminder_data = ReminderCreateDTO(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
        text="Weekly reminder",
        schedule_time="09:00",
        interval_days=7,
        weekday=1,
    )

    reminder_dto = await reminder_service.create_reminder(reminder_data)

    assert reminder_dto.text == "Weekly reminder"
    assert reminder_dto.weekday == 1


@pytest.mark.asyncio
async def test_reminder_service_update_reminder_with_weekday(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    update_data = ReminderUpdateDTO(
        weekday=3,
    )

    updated_reminder = await reminder_service.update_reminder(
        reminder.id, user.telegram_id, update_data
    )

    assert updated_reminder is not None
    assert updated_reminder.weekday == 3


@pytest.mark.asyncio
async def test_reminder_service_update_reminder_with_cron_expression(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    update_data = ReminderUpdateDTO(
        cron_expression="0 12 * * 1-5",
    )

    updated_reminder = await reminder_service.update_reminder(
        reminder.id, user.telegram_id, update_data
    )

    assert updated_reminder is not None
    assert updated_reminder.cron_expression == "0 12 * * 1-5"


@pytest.mark.asyncio
async def test_reminder_service_confirm_reminder_not_active(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    await reminder_service.update_reminder(
        reminder.id,
        user.telegram_id,
        ReminderUpdateDTO(status=ReminderStatus.COMPLETED),
    )

    success = await reminder_service.confirm_reminder(reminder.id, user.telegram_id)

    assert success is False


@pytest.mark.asyncio
async def test_reminder_service_confirm_reminder_wrong_user(
    reminder_service, populated_database
):
    reminder = populated_database["reminder"]

    success = await reminder_service.confirm_reminder(reminder.id, 999999)

    assert success is False


@pytest.mark.asyncio
async def test_reminder_service_confirm_reminder_with_job_scheduler(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    job_scheduler_mock = AsyncMock()
    job_scheduler_mock.scheduler = MagicMock()
    job_scheduler_mock.scheduler.get_jobs = MagicMock(return_value=[])

    success = await reminder_service.confirm_reminder(
        reminder.id, user.telegram_id, job_scheduler_mock
    )

    assert success is True
    job_scheduler_mock.cancel_reminder.assert_called_once_with(reminder.id)


@pytest.mark.asyncio
async def test_reminder_service_confirm_reminder_cancels_notification_jobs(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    job_scheduler_mock = AsyncMock()
    mock_job = MagicMock()
    mock_job.id = f"notification_{reminder.id}_1234567890"
    job_scheduler_mock.scheduler = MagicMock()
    job_scheduler_mock.scheduler.get_jobs = MagicMock(return_value=[mock_job])
    job_scheduler_mock.scheduler.remove_job = MagicMock()

    success = await reminder_service.confirm_reminder(
        reminder.id, user.telegram_id, job_scheduler_mock
    )

    assert success is True


@pytest.mark.asyncio
async def test_reminder_service_confirm_one_time_completes(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    await reminder_service.update_reminder(
        reminder.id,
        user.telegram_id,
        ReminderUpdateDTO(interval_days=0, cron_expression=None),
    )

    success = await reminder_service.confirm_reminder(reminder.id, user.telegram_id)

    assert success is True

    retrieved = await reminder_service.get_reminder_by_id(reminder.id)
    assert retrieved.status == ReminderStatus.COMPLETED


@pytest.mark.asyncio
async def test_reminder_service_confirm_with_weekday_reschedules(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    await reminder_service.update_reminder(
        reminder.id,
        user.telegram_id,
        ReminderUpdateDTO(interval_days=7, weekday=0, cron_expression=None),
    )

    job_scheduler_mock = AsyncMock()
    job_scheduler_mock.scheduler = MagicMock()
    job_scheduler_mock.scheduler.get_jobs = MagicMock(return_value=[])

    success = await reminder_service.confirm_reminder(
        reminder.id, user.telegram_id, job_scheduler_mock
    )

    assert success is True


@pytest.mark.asyncio
async def test_reminder_service_confirm_with_cron_reschedules(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    await reminder_service.update_reminder(
        reminder.id,
        user.telegram_id,
        ReminderUpdateDTO(interval_days=0, weekday=None, cron_expression="0 9 * * *"),
    )

    job_scheduler_mock = AsyncMock()
    job_scheduler_mock.scheduler = MagicMock()
    job_scheduler_mock.scheduler.get_jobs = MagicMock(return_value=[])

    success = await reminder_service.confirm_reminder(
        reminder.id, user.telegram_id, job_scheduler_mock
    )

    assert success is True


@pytest.mark.asyncio
async def test_reminder_service_calculate_next_notification_time_with_cron(
    reminder_service,
):
    with freeze_time("2024-01-01 12:00:00"):
        next_time = reminder_service._calculate_next_notification_time(
            "09:00", 0, pytz.UTC, None, "0 9 * * *"
        )

        assert next_time.hour == 9
        assert next_time.minute == 0


@pytest.mark.asyncio
async def test_reminder_service_calculate_next_notification_time_with_weekday(
    reminder_service,
):
    with freeze_time("2024-01-01 12:00:00"):
        next_time = reminder_service._calculate_next_notification_time(
            "14:30", 7, pytz.UTC, 2, None
        )

        assert next_time.hour == 14
        assert next_time.minute == 30


@pytest.mark.asyncio
async def test_reminder_service_calculate_next_notification_time_same_day_future(
    reminder_service,
):
    with freeze_time("2024-01-01 08:00:00"):
        next_time = reminder_service._calculate_next_notification_time(
            "14:00", 1, pytz.UTC, None, None
        )

        assert next_time.hour == 14
        assert next_time.minute == 0


@pytest.mark.asyncio
async def test_reminder_service_recompute_reminders_for_timezone_change(
    reminder_service, populated_database
):
    user = populated_database["user"]

    job_scheduler_mock = AsyncMock()

    count = await reminder_service.recompute_reminders_for_timezone_change(
        user.telegram_id, pytz.timezone("Europe/London"), job_scheduler_mock
    )

    assert count >= 1


@pytest.mark.asyncio
async def test_reminder_service_recompute_reminders_no_job_scheduler(
    reminder_service, populated_database
):
    user = populated_database["user"]

    count = await reminder_service.recompute_reminders_for_timezone_change(
        user.telegram_id, pytz.timezone("Europe/London"), None
    )

    assert count >= 1


@pytest.mark.asyncio
async def test_reminder_service_update_next_notification_no_reminder(reminder_service):
    success = await reminder_service.snooze_reminder(99999, 15)

    assert success is False


@pytest.mark.asyncio
async def test_reminder_service_get_user_reminders_exception(reminder_service):
    from reminder_bot.utils.exceptions import DatabaseException

    with patch.object(
        reminder_service.reminder_repo,
        "get_by_user_id",
        side_effect=Exception("DB error"),
    ):
        with pytest.raises(DatabaseException):
            await reminder_service.get_user_reminders(12345)


@pytest.mark.asyncio
async def test_reminder_service_get_reminder_by_id_exception(reminder_service):
    from reminder_bot.utils.exceptions import DatabaseException

    with patch.object(
        reminder_service.reminder_repo, "get_by_id", side_effect=Exception("DB error")
    ):
        with pytest.raises(DatabaseException):
            await reminder_service.get_reminder_by_id(12345)


@pytest.mark.asyncio
async def test_reminder_service_get_active_reminders_exception(reminder_service):
    from reminder_bot.utils.exceptions import DatabaseException

    with patch.object(
        reminder_service.reminder_repo,
        "get_active_reminders",
        side_effect=Exception("DB error"),
    ):
        with pytest.raises(DatabaseException):
            await reminder_service.get_active_reminders()


@pytest.mark.asyncio
async def test_reminder_service_delete_reminder_exception(reminder_service):
    from reminder_bot.utils.exceptions import DatabaseException

    with patch.object(
        reminder_service.reminder_repo, "get_by_id", side_effect=Exception("DB error")
    ):
        with pytest.raises(DatabaseException):
            await reminder_service.delete_reminder(12345, 12345)


@pytest.mark.asyncio
async def test_reminder_service_update_reminder_exception(reminder_service):
    from reminder_bot.utils.exceptions import DatabaseException

    with patch.object(
        reminder_service.reminder_repo, "get_by_id", side_effect=Exception("DB error")
    ):
        with pytest.raises(DatabaseException):
            await reminder_service.update_reminder(
                12345, 12345, ReminderUpdateDTO(text="Test")
            )


@pytest.mark.asyncio
async def test_reminder_service_confirm_reminder_exception(reminder_service):
    from reminder_bot.utils.exceptions import DatabaseException

    with patch.object(
        reminder_service.reminder_repo, "get_by_id", side_effect=Exception("DB error")
    ):
        with pytest.raises(DatabaseException):
            await reminder_service.confirm_reminder(12345, 12345)


@pytest.mark.asyncio
async def test_reminder_service_calculate_next_from_cron_exception(reminder_service):
    with freeze_time("2024-01-01 12:00:00"):
        next_time = reminder_service._calculate_next_from_cron(
            "invalid_cron", pytz.UTC, datetime.now(pytz.UTC)
        )

        assert next_time is not None


@pytest.mark.asyncio
async def test_reminder_service_process_confirmation_with_job_scheduler(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    job_scheduler_mock = AsyncMock()
    job_scheduler_mock.scheduler = MagicMock()
    job_scheduler_mock.scheduler.get_jobs = MagicMock(return_value=[])

    entity = await reminder_service.reminder_repo.get_by_id(reminder.id)

    result = await reminder_service._process_confirmation(
        entity,
        reminder.id,
        user.telegram_id,
        job_scheduler_mock,
        reminder_service.reminder_repo,
    )

    assert result is True


@pytest.mark.asyncio
async def test_reminder_service_create_with_user_timezone_exception(
    reminder_service, populated_database
):
    user = populated_database["user"]

    reminder_data = ReminderCreateDTO(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
        text="Test reminder",
        schedule_time="14:30",
        interval_days=1,
    )

    with patch.object(
        reminder_service,
        "_calculate_next_notification_time",
        side_effect=Exception("Calc error"),
    ):
        with pytest.raises(Exception):
            await reminder_service.create_reminder(reminder_data)


@pytest.mark.asyncio
async def test_reminder_service_create_reminder_without_repo(
    reminder_service, populated_database
):
    user = populated_database["user"]

    reminder_service.reminder_repo = None

    reminder_data = ReminderCreateDTO(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
        text="No repo reminder",
        schedule_time="14:30",
        interval_days=1,
    )

    reminder_dto = await reminder_service.create_reminder(reminder_data)

    assert reminder_dto.text == "No repo reminder"


@pytest.mark.asyncio
async def test_reminder_service_confirm_cancels_notification_jobs(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    job_scheduler_mock = AsyncMock()
    job_scheduler_mock.scheduler = MagicMock()
    job_scheduler_mock.scheduler.get_jobs = MagicMock(return_value=[])

    success = await reminder_service.confirm_reminder(
        reminder.id, user.telegram_id, job_scheduler_mock
    )

    assert success is True
    job_scheduler_mock.cancel_reminder.assert_called_once_with(reminder.id)
    job_scheduler_mock.cancel_notification_jobs.assert_called_once_with(reminder.id)


@pytest.mark.asyncio
async def test_reminder_service_recompute_cancels_notification_jobs(
    reminder_service, populated_database
):
    user = populated_database["user"]

    job_scheduler_mock = AsyncMock()

    count = await reminder_service.recompute_reminders_for_timezone_change(
        user.telegram_id, pytz.timezone("Europe/London"), job_scheduler_mock
    )

    assert count >= 1
    job_scheduler_mock.cancel_notification_jobs.assert_called()


@pytest.mark.asyncio
async def test_reminder_service_confirm_one_time_cancels_jobs(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    await reminder_service.update_reminder(
        reminder.id,
        user.telegram_id,
        ReminderUpdateDTO(interval_days=0, cron_expression=None),
    )

    job_scheduler_mock = AsyncMock()
    job_scheduler_mock.scheduler = MagicMock()
    job_scheduler_mock.scheduler.get_jobs = MagicMock(return_value=[])

    success = await reminder_service.confirm_reminder(
        reminder.id, user.telegram_id, job_scheduler_mock
    )

    assert success is True
    job_scheduler_mock.cancel_reminder.assert_called_once_with(reminder.id)
    job_scheduler_mock.cancel_notification_jobs.assert_called_once_with(reminder.id)
