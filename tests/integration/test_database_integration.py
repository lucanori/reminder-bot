import pytest
import asyncio
from datetime import datetime, timedelta
from reminder_bot.models.entities import UserEntity, ReminderEntity, ReminderStatus
from reminder_bot.repositories.user_repository import UserRepository
from reminder_bot.repositories.reminder_repository import ReminderRepository
from reminder_bot.services.user_service import UserService
from reminder_bot.services.reminder_service import ReminderService
from reminder_bot.models.dtos import ReminderCreateDTO


@pytest.mark.asyncio
async def test_end_to_end_user_reminder_workflow(async_session):
    user_repo = UserRepository(async_session)
    reminder_repo = ReminderRepository(async_session)
    user_service = UserService(user_repo)
    reminder_service = ReminderService(reminder_repo)
    
    telegram_id = 123456789
    
    user_dto = await user_service.register_or_update_user(telegram_id)
    assert user_dto.telegram_id == telegram_id
    
    reminder_data = ReminderCreateDTO(
        user_id=telegram_id,
        chat_id=telegram_id,
        text="Integration test reminder",
        schedule_time="10:30",
        interval_days=2,
        notification_interval_minutes=7,
        max_notifications=8
    )
    
    reminder_dto = await reminder_service.create_reminder(reminder_data)
    assert reminder_dto.text == "Integration test reminder"
    assert reminder_dto.user_id == telegram_id
    
    user_reminders = await reminder_service.get_user_reminders(telegram_id)
    assert len(user_reminders) == 1
    assert user_reminders[0].id == reminder_dto.id
    
    success = await reminder_service.confirm_reminder(reminder_dto.id, telegram_id)
    assert success is True
    
    updated_reminder = await reminder_service.get_reminder_by_id(reminder_dto.id)
    assert updated_reminder.notification_count == 0
    assert updated_reminder.next_notification > reminder_dto.next_notification


@pytest.mark.asyncio
async def test_user_access_control_integration(async_session):
    user_repo = UserRepository(async_session)
    user_service = UserService(user_repo)
    
    telegram_id = 987654321
    
    has_access = await user_service.check_user_access(telegram_id)
    assert has_access is True
    
    await user_service.register_or_update_user(telegram_id)
    
    success = await user_service.block_user(telegram_id)
    assert success is True
    
    has_access = await user_service.check_user_access(telegram_id)
    assert has_access is False
    
    success = await user_service.unblock_user(telegram_id)
    assert success is True
    
    has_access = await user_service.check_user_access(telegram_id)
    assert has_access is True


@pytest.mark.asyncio
async def test_reminder_status_transitions(async_session):
    user_repo = UserRepository(async_session)
    reminder_repo = ReminderRepository(async_session)
    user_service = UserService(user_repo)
    reminder_service = ReminderService(reminder_repo)
    
    telegram_id = 555666777
    
    await user_service.register_or_update_user(telegram_id)
    
    reminder_data = ReminderCreateDTO(
        user_id=telegram_id,
        chat_id=telegram_id,
        text="Status transition test",
        schedule_time="15:45",
        interval_days=0
    )
    
    reminder_dto = await reminder_service.create_reminder(reminder_data)
    assert reminder_dto.status == ReminderStatus.ACTIVE
    
    success = await reminder_service.confirm_reminder(reminder_dto.id, telegram_id)
    assert success is True
    
    updated_reminder = await reminder_service.get_reminder_by_id(reminder_dto.id)
    assert updated_reminder.status == ReminderStatus.COMPLETED


@pytest.mark.asyncio
async def test_concurrent_reminder_operations(async_session):
    user_repo = UserRepository(async_session)
    reminder_repo = ReminderRepository(async_session)
    user_service = UserService(user_repo)
    reminder_service = ReminderService(reminder_repo)
    
    telegram_id = 111222333
    await user_service.register_or_update_user(telegram_id)
    
    async def create_reminder(index):
        reminder_data = ReminderCreateDTO(
            user_id=telegram_id,
            chat_id=telegram_id,
            text=f"Concurrent reminder {index}",
            schedule_time=f"{10 + index % 12:02d}:00",
            interval_days=1
        )
        return await reminder_service.create_reminder(reminder_data)
    
    tasks = [create_reminder(i) for i in range(5)]
    reminder_dtos = await asyncio.gather(*tasks)
    
    assert len(reminder_dtos) == 5
    assert all(r.user_id == telegram_id for r in reminder_dtos)
    
    user_reminders = await reminder_service.get_user_reminders(telegram_id)
    assert len(user_reminders) == 5


@pytest.mark.asyncio
async def test_database_transaction_rollback(async_session):
    user_repo = UserRepository(async_session)
    
    user = UserEntity(
        telegram_id=999888777,
        is_blocked=False,
        is_whitelisted=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    try:
        async_session.add(user)
        await async_session.flush()
        
        raise Exception("Simulated error")
        
    except Exception:
        await async_session.rollback()
    
    retrieved_user = await user_repo.get_by_id(999888777)
    assert retrieved_user is None


@pytest.mark.asyncio
async def test_reminder_time_calculations(async_session):
    reminder_repo = ReminderRepository(async_session)
    reminder_service = ReminderService(reminder_repo)
    
    next_8am = reminder_service._calculate_next_notification_time("08:00", 1)
    next_2pm = reminder_service._calculate_next_notification_time("14:00", 1)
    
    assert next_8am.hour == 8
    assert next_8am.minute == 0
    assert next_2pm.hour == 14
    assert next_2pm.minute == 0
    
    now = datetime.utcnow()
    if now.hour < 8:
        assert next_8am.date() == now.date()
    else:
        assert next_8am.date() == now.date() + timedelta(days=1)


@pytest.mark.asyncio
async def test_user_statistics_accuracy(async_session):
    user_repo = UserRepository(async_session)
    user_service = UserService(user_repo)
    
    initial_stats = await user_service.get_user_statistics()
    
    for i in range(3):
        await user_service.register_or_update_user(800000 + i)
    
    await user_service.block_user(800001)
    await user_service.whitelist_user(800002)
    
    final_stats = await user_service.get_user_statistics()
    
    assert final_stats["total_users"] >= initial_stats["total_users"] + 3
    assert final_stats["blocked_users"] >= initial_stats["blocked_users"] + 1
    assert final_stats["whitelisted_users"] >= initial_stats["whitelisted_users"] + 1