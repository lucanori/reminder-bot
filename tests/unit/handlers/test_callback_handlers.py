from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reminder_bot.handlers.callback_handlers import CallbackHandlers
from telegram import CallbackQuery, Chat, Message, Update, User
from telegram.ext import ContextTypes


def create_mock_update(callback_data=None, text=None, user_id=12345):
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.first_name = "Test"
    
    mock_chat = MagicMock(spec=Chat)
    mock_chat.id = 12345
    
    mock_message = MagicMock(spec=Message)
    mock_message.chat = mock_chat
    mock_message.message_id = 100
    mock_message.text = text
    
    if callback_data:
        mock_query = MagicMock(spec=CallbackQuery)
        mock_query.data = callback_data
        mock_query.from_user = mock_user
        mock_query.message = mock_message
        mock_query.answer = AsyncMock()
        mock_query.edit_message_text = AsyncMock()
        
        mock_update = MagicMock(spec=Update)
        mock_update.callback_query = mock_query
        mock_update.effective_user = mock_user
        mock_update.effective_chat = mock_chat
        mock_update.message = None
    else:
        mock_update = MagicMock(spec=Update)
        mock_update.callback_query = None
        mock_update.effective_user = mock_user
        mock_update.effective_chat = mock_chat
        mock_update.message = mock_message
    
    return mock_update


def create_mock_context():
    mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    mock_context.user_data = {}
    mock_context.bot = MagicMock()
    return mock_context


@pytest.mark.asyncio
async def test_callback_handler_reminder_callback(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="confirm_1")
    mock_context = create_mock_context()
    
    with patch.object(
        notification_service, 'handle_notification_response', new_callable=AsyncMock
    ) as mock_handle:
        await handlers.handle_reminder_callback(mock_update, mock_context)
        mock_handle.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_menu_callback_set(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="cmd_set")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_menu_callback_view(
    mock_bot, reminder_repository, user_repository, populated_database
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="cmd_view")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_menu_callback_view_no_reminders(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="cmd_view", user_id=999999)
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_menu_callback_delete(
    mock_bot, reminder_repository, user_repository, populated_database
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="cmd_delete")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_menu_callback_help(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="cmd_help")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_menu_callback_timezone(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="cmd_timezone")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_timezone_selection(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    from reminder_bot.utils.scheduler import JobScheduler
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    job_scheduler = JobScheduler(notification_service, reminder_repository)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service, job_scheduler
    )
    
    mock_update = create_mock_update(callback_data="tz_Europe/London")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_template_selection(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="template_medication")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_template_custom(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="template_custom")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_custom_time_selection(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="customtime_08:00")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_custom_interval_selection(
    mock_bot, reminder_repository, user_repository, populated_database
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="custominterval_1")
    mock_context = create_mock_context()
    mock_context.user_data["custom_text"] = "Test reminder"
    mock_context.user_data["custom_time"] = "09:00"
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_weekday_selection(
    mock_bot, reminder_repository, user_repository, populated_database
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="weekday_1")
    mock_context = create_mock_context()
    mock_context.user_data["custom_text"] = "Test reminder"
    mock_context.user_data["custom_time"] = "09:00"
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_enter_cron(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="enter_cron")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()
    assert mock_context.user_data["waiting_for"] == "cron_expression"


@pytest.mark.asyncio
async def test_callback_handler_back_to_menu(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data="back_to_menu")
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_callback_handler_delete_reminder(
    mock_bot, reminder_repository, user_repository, populated_database
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user = populated_database["user"]
    reminder = populated_database["reminder"]
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(callback_data=f"delete_{reminder.id}", user_id=user.telegram_id)
    mock_context = create_mock_context()
    
    await handlers.handle_menu_callback(mock_update, mock_context)
    
    mock_update.callback_query.answer.assert_called_once()
    mock_update.callback_query.edit_message_text.assert_called_once()


@pytest.mark.asyncio
async def test_custom_text_input_handler(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(text="My custom reminder")
    mock_context = create_mock_context()
    mock_context.user_data["waiting_for"] = "custom_text"
    mock_update.message.reply_text = AsyncMock()
    
    await handlers.handle_custom_text_input(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()
    assert mock_context.user_data["custom_text"] == "My custom reminder"


@pytest.mark.asyncio
async def test_custom_time_input_handler(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(text="14:30")
    mock_context = create_mock_context()
    mock_context.user_data["waiting_for"] = "custom_time"
    mock_context.user_data["custom_text"] = "Test reminder"
    mock_update.message.reply_text = AsyncMock()
    
    await handlers.handle_custom_text_input(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()
    assert mock_context.user_data["custom_time"] == "14:30"


@pytest.mark.asyncio
async def test_custom_interval_input_handler(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(text="3")
    mock_context = create_mock_context()
    mock_context.user_data["waiting_for"] = "custom_interval"
    mock_context.user_data["custom_text"] = "Test reminder"
    mock_context.user_data["custom_time"] = "09:00"
    mock_update.message.reply_text = AsyncMock()
    
    await handlers.handle_custom_text_input(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_timezone_manual_input_handler(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(text="Europe/Paris")
    mock_context = create_mock_context()
    mock_context.user_data["waiting_for"] = "timezone_manual"
    mock_update.message.reply_text = AsyncMock()
    
    await handlers.handle_custom_text_input(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cron_expression_input_handler(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(text="0 9 * * 1")
    mock_context = create_mock_context()
    mock_context.user_data["waiting_for"] = "cron_expression"
    mock_context.user_data["custom_text"] = "Monday meeting"
    mock_context.user_data["custom_time"] = "09:00"
    mock_update.message.reply_text = AsyncMock()
    
    await handlers.handle_custom_text_input(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cron_expression_input_handler_invalid(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(text="invalid_cron")
    mock_context = create_mock_context()
    mock_context.user_data["waiting_for"] = "cron_expression"
    mock_update.message.reply_text = AsyncMock()
    
    await handlers.handle_custom_text_input(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_delete_reminder_text_handler(
    mock_bot, reminder_repository, user_repository, populated_database
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user = populated_database["user"]
    reminder = populated_database["reminder"]
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(text=str(reminder.id), user_id=user.telegram_id)
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    await handlers.handle_delete_reminder_text(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_delete_reminder_text_handler_invalid_id(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    mock_update = create_mock_update(text="not_a_number")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    await handlers.handle_delete_reminder_text(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_format_interval_text_cron(mock_bot, reminder_repository, user_repository):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    result = handlers._format_interval_text(1, None, "0 9 * * *")
    assert result == "Cron: 0 9 * * *"


@pytest.mark.asyncio
async def test_format_interval_text_weekday(mock_bot, reminder_repository, user_repository):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    result = handlers._format_interval_text(7, 1, None)
    assert "Weekly on Tuesday" == result


@pytest.mark.asyncio
async def test_format_interval_text_various_days(
    mock_bot, reminder_repository, user_repository
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    
    handlers = CallbackHandlers(
        notification_service, reminder_service, user_service
    )
    
    assert handlers._format_interval_text(0, None, None) == "One-time"
    assert handlers._format_interval_text(1, None, None) == "Daily"
    assert handlers._format_interval_text(7, None, None) == "Weekly"
    assert handlers._format_interval_text(30, None, None) == "Monthly"
    assert handlers._format_interval_text(5, None, None) == "Every 5 days"
