from telegram import Update
from telegram.ext import ContextTypes

from ..utils.logging import get_logger

logger = get_logger()


class CallbackHandlers:
    def __init__(
        self, notification_service, reminder_service, user_service, job_scheduler=None
    ):
        self.notification_service = notification_service
        self.reminder_service = reminder_service
        self.user_service = user_service
        self.job_scheduler = job_scheduler

    async def handle_reminder_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        user_id = query.from_user.id

        logger.info("callback_received", user_id=user_id, callback_data=query.data)

        is_allowed = await self.user_service.check_user_access(user_id)
        if not is_allowed:
            await query.answer("🚫 Access denied.", show_alert=True)
            return

        await self.notification_service.handle_notification_response(
            query, self.reminder_service, self.job_scheduler
        )

    async def handle_menu_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        user_id = query.from_user.id

        logger.info("menu_callback_received", user_id=user_id, callback_data=query.data)

        is_allowed = await self.user_service.check_user_access(user_id)
        if not is_allowed:
            await query.answer("🚫 Access denied.", show_alert=True)
            return

        await query.answer()

        if query.data == "cmd_set":
            await self._handle_set_command(query, context)
        elif query.data == "cmd_view":
            await self._handle_view_command(query, context)
        elif query.data == "cmd_delete":
            await self._handle_delete_command(query, context)
        elif query.data == "cmd_help":
            await self._handle_help_command(query, context)
        elif query.data == "cmd_timezone":
            await self._handle_timezone_command(query, context)
        elif query.data.startswith("template_"):
            await self._handle_template_selection(query, context)
        elif query.data == "custom_time_manual":
            await self._handle_custom_time_manual(query, context)
        elif query.data == "custom_interval_manual":
            await self._handle_custom_interval_manual(query, context)
        elif query.data.startswith("custom_"):
            await self._handle_custom_option(query, context)
        elif query.data.startswith("customtime_"):
            await self._handle_custom_time_selection(query, context)
        elif query.data.startswith("custominterval_"):
            await self._handle_custom_interval_selection(query, context)
        elif query.data.startswith("weekday_"):
            await self._handle_weekday_selection(query, context)
        elif query.data == "enter_cron":
            await self._handle_enter_cron(query, context)
        elif query.data == "use_set_command":
            await self._handle_use_set_command(query, context)
        elif query.data.startswith("delete_"):
            await self._handle_delete_reminder(query, context)
        elif query.data == "back_to_menu":
            await self._show_main_menu(query, context)
        elif query.data.startswith("tz_"):
            await self._handle_timezone_selection(query, context)
        elif query.data == "tz_manual":
            await self._handle_timezone_manual(query, context)

    async def _handle_set_command(self, query, context):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [
            [
                InlineKeyboardButton(
                    "💊 Take medication", callback_data="template_medication"
                )
            ],
            [InlineKeyboardButton("🥗 Meal reminder", callback_data="template_meal")],
            [InlineKeyboardButton("💧 Drink water", callback_data="template_water")],
            [InlineKeyboardButton("🏃 Exercise", callback_data="template_exercise")],
            [
                InlineKeyboardButton(
                    "✏️ Custom reminder", callback_data="template_custom"
                )
            ],
            [InlineKeyboardButton("🔙 Back to menu", callback_data="back_to_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "🔔 <b>Create New Reminder</b>\n\n"
            "Choose a template or create a custom reminder:\n\n"
            "💡 <i>Templates will guide you through the setup process</i>",
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    async def _handle_view_command(self, query, context):
        user_id = query.from_user.id

        try:
            reminders = await self.reminder_service.get_user_reminders(user_id)

            if not reminders:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🏠 Back to Menu", callback_data="back_to_menu"
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    "📭 <b>No Active Reminders</b>\n\n"
                    "Use the menu below to create your first reminder!",
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                return

            active_reminders = [r for r in reminders if r.status.value == "active"]

            if not active_reminders:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🏠 Back to Menu", callback_data="back_to_menu"
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    "📭 <b>No Active Reminders</b>\n\n"
                    "All your reminders are completed or suspended.\n"
                    "Use the menu below to create a new one!",
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                return

            message_lines = ["📋 <b>Your Active Reminders:</b>\n"]

            for reminder in active_reminders[:10]:
                interval_text = self._format_interval_text(
                    reminder.interval_days, reminder.weekday, reminder.cron_expression
                )
                next_time = reminder.next_notification.strftime("%m-%d %H:%M UTC")

                status_emoji = (
                    "🔔"
                    if reminder.notification_count == 0
                    else f"⚠️({reminder.notification_count})"
                )

                message_lines.append(
                    f"{status_emoji} <b>{reminder.text}</b>\n"
                    f"   ⏰ {reminder.schedule_time} • 🔄 {interval_text}\n"
                    f"   📅 Next: {next_time}\n"
                )

            if len(active_reminders) > 10:
                message_lines.append(
                    f"\n<i>... and {len(active_reminders) - 10} more</i>"
                )

            message_lines.append("\n💡 Use the delete option to remove a reminder")

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "\n".join(message_lines), parse_mode="HTML", reply_markup=reply_markup
            )

        except Exception as e:
            logger.error("view_reminders_failed", error=str(e), user_id=user_id)
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ Failed to fetch reminders. Please try again later.",
                reply_markup=reply_markup,
            )

    async def _handle_delete_command(self, query, context):
        user_id = query.from_user.id

        try:
            reminders = await self.reminder_service.get_user_reminders(user_id)
            active_reminders = [r for r in reminders if r.status.value == "active"]

            if not active_reminders:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🏠 Back to Menu", callback_data="back_to_menu"
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    "📭 <b>No Active Reminders to Delete</b>\n\n"
                    "You don't have any active reminders to delete.",
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                return

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = []

            for reminder in active_reminders[:10]:
                interval_text = self._format_interval_text(
                    reminder.interval_days, reminder.weekday, reminder.cron_expression
                )
                button_text = (
                    f"🗑 {reminder.text[:30]}{'...' if len(reminder.text) > 30 else ''}"
                )
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            button_text, callback_data=f"delete_{reminder.id}"
                        )
                    ]
                )

            keyboard.append(
                [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
            )
            reply_markup = InlineKeyboardMarkup(keyboard)

            message_lines = ["🗑 <b>Delete Reminder</b>\n\n"]
            message_lines.append("Select a reminder to delete:\n")

            for reminder in active_reminders[:10]:
                interval_text = self._format_interval_text(
                    reminder.interval_days, reminder.weekday, reminder.cron_expression
                )
                msg = (
                    f"• <b>{reminder.text}</b> "
                    f"(⏰ {reminder.schedule_time}, 🔄 {interval_text})"
                )
                message_lines.append(msg)

            await query.edit_message_text(
                "\n".join(message_lines), parse_mode="HTML", reply_markup=reply_markup
            )

        except Exception as e:
            logger.error("delete_command_failed", error=str(e), user_id=user_id)
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ Failed to load reminders. Please try again later.",
                reply_markup=reply_markup,
            )

    async def _handle_help_command(self, query, context):
        help_text = (
            "<b>📋 How to use Reminder Bot</b>\n\n"
            "<b>🔔 Creating Reminders:</b>\n"
            "Use the Create button and follow the prompts.\n\n"
            "<b>⏰ Time Format:</b>\n"
            "• Use HH:MM format (24-hour)\n"
            "• Example: 14:30 for 2:30 PM\n\n"
            "<b>🌍 Timezone:</b>\n"
            "• Set your local timezone for accurate reminders\n"
            "• Reminders are scheduled in your local time\n"
            "• DST changes are handled automatically\n\n"
            "<b>🔄 Reminder Types:</b>\n"
            "• <b>One-time:</b> Set interval to 0 days\n"
            "• <b>Daily:</b> Set interval to 1 day\n"
            "• <b>Weekly:</b> Set interval to 7 days\n"
            "• <b>Custom:</b> Any number of days\n\n"
            "<b>📱 Notification Features:</b>\n"
            "• Smart escalating intervals (5min, 10min, 15min...)\n"
            "• Click ✅ to confirm completion\n"
            "• Click ⏰ to snooze for 5 minutes\n"
            "• Reminders stay active until confirmed\n\n"
            "<b>📝 Example Reminders:</b>\n"
            "• Take morning vitamins at 08:00 (daily)\n"
            "• Water plants at 19:00 (every 3 days)\n"
            "• Check emails at 09:00 (weekdays only)"
        )

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [
            [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            help_text, parse_mode="HTML", reply_markup=reply_markup
        )

    async def _handle_timezone_command(self, query, context):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        user_id = query.from_user.id
        preferences = await self.user_service.get_user_preferences(user_id)
        current_tz = preferences.timezone

        common_timezones = [
            ("UTC", "UTC"),
            ("Europe/London", "London"),
            ("Europe/Paris", "Paris"),
            ("Europe/Rome", "Rome"),
            ("Europe/Berlin", "Berlin"),
            ("America/New_York", "New York"),
            ("America/Chicago", "Chicago"),
            ("America/Denver", "Denver"),
            ("America/Los_Angeles", "Los Angeles"),
            ("America/Toronto", "Toronto"),
            ("America/Sao_Paulo", "São Paulo"),
            ("Asia/Tokyo", "Tokyo"),
            ("Asia/Shanghai", "Shanghai"),
            ("Asia/Singapore", "Singapore"),
            ("Asia/Dubai", "Dubai"),
            ("Asia/Kolkata", "Mumbai"),
            ("Australia/Sydney", "Sydney"),
            ("Pacific/Auckland", "Auckland"),
        ]

        keyboard = []
        row = []
        for tz_value, tz_label in common_timezones:
            prefix = "✅ " if tz_value == current_tz else ""
            row.append(
                InlineKeyboardButton(
                    f"{prefix}{tz_label}", callback_data=f"tz_{tz_value}"
                )
            )
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append(
            [InlineKeyboardButton("✏️ Enter Custom Timezone", callback_data="tz_manual")]
        )
        keyboard.append(
            [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🌍 <b>Set Your Timezone</b>\n\n"
            f"Current timezone: <code>{current_tz}</code>\n\n"
            f"Select your timezone from the list below, or enter a custom one:\n\n"
            f"<i>Reminders will be scheduled in your local time.</i>",
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    async def _handle_timezone_selection(self, query, context):
        timezone_str = query.data.replace("tz_", "")
        user_id = query.from_user.id

        try:
            is_valid = await self.user_service.validate_timezone(timezone_str)
            if not is_valid:
                await query.answer(
                    "Invalid timezone. Please try again.", show_alert=True
                )
                return

            success = await self.user_service.set_user_timezone(user_id, timezone_str)
            if not success:
                await query.answer(
                    "Failed to set timezone. Please try again.", show_alert=True
                )
                return

            if self.job_scheduler:
                from pytz import timezone

                user_tz = timezone(timezone_str)
                await self.reminder_service.recompute_reminders_for_timezone_change(
                    user_id, user_tz, self.job_scheduler
                )

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🌍 Change Timezone", callback_data="cmd_timezone"
                    )
                ],
                [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"✅ <b>Timezone Updated!</b>\n\n"
                f"Your timezone is now set to: <code>{timezone_str}</code>\n\n"
                f"All your reminders have been updated to use this timezone.",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

            logger.info(
                "timezone_set_via_button", user_id=user_id, timezone=timezone_str
            )

        except Exception as e:
            logger.error("timezone_selection_failed", error=str(e), user_id=user_id)
            await query.answer("An error occurred. Please try again.", show_alert=True)

    async def _handle_timezone_manual(self, query, context):
        context.user_data["waiting_for"] = "timezone_manual"
        context.user_data["original_message_id"] = query.message.message_id

        await query.edit_message_text(
            "🌍 <b>Enter Custom Timezone</b>\n\n"
            "Please type your timezone in IANA format.\n\n"
            "<b>Examples:</b>\n"
            "• Europe/London\n"
            "• America/New_York\n"
            "• Asia/Tokyo\n"
            "• Australia/Sydney\n\n"
            "You can find your timezone at: https://timezonedb.com/time-zones",
            parse_mode="HTML",
        )

    async def _handle_template_selection(self, query, context):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        template = query.data.replace("template_", "")

        if template == "custom":
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [
                    InlineKeyboardButton(
                        "📝 Enter custom text", callback_data="custom_text"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⏰ Set custom time", callback_data="custom_time"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔄 Set custom interval", callback_data="custom_interval"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🚀 Use /set command", callback_data="use_set_command"
                    )
                ],
                [InlineKeyboardButton("🔙 Back", callback_data="cmd_set")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "✏️ <b>Custom Reminder</b>\n\n"
                "Choose how you want to create your custom reminder:\n\n"
                "• <b>Quick setup:</b> Use the buttons below for guided creation\n"
                "• <b>Full control:</b> Use /set command for complete customization",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return

        templates = {
            "medication": "Take medication",
            "meal": "Meal time",
            "water": "Drink water",
            "exercise": "Exercise time",
        }

        if template in templates:
            template_text = templates[template]
            context.user_data["custom_text"] = template_text

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            times = [
                "07:00",
                "08:00",
                "09:00",
                "12:00",
                "18:00",
                "19:00",
                "20:00",
                "21:00",
            ]
            keyboard = []

            for i in range(0, len(times), 3):
                row = []
                for j in range(3):
                    if i + j < len(times):
                        time = times[i + j]
                        row.append(
                            InlineKeyboardButton(
                                f"⏰ {time}", callback_data=f"customtime_{time}"
                            )
                        )
                keyboard.append(row)

            keyboard.append(
                [
                    InlineKeyboardButton(
                        "✏️ Enter Custom Time", callback_data="custom_time_manual"
                    )
                ]
            )
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="cmd_set")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"✅ <b>Text set:</b> {template_text}\n\n"
                "⏰ <b>Select Time</b>\n\n"
                "Choose a time for your reminder:",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

    async def _handle_custom_option(self, query, context):
        option = query.data.replace("custom_", "")

        if option == "text":
            context.user_data["waiting_for"] = "custom_text"
            context.user_data["original_message_id"] = query.message.message_id

            await query.edit_message_text(
                "📝 <b>Custom Reminder Text</b>\n\n"
                "Please type your custom reminder text in the chat.\n\n"
                "Example: <i>Call mom about weekend plans</i>\n\n"
                "💡 <i>Just type your message and I'll guide you through the rest!</i>",
                parse_mode="HTML",
            )
        elif option == "time":
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            times = [
                "07:00",
                "08:00",
                "09:00",
                "12:00",
                "18:00",
                "19:00",
                "20:00",
                "21:00",
            ]
            keyboard = []

            for i in range(0, len(times), 3):
                row = []
                for j in range(3):
                    if i + j < len(times):
                        time = times[i + j]
                        row.append(
                            InlineKeyboardButton(
                                f"⏰ {time}", callback_data=f"customtime_{time}"
                            )
                        )
                keyboard.append(row)

            keyboard.append(
                [
                    InlineKeyboardButton(
                        "✏️ Enter Custom Time", callback_data="custom_time_manual"
                    )
                ]
            )
            keyboard.append(
                [InlineKeyboardButton("🔙 Back", callback_data="template_custom")]
            )

            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "⏰ <b>Select Time</b>\n\n"
                "Choose a time for your reminder or enter a custom one:",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        elif option == "interval":
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔄 One-time only", callback_data="custominterval_0"
                    )
                ],
                [InlineKeyboardButton("📅 Daily", callback_data="custominterval_1")],
                [
                    InlineKeyboardButton(
                        "🗓 Every 2 days", callback_data="custominterval_2"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📆 Every 3 days", callback_data="custominterval_3"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🗓️ Weekly (pick day)", callback_data="custominterval_7"
                    )
                ],
                [InlineKeyboardButton("📅 Monthly", callback_data="custominterval_30")],
                [
                    InlineKeyboardButton(
                        "✏️ Custom interval", callback_data="custom_interval_manual"
                    )
                ],
                [InlineKeyboardButton("⚙️ Advanced (cron)", callback_data="enter_cron")],
                [InlineKeyboardButton("🔙 Back", callback_data="template_custom")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "🔄 <b>Select Interval</b>\n\nHow often should this reminder repeat?",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

    async def _handle_custom_time_selection(self, query, context):
        time = query.data.replace("customtime_", "")

        context.user_data["custom_time"] = time

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [
            [
                InlineKeyboardButton(
                    "🔄 One-time only", callback_data="custominterval_0"
                )
            ],
            [InlineKeyboardButton("📅 Daily", callback_data="custominterval_1")],
            [InlineKeyboardButton("🗓 Every 2 days", callback_data="custominterval_2")],
            [InlineKeyboardButton("📆 Every 3 days", callback_data="custominterval_3")],
            [
                InlineKeyboardButton(
                    "🗓️ Weekly (pick day)", callback_data="custominterval_7"
                )
            ],
            [InlineKeyboardButton("📅 Monthly", callback_data="custominterval_30")],
            [
                InlineKeyboardButton(
                    "✏️ Custom interval", callback_data="custom_interval_manual"
                )
            ],
            [InlineKeyboardButton("⚙️ Advanced (cron)", callback_data="enter_cron")],
            [InlineKeyboardButton("🔙 Back", callback_data="custom_time")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"⏰ <b>Time selected:</b> {time}\n\n"
            "🔄 <b>Select Interval</b>\n\n"
            "How often should this reminder repeat?",
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    async def _handle_custom_interval_selection(self, query, context):
        interval = int(query.data.replace("custominterval_", ""))

        if interval == 7:
            context.user_data["interval_days"] = 7
            await self._show_weekday_selection(query, context)
            return

        custom_text = context.user_data.get("custom_text", "Custom reminder")
        custom_time = context.user_data.get("custom_time", "09:00")

        try:
            from ..models.dtos import ReminderCreateDTO

            reminder_data = ReminderCreateDTO(
                user_id=query.from_user.id,
                chat_id=query.message.chat_id,
                text=custom_text,
                schedule_time=custom_time,
                interval_days=interval,
            )

            reminder = await self.reminder_service.create_reminder(reminder_data)

            if self.job_scheduler:
                await self.job_scheduler.schedule_reminder(reminder)

            interval_text = self._format_interval_text(interval)

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            next_notif = reminder.next_notification.strftime("%Y-%m-%d %H:%M")
            await query.edit_message_text(
                f"✅ <b>Custom Reminder Created!</b>\n\n"
                f"📝 <b>Text:</b> {reminder.text}\n"
                f"⏰ <b>Time:</b> {reminder.schedule_time}\n"
                f"🔄 <b>Repeat:</b> {interval_text}\n\n"
                f"🔔 Next notification: <b>{next_notif}</b>",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

            context.user_data.clear()

            logger.info(
                "custom_reminder_created",
                user_id=query.from_user.id,
                reminder_id=reminder.id,
                interval_days=interval,
            )

        except Exception as e:
            logger.error(
                "custom_reminder_creation_failed",
                error=str(e),
                user_id=query.from_user.id,
            )
            await query.edit_message_text(
                "❌ Failed to create custom reminder. Please try again later."
            )

    async def _show_weekday_selection(self, query, context):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        weekdays = [
            ("Monday", 0),
            ("Tuesday", 1),
            ("Wednesday", 2),
            ("Thursday", 3),
            ("Friday", 4),
            ("Saturday", 5),
            ("Sunday", 6),
        ]

        keyboard = []
        row = []
        for name, value in weekdays:
            row.append(InlineKeyboardButton(name, callback_data=f"weekday_{value}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

        keyboard.append(
            [
                InlineKeyboardButton(
                    "⚙️ Enter Cron Expression", callback_data="enter_cron"
                )
            ]
        )
        keyboard.append(
            [InlineKeyboardButton("🔙 Back", callback_data="custom_interval")]
        )

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "📅 <b>Select Weekday</b>\n\n"
            "Choose which day of the week for your weekly reminder:\n\n"
            "<i>Or use a custom cron expression for advanced scheduling</i>",
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

    async def _handle_weekday_selection(self, query, context):
        weekday = int(query.data.replace("weekday_", ""))

        custom_text = context.user_data.get("custom_text", "Custom reminder")
        custom_time = context.user_data.get("custom_time", "09:00")

        weekday_names = [
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        ]

        try:
            from ..models.dtos import ReminderCreateDTO

            reminder_data = ReminderCreateDTO(
                user_id=query.from_user.id,
                chat_id=query.message.chat_id,
                text=custom_text,
                schedule_time=custom_time,
                interval_days=7,
                weekday=weekday,
            )

            reminder = await self.reminder_service.create_reminder(reminder_data)

            if self.job_scheduler:
                await self.job_scheduler.schedule_reminder(reminder)

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            next_notif = reminder.next_notification.strftime("%Y-%m-%d %H:%M")
            await query.edit_message_text(
                f"✅ <b>Weekly Reminder Created!</b>\n\n"
                f"📝 <b>Text:</b> {reminder.text}\n"
                f"⏰ <b>Time:</b> {reminder.schedule_time}\n"
                f"🔄 <b>Repeat:</b> Weekly on {weekday_names[weekday]}\n\n"
                f"🔔 Next notification: <b>{next_notif}</b>",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

            context.user_data.clear()

            logger.info(
                "weekly_reminder_created",
                user_id=query.from_user.id,
                reminder_id=reminder.id,
                weekday=weekday,
            )

        except Exception as e:
            logger.error(
                "weekly_reminder_creation_failed",
                error=str(e),
                user_id=query.from_user.id,
            )
            await query.edit_message_text(
                "❌ Failed to create reminder. Please try again later."
            )

    async def _handle_enter_cron(self, query, context):
        context.user_data["waiting_for"] = "cron_expression"
        context.user_data["original_message_id"] = query.message.message_id

        await query.edit_message_text(
            "⚙️ <b>Enter Cron Expression</b>\n\n"
            "Please type a cron expression in the chat.\n\n"
            "<b>Format:</b> minute hour day month weekday\n"
            "<b>Examples:</b>\n"
            "• <code>0 9 * * 1</code> - Every Monday at 09:00\n"
            "• <code>0 8 * * 1-5</code> - Weekdays at 08:00\n"
            "• <code>0 0 1 * *</code> - First day of month at 00:00\n\n"
            "<i>Type your cron expression below:</i>",
            parse_mode="HTML",
        )

    async def _handle_custom_time_manual(self, query, context):
        context.user_data["waiting_for"] = "custom_time"
        context.user_data["original_message_id"] = query.message.message_id

        await query.edit_message_text(
            "⏰ <b>Enter Custom Time</b>\n\n"
            "Please type your desired time in HH:MM format (24-hour).\n\n"
            "<b>Examples:</b>\n"
            "• 06:30 (6:30 AM)\n"
            "• 14:45 (2:45 PM)\n"
            "• 23:15 (11:15 PM)\n\n"
            "💡 <i>Just type the time and I'll continue with the setup!</i>",
            parse_mode="HTML",
        )

    async def _handle_custom_interval_manual(self, query, context):
        context.user_data["waiting_for"] = "custom_interval"
        context.user_data["original_message_id"] = query.message.message_id

        await query.edit_message_text(
            "🔄 <b>Enter Custom Interval</b>\n\n"
            "Please type the number of days for your reminder interval.\n\n"
            "<b>Examples:</b>\n"
            "• 0 (one-time only)\n"
            "• 1 (daily)\n"
            "• 3 (every 3 days)\n"
            "• 14 (every 2 weeks)\n\n"
            "💡 <i>Enter any number from 0 to 365!</i>",
            parse_mode="HTML",
        )

    async def _handle_use_set_command(self, query, context):
        await query.edit_message_text(
            "🚀 <b>Full Custom Setup</b>\n\n"
            "To create a fully customized reminder with complete control over:\n"
            "• Custom reminder text\n"
            "• Any time (HH:MM format)\n"
            "• Any interval (0-365 days)\n"
            "• Notification settings\n\n"
            "Please use the command: <code>/set</code>\n\n"
            "This will start the interactive setup process!",
            parse_mode="HTML",
        )

    async def _show_main_menu(self, query, context):
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        keyboard = [
            [InlineKeyboardButton("🔔 Create New Reminder", callback_data="cmd_set")],
            [InlineKeyboardButton("📋 View My Reminders", callback_data="cmd_view")],
            [InlineKeyboardButton("🗑 Delete Reminder", callback_data="cmd_delete")],
            [InlineKeyboardButton("🌍 Set Timezone", callback_data="cmd_timezone")],
            [InlineKeyboardButton("❓ Help & Examples", callback_data="cmd_help")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        user_name = query.from_user.first_name
        welcome_message = (
            f"👋 Welcome back, {user_name}!\n\n"
            "🔔 I'll help you never forget your important tasks.\n\n"
            "Choose an option below to get started:"
        )

        await query.edit_message_text(
            welcome_message, parse_mode="HTML", reply_markup=reply_markup
        )

    async def _handle_delete_reminder(self, query, context):
        reminder_id = int(query.data.replace("delete_", ""))
        user_id = query.from_user.id

        try:
            success = await self.reminder_service.delete_reminder(reminder_id, user_id)

            if success:
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🏠 Back to Menu", callback_data="back_to_menu"
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    f"✅ <b>Reminder Deleted Successfully!</b>\n\n"
                    f"Reminder ID {reminder_id} has been deleted.",
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )

                logger.info(
                    "reminder_deleted_via_button",
                    reminder_id=reminder_id,
                    user_id=user_id,
                )
            else:
                msg = (
                    f"❌ Failed to delete reminder {reminder_id}. "
                    "Not found or no permission."
                )
                await query.edit_message_text(msg)

        except Exception as e:
            logger.error(
                "delete_reminder_button_failed",
                error=str(e),
                reminder_id=reminder_id,
                user_id=user_id,
            )
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ Failed to delete reminder. Please try again later.",
                reply_markup=reply_markup,
            )

    def _format_interval_text(
        self, days: int, weekday: int | None = None, cron_expression: str | None = None
    ) -> str:
        if cron_expression:
            return f"Cron: {cron_expression}"
        if weekday is not None:
            weekday_names = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            return f"Weekly on {weekday_names[weekday]}"
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

    async def handle_custom_text_input(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        waiting_for = context.user_data.get("waiting_for")
        text = update.message.text.strip()

        if waiting_for == "custom_text":
            custom_text = text

            if len(custom_text) > 500:
                await update.message.reply_text(
                    "❌ Reminder text is too long. Please keep it under 500 characters."
                )
                return

            context.user_data["custom_text"] = custom_text
            context.user_data["waiting_for"] = None

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            times = [
                "07:00",
                "08:00",
                "09:00",
                "12:00",
                "18:00",
                "19:00",
                "20:00",
                "21:00",
            ]
            keyboard = []

            for i in range(0, len(times), 3):
                row = []
                for j in range(3):
                    if i + j < len(times):
                        time = times[i + j]
                        row.append(
                            InlineKeyboardButton(
                                f"⏰ {time}", callback_data=f"customtime_{time}"
                            )
                        )
                keyboard.append(row)

            keyboard.append(
                [
                    InlineKeyboardButton(
                        "✏️ Enter Custom Time", callback_data="custom_time_manual"
                    )
                ]
            )
            keyboard.append(
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")]
            )
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ <b>Text set:</b> {custom_text}\n\n"
                "⏰ <b>Select Time</b>\n\n"
                "Choose a time for your reminder:",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

        elif waiting_for == "custom_time":
            import re

            time_text = update.message.text.strip()

            if not re.match(r"^([01]?[0-9]|2[0-3]):[0-5][0-9]$", time_text):
                await update.message.reply_text(
                    "❌ Invalid time format! Please use HH:MM (24-hour format).\n\n"
                    "<i>Examples: 08:30, 14:45, 20:00</i>",
                    parse_mode="HTML",
                )
                return

            context.user_data["custom_time"] = time_text
            context.user_data["waiting_for"] = None

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🔄 One-time only", callback_data="custominterval_0"
                    )
                ],
                [InlineKeyboardButton("📅 Daily", callback_data="custominterval_1")],
                [
                    InlineKeyboardButton(
                        "🗓 Every 2 days", callback_data="custominterval_2"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "📆 Every 3 days", callback_data="custominterval_3"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🗓️ Weekly (pick day)", callback_data="custominterval_7"
                    )
                ],
                [InlineKeyboardButton("📅 Monthly", callback_data="custominterval_30")],
                [
                    InlineKeyboardButton(
                        "✏️ Custom interval", callback_data="custom_interval_manual"
                    )
                ],
                [InlineKeyboardButton("⚙️ Advanced (cron)", callback_data="enter_cron")],
                [InlineKeyboardButton("🔙 Back to Menu", callback_data="back_to_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"⏰ <b>Time set:</b> {time_text}\n\n"
                "🔄 <b>Select Interval</b>\n\n"
                "How often should this reminder repeat?",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

        elif waiting_for == "custom_interval":
            try:
                interval = int(update.message.text.strip())
                if not (0 <= interval <= 365):
                    raise ValueError()
            except ValueError:
                await update.message.reply_text(
                    "❌ Please enter a valid number of days (0-365).\n\n"
                    "<i>Examples: 0 (one-time), 1 (daily), 7 (weekly)</i>",
                    parse_mode="HTML",
                )
                return

            custom_text = context.user_data.get("custom_text", "Custom reminder")
            custom_time = context.user_data.get("custom_time", "09:00")

            try:
                from ..models.dtos import ReminderCreateDTO

                reminder_data = ReminderCreateDTO(
                    user_id=update.effective_user.id,
                    chat_id=update.effective_chat.id,
                    text=custom_text,
                    schedule_time=custom_time,
                    interval_days=interval,
                )

                reminder = await self.reminder_service.create_reminder(reminder_data)

                if self.job_scheduler:
                    await self.job_scheduler.schedule_reminder(reminder)

                interval_text = self._format_interval_text(interval)

                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🏠 Back to Menu", callback_data="back_to_menu"
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                next_notif = reminder.next_notification.strftime("%Y-%m-%d %H:%M")
                await update.message.reply_text(
                    f"✅ <b>Custom Reminder Created!</b>\n\n"
                    f"📝 <b>Text:</b> {reminder.text}\n"
                    f"⏰ <b>Time:</b> {reminder.schedule_time}\n"
                    f"🔄 <b>Repeat:</b> {interval_text}\n\n"
                    f"🔔 Next notification: <b>{next_notif}</b>",
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )

                context.user_data.clear()

                logger.info(
                    "fully_custom_reminder_created",
                    user_id=update.effective_user.id,
                    reminder_id=reminder.id,
                    interval_days=interval,
                )

            except Exception as e:
                logger.error(
                    "fully_custom_reminder_creation_failed",
                    error=str(e),
                    user_id=update.effective_user.id,
                )
                await update.message.reply_text(
                    "❌ Failed to create custom reminder. Please try again later."
                )

            return

        elif waiting_for == "timezone_manual":
            timezone_str = text
            user_id = update.effective_user.id

            is_valid = await self.user_service.validate_timezone(timezone_str)
            if not is_valid:
                msg = (
                    "❌ Invalid timezone. Use format like 'Europe/London'.\n\n"
                    "Find yours at: timezonedb.com/time-zones"
                )
                await update.message.reply_text(msg)
                return

            success = await self.user_service.set_user_timezone(user_id, timezone_str)
            if not success:
                await update.message.reply_text(
                    "❌ Failed to set timezone. Please try again later."
                )
                return

            if self.job_scheduler:
                from pytz import timezone

                user_tz = timezone(timezone_str)
                await self.reminder_service.recompute_reminders_for_timezone_change(
                    user_id, user_tz, self.job_scheduler
                )

            from telegram import InlineKeyboardButton, InlineKeyboardMarkup

            keyboard = [
                [
                    InlineKeyboardButton(
                        "🌍 Change Timezone", callback_data="cmd_timezone"
                    )
                ],
                [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_menu")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"✅ <b>Timezone Updated!</b>\n\n"
                f"Your timezone is now set to: <code>{timezone_str}</code>\n\n"
                f"All your reminders have been updated to use this timezone.",
                parse_mode="HTML",
                reply_markup=reply_markup,
            )

            context.user_data.clear()

            logger.info("timezone_set_via_text", user_id=user_id, timezone=timezone_str)
            return

        elif waiting_for == "cron_expression":
            cron_expr = text

            try:
                from croniter import croniter

                if not croniter.is_valid(cron_expr):
                    cron_help = (
                        "❌ Invalid cron expression. "
                        "Format: <code>min hour day month weekday</code>\n\n"
                        "<b>Examples:</b>\n"
                        "• <code>0 9 * * 1</code> - Monday 09:00\n"
                        "• <code>0 8 * * 1-5</code> - Weekdays 08:00\n\n"
                        "Please try again:"
                    )
                    await update.message.reply_text(cron_help, parse_mode="HTML")
                    return
            except Exception:
                await update.message.reply_text(
                    "❌ Invalid cron expression. Please try again.",
                )
                return

            custom_text = context.user_data.get("custom_text", "Custom reminder")
            custom_time = context.user_data.get("custom_time", "09:00")

            try:
                from ..models.dtos import ReminderCreateDTO

                reminder_data = ReminderCreateDTO(
                    user_id=update.effective_user.id,
                    chat_id=update.effective_chat.id,
                    text=custom_text,
                    schedule_time=custom_time,
                    interval_days=0,
                    cron_expression=cron_expr,
                )

                reminder = await self.reminder_service.create_reminder(reminder_data)

                if self.job_scheduler:
                    await self.job_scheduler.schedule_reminder(reminder)

                from telegram import InlineKeyboardButton, InlineKeyboardMarkup

                keyboard = [
                    [
                        InlineKeyboardButton(
                            "🏠 Back to Menu", callback_data="back_to_menu"
                        )
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                next_notif = reminder.next_notification.strftime("%Y-%m-%d %H:%M")
                await update.message.reply_text(
                    f"✅ <b>Cron Reminder Created!</b>\n\n"
                    f"📝 <b>Text:</b> {reminder.text}\n"
                    f"⏰ <b>Schedule:</b> <code>{cron_expr}</code>\n\n"
                    f"🔔 Next notification: <b>{next_notif}</b>",
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )

                context.user_data.clear()

                logger.info(
                    "cron_reminder_created",
                    user_id=update.effective_user.id,
                    reminder_id=reminder.id,
                    cron_expression=cron_expr,
                )

            except Exception as e:
                logger.error(
                    "cron_reminder_creation_failed",
                    error=str(e),
                    user_id=update.effective_user.id,
                )
                await update.message.reply_text(
                    "❌ Failed to create reminder. Please try again later."
                )

            return

        if text.isdigit():
            await self.handle_delete_reminder_text(update, context)

    async def handle_delete_reminder_text(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user_id = update.effective_user.id
        text = update.message.text.strip()

        is_allowed = await self.user_service.check_user_access(user_id)
        if not is_allowed:
            await update.message.reply_text("🚫 Access denied.")
            return

        try:
            reminder_id = int(text)
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid reminder ID. Please enter a number.\n"
                "Use /view to see your reminders and their IDs."
            )
            return

        try:
            success = await self.reminder_service.delete_reminder(reminder_id, user_id)

            if success:
                await update.message.reply_text(
                    f"✅ <b>Reminder {reminder_id} deleted successfully!</b>",
                    parse_mode="HTML",
                )
                logger.info(
                    "reminder_deleted_via_text",
                    reminder_id=reminder_id,
                    user_id=user_id,
                )
            else:
                msg = f"❌ Reminder {reminder_id} not found or no permission."
                await update.message.reply_text(msg)

        except Exception as e:
            logger.error(
                "delete_reminder_failed",
                error=str(e),
                reminder_id=reminder_id,
                user_id=user_id,
            )
            await update.message.reply_text(
                "❌ Failed to delete reminder. Please try again later."
            )
