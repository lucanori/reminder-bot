import asyncio
from collections.abc import Coroutine
from concurrent.futures import Future
from typing import Any, TypeVar

from telegram import Bot, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

from .config import settings
from .handlers.callback_handlers import CallbackHandlers
from .handlers.command_handlers import SET_INTERVAL, SET_TEXT, SET_TIME, CommandHandlers
from .models.entities import Base
from .services.notification_service import NotificationService
from .services.reminder_service import ReminderService
from .services.user_service import UserService
from .utils.database import engine, get_async_session
from .utils.exceptions import ReminderBotException
from .utils.logging import configure_logging, get_logger
from .utils.scheduler import JobScheduler
from .utils.version import get_version

logger = get_logger()

T = TypeVar("T")


class BotService:
    def __init__(self):
        self.application: Application = None
        self.bot: Bot = None
        self.job_scheduler: JobScheduler = None
        self.reminder_service: ReminderService = None
        self.notification_service: NotificationService = None
        self.user_service: UserService = None
        self.command_handlers: CommandHandlers = None
        self.callback_handlers: CallbackHandlers = None
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._polling_task: asyncio.Task | None = None

    async def initialize(self) -> None:
        try:
            configure_logging(settings.log_level)
            logger.info("bot_initialization_started", version=get_version())

            await self._create_database_tables()
            await self._initialize_services()
            await self._setup_telegram_handlers()
            await self._recover_scheduled_jobs()

            logger.info("bot_initialization_completed")

        except Exception as e:
            logger.error("bot_initialization_failed", error=str(e), exc_info=True)
            raise ReminderBotException(f"Failed to initialize bot: {e}")

    async def start_bot(self) -> None:
        try:
            logger.info("bot_starting")
            await self.job_scheduler.start()
            await self.application.initialize()
            await self.application.start()

            if settings.telegram_webhook_url:
                await self._setup_webhook()
            else:
                await self._start_polling()

        except Exception as e:
            logger.error("bot_start_failed", error=str(e), exc_info=True)
            raise ReminderBotException(f"Failed to start bot: {e}")

    async def start_polling_non_blocking(self) -> None:
        try:
            logger.info("bot_starting_non_blocking")

            # Store reference to the main event loop for cross-thread access
            self._main_loop = asyncio.get_running_loop()
            logger.info("main_event_loop_stored")

            await self.job_scheduler.start()

            if settings.telegram_webhook_url:
                await self._setup_webhook()
            else:
                # PTB v22+ proper lifecycle: initialize and start before polling
                await self.application.initialize()
                await self.application.start()
                logger.info("telegram_application_initialized_and_started")

                # Start polling as a background task
                self._polling_task = asyncio.create_task(
                    self.application.updater.start_polling(
                        drop_pending_updates=True, allowed_updates=Update.ALL_TYPES
                    )
                )
                logger.info("polling_started_non_blocking")

        except Exception as e:
            logger.error("bot_start_non_blocking_failed", error=str(e), exc_info=True)
            raise ReminderBotException(f"Failed to start bot non-blocking: {e}")

    async def stop_bot(self) -> None:
        try:
            logger.info("bot_stopping")

            # Cancel polling task if running
            if self._polling_task and not self._polling_task.done():
                self._polling_task.cancel()
                try:
                    await self._polling_task
                except asyncio.CancelledError:
                    logger.info("polling_task_cancelled")

            if self.application:
                await self.application.stop()
                await self.application.shutdown()

            if self.job_scheduler:
                await self.job_scheduler.shutdown()

            if engine:
                await engine.dispose()

            self._main_loop = None
            logger.info("bot_stopped")

        except Exception as e:
            logger.error("bot_stop_failed", error=str(e), exc_info=True)

    async def _create_database_tables(self) -> None:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("database_tables_created")
        except Exception as e:
            logger.error("database_tables_creation_failed", error=str(e))
            raise

    async def _initialize_services(self) -> None:
        self.application = (
            Application.builder().token(settings.telegram_bot_token).build()
        )
        self.bot = self.application.bot

        self.user_service = UserService(None)
        self.reminder_service = ReminderService(None)
        self.notification_service = NotificationService(
            self.bot, None, self.user_service
        )
        self.job_scheduler = JobScheduler(self.notification_service, None)

        self.command_handlers = CommandHandlers(
            self.reminder_service, self.user_service, self.job_scheduler
        )
        self.callback_handlers = CallbackHandlers(
            self.notification_service,
            self.reminder_service,
            self.user_service,
            self.job_scheduler,
        )

        logger.info("services_initialized")

    async def _setup_telegram_handlers(self) -> None:
        self.application.add_handler(
            CommandHandler("start", self.command_handlers.start_command)
        )
        self.application.add_handler(
            CommandHandler("help", self.command_handlers.help_command)
        )
        self.application.add_handler(
            CommandHandler("view", self.command_handlers.view_reminders)
        )
        self.application.add_handler(
            CommandHandler("delete", self.command_handlers.delete_reminder_start)
        )

        set_reminder_handler = ConversationHandler(
            entry_points=[
                CommandHandler("set", self.command_handlers.set_reminder_start)
            ],
            states={
                SET_TEXT: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.command_handlers.set_reminder_text,
                    )
                ],
                SET_TIME: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.command_handlers.set_reminder_time,
                    )
                ],
                SET_INTERVAL: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.command_handlers.set_reminder_interval,
                    )
                ],
            },
            fallbacks=[
                CommandHandler("cancel", self.command_handlers.cancel_conversation)
            ],
            allow_reentry=True,
        )

        self.application.add_handler(set_reminder_handler)

        self.application.add_handler(
            CallbackQueryHandler(
                self.callback_handlers.handle_reminder_callback,
                pattern=r"^(confirm|snooze)_\d+$",
            )
        )

        self.application.add_handler(
            CallbackQueryHandler(
                self.callback_handlers.handle_menu_callback,
                pattern=r"^(cmd_(set|view|delete|help|timezone)|template_\w+|back_to_menu|time_\w+_[\d:]+|create_\w+_[\d:]+_\d+|custom_\w+|customtime_[\d:]+|custominterval_\d+|custom_time_manual|custom_interval_manual|delete_\d+|use_set_command|tz_[A-Za-z_/]+|tz_manual)$",
            )
        )

        self.application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                self.callback_handlers.handle_custom_text_input,
            ),
            group=1,
        )

        self.application.add_error_handler(self._error_handler)

        logger.info("telegram_handlers_configured")

    async def _setup_webhook(self) -> None:
        try:
            await self.bot.set_webhook(url=settings.telegram_webhook_url)
            logger.info("webhook_configured", url=settings.telegram_webhook_url)
        except Exception as e:
            logger.error("webhook_setup_failed", error=str(e))
            raise

    async def _start_polling(self) -> None:
        try:
            await self.application.run_polling(
                drop_pending_updates=True, allowed_updates=Update.ALL_TYPES
            )
        except Exception as e:
            logger.error("polling_failed", error=str(e))
            raise

    async def _recover_scheduled_jobs(self) -> None:
        try:
            await self.job_scheduler.recover_jobs_from_database()
            logger.info("scheduled_jobs_recovered")
        except Exception as e:
            logger.warning("jobs_recovery_failed", error=str(e))

    async def _error_handler(self, update: object, context) -> None:
        logger.error(
            "telegram_update_error",
            error=str(context.error),
            update_type=type(update).__name__ if update else "unknown",
            exc_info=True,
        )

        if update and hasattr(update, "effective_chat") and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ An error occurred. Please try again later.",
                )
            except Exception as e:
                logger.error("error_notification_failed", error=str(e))

    def run_coroutine_threadsafe(self, coro: Coroutine[Any, Any, T]) -> T:
        """Run a coroutine on the main event loop from a different thread.

        This method allows Flask routes (running in a daemon thread) to safely
        execute async code on the bot's main event loop without creating new
        event loops or using asyncio.run().

        Args:
            coro: The coroutine to execute

        Returns:
            The result of the coroutine

        Raises:
            RuntimeError: If the main loop is not available
        """
        if self._main_loop is None or self._main_loop.is_closed():
            raise RuntimeError("Main event loop is not available")

        future: Future[T] = asyncio.run_coroutine_threadsafe(coro, self._main_loop)
        return future.result(timeout=30)  # 30 second timeout for safety

    async def health_check(self) -> dict:
        try:
            async with get_async_session() as session:
                await session.execute("SELECT 1")

            bot_info = await self.bot.get_me()

            scheduler_running = (
                self.job_scheduler.scheduler.running if self.job_scheduler else False
            )

            return {
                "status": "healthy",
                "bot_username": bot_info.username,
                "scheduler_running": scheduler_running,
                "database_connected": True,
                "timestamp": asyncio.get_event_loop().time(),
            }

        except Exception as e:
            logger.error("health_check_failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time(),
            }
