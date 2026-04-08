from datetime import datetime

import pytest
import pytz
from freezegun import freeze_time
from reminder_bot.models.dtos import ReminderCreateDTO, ReminderUpdateDTO
from reminder_bot.models.entities import ReminderStatus


@pytest.mark.asyncio
async def test_create_reminder_with_weekday(reminder_service, populated_database):
    user = populated_database["user"]

    reminder_data = ReminderCreateDTO(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
        text="Weekly meeting",
        schedule_time="14:30",
        interval_days=7,
        weekday=0,
    )

    reminder_dto = await reminder_service.create_reminder(reminder_data)

    assert reminder_dto.text == "Weekly meeting"
    assert reminder_dto.schedule_time == "14:30"
    assert reminder_dto.interval_days == 7
    assert reminder_dto.weekday == 0


@pytest.mark.asyncio
async def test_create_reminder_with_cron_expression(
    reminder_service, populated_database
):
    user = populated_database["user"]

    reminder_data = ReminderCreateDTO(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
        text="Monday morning task",
        schedule_time="09:00",
        interval_days=0,
        cron_expression="0 9 * * 1",
    )

    reminder_dto = await reminder_service.create_reminder(reminder_data)

    assert reminder_dto.text == "Monday morning task"
    assert reminder_dto.cron_expression == "0 9 * * 1"
    assert reminder_dto.interval_days == 0


@pytest.mark.asyncio
async def test_create_reminder_with_invalid_cron_expression(
    reminder_service, populated_database
):
    user = populated_database["user"]

    with pytest.raises(ValueError, match="Invalid cron expression"):
        ReminderCreateDTO(
            user_id=user.telegram_id,
            chat_id=user.telegram_id,
            text="Invalid cron",
            schedule_time="09:00",
            interval_days=0,
            cron_expression="invalid cron",
        )


@pytest.mark.asyncio
@freeze_time("2024-01-15 10:00:00")
async def test_calculate_next_notification_time_with_weekday(reminder_service):
    tz = pytz.timezone("UTC")

    next_time = reminder_service._calculate_next_notification_time(
        schedule_time="14:30",
        interval_days=7,
        user_timezone=tz,
        weekday=0,
    )

    assert next_time.weekday() == 0
    assert next_time.hour == 14
    assert next_time.minute == 30


@pytest.mark.asyncio
@freeze_time("2024-01-15 10:00:00")
async def test_calculate_next_notification_time_with_cron(reminder_service):
    tz = pytz.timezone("UTC")

    next_time = reminder_service._calculate_next_notification_time(
        schedule_time="09:00",
        interval_days=0,
        user_timezone=tz,
        cron_expression="0 9 * * 1",
    )

    assert next_time.weekday() == 0
    assert next_time.hour == 9
    assert next_time.minute == 0


@pytest.mark.asyncio
@freeze_time("2024-01-15 10:00:00")
async def test_calculate_next_notification_time_cron_priority_over_weekday(
    reminder_service,
):
    tz = pytz.timezone("UTC")

    next_time = reminder_service._calculate_next_notification_time(
        schedule_time="09:00",
        interval_days=7,
        user_timezone=tz,
        weekday=2,
        cron_expression="0 9 * * 1",
    )

    assert next_time.weekday() == 0


@pytest.mark.asyncio
async def test_update_reminder_with_weekday(reminder_service, populated_database):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    update_data = ReminderUpdateDTO(
        weekday=3,
        interval_days=7,
    )

    updated_reminder = await reminder_service.update_reminder(
        reminder.id, user.telegram_id, update_data
    )

    assert updated_reminder is not None
    assert updated_reminder.weekday == 3


@pytest.mark.asyncio
async def test_update_reminder_with_cron_expression(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    update_data = ReminderUpdateDTO(
        cron_expression="0 15 * * 5",
        interval_days=0,
    )

    updated_reminder = await reminder_service.update_reminder(
        reminder.id, user.telegram_id, update_data
    )

    assert updated_reminder is not None
    assert updated_reminder.cron_expression == "0 15 * * 5"


@pytest.mark.asyncio
async def test_confirm_reminder_with_weekday_reschedules_correctly(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    await reminder_service.update_reminder(
        reminder.id, user.telegram_id, ReminderUpdateDTO(interval_days=7, weekday=0)
    )

    original_next = reminder.next_notification

    success = await reminder_service.confirm_reminder(reminder.id, user.telegram_id)

    assert success is True

    retrieved_reminder = await reminder_service.get_reminder_by_id(reminder.id)
    assert retrieved_reminder.notification_count == 0
    assert retrieved_reminder.next_notification > original_next


@pytest.mark.asyncio
async def test_confirm_reminder_with_cron_reschedules_correctly(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    await reminder_service.update_reminder(
        reminder.id,
        user.telegram_id,
        ReminderUpdateDTO(interval_days=0, cron_expression="0 9 * * 1"),
    )

    original_next = reminder.next_notification

    success = await reminder_service.confirm_reminder(reminder.id, user.telegram_id)

    assert success is True

    retrieved_reminder = await reminder_service.get_reminder_by_id(reminder.id)
    assert retrieved_reminder.notification_count == 0
    assert retrieved_reminder.next_notification > original_next


@pytest.mark.asyncio
async def test_confirm_one_time_reminder_with_cron_completes(
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

    retrieved_reminder = await reminder_service.get_reminder_by_id(reminder.id)
    assert retrieved_reminder.status == ReminderStatus.COMPLETED


@pytest.mark.asyncio
async def test_calculate_next_from_cron_with_valid_expression(reminder_service):
    tz = pytz.timezone("UTC")
    now_local = datetime(2024, 1, 15, 10, 0, 0, tzinfo=tz)

    next_time = reminder_service._calculate_next_from_cron("0 9 * * 1", tz, now_local)

    assert next_time.weekday() == 0
    assert next_time.hour == 9
    assert next_time.minute == 0


@pytest.mark.asyncio
async def test_calculate_next_from_cron_with_invalid_expression(reminder_service):
    tz = pytz.timezone("UTC")
    now_local = datetime(2024, 1, 15, 10, 0, 0, tzinfo=tz)

    next_time = reminder_service._calculate_next_from_cron("invalid", tz, now_local)

    assert next_time is not None


@pytest.mark.asyncio
async def test_recompute_reminders_for_timezone_change_with_weekday(
    reminder_service, populated_database
):
    user = populated_database["user"]
    reminder = populated_database["reminder"]

    await reminder_service.update_reminder(
        reminder.id, user.telegram_id, ReminderUpdateDTO(weekday=2, interval_days=7)
    )

    new_tz = pytz.timezone("America/New_York")
    count = await reminder_service.recompute_reminders_for_timezone_change(
        user.telegram_id, new_tz
    )

    assert count >= 1

    retrieved_reminder = await reminder_service.get_reminder_by_id(reminder.id)
    assert retrieved_reminder is not None
