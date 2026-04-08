from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from freezegun import freeze_time
from reminder_bot.models.dtos import UserPreferencesDTO
from reminder_bot.utils.exceptions import DatabaseException


@pytest.mark.asyncio
async def test_user_service_set_user_timezone(user_service, populated_database):
    user = populated_database["user"]

    success = await user_service.set_user_timezone(user.telegram_id, "Europe/Paris")

    assert success is True

    prefs = await user_service.get_user_preferences(user.telegram_id)
    assert prefs.timezone == "Europe/Paris"


@pytest.mark.asyncio
async def test_user_service_set_user_timezone_invalid(user_service, populated_database):
    user = populated_database["user"]

    success = await user_service.set_user_timezone(user.telegram_id, "Invalid/Timezone")

    assert success is False


@pytest.mark.asyncio
async def test_user_service_validate_timezone(user_service):
    assert await user_service.validate_timezone("UTC") is True
    assert await user_service.validate_timezone("Europe/London") is True
    assert await user_service.validate_timezone("America/New_York") is True
    assert await user_service.validate_timezone("Invalid/Timezone") is False


@pytest.mark.asyncio
async def test_user_service_get_user_timezone_with_invalid_preference(
    user_service, populated_database
):
    user = populated_database["user"]

    prefs = UserPreferencesDTO(timezone="Invalid/Timezone")
    await user_service.update_user_preferences(user.telegram_id, prefs)

    tz = await user_service.get_user_timezone(user.telegram_id)

    assert str(tz) == "UTC"


@pytest.mark.asyncio
async def test_user_service_get_user_timezone_exception(
    user_service, populated_database
):
    user = populated_database["user"]

    with patch.object(
        user_service, "get_user_preferences", side_effect=Exception("DB error")
    ):
        tz = await user_service.get_user_timezone(user.telegram_id)
        assert str(tz) == "UTC"


@pytest.mark.asyncio
async def test_user_service_remove_from_whitelist(user_service, populated_database):
    user = populated_database["user"]

    await user_service.whitelist_user(user.telegram_id)

    success = await user_service.remove_from_whitelist(user.telegram_id)

    assert success is True

    user_dto = await user_service.get_user(user.telegram_id)
    assert user_dto.is_whitelisted is False


@pytest.mark.asyncio
async def test_user_service_check_user_access_whitelist_mode(
    user_service, populated_database
):
    user = populated_database["user"]

    with patch("reminder_bot.services.user_service.settings") as mock_settings:
        mock_settings.bot_mode = "whitelist"

        has_access = await user_service.check_user_access(user.telegram_id)

        assert has_access is False


@pytest.mark.asyncio
async def test_user_service_check_user_access_whitelist_allowed(
    user_service, populated_database
):
    user = populated_database["user"]

    await user_service.whitelist_user(user.telegram_id)

    with patch("reminder_bot.services.user_service.settings") as mock_settings:
        mock_settings.bot_mode = "whitelist"

        has_access = await user_service.check_user_access(user.telegram_id)

        assert has_access is True


@pytest.mark.asyncio
async def test_user_service_check_user_access_blocklist_blocked(
    user_service, populated_database
):
    user = populated_database["user"]

    await user_service.block_user(user.telegram_id)

    with patch("reminder_bot.services.user_service.settings") as mock_settings:
        mock_settings.bot_mode = "blocklist"

        has_access = await user_service.check_user_access(user.telegram_id)

        assert has_access is False


@pytest.mark.asyncio
async def test_user_service_check_user_access_blocklist_allowed(
    user_service, populated_database
):
    user = populated_database["user"]

    with patch("reminder_bot.services.user_service.settings") as mock_settings:
        mock_settings.bot_mode = "blocklist"

        has_access = await user_service.check_user_access(user.telegram_id)

        assert has_access is True


@pytest.mark.asyncio
async def test_user_service_check_user_access_new_user_whitelist_mode(user_service):
    with patch("reminder_bot.services.user_service.settings") as mock_settings:
        mock_settings.bot_mode = "whitelist"

        has_access = await user_service.check_user_access(999999)

        assert has_access is False


@pytest.mark.asyncio
async def test_user_service_check_user_access_rate_limit_cache_cleanup(user_service):
    user_service._rate_limit_max_requests = 2

    user_id = 777777

    assert await user_service.check_user_access(user_id) is True
    assert await user_service.check_user_access(user_id) is True
    assert await user_service.check_user_access(user_id) is False


@pytest.mark.asyncio
async def test_user_service_cleanup_rate_limit_cache(user_service):
    with freeze_time("2024-01-01 12:00:00"):
        user_id = 888888
        old_time = datetime.utcnow() - timedelta(seconds=200)
        user_service._rate_limit_cache[user_id] = [old_time]

        user_service._cleanup_rate_limit_cache()

        assert user_id not in user_service._rate_limit_cache


@pytest.mark.asyncio
async def test_user_service_register_or_update_user_without_repo(user_service):
    user_service.user_repo = None

    user_dto = await user_service.register_or_update_user(999999)

    assert user_dto.telegram_id == 999999


@pytest.mark.asyncio
async def test_user_service_check_user_access_without_repo(user_service):
    user_service.user_repo = None

    has_access = await user_service.check_user_access(999999)

    assert has_access is True


@pytest.mark.asyncio
async def test_user_service_get_user_preferences_without_repo(
    user_service, populated_database
):
    user = populated_database["user"]

    user_service.user_repo = None

    prefs = await user_service.get_user_preferences(user.telegram_id)

    assert prefs.timezone == "UTC"


@pytest.mark.asyncio
async def test_user_service_get_all_users_exception(user_service):
    with patch.object(
        user_service.user_repo, "get_all", side_effect=Exception("DB error")
    ):
        with pytest.raises(DatabaseException):
            await user_service.get_all_users()


@pytest.mark.asyncio
async def test_user_service_block_user_exception(user_service, populated_database):
    user = populated_database["user"]

    with patch.object(
        user_service.user_repo,
        "update_blocked_status",
        side_effect=Exception("DB error"),
    ):
        with pytest.raises(DatabaseException):
            await user_service.block_user(user.telegram_id)


@pytest.mark.asyncio
async def test_user_service_unblock_user_exception(user_service, populated_database):
    user = populated_database["user"]

    with patch.object(
        user_service.user_repo,
        "update_blocked_status",
        side_effect=Exception("DB error"),
    ):
        with pytest.raises(DatabaseException):
            await user_service.unblock_user(user.telegram_id)


@pytest.mark.asyncio
async def test_user_service_whitelist_user_exception(user_service, populated_database):
    user = populated_database["user"]

    with patch.object(
        user_service.user_repo,
        "update_whitelisted_status",
        side_effect=Exception("DB error"),
    ):
        with pytest.raises(DatabaseException):
            await user_service.whitelist_user(user.telegram_id)


@pytest.mark.asyncio
async def test_user_service_remove_from_whitelist_exception(
    user_service, populated_database
):
    user = populated_database["user"]

    with patch.object(
        user_service.user_repo,
        "update_whitelisted_status",
        side_effect=Exception("DB error"),
    ):
        with pytest.raises(DatabaseException):
            await user_service.remove_from_whitelist(user.telegram_id)


@pytest.mark.asyncio
async def test_user_service_get_user_exception(user_service):
    with patch.object(
        user_service.user_repo, "get_by_id", side_effect=Exception("DB error")
    ):
        with pytest.raises(DatabaseException):
            await user_service.get_user(12345)


@pytest.mark.asyncio
async def test_user_service_update_user_preferences_exception(
    user_service, populated_database
):
    user = populated_database["user"]

    with patch.object(
        user_service.user_repo, "get_by_id", side_effect=Exception("DB error")
    ):
        with pytest.raises(DatabaseException):
            await user_service.update_user_preferences(
                user.telegram_id, UserPreferencesDTO()
            )


@pytest.mark.asyncio
async def test_user_service_set_user_timezone_exception(
    user_service, populated_database
):
    user = populated_database["user"]

    with patch.object(
        user_service, "update_user_preferences", side_effect=Exception("DB error")
    ):
        with pytest.raises(DatabaseException):
            await user_service.set_user_timezone(user.telegram_id, "Europe/Paris")


@pytest.mark.asyncio
async def test_user_service_get_user_statistics_exception(user_service):
    with patch.object(
        user_service.user_repo, "get_all", side_effect=Exception("DB error")
    ):
        with pytest.raises(DatabaseException):
            await user_service.get_user_statistics()


@pytest.mark.asyncio
async def test_user_service_get_user_preferences_with_no_user(user_service):
    prefs = await user_service.get_user_preferences(999999)

    assert prefs.timezone == "UTC"
    assert prefs.default_notification_interval == 5


@pytest.mark.asyncio
async def test_user_service_get_user_preferences_exception_returns_default(
    user_service,
):
    with patch.object(
        user_service.user_repo, "get_by_id", side_effect=Exception("DB error")
    ):
        prefs = await user_service.get_user_preferences(12345)
        assert prefs.timezone == "UTC"


@pytest.mark.asyncio
async def test_user_service_update_user_preferences_user_not_found(user_service):
    success = await user_service.update_user_preferences(999999, UserPreferencesDTO())

    assert success is False


@pytest.mark.asyncio
async def test_user_service_check_user_access_exception_returns_false(user_service):
    with patch.object(
        user_service, "_check_rate_limit", side_effect=Exception("Unexpected error")
    ):
        has_access = await user_service.check_user_access(12345)
        assert has_access is False
