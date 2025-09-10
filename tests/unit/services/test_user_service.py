import pytest
from datetime import datetime
from reminder_bot.models.entities import UserEntity
from reminder_bot.models.dtos import UserPreferencesDTO
from reminder_bot.utils.exceptions import DatabaseException


@pytest.mark.asyncio
async def test_register_new_user(user_service, async_session):
    telegram_id = 999999
    
    user_dto = await user_service.register_or_update_user(telegram_id)
    
    assert user_dto.telegram_id == telegram_id
    assert not user_dto.is_blocked
    assert not user_dto.is_whitelisted
    assert user_dto.created_at is not None


@pytest.mark.asyncio
async def test_update_existing_user(user_service, populated_database):
    user = populated_database["user"]
    original_updated_at = user.updated_at
    
    await asyncio.sleep(0.001)
    user_dto = await user_service.register_or_update_user(user.telegram_id)
    
    assert user_dto.telegram_id == user.telegram_id
    assert user_dto.updated_at > original_updated_at


@pytest.mark.asyncio
async def test_check_user_access_new_user(user_service):
    telegram_id = 888888
    
    has_access = await user_service.check_user_access(telegram_id)
    
    assert has_access is True


@pytest.mark.asyncio
async def test_check_user_access_blocked_user(user_service, populated_database):
    user = populated_database["user"]
    
    await user_service.block_user(user.telegram_id)
    has_access = await user_service.check_user_access(user.telegram_id)
    
    assert has_access is False


@pytest.mark.asyncio
async def test_block_user(user_service, populated_database):
    user = populated_database["user"]
    
    success = await user_service.block_user(user.telegram_id)
    
    assert success is True
    
    user_dto = await user_service.get_user(user.telegram_id)
    assert user_dto.is_blocked is True


@pytest.mark.asyncio
async def test_unblock_user(user_service, populated_database):
    user = populated_database["user"]
    
    await user_service.block_user(user.telegram_id)
    success = await user_service.unblock_user(user.telegram_id)
    
    assert success is True
    
    user_dto = await user_service.get_user(user.telegram_id)
    assert user_dto.is_blocked is False


@pytest.mark.asyncio
async def test_whitelist_user(user_service, populated_database):
    user = populated_database["user"]
    
    success = await user_service.whitelist_user(user.telegram_id)
    
    assert success is True
    
    user_dto = await user_service.get_user(user.telegram_id)
    assert user_dto.is_whitelisted is True


@pytest.mark.asyncio
async def test_get_user_statistics(user_service, populated_database):
    stats = await user_service.get_user_statistics()
    
    assert stats["total_users"] >= 1
    assert stats["blocked_users"] >= 0
    assert stats["whitelisted_users"] >= 0
    assert stats["active_users"] >= 0


@pytest.mark.asyncio
async def test_rate_limiting(user_service):
    telegram_id = 777777
    
    for i in range(35):
        has_access = await user_service.check_user_access(telegram_id)
        if i < 30:
            assert has_access is True
        else:
            assert has_access is False


@pytest.mark.asyncio
async def test_user_preferences_default(user_service, populated_database):
    user = populated_database["user"]
    
    prefs = await user_service.get_user_preferences(user.telegram_id)
    
    assert prefs.default_notification_interval == 5
    assert prefs.max_notifications_per_reminder == 10
    assert prefs.timezone == "UTC"


@pytest.mark.asyncio
async def test_update_user_preferences(user_service, populated_database):
    user = populated_database["user"]
    new_prefs = UserPreferencesDTO(
        default_notification_interval=10,
        max_notifications_per_reminder=15,
        timezone="Europe/Rome"
    )
    
    success = await user_service.update_user_preferences(user.telegram_id, new_prefs)
    
    assert success is True
    
    retrieved_prefs = await user_service.get_user_preferences(user.telegram_id)
    assert retrieved_prefs.default_notification_interval == 10
    assert retrieved_prefs.max_notifications_per_reminder == 15
    assert retrieved_prefs.timezone == "Europe/Rome"