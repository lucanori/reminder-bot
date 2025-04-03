import logging
import os
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, JobQueue
from telegram import Update
import pytz
import sys
import asyncio
from models import create_db_and_tables, engine, SessionLocal, Reminder
import reminders

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/reminders.db")
TIMEZONE = os.getenv("TIMEZONE", "UTC")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=log_level
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends explanation on how to use the bot."""
    user_name = update.effective_user.first_name
    help_text = (
        f"Hello {user_name}!\n\n"
        "I can help you schedule reminders for tasks.\n\n"
        "Commands:\n"
        "/set <Reminder Text> <HH:MM> [every <N> days] - Set a new reminder (e.g., /set Take out trash 08:00 every 1 days)\n"
        "/view - Show your current reminders\n"
        "/delete <Reminder ID> - Delete a specific reminder (use /view to get IDs)\n"
        "/help - Show this help message"
    )
    await update.message.reply_text(help_text)

async def set_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /set command to add a reminder."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not context.args:
        await update.message.reply_text("Please provide reminder details. Use: /set <Reminder Text> <HH:MM> [every <N> days]")
        return
    
    reminder_text = " ".join(context.args)
    response = await reminders.add_reminder(context, user_id, chat_id, f"set {reminder_text}")
    await update.message.reply_text(response)

async def view_reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /view command to show reminders."""
    user_id = update.effective_user.id
    response = await reminders.get_reminders(context, user_id)
    await update.message.reply_text(response)

async def delete_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /delete command."""
    user_id = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Please provide the ID of the reminder to delete. Use /view to see IDs.")
        return

    delete_text = " ".join(context.args)
    response = await reminders.remove_reminder(context, user_id, f"delete {delete_text}")
    await update.message.reply_text(response)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles unknown commands."""
    await update.message.reply_text("Sorry, I didn't understand that command. Use /help to see available commands.")

def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in the environment variables.")
        return

    job_queue = JobQueue()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).job_queue(job_queue).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("set", set_reminder_command))
    application.add_handler(CommandHandler("view", view_reminders_command))
    application.add_handler(CommandHandler("delete", delete_reminder_command))

    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("Application and JobQueue will start.")

    logger.info("Starting bot polling...")
    application.run_polling()

if __name__ == "__main__":
    if DATABASE_URL.startswith("sqlite"):
        if DATABASE_URL.startswith("sqlite:////"):
             db_path = DATABASE_URL.split("////")[1]
             if not db_path.startswith('/'):
                 db_path = '/' + db_path
        elif DATABASE_URL.startswith("sqlite:///"):
             db_path = DATABASE_URL.split("///")[1]
        else:
             db_path = "reminders.db"
             logger.warning(f"Could not parse directory from DATABASE_URL: {DATABASE_URL}. Assuming relative path.")

        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            try:
                os.makedirs(db_dir)
                logger.info(f"Created data directory: {db_dir}")
            except OSError as e:
                 logger.error(f"Failed to create data directory {db_dir}: {e}")

    logger.info("Ensuring database tables exist...")
    try:
        create_db_and_tables()
        logger.info("Database tables verified/created.")
    except Exception as e:
        logger.error(f"Failed to create/verify database tables: {e}", exc_info=True)
        sys.exit(1)

    main()