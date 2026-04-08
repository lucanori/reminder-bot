from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from reminder_bot.handlers.command_handlers import (
    SET_INTERVAL,
    SET_TEXT,
    SET_TIME,
    CommandHandlers,
)
from telegram import Chat, Message, Update, User
from telegram.ext import ContextTypes, ConversationHandler


def create_mock_update(text=None, user_id=12345, username="testuser"):
    mock_user = MagicMock(spec=User)
    mock_user.id = user_id
    mock_user.username = username
    mock_user.first_name = "Test"
    
    mock_chat = MagicMock(spec=Chat)
    mock_chat.id = 12345
    
    mock_message = MagicMock(spec=Message)
    mock_message.chat = mock_chat
    mock_message.text = text
    
    mock_update = MagicMock(spec=Update)
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
async def test_start_command(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update()
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    await handlers.start_command(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_help_command(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update()
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    await handlers.help_command(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_start(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update()
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    result = await handlers.set_reminder_start(mock_update, mock_context)
    
    assert result == SET_TEXT
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_text(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(text="Take medicine")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    result = await handlers.set_reminder_text(mock_update, mock_context)
    
    assert result == SET_TIME
    assert mock_context.user_data["reminder_text"] == "Take medicine"
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_text_empty(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(text="")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    result = await handlers.set_reminder_text(mock_update, mock_context)
    
    assert result == SET_TEXT
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_text_cancel(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(text="❌ Cancel")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    result = await handlers.set_reminder_text(mock_update, mock_context)
    
    assert result == ConversationHandler.END
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_time(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(text="14:30")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    result = await handlers.set_reminder_time(mock_update, mock_context)
    
    assert result == SET_INTERVAL
    assert mock_context.user_data["reminder_time"] == "14:30"
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_time_invalid(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(text="invalid_time")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    result = await handlers.set_reminder_time(mock_update, mock_context)
    
    assert result == SET_TIME
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_interval_one_time(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(text="0 (One-time)")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    mock_context.user_data["reminder_text"] = "Test reminder"
    mock_context.user_data["reminder_time"] = "09:00"
    
    with patch.object(job_scheduler, 'schedule_reminder', new_callable=AsyncMock) as mock_schedule:
        result = await handlers.set_reminder_interval(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        mock_schedule.assert_called_once()
        mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_interval_daily(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(text="1 (Daily)")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    mock_context.user_data["reminder_text"] = "Test reminder"
    mock_context.user_data["reminder_time"] = "09:00"
    
    with patch.object(job_scheduler, 'schedule_reminder', new_callable=AsyncMock) as mock_schedule:
        result = await handlers.set_reminder_interval(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        mock_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_interval_custom_number(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(text="5")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    mock_context.user_data["reminder_text"] = "Test reminder"
    mock_context.user_data["reminder_time"] = "09:00"
    
    with patch.object(job_scheduler, 'schedule_reminder', new_callable=AsyncMock) as mock_schedule:
        result = await handlers.set_reminder_interval(mock_update, mock_context)
        
        assert result == ConversationHandler.END
        mock_schedule.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_interval_custom_option(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(text="Custom")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    result = await handlers.set_reminder_interval(mock_update, mock_context)
    
    assert result == SET_INTERVAL
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_set_reminder_interval_invalid(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(text="invalid")
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    result = await handlers.set_reminder_interval(mock_update, mock_context)
    
    assert result == SET_INTERVAL
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_view_reminders(
    mock_bot, reminder_repository, user_repository, populated_database
):
    from reminder_bot.services.notification_service import NotificationService
    from reminder_bot.services.reminder_service import ReminderService
    from reminder_bot.services.user_service import UserService
    from reminder_bot.utils.scheduler import JobScheduler
    
    user_service = UserService(user_repository)
    reminder_service = ReminderService(reminder_repository)
    notification_service = NotificationService(mock_bot, reminder_repository, user_service)
    job_scheduler = JobScheduler(notification_service, reminder_repository)
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update()
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    await handlers.view_reminders(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_view_reminders_empty(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update(user_id=999999)
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    await handlers.view_reminders(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_delete_reminder_start(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update()
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    
    await handlers.delete_reminder_start(mock_update, mock_context)
    
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cancel_conversation(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    mock_update = create_mock_update()
    mock_update.message.reply_text = AsyncMock()
    
    mock_context = create_mock_context()
    mock_context.user_data["test_key"] = "test_value"
    
    result = await handlers.cancel_conversation(mock_update, mock_context)
    
    assert result == ConversationHandler.END
    assert len(mock_context.user_data) == 0
    mock_update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_format_interval_text(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    assert handlers._format_interval_text(0) == "One-time"
    assert handlers._format_interval_text(1) == "Daily"
    assert handlers._format_interval_text(7) == "Weekly"
    assert handlers._format_interval_text(30) == "Monthly"
    assert handlers._format_interval_text(5) == "Every 5 days"


@pytest.mark.asyncio
async def test_get_main_menu_keyboard(
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
    
    handlers = CommandHandlers(reminder_service, user_service, job_scheduler)
    
    result = handlers._get_main_menu_keyboard()
    
    assert result is not None
