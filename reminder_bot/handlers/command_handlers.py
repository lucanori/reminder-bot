import re
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler
from ..models.dtos import ReminderCreateDTO
from ..utils.logging import get_logger

logger = get_logger()

SET_TEXT, SET_TIME, SET_INTERVAL = range(3)

class CommandHandlers:
    def __init__(self, reminder_service, user_service, job_scheduler):
        self.reminder_service = reminder_service
        self.user_service = user_service
        self.job_scheduler = job_scheduler

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user = update.effective_user
        chat = update.effective_chat
        
        logger.info(
            "user_started_bot",
            user_id=user.id,
            username=user.username,
            chat_id=chat.id
        )

        is_allowed = await self.user_service.check_user_access(user.id)
        if not is_allowed:
            await update.message.reply_text(
                "🚫 Sorry, you don't have permission to use this bot."
            )
            return

        await self.user_service.register_or_update_user(user.id)

        welcome_message = (
            f"👋 Welcome to the Reminder Bot, {user.first_name}!\n\n"
            "🔔 I'll help you never forget your important tasks.\n\n"
            "Choose an option below to get started:"
        )

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        keyboard = [
            [InlineKeyboardButton("🔔 Create New Reminder", callback_data="cmd_set")],
            [InlineKeyboardButton("📋 View My Reminders", callback_data="cmd_view")],
            [InlineKeyboardButton("🗑 Delete Reminder", callback_data="cmd_delete")],
            [InlineKeyboardButton("❓ Help & Examples", callback_data="cmd_help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            welcome_message,
            parse_mode='HTML',
            reply_markup=reply_markup
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        help_text = (
            "<b>📋 How to use Reminder Bot</b>\n\n"
            
            "<b>🔔 Creating Reminders:</b>\n"
            "Use /set and follow the prompts to create reminders.\n\n"
            
            "<b>⏰ Time Format:</b>\n"
            "• Use HH:MM format (24-hour)\n"
            "• Example: 14:30 for 2:30 PM\n\n"
            
            "<b>🔄 Reminder Types:</b>\n"
            "• <b>One-time:</b> Set interval to 0 days\n"
            "• <b>Daily:</b> Set interval to 1 day\n"
            "• <b>Weekly:</b> Set interval to 7 days\n"
            "• <b>Custom:</b> Any number of days\n\n"
            
            "<b>📱 Notification Features:</b>\n"
            "• Smart escalating intervals (5min, 10min, 15min...)\n"
            "• Click ✅ to confirm completion\n"
            "• Click ⏰ to snooze for 5 minutes\n"
            "• Automatic suspension after max attempts\n\n"
            
            "<b>📝 Example Reminders:</b>\n"
            "• Take morning vitamins at 08:00 (daily)\n"
            "• Water plants at 19:00 (every 3 days)\n"
            "• Check emails at 09:00 (weekdays only)\n\n"
            
            "<b>🎛 Commands:</b>\n"
            "/set - Create new reminder\n"
            "/view - List your reminders\n"
            "/delete - Remove a reminder\n"
            "/help - Show this help"
        )

        await update.message.reply_text(help_text, parse_mode='HTML')

    async def set_reminder_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        user_id = update.effective_user.id
        
        is_allowed = await self.user_service.check_user_access(user_id)
        if not is_allowed:
            await update.message.reply_text("🚫 Access denied.")
            return ConversationHandler.END

        cancel_keyboard = ReplyKeyboardMarkup([["❌ Cancel"]], resize_keyboard=True)
        
        await update.message.reply_text(
            "🔔 <b>Create New Reminder</b>\n\n"
            "📝 Please enter the reminder text:\n\n"
            "<i>Example: Take morning vitamins</i>",
            parse_mode='HTML',
            reply_markup=cancel_keyboard
        )
        
        return SET_TEXT

    async def set_reminder_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        text = update.message.text.strip()
        
        if text == "❌ Cancel":
            await self.cancel_conversation(update, context)
            return ConversationHandler.END
        
        if not text or len(text) > 500:
            await update.message.reply_text(
                "❌ Please enter a valid reminder text (1-500 characters)."
            )
            return SET_TEXT
        
        context.user_data['reminder_text'] = text
        
        await update.message.reply_text(
            f"✅ Reminder text: <b>{text}</b>\n\n"
            "⏰ Now enter the time (HH:MM format):\n\n"
            "<i>Examples: 08:30, 14:45, 20:00</i>",
            parse_mode='HTML'
        )
        
        return SET_TIME

    async def set_reminder_time(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        time_text = update.message.text.strip()
        
        if time_text == "❌ Cancel":
            await self.cancel_conversation(update, context)
            return ConversationHandler.END
        
        if not re.match(r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$', time_text):
            await update.message.reply_text(
                "❌ Invalid time format! Please use HH:MM (24-hour format).\n\n"
                "<i>Examples: 08:30, 14:45, 20:00</i>"
            )
            return SET_TIME
        
        context.user_data['reminder_time'] = time_text
        
        interval_keyboard = ReplyKeyboardMarkup([
            ["0 (One-time)", "1 (Daily)"],
            ["3 (Every 3 days)", "7 (Weekly)"],
            ["30 (Monthly)", "Custom"],
            ["❌ Cancel"]
        ], resize_keyboard=True)
        
        await update.message.reply_text(
            f"⏰ Time set: <b>{time_text}</b>\n\n"
            "🔄 Select repeat interval (in days):",
            parse_mode='HTML',
            reply_markup=interval_keyboard
        )
        
        return SET_INTERVAL

    async def set_reminder_interval(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        interval_text = update.message.text.strip()
        
        if interval_text == "❌ Cancel":
            await self.cancel_conversation(update, context)
            return ConversationHandler.END
        
        if interval_text == "Custom":
            await update.message.reply_text(
                "🔢 Enter custom interval in days (0-365):\n\n"
                "<i>Use 0 for one-time reminders</i>",
                parse_mode='HTML'
            )
            return SET_INTERVAL
        
        try:
            if interval_text.startswith("0"):
                interval_days = 0
            elif interval_text.startswith("1"):
                interval_days = 1
            elif interval_text.startswith("3"):
                interval_days = 3
            elif interval_text.startswith("7"):
                interval_days = 7
            elif interval_text.startswith("30"):
                interval_days = 30
            else:
                interval_days = int(interval_text)
                if not (0 <= interval_days <= 365):
                    raise ValueError()
                    
        except ValueError:
            await update.message.reply_text(
                "❌ Please enter a valid number of days (0-365).\n\n"
                "<i>Use 0 for one-time reminders</i>",
                parse_mode='HTML'
            )
            return SET_INTERVAL
        
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        try:
            reminder_data = ReminderCreateDTO(
                user_id=user_id,
                chat_id=chat_id,
                text=context.user_data['reminder_text'],
                schedule_time=context.user_data['reminder_time'],
                interval_days=interval_days
            )
            
            reminder = await self.reminder_service.create_reminder(reminder_data)
            await self.job_scheduler.schedule_reminder(reminder)
            
            interval_text = self._format_interval_text(interval_days)
            
            await update.message.reply_text(
                f"✅ <b>Reminder Created Successfully!</b>\n\n"
                f"📝 <b>Text:</b> {reminder.text}\n"
                f"⏰ <b>Time:</b> {reminder.schedule_time}\n"
                f"🔄 <b>Repeat:</b> {interval_text}\n\n"
                f"🔔 Next notification: <b>{reminder.next_notification.strftime('%Y-%m-%d %H:%M')}</b>",
                parse_mode='HTML',
                reply_markup=self._get_main_menu_keyboard()
            )
            
            logger.info(
                "reminder_created_via_conversation",
                user_id=user_id,
                reminder_id=reminder.id,
                interval_days=interval_days
            )
            
        except Exception as e:
            logger.error("reminder_creation_failed", error=str(e), user_id=user_id)
            await update.message.reply_text(
                "❌ Failed to create reminder. Please try again later.",
                reply_markup=self._get_main_menu_keyboard()
            )
        
        context.user_data.clear()
        return ConversationHandler.END

    async def view_reminders(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        
        is_allowed = await self.user_service.check_user_access(user_id)
        if not is_allowed:
            await update.message.reply_text("🚫 Access denied.")
            return
        
        try:
            reminders = await self.reminder_service.get_user_reminders(user_id)
            
            if not reminders:
                await update.message.reply_text(
                    "📭 <b>No Active Reminders</b>\n\n"
                    "Use /set to create your first reminder!",
                    parse_mode='HTML'
                )
                return
            
            active_reminders = [r for r in reminders if r.status.value == "active"]
            
            if not active_reminders:
                await update.message.reply_text(
                    "📭 <b>No Active Reminders</b>\n\n"
                    "All your reminders are completed or suspended.\n"
                    "Use /set to create a new one!",
                    parse_mode='HTML'
                )
                return
            
            message_lines = ["📋 <b>Your Active Reminders:</b>\n"]
            
            for reminder in active_reminders[:10]:
                interval_text = self._format_interval_text(reminder.interval_days)
                next_time = reminder.next_notification.strftime('%m-%d %H:%M UTC')
                
                status_emoji = "🔔" if reminder.notification_count == 0 else f"⚠️({reminder.notification_count})"
                
                message_lines.append(
                    f"{status_emoji} <b>{reminder.text}</b> (ID: {reminder.id})\n"
                    f"   ⏰ {reminder.schedule_time} • 🔄 {interval_text}\n"
                    f"   📅 Next: {next_time}\n"
                )
            
            if len(active_reminders) > 10:
                message_lines.append(f"\n<i>... and {len(active_reminders) - 10} more</i>")
            
            message_lines.append(f"\n💡 Use /delete [ID] to remove a reminder")
            
            await update.message.reply_text(
                "\n".join(message_lines),
                parse_mode='HTML'
            )
            
        except Exception as e:
            logger.error("view_reminders_failed", error=str(e), user_id=user_id)
            await update.message.reply_text(
                "❌ Failed to fetch reminders. Please try again later."
            )

    async def delete_reminder_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id
        
        is_allowed = await self.user_service.check_user_access(user_id)
        if not is_allowed:
            await update.message.reply_text("🚫 Access denied.")
            return
        
        await update.message.reply_text(
            "🗑 <b>Delete Reminder</b>\n\n"
            "Please send the reminder ID you want to delete.\n"
            "Use /view to see your reminders and their IDs.",
            parse_mode='HTML'
        )

    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        await update.message.reply_text(
            "❌ <b>Operation Cancelled</b>\n\n"
            "Use /set to create a new reminder anytime!",
            parse_mode='HTML',
            reply_markup=self._get_main_menu_keyboard()
        )
        context.user_data.clear()
        return ConversationHandler.END

    def _format_interval_text(self, days: int) -> str:
        if days == 0:
            return "One-time"
        elif days == 1:
            return "Daily"
        elif days == 7:
            return "Weekly"
        elif days == 30:
            return "Monthly"
        else:
            return f"Every {days} days"

    def _get_main_menu_keyboard(self):
        from telegram import ReplyKeyboardRemove
        return ReplyKeyboardRemove()