from datetime import datetime

import pytest
from reminder_bot.models.entities import ReminderEntity, ReminderStatus, UserEntity
from reminder_bot.repositories.reminder_repository import ReminderRepository
from reminder_bot.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_reminder_repository_create(async_session):
    repo = ReminderRepository(async_session)
    
    entity = ReminderEntity(
        user_id=12345,
        chat_id=12345,
        text="Test reminder",
        schedule_time="08:00",
        interval_days=1,
        status=ReminderStatus.ACTIVE.value,
        next_notification=datetime.utcnow(),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    result = await repo.create(entity)
    
    assert result.id is not None
    assert result.text == "Test reminder"
    assert result.status == ReminderStatus.ACTIVE.value


@pytest.mark.asyncio
async def test_reminder_repository_get_by_id(async_session, populated_database):
    repo = ReminderRepository(async_session)
    reminder = populated_database["reminder"]
    
    result = await repo.get_by_id(reminder.id)
    
    assert result is not None
    assert result.id == reminder.id
    assert result.text == reminder.text


@pytest.mark.asyncio
async def test_reminder_repository_get_by_id_not_found(async_session):
    repo = ReminderRepository(async_session)
    
    result = await repo.get_by_id(99999)
    
    assert result is None


@pytest.mark.asyncio
async def test_reminder_repository_update(async_session, populated_database):
    repo = ReminderRepository(async_session)
    reminder = populated_database["reminder"]
    
    reminder.text = "Updated text"
    
    result = await repo.update(reminder)
    
    assert result.text == "Updated text"
    
    retrieved = await repo.get_by_id(reminder.id)
    assert retrieved.text == "Updated text"


@pytest.mark.asyncio
async def test_reminder_repository_delete(async_session, populated_database):
    repo = ReminderRepository(async_session)
    reminder = populated_database["reminder"]
    
    success = await repo.delete(reminder.id)
    
    assert success is True
    
    result = await repo.get_by_id(reminder.id)
    assert result is None


@pytest.mark.asyncio
async def test_reminder_repository_delete_not_found(async_session):
    repo = ReminderRepository(async_session)
    
    success = await repo.delete(99999)
    
    assert success is False


@pytest.mark.asyncio
async def test_reminder_repository_get_all(async_session, populated_database):
    repo = ReminderRepository(async_session)
    
    results = await repo.get_all()
    
    assert len(results) >= 1
    assert any(r.id == populated_database["reminder"].id for r in results)


@pytest.mark.asyncio
async def test_reminder_repository_get_by_user_id(async_session, populated_database):
    repo = ReminderRepository(async_session)
    user = populated_database["user"]
    
    results = await repo.get_by_user_id(user.telegram_id)
    
    assert len(results) >= 1
    assert all(r.user_id == user.telegram_id for r in results)


@pytest.mark.asyncio
async def test_reminder_repository_get_active_reminders(async_session, populated_database):
    repo = ReminderRepository(async_session)
    
    results = await repo.get_active_reminders()
    
    assert len(results) >= 1
    assert all(r.status == ReminderStatus.ACTIVE.value for r in results)


@pytest.mark.asyncio
async def test_reminder_repository_update_status(async_session, populated_database):
    repo = ReminderRepository(async_session)
    reminder = populated_database["reminder"]
    
    success = await repo.update_status(reminder.id, ReminderStatus.COMPLETED)
    
    assert success is True
    
    updated = await repo.get_by_id(reminder.id)
    assert updated.status == ReminderStatus.COMPLETED.value


@pytest.mark.asyncio
async def test_reminder_repository_update_message_id(async_session, populated_database):
    repo = ReminderRepository(async_session)
    reminder = populated_database["reminder"]
    
    success = await repo.update_message_id(reminder.id, 12345)
    
    assert success is True
    
    updated = await repo.get_by_id(reminder.id)
    assert updated.last_message_id == 12345


@pytest.mark.asyncio
async def test_reminder_repository_increment_notification_count(
    async_session, populated_database
):
    repo = ReminderRepository(async_session)
    reminder = populated_database["reminder"]
    original_count = reminder.notification_count
    
    success = await repo.increment_notification_count(reminder.id)
    
    assert success is True
    
    updated = await repo.get_by_id(reminder.id)
    assert updated.notification_count == original_count + 1


@pytest.mark.asyncio
async def test_reminder_repository_update_next_notification(
    async_session, populated_database
):
    from datetime import datetime, timedelta
    
    repo = ReminderRepository(async_session)
    reminder = populated_database["reminder"]
    new_time = datetime.utcnow() + timedelta(hours=2)
    
    success = await repo.update_next_notification(reminder.id, new_time)
    
    assert success is True
    
    updated = await repo.get_by_id(reminder.id)
    assert updated.next_notification == new_time


@pytest.mark.asyncio
async def test_reminder_repository_cancel_all_reminders_for_user(
    async_session, populated_database
):
    repo = ReminderRepository(async_session)
    user = populated_database["user"]
    
    count = await repo.cancel_all_reminders_for_user(user.telegram_id)
    
    assert count >= 1
    
    results = await repo.get_by_user_id(user.telegram_id)
    active = [r for r in results if r.status == ReminderStatus.ACTIVE.value]
    assert len(active) == 0


@pytest.mark.asyncio
async def test_reminder_repository_get_all_reminders(async_session, populated_database):
    repo = ReminderRepository(async_session)
    
    results = await repo.get_all_reminders()
    
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_user_repository_create(async_session):
    repo = UserRepository(async_session)
    
    entity = UserEntity(
        telegram_id=99999,
        is_blocked=False,
        is_whitelisted=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    
    result = await repo.create(entity)
    
    assert result.telegram_id == 99999
    assert result.is_blocked is False


@pytest.mark.asyncio
async def test_user_repository_get_by_id(async_session, populated_database):
    repo = UserRepository(async_session)
    user = populated_database["user"]
    
    result = await repo.get_by_id(user.telegram_id)
    
    assert result is not None
    assert result.telegram_id == user.telegram_id


@pytest.mark.asyncio
async def test_user_repository_get_by_id_not_found(async_session):
    repo = UserRepository(async_session)
    
    result = await repo.get_by_id(99999)
    
    assert result is None


@pytest.mark.asyncio
async def test_user_repository_update(async_session, populated_database):
    repo = UserRepository(async_session)
    user = populated_database["user"]
    
    user.is_blocked = True
    
    result = await repo.update(user)
    
    assert result.is_blocked is True
    
    retrieved = await repo.get_by_id(user.telegram_id)
    assert retrieved.is_blocked is True


@pytest.mark.asyncio
async def test_user_repository_delete(async_session):
    repo = UserRepository(async_session)
    
    entity = UserEntity(
        telegram_id=88888,
        is_blocked=False,
        is_whitelisted=False,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    await repo.create(entity)
    
    success = await repo.delete(88888)
    
    assert success is True
    
    result = await repo.get_by_id(88888)
    assert result is None


@pytest.mark.asyncio
async def test_user_repository_delete_not_found(async_session):
    repo = UserRepository(async_session)
    
    success = await repo.delete(99999)
    
    assert success is False


@pytest.mark.asyncio
async def test_user_repository_get_all(async_session, populated_database):
    repo = UserRepository(async_session)
    
    results = await repo.get_all()
    
    assert len(results) >= 1
    assert any(u.telegram_id == populated_database["user"].telegram_id for u in results)


@pytest.mark.asyncio
async def test_user_repository_update_blocked_status(async_session, populated_database):
    repo = UserRepository(async_session)
    user = populated_database["user"]
    
    success = await repo.update_blocked_status(user.telegram_id, True)
    
    assert success is True
    
    updated = await repo.get_by_id(user.telegram_id)
    assert updated.is_blocked is True
    
    success = await repo.update_blocked_status(user.telegram_id, False)
    assert success is True
    
    updated = await repo.get_by_id(user.telegram_id)
    assert updated.is_blocked is False


@pytest.mark.asyncio
async def test_user_repository_update_whitelisted_status(
    async_session, populated_database
):
    repo = UserRepository(async_session)
    user = populated_database["user"]
    
    success = await repo.update_whitelisted_status(user.telegram_id, True)
    
    assert success is True
    
    updated = await repo.get_by_id(user.telegram_id)
    assert updated.is_whitelisted is True
    
    success = await repo.update_whitelisted_status(user.telegram_id, False)
    assert success is True
    
    updated = await repo.get_by_id(user.telegram_id)
    assert updated.is_whitelisted is False
