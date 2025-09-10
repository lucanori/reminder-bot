import pytest
import asyncio
from datetime import datetime, timedelta
from reminder_bot.models.dtos import ReminderCreateDTO, ReminderUpdateDTO
from reminder_bot.models.entities import ReminderStatus
from reminder_bot.utils.exceptions import ValidationException


@pytest.mark.asyncio
async def test_create_reminder(reminder_service, populated_database):
    user = populated_database["user"]
    
    reminder_data = ReminderCreateDTO(
        user_id=user.telegram_id,
        chat_id=user.telegram_id,
        text="Take medicine",
        schedule_time="14:30",
        interval_days=7,
        notification_interval_minutes=10,
        max_notifications=15
    )
    
    reminder_dto = await reminder_service.create_reminder(reminder_data)
    
    assert reminder_dto.text == "Take medicine"
    assert reminder_dto.schedule_time == "14:30"
    assert reminder_dto.interval_days == 7
    assert reminder_dto.notification_interval_minutes == 10
    assert reminder_dto.max_notifications == 15
    assert reminder_dto.status == ReminderStatus.ACTIVE
    assert reminder_dto.notification_count == 0


@pytest.mark.asyncio
async def test_get_user_reminders(reminder_service, populated_database):
    user = populated_database["user"]
    
    reminders = await reminder_service.get_user_reminders(user.telegram_id)
    
    assert len(reminders) >= 1
    assert all(r.user_id == user.telegram_id for r in reminders)


@pytest.mark.asyncio
async def test_get_reminder_by_id(reminder_service, populated_database):
    reminder = populated_database["reminder"]
    
    retrieved_reminder = await reminder_service.get_reminder_by_id(reminder.id)
    
    assert retrieved_reminder is not None
    assert retrieved_reminder.id == reminder.id
    assert retrieved_reminder.text == reminder.text


@pytest.mark.asyncio
async def test_update_reminder(reminder_service, populated_database):
    user = populated_database["user"]
    reminder = populated_database["reminder"]
    
    update_data = ReminderUpdateDTO(
        text="Updated reminder text",
        schedule_time="16:45",
        interval_days=3
    )
    
    updated_reminder = await reminder_service.update_reminder(
        reminder.id, user.telegram_id, update_data
    )
    
    assert updated_reminder is not None
    assert updated_reminder.text == "Updated reminder text"
    assert updated_reminder.schedule_time == "16:45"
    assert updated_reminder.interval_days == 3


@pytest.mark.asyncio
async def test_update_reminder_unauthorized(reminder_service, populated_database):
    reminder = populated_database["reminder"]
    
    update_data = ReminderUpdateDTO(text="Unauthorized update")
    
    result = await reminder_service.update_reminder(
        reminder.id, 999999, update_data
    )
    
    assert result is None


@pytest.mark.asyncio
async def test_confirm_one_time_reminder(reminder_service, populated_database):
    user = populated_database["user"]
    reminder = populated_database["reminder"]
    
    await reminder_service.update_reminder(
        reminder.id, user.telegram_id, 
        ReminderUpdateDTO(interval_days=0)
    )
    
    success = await reminder_service.confirm_reminder(reminder.id, user.telegram_id)
    
    assert success is True
    
    retrieved_reminder = await reminder_service.get_reminder_by_id(reminder.id)
    assert retrieved_reminder.status == ReminderStatus.COMPLETED


@pytest.mark.asyncio
async def test_confirm_recurring_reminder(reminder_service, populated_database):
    user = populated_database["user"]
    reminder = populated_database["reminder"]
    
    original_next_notification = reminder.next_notification
    
    success = await reminder_service.confirm_reminder(reminder.id, user.telegram_id)
    
    assert success is True
    
    retrieved_reminder = await reminder_service.get_reminder_by_id(reminder.id)
    assert retrieved_reminder.notification_count == 0
    assert retrieved_reminder.next_notification > original_next_notification
    assert retrieved_reminder.last_message_id is None


@pytest.mark.asyncio
async def test_snooze_reminder(reminder_service, populated_database):
    reminder = populated_database["reminder"]
    
    original_next_notification = reminder.next_notification
    
    success = await reminder_service.snooze_reminder(reminder.id, 15)
    
    assert success is True
    
    retrieved_reminder = await reminder_service.get_reminder_by_id(reminder.id)
    assert retrieved_reminder.next_notification > original_next_notification


@pytest.mark.asyncio
async def test_delete_reminder(reminder_service, populated_database):
    user = populated_database["user"]
    reminder = populated_database["reminder"]
    
    success = await reminder_service.delete_reminder(reminder.id, user.telegram_id)
    
    assert success is True
    
    retrieved_reminder = await reminder_service.get_reminder_by_id(reminder.id)
    assert retrieved_reminder is None


@pytest.mark.asyncio
async def test_delete_reminder_unauthorized(reminder_service, populated_database):
    reminder = populated_database["reminder"]
    
    success = await reminder_service.delete_reminder(reminder.id, 999999)
    
    assert success is False


@pytest.mark.asyncio
async def test_get_active_reminders(reminder_service, populated_database):
    active_reminders = await reminder_service.get_active_reminders()
    
    assert len(active_reminders) >= 1
    assert all(r.status == ReminderStatus.ACTIVE for r in active_reminders)


@pytest.mark.asyncio 
async def test_calculate_next_notification_time_daily(reminder_service):
    next_time = reminder_service._calculate_next_notification_time("08:00", 1)
    
    assert next_time.hour == 8
    assert next_time.minute == 0
    assert next_time.date() >= datetime.utcnow().date()


@pytest.mark.asyncio
async def test_calculate_next_notification_time_weekly(reminder_service):
    next_time = reminder_service._calculate_next_notification_time("14:30", 7)
    
    assert next_time.hour == 14
    assert next_time.minute == 30
    
    expected_date = datetime.utcnow().date()
    if next_time.time() <= datetime.utcnow().time():
        expected_date += timedelta(days=1)
    
    assert next_time.date() >= expected_date