import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram.error import TelegramError
from reminder_bot.models.entities import ReminderStatus
from reminder_bot.utils.transformers import entity_to_reminder_dto


@pytest.mark.asyncio
async def test_send_reminder_notification_success(notification_service, populated_database, mock_bot):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)
    
    mock_message = MagicMock()
    mock_message.message_id = 123
    mock_bot.send_message.return_value = mock_message
    
    result = await notification_service.send_reminder_notification(reminder_dto)
    
    assert result.success is True
    assert result.message_id == 123
    assert mock_bot.send_message.called


@pytest.mark.asyncio
async def test_send_reminder_notification_with_previous_message_deletion(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder.last_message_id = 456
    reminder_dto = entity_to_reminder_dto(reminder)
    
    mock_message = MagicMock()
    mock_message.message_id = 789
    mock_bot.send_message.return_value = mock_message
    
    result = await notification_service.send_reminder_notification(reminder_dto)
    
    assert result.success is True
    assert result.message_id == 789
    mock_bot.delete_message.assert_called_once_with(
        chat_id=reminder.chat_id,
        message_id=456
    )


@pytest.mark.asyncio
async def test_send_reminder_notification_delete_fails(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder.last_message_id = 456
    reminder_dto = entity_to_reminder_dto(reminder)
    
    mock_bot.delete_message.side_effect = TelegramError("Message not found")
    mock_message = MagicMock()
    mock_message.message_id = 789
    mock_bot.send_message.return_value = mock_message
    
    result = await notification_service.send_reminder_notification(reminder_dto)
    
    assert result.success is True
    assert result.message_id == 789


@pytest.mark.asyncio
async def test_send_reminder_notification_send_fails(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)
    
    mock_bot.send_message.side_effect = TelegramError("Bot was blocked")
    
    result = await notification_service.send_reminder_notification(reminder_dto)
    
    assert result.success is False
    assert result.error == "Bot was blocked"


@pytest.mark.asyncio
async def test_build_notification_text_first_attempt(notification_service, populated_database):
    reminder = populated_database["reminder"]
    reminder.notification_count = 0
    reminder_dto = entity_to_reminder_dto(reminder)
    
    text = notification_service._build_notification_text(reminder_dto)
    
    assert "🔔" in text
    assert reminder.text in text
    assert "Daily reminder" in text


@pytest.mark.asyncio
async def test_build_notification_text_escalated(notification_service, populated_database):
    reminder = populated_database["reminder"]
    reminder.notification_count = 3
    reminder_dto = entity_to_reminder_dto(reminder)
    
    text = notification_service._build_notification_text(reminder_dto)
    
    assert "⚠️" in text or "🚨" in text
    assert reminder.text in text
    assert "Attempt 4/10" in text


@pytest.mark.asyncio
async def test_build_notification_text_weekly_reminder(notification_service, populated_database):
    reminder = populated_database["reminder"]
    reminder.interval_days = 7
    reminder_dto = entity_to_reminder_dto(reminder)
    
    text = notification_service._build_notification_text(reminder_dto)
    
    assert "Repeats every 7 day(s)" in text


@pytest.mark.asyncio
async def test_send_escalation_warning_success(notification_service, populated_database, mock_bot):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)
    
    success = await notification_service.send_escalation_warning(reminder_dto)
    
    assert success is True
    mock_bot.send_message.assert_called_once()
    
    call_args = mock_bot.send_message.call_args
    assert "Final Warning" in call_args[1]['text']
    assert reminder.text in call_args[1]['text']


@pytest.mark.asyncio
async def test_send_escalation_warning_fails(notification_service, populated_database, mock_bot):
    reminder = populated_database["reminder"]
    reminder_dto = entity_to_reminder_dto(reminder)
    
    mock_bot.send_message.side_effect = TelegramError("Chat not found")
    
    success = await notification_service.send_escalation_warning(reminder_dto)
    
    assert success is False


@pytest.mark.asyncio
async def test_calculate_next_notification_interval_escalating(notification_service):
    base_interval = 5
    
    interval_0 = notification_service.calculate_next_notification_interval(0, base_interval)
    interval_1 = notification_service.calculate_next_notification_interval(1, base_interval)  
    interval_3 = notification_service.calculate_next_notification_interval(3, base_interval)
    interval_5 = notification_service.calculate_next_notification_interval(5, base_interval)
    
    assert interval_0 == 5
    assert interval_1 == 5  
    assert interval_3 == 15
    assert interval_5 == 30


@pytest.mark.asyncio
async def test_calculate_next_notification_interval_max_cap(notification_service):
    base_interval = 10
    
    interval = notification_service.calculate_next_notification_interval(10, base_interval)
    
    assert interval == 30


@pytest.mark.asyncio
async def test_handle_notification_response_confirm(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    
    mock_query = MagicMock()
    mock_query.data = f"confirm_{reminder.id}"
    mock_query.from_user.id = reminder.user_id
    mock_query.answer = AsyncMock()
    mock_query.edit_message_text = AsyncMock()
    
    mock_reminder_service = AsyncMock()
    mock_reminder_service.get_reminder_by_id.return_value = entity_to_reminder_dto(reminder)
    mock_reminder_service.confirm_reminder.return_value = True
    
    await notification_service.handle_notification_response(mock_query, mock_reminder_service)
    
    mock_query.answer.assert_called_once()
    mock_reminder_service.confirm_reminder.assert_called_once_with(reminder.id, reminder.user_id)
    mock_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_handle_notification_response_snooze(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    
    mock_query = MagicMock()
    mock_query.data = f"snooze_{reminder.id}"
    mock_query.from_user.id = reminder.user_id
    mock_query.answer = AsyncMock()
    mock_query.edit_message_text = AsyncMock()
    
    mock_reminder_service = AsyncMock()
    mock_reminder_service.get_reminder_by_id.return_value = entity_to_reminder_dto(reminder)
    mock_reminder_service.snooze_reminder.return_value = True
    
    await notification_service.handle_notification_response(mock_query, mock_reminder_service)
    
    mock_query.answer.assert_called_once()
    mock_reminder_service.snooze_reminder.assert_called_once_with(reminder.id, 5)
    mock_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_handle_notification_response_unauthorized(
    notification_service, populated_database, mock_bot
):
    reminder = populated_database["reminder"]
    
    mock_query = MagicMock()
    mock_query.data = f"confirm_{reminder.id}"
    mock_query.from_user.id = 999999
    mock_query.answer = AsyncMock()
    
    mock_reminder_service = AsyncMock()
    mock_reminder_service.get_reminder_by_id.return_value = entity_to_reminder_dto(reminder)
    
    await notification_service.handle_notification_response(mock_query, mock_reminder_service)
    
    mock_query.answer.assert_called_once_with("Reminder not found or access denied.", show_alert=True)