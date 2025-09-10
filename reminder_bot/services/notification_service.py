import asyncio
from datetime import datetime, timedelta
from typing import Optional
import pytz
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram import CallbackQuery
from ..repositories.reminder_repository import ReminderRepository
from ..models.dtos import ReminderDTO, NotificationResult
from ..models.entities import ReminderStatus
from ..utils.logging import get_logger
from ..utils.exceptions import TelegramAPIException

logger = get_logger()


class NotificationService:
    def __init__(self, bot: Bot, reminder_repo: ReminderRepository):
        self.bot = bot
        self.reminder_repo = reminder_repo

    async def send_reminder_notification(self, reminder: ReminderDTO) -> NotificationResult:
        try:
            if reminder.last_message_id:
                try:
                    await self.bot.delete_message(
                        chat_id=reminder.chat_id,
                        message_id=reminder.last_message_id
                    )
                except TelegramError as e:
                    logger.warning(
                        "failed_to_delete_previous_message",
                        reminder_id=reminder.id,
                        message_id=reminder.last_message_id,
                        error=str(e)
                    )

            keyboard = [
                [
                    InlineKeyboardButton("✅ Completed", callback_data=f"confirm_{reminder.id}"),
                    InlineKeyboardButton("⏰ Snooze 5min", callback_data=f"snooze_{reminder.id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            notification_text = self._build_notification_text(reminder)
            
            message = await self.bot.send_message(
                chat_id=reminder.chat_id,
                text=notification_text,
                reply_markup=reply_markup,
                parse_mode='HTML'
            )

            try:
                await self.reminder_repo.update_message_id(reminder.id, message.message_id)
            except Exception as e:
                logger.warning("failed_to_update_message_id", reminder_id=reminder.id, error=str(e))
            
            logger.info(
                "notification_sent",
                reminder_id=reminder.id,
                chat_id=reminder.chat_id,
                message_id=message.message_id,
                notification_count=reminder.notification_count + 1
            )

            return NotificationResult(
                message_id=message.message_id,
                sent_at=datetime.now(pytz.UTC).replace(tzinfo=None),
                success=True
            )

        except TelegramError as e:
            logger.error(
                "telegram_notification_failed",
                reminder_id=reminder.id,
                chat_id=reminder.chat_id,
                error=str(e)
            )
            return NotificationResult(
                message_id=0,
                sent_at=datetime.now(pytz.UTC).replace(tzinfo=None),
                success=False,
                error=str(e)
            )
        except Exception as e:
            logger.error(
                "notification_failed",
                reminder_id=reminder.id,
                error=str(e)
            )
            raise TelegramAPIException(f"Failed to send notification: {e}")

    async def handle_notification_response(self, callback_query: CallbackQuery, reminder_service, job_scheduler=None) -> None:
        try:
            await callback_query.answer()
            
            if not callback_query.data:
                return

            action, reminder_id_str = callback_query.data.split("_", 1)
            reminder_id = int(reminder_id_str)
            user_id = callback_query.from_user.id

            reminder = await reminder_service.get_reminder_by_id(reminder_id)
            if not reminder or reminder.user_id != user_id:
                await callback_query.answer("Reminder not found or access denied.", show_alert=True)
                return

            if action == "confirm":
                await self._handle_confirmation(callback_query, reminder, reminder_service, job_scheduler)
            elif action == "snooze":
                await self._handle_snooze(callback_query, reminder, reminder_service)

        except Exception as e:
            logger.error(
                "callback_handling_failed",
                callback_data=callback_query.data,
                user_id=callback_query.from_user.id,
                error=str(e)
            )
            try:
                await callback_query.answer("An error occurred. Please try again.", show_alert=True)
            except TelegramError:
                pass

    async def _handle_confirmation(self, callback_query: CallbackQuery, reminder: ReminderDTO, reminder_service, job_scheduler=None) -> None:
        success = await reminder_service.confirm_reminder(reminder.id, callback_query.from_user.id, job_scheduler)
        
        if success:
            from ..config import settings
            tz = pytz.timezone(settings.timezone)
            now_local = datetime.now(tz)
            completion_text = f"✅ <b>Completed:</b> {reminder.text}\n⏰ {now_local.strftime('%H:%M')}"
            
            try:
                await callback_query.edit_message_text(
                    text=completion_text,
                    parse_mode='HTML'
                )
                logger.info(
                    "reminder_confirmed",
                    reminder_id=reminder.id,
                    user_id=callback_query.from_user.id
                )
            except TelegramError as e:
                logger.error("failed_to_edit_confirmation_message", error=str(e))
        else:
            await callback_query.answer("Failed to confirm reminder.", show_alert=True)

    async def _handle_snooze(self, callback_query: CallbackQuery, reminder: ReminderDTO, reminder_service) -> None:
        snooze_minutes = 5
        success = await reminder_service.snooze_reminder(reminder.id, snooze_minutes)
        
        if success:
            snooze_text = f"⏰ <b>Snoozed for {snooze_minutes} minutes</b>\n\n{reminder.text}"
            
            try:
                await callback_query.edit_message_text(
                    text=snooze_text,
                    parse_mode='HTML'
                )
                logger.info(
                    "reminder_snoozed",
                    reminder_id=reminder.id,
                    user_id=callback_query.from_user.id,
                    snooze_minutes=snooze_minutes
                )
            except TelegramError as e:
                logger.error("failed_to_edit_snooze_message", error=str(e))
        else:
            await callback_query.answer("Failed to snooze reminder.", show_alert=True)

    def _build_notification_text(self, reminder: ReminderDTO) -> str:
        urgency_indicators = {
            0: "🔔",
            1: "🔔",
            2: "⚠️",
            3: "⚠️",
            4: "🚨",
        }
        
        urgency_level = min(reminder.notification_count, 4)
        indicator = urgency_indicators.get(urgency_level, "🚨")
        
        text = f"{indicator} <b>Reminder:</b> {reminder.text}\n"
        
        if reminder.notification_count > 0:
            text += f"📊 Attempt {reminder.notification_count + 1}/{reminder.max_notifications}"
        
        if reminder.interval_days > 1:
            text += f"\n🔄 Repeats every {reminder.interval_days} day(s)"
        elif reminder.interval_days == 1:
            text += f"\n🔄 Daily reminder"
        
        return text

    async def send_escalation_warning(self, reminder: ReminderDTO) -> bool:
        try:
            warning_text = (
                f"⚠️ <b>Final Warning</b>\n\n"
                f"Reminder: {reminder.text}\n\n"
                f"This reminder has reached the maximum number of attempts "
                f"({reminder.max_notifications}) and will be suspended.\n\n"
                f"You can reactivate it later from your reminder list."
            )
            
            await self.bot.send_message(
                chat_id=reminder.chat_id,
                text=warning_text,
                parse_mode='HTML'
            )
            
            logger.info(
                "escalation_warning_sent",
                reminder_id=reminder.id,
                chat_id=reminder.chat_id
            )
            
            return True
            
        except TelegramError as e:
            logger.error(
                "escalation_warning_failed",
                reminder_id=reminder.id,
                error=str(e)
            )
            return False

    def calculate_next_notification_interval(self, current_count: int, base_interval: int) -> int:
        escalation_multipliers = [1, 1, 2, 3, 5, 6]
        
        multiplier_index = min(current_count, len(escalation_multipliers) - 1)
        multiplier = escalation_multipliers[multiplier_index]
        
        return min(base_interval * multiplier, 30)