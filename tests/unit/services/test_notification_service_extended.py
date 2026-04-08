from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytz
from reminder_bot.utils.transformers import entity_to_reminder_dto
from telegram.error import Forbidden, TelegramError


@pytest.mark.asyncio
async def test_send_reminder_notification_with_blocked_user(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)

    mock_bot.send_message.side_effect = Forbidden("Bot was blocked by the user")

    user_service_mock = AsyncMock()
    user_service_mock.block_user = AsyncMock(return_value=True)
    notification_service.user_service = user_service_mock

    result = await notification_service.send_reminder_notification(reminder_dto)

    assert result.success is False
    assert "blocked" in result.error
    user_service_mock.block_user.assert_called_once_with(reminder.user_id)


@pytest.mark.asyncio
async def test_send_reminder_notification_update_message_id_fails(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)

    mock_message = MagicMock()
    mock_message.message_id = 123
    mock_bot.send_message.return_value = mock_message

    with patch.object(
        notification_service.reminder_repo,
        "update_message_id",
        side_effect=Exception("DB error"),
    ):
        result = await notification_service.send_reminder_notification(reminder_dto)

        assert result.success is True
        assert result.message_id == 123


@pytest.mark.asyncio
async def test_handle_notification_response_no_data(notification_service, mock_bot):
    mock_query = MagicMock()
    mock_query.data = None
    mock_query.from_user.id = 12345
    mock_query.answer = AsyncMock()

    await notification_service.handle_notification_response(mock_query, None)

    mock_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_notification_response_exception(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]

    mock_query = MagicMock()
    mock_query.data = f"confirm_{reminder.id}"
    mock_query.from_user.id = reminder.user_id
    mock_query.answer = AsyncMock()

    mock_reminder_service = AsyncMock()
    mock_reminder_service.get_reminder_by_id = AsyncMock(
        side_effect=Exception("DB error")
    )

    await notification_service.handle_notification_response(
        mock_query, mock_reminder_service
    )

    mock_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_handle_confirmation_no_user_service(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)

    mock_query = MagicMock()
    mock_query.from_user.id = reminder.user_id
    mock_query.edit_message_text = AsyncMock()

    notification_service.user_service = None

    mock_reminder_service = AsyncMock()
    mock_reminder_service.confirm_reminder = AsyncMock(return_value=True)

    await notification_service._handle_confirmation(
        mock_query, reminder_dto, mock_reminder_service
    )

    mock_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_handle_confirmation_edit_fails(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)

    mock_query = MagicMock()
    mock_query.from_user.id = reminder.user_id
    mock_query.edit_message_text = AsyncMock(
        side_effect=TelegramError("Message not found")
    )

    user_service_mock = AsyncMock()
    user_service_mock.get_user_timezone = AsyncMock(return_value=pytz.UTC)
    notification_service.user_service = user_service_mock

    mock_reminder_service = AsyncMock()
    mock_reminder_service.confirm_reminder = AsyncMock(return_value=True)

    await notification_service._handle_confirmation(
        mock_query, reminder_dto, mock_reminder_service
    )


@pytest.mark.asyncio
async def test_handle_confirmation_failure(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)

    mock_query = MagicMock()
    mock_query.from_user.id = reminder.user_id
    mock_query.answer = AsyncMock()

    mock_reminder_service = AsyncMock()
    mock_reminder_service.confirm_reminder = AsyncMock(return_value=False)

    await notification_service._handle_confirmation(
        mock_query, reminder_dto, mock_reminder_service
    )

    mock_query.answer.assert_called_once_with(
        "Failed to confirm reminder.", show_alert=True
    )


@pytest.mark.asyncio
async def test_handle_snooze_edit_fails(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)

    mock_query = MagicMock()
    mock_query.from_user.id = reminder.user_id
    mock_query.edit_message_text = AsyncMock(
        side_effect=TelegramError("Message not found")
    )

    mock_reminder_service = AsyncMock()
    mock_reminder_service.snooze_reminder = AsyncMock(return_value=True)

    await notification_service._handle_snooze(
        mock_query, reminder_dto, mock_reminder_service
    )


@pytest.mark.asyncio
async def test_handle_snooze_failure(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)

    mock_query = MagicMock()
    mock_query.from_user.id = reminder.user_id
    mock_query.answer = AsyncMock()

    mock_reminder_service = AsyncMock()
    mock_reminder_service.snooze_reminder = AsyncMock(return_value=False)

    await notification_service._handle_snooze(
        mock_query, reminder_dto, mock_reminder_service
    )

    mock_query.answer.assert_called_once_with(
        "Failed to snooze reminder.", show_alert=True
    )


@pytest.mark.asyncio
async def test_build_notification_text_max_notifications(
    notification_service, populated_database
):
    reminder = populated_database["reminder"]
    reminder.notification_count = 10
    reminder.max_notifications = 10
    reminder_dto = entity_to_reminder_dto(reminder)

    text = notification_service._build_notification_text(reminder_dto)

    assert "Attempt 11/10" in text
    assert "🚨" in text


@pytest.mark.asyncio
async def test_build_notification_text_one_time(
    notification_service, populated_database
):
    reminder = populated_database["reminder"]
    reminder.interval_days = 0
    reminder_dto = entity_to_reminder_dto(reminder)

    text = notification_service._build_notification_text(reminder_dto)

    assert "Repeats" not in text


@pytest.mark.asyncio
async def test_build_notification_text_interval_days(
    notification_service, populated_database
):
    reminder = populated_database["reminder"]
    reminder.interval_days = 3
    reminder_dto = entity_to_reminder_dto(reminder)

    text = notification_service._build_notification_text(reminder_dto)

    assert "Repeats every 3 day(s)" in text


@pytest.mark.asyncio
async def test_send_escalation_warning_exception(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)

    mock_bot.send_message.side_effect = TelegramError("Network error")

    success = await notification_service.send_escalation_warning(reminder_dto)

    assert success is False


@pytest.mark.asyncio
async def test_calculate_next_notification_interval_base_cases(notification_service):
    base_interval = 5

    assert (
        notification_service.calculate_next_notification_interval(0, base_interval) == 5
    )
    assert (
        notification_service.calculate_next_notification_interval(1, base_interval) == 5
    )
    assert (
        notification_service.calculate_next_notification_interval(2, base_interval)
        == 10
    )
    assert (
        notification_service.calculate_next_notification_interval(3, base_interval)
        == 15
    )
    assert (
        notification_service.calculate_next_notification_interval(4, base_interval)
        == 25
    )
    assert (
        notification_service.calculate_next_notification_interval(5, base_interval)
        == 30
    )


@pytest.mark.asyncio
async def test_send_reminder_notification_generic_exception(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)

    mock_bot.send_message.side_effect = Exception("Unexpected error")

    from reminder_bot.utils.exceptions import TelegramAPIException

    with pytest.raises(TelegramAPIException):
        await notification_service.send_reminder_notification(reminder_dto)


@pytest.mark.asyncio
async def test_send_reminder_notification_blocked_user_auto_block_fails(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)

    mock_bot.send_message.side_effect = Forbidden("Bot was blocked by the user")

    user_service_mock = AsyncMock()
    user_service_mock.block_user = AsyncMock(side_effect=Exception("DB error"))
    user_service_mock.get_user_timezone = AsyncMock(return_value=pytz.UTC)
    notification_service.user_service = user_service_mock

    result = await notification_service.send_reminder_notification(reminder_dto)

    assert result.success is False
    assert "blocked" in result.error
