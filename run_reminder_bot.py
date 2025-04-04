import logging
import signal
import sys

def signal_handler(sig, frame):
    print('Shutting down gracefully...')
    application.stop()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
import os
from dotenv import load_dotenv
import re # Import regex for time validation
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, JobQueue,
    CallbackQueryHandler, ConversationHandler, PicklePersistence
)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
import pytz
import sys
import asyncio
from models import create_db_and_tables, engine, SessionLocal, Reminder, User
import reminders

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/data/reminders.db")
TIMEZONE = os.getenv("TIMEZONE", "UTC")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
BOT_MODE = os.getenv("BOT_MODE", "blocklist").lower() # Read bot mode, default to blocklist

log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=log_level
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Callback Data Constants
CALLBACK_SET_START = "set_start"
CALLBACK_VIEW = "view"
CALLBACK_DELETE_MENU = "delete_menu"
CALLBACK_DELETE_CONFIRM_PREFIX = "delete_confirm_" # Prefix for delete buttons in the dedicated delete menu
CALLBACK_VIEW_DELETE_PREFIX = "view_delete_" # Prefix for delete buttons in the view list
CALLBACK_FREQUENCY_DAILY = "freq_daily"
CALLBACK_FREQUENCY_SPECIFY = "freq_specify"
CALLBACK_CANCEL = "cancel_conv"
CALLBACK_MAIN_MENU = "main_menu" # Added for back button consistency

# Conversation States (for setting reminder)
ASK_TEXT, ASK_TIME, ASK_FREQUENCY = range(3)

async def check_user_access(user_id: int) -> tuple[bool, str | None]:
    """Checks if a user is allowed to interact based on BOT_MODE and their status."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.telegram_id == user_id).first()
        if not user:
            # Create user if they don't exist
            user = User(telegram_id=user_id, is_blocked=False, is_whitelisted=False)
            db.add(user)
            db.commit()
            logger.info(f"Created new user record for {user_id}")
            # Re-query to get the managed object
            user = db.query(User).filter(User.telegram_id == user_id).first()


        if BOT_MODE == "whitelist":
            if not user.is_whitelisted:
                logger.warning(f"Access denied for user {user_id} in whitelist mode (not whitelisted).")
                return False, "Sorry, you are not authorized to use this bot. Please contact the administrator."
        elif BOT_MODE == "blocklist":
            if user.is_blocked:
                logger.warning(f"Access denied for user {user_id} in blocklist mode (blocked).")
                return False, "Sorry, you have been blocked from using this bot."

        return True, None # Access granted
    except Exception as e:
        db.rollback()
        logger.error(f"Database error checking access for user {user_id}: {e}", exc_info=True)
        return False, "An internal error occurred while checking your access. Please try again later."
    finally:
        db.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message with the main action buttons."""
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name

    allowed, message = await check_user_access(user_id)
    if not allowed:
        await update.message.reply_text(message)
        return

    keyboard = [
        [InlineKeyboardButton("Set Reminder", callback_data=CALLBACK_SET_START)],
        [InlineKeyboardButton("View Reminders", callback_data=CALLBACK_VIEW)],
        [InlineKeyboardButton("Delete Reminder", callback_data=CALLBACK_DELETE_MENU)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(f"Hello {user_name}! What would you like to do?", reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provides help text, keeping slash commands for reference."""
    user_name = update.effective_user.first_name
    help_text = (
        f"Hello {user_name}!\n\n"
        "Use the buttons below to manage your reminders.\n\n"
        "Alternatively, you can use these commands:\n"
        "/set <Reminder Text> <HH:MM> [every <N> days] - Set a new reminder\n"
        "/view - Show your current reminders\n"
        "/delete <Reminder ID> - Delete a specific reminder\n"
        "/help - Show this help message"
    )
    # Also show the main menu buttons with the help message
    keyboard = [
        [InlineKeyboardButton("Set Reminder", callback_data=CALLBACK_SET_START)],
        [InlineKeyboardButton("View Reminders", callback_data=CALLBACK_VIEW)],
        [InlineKeyboardButton("Delete Reminder", callback_data=CALLBACK_DELETE_MENU)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(help_text, reply_markup=reply_markup)

async def set_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the /set command by directly starting the conversation flow."""
    # This now acts purely as an entry point, similar to the button.
    # The actual logic and access check happen in set_reminder_start.
    return await set_reminder_start(update, context)

async def view_reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /view command by showing the main menu."""
    user_id = update.effective_user.id
    allowed, message = await check_user_access(user_id)
    if not allowed:
        await update.message.reply_text(message)
        return
    # Instead of showing text, show the main menu buttons
    await send_main_menu(chat_id=update.message.chat_id, context=context, user_name=update.effective_user.first_name)

async def delete_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /delete command by showing the main menu."""
    user_id = update.effective_user.id
    allowed, message = await check_user_access(user_id)
    if not allowed:
        await update.message.reply_text(message)
        return
    # Instead of handling args, show the main menu buttons
    await send_main_menu(chat_id=update.message.chat_id, context=context, user_name=update.effective_user.first_name)

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles unknown commands."""
    await update.message.reply_text("Sorry, I didn't understand that command. Use /help or the buttons.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    user_id = query.from_user.id

    # Answer the callback query first (important!)
    await query.answer()

    # Check access
    allowed, message = await check_user_access(user_id)
    if not allowed:
        await query.edit_message_text(text=message)
        return

    callback_data = query.data

    # Handle main menu navigation first if applicable
    # Handle main menu navigation (e.g., from 'Back' buttons)
    if callback_data == CALLBACK_MAIN_MENU:
        # Edit the previous message first to remove buttons/indicate action
        await query.edit_message_text(text="Returning to main menu...")
        # Then send the main menu as a new message
        await send_main_menu(chat_id=query.message.chat_id, context=context, user_name=query.from_user.first_name)
        return

    # Check access again (belt and suspenders, might be redundant if start checks)
    allowed, message = await check_user_access(user_id)
    if not allowed:
        await query.edit_message_text(text=message)
        return

    # Route based on main menu choices
    if callback_data == CALLBACK_SET_START:
        # This button press now acts as an entry point to the conversation
        # We need to call the *start* function of the conversation handler
        # However, CallbackQueryHandler doesn't directly integrate like CommandHandler entry_points
        # So, we manually start the flow here.
        await query.edit_message_text(text="Okay, let's set a new reminder. What should the reminder text be?")
        # We return the *state* expected by the ConversationHandler
        return ASK_TEXT
    elif callback_data == CALLBACK_VIEW:
        await view_reminders_action(query, context)
    elif callback_data == CALLBACK_DELETE_MENU:
        await delete_reminder_menu_action(query, context)
    elif callback_data.startswith(CALLBACK_DELETE_CONFIRM_PREFIX) or callback_data.startswith(CALLBACK_VIEW_DELETE_PREFIX):
        await delete_reminder_confirm_action(query, context, callback_data) # Use the same confirmation logic
    elif callback_data == CALLBACK_CANCEL: # Handle cancellation from buttons
         # Send confirmation as a new message
         await context.bot.send_message(chat_id=query.message.chat_id, text="Operation cancelled.")
         # Edit the original message (e.g., frequency choice) to remove buttons
         await query.edit_message_text(text="Operation cancelled.")
         # Send the main menu as a new message
         await send_main_menu(chat_id=query.message.chat_id, context=context, user_name=query.from_user.first_name)
         return ConversationHandler.END
    else:
        await query.edit_message_text(text="Unknown button action.")

async def view_reminders_action(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE):
    """Handles the 'View Reminders' button, showing a list with inline delete buttons."""
    user_id = query.from_user.id
    reminders_list = await reminders.get_reminders_list(context, user_id)

    if not reminders_list:
        keyboard = [[InlineKeyboardButton("« Back to Main Menu", callback_data=CALLBACK_MAIN_MENU)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="You have no reminders set.", reply_markup=reply_markup)
        return

    keyboard = []
    text = "Your reminders:\n\n"
    for reminder_id, reminder_text, reminder_time_str in reminders_list:
        # Shorten long text for button label
        display_text = (reminder_text[:20] + '...') if len(reminder_text) > 20 else reminder_text
        # Add reminder info to text
        text += f"🔹 {reminder_text} (at {reminder_time_str})\n"
        # Add inline delete button for this reminder
        delete_button_text = f"❌ Delete ID {reminder_id}"
        delete_callback = f"{CALLBACK_VIEW_DELETE_PREFIX}{reminder_id}"
        keyboard.append([InlineKeyboardButton(delete_button_text, callback_data=delete_callback)])

    keyboard.append([InlineKeyboardButton("« Back to Main Menu", callback_data=CALLBACK_MAIN_MENU)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)

async def delete_reminder_menu_action(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE):
    """Handles the 'Delete Reminder' button, showing a list with delete buttons."""
    user_id = query.from_user.id
    reminders_list = await reminders.get_reminders_list(context, user_id) # Assumes new function

    if not reminders_list:
        await query.edit_message_text(text="You have no reminders to delete.")
        return

    keyboard = []
    text = "Select the reminder to delete:\n\n"
    for reminder_id, reminder_text, reminder_time_str in reminders_list:
        # Shorten long text for button label
        display_text = (reminder_text[:20] + '...') if len(reminder_text) > 20 else reminder_text
        button_text = f"❌ {reminder_id}: {display_text} ({reminder_time_str})"
        callback = f"{CALLBACK_DELETE_CONFIRM_PREFIX}{reminder_id}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])
        text += f"ID: {reminder_id} - {reminder_text} at {reminder_time_str}\n" # Keep full text in message

    # Add a back button maybe? For now, just the list.
    keyboard.append([InlineKeyboardButton("« Back to Main Menu", callback_data=CALLBACK_MAIN_MENU)])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)


async def delete_reminder_confirm_action(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE, callback_data: str):
    """Handles the confirmation button for deleting a specific reminder."""
    user_id = query.from_user.id
    try:
        if callback_data.startswith(CALLBACK_DELETE_CONFIRM_PREFIX):
            reminder_id_to_delete = int(callback_data.split(CALLBACK_DELETE_CONFIRM_PREFIX)[1])
        elif callback_data.startswith(CALLBACK_VIEW_DELETE_PREFIX):
             reminder_id_to_delete = int(callback_data.split(CALLBACK_VIEW_DELETE_PREFIX)[1])
        else:
             raise ValueError("Unknown delete prefix")
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data for delete confirmation: {callback_data}")
        await query.edit_message_text(text="Error processing delete request.")
        return

    response = await reminders.remove_reminder_by_id(context, user_id, reminder_id_to_delete)

    await query.edit_message_text(text=response)
    # Send main menu as a new message after deletion confirmation
    await send_main_menu(chat_id=query.message.chat_id, context=context, user_name=query.from_user.first_name)
async def send_main_menu(chat_id: int, context: ContextTypes.DEFAULT_TYPE, user_name: str = "there"):
    """Sends the main menu keyboard as a new message."""
    keyboard = [
        [InlineKeyboardButton("Set Reminder", callback_data=CALLBACK_SET_START)],
        [InlineKeyboardButton("View Reminders", callback_data=CALLBACK_VIEW)],
        [InlineKeyboardButton("Delete Reminder", callback_data=CALLBACK_DELETE_MENU)],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = f"Hello {user_name}! What would you like to do?"
    await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)


# Wrapper for handling main menu callback within ConversationHandler fallbacks
async def handle_main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the main menu button press, edits previous message, sends new menu."""
    query = update.callback_query
    await query.answer()
    # Edit the previous message first
    await query.edit_message_text(text="Returning to main menu...")
    # Send the main menu as a new message
    await send_main_menu(chat_id=query.message.chat_id, context=context, user_name=query.from_user.first_name)
    # Decide if this should end a conversation if called as a fallback
    # For now, let's assume it shouldn't implicitly end it, but depends on context.
    # If it needs to end, return ConversationHandler.END
    return ConversationHandler.END # Assume fallback means ending the current flow


# --- Conversation Handler Functions for Setting Reminder ---

async def set_reminder_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the conversation for setting a reminder (entry point for command and button)."""
    user_id = update.effective_user.id
    allowed, message = await check_user_access(user_id)
    if not allowed:
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(message)
        elif update.message:
            await update.message.reply_text(message)
        return ConversationHandler.END # Stop conversation if not allowed

    prompt_text = "Okay, let's set a new reminder. What should the reminder text be?"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(prompt_text)
    elif update.message: # From /set command
        await update.message.reply_text(prompt_text)

    return ASK_TEXT

async def ask_reminder_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the reminder text and asks for the time."""
    text = update.message.text
    context.user_data['reminder_text'] = text
    logger.info(f"User {update.effective_user.id} set reminder text: {text}")

    await update.message.reply_text("Got it. Now, please tell me the time for the reminder in HH:MM format (e.g., 09:30 or 14:00).")
    return ASK_TIME

async def ask_reminder_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Stores the time, validates it, and asks for frequency."""
    time_str = update.message.text
    # Basic validation using regex
    if not re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", time_str):
        await update.message.reply_text("Invalid time format. Please use HH:MM (e.g., 09:30 or 14:00). Try again.")
        return ASK_TIME # Ask again

    context.user_data['schedule_time'] = time_str
    logger.info(f"User {update.effective_user.id} set reminder time: {time_str}")

    keyboard = [
        [InlineKeyboardButton("Daily", callback_data=CALLBACK_FREQUENCY_DAILY)],
        [InlineKeyboardButton("Specify Interval (Days)", callback_data=CALLBACK_FREQUENCY_SPECIFY)],
        [InlineKeyboardButton("Cancel", callback_data=CALLBACK_CANCEL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Great. How often should this reminder repeat?", reply_markup=reply_markup)
    return ASK_FREQUENCY

async def ask_reminder_frequency_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the button choice for frequency (Daily or Specify)."""
    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == CALLBACK_FREQUENCY_DAILY:
        context.user_data['interval_days'] = 1
        logger.info(f"User {update.effective_user.id} chose daily frequency.")
        # All data collected, proceed to save
        return await save_reminder(update, context)
    elif choice == CALLBACK_FREQUENCY_SPECIFY:
        logger.info(f"User {update.effective_user.id} chose to specify frequency.")
        await query.edit_message_text("Okay, please enter the interval in days (e.g., 3 for every 3 days).")
        # Stay in ASK_FREQUENCY state, but expect a text message now
        return ASK_FREQUENCY
    else:
        # Should not happen if buttons are defined correctly
        await query.edit_message_text("Invalid choice. Please try again.")
        return ASK_FREQUENCY


async def ask_reminder_frequency_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles the user entering the number of days for the interval."""
    days_str = update.message.text
    try:
        interval_days = int(days_str)
        if interval_days <= 0:
            raise ValueError("Interval must be positive.")
        context.user_data['interval_days'] = interval_days
        logger.info(f"User {update.effective_user.id} set frequency interval: {interval_days} days.")
        # All data collected, proceed to save
        return await save_reminder(update, context)
    except ValueError:
        await update.message.reply_text("Invalid number. Please enter a positive whole number for the days interval (e.g., 7).")
        return ASK_FREQUENCY # Ask again

async def save_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the reminder using collected data and ends the conversation."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    reminder_text = context.user_data.get('reminder_text')
    schedule_time = context.user_data.get('schedule_time')
    interval_days = context.user_data.get('interval_days')

    # Double-check authorization before saving
    allowed, auth_message = await check_user_access(user_id)
    if not allowed:
        final_message = auth_message
        if update.callback_query:
            await update.callback_query.edit_message_text(final_message)
        elif update.message: # Should not happen if entry point checks, but safety first
             await context.bot.send_message(chat_id=chat_id, text=final_message)
        context.user_data.clear()
        return ConversationHandler.END

    # Ensure all data is present
    if not all([reminder_text, schedule_time, interval_days]):
        logger.error(f"Missing data in user_data when trying to save reminder for user {user_id}. Data: {context.user_data}")
        final_message = "Something went wrong, missing some details. Please try setting the reminder again."
        if update.callback_query:
            await update.callback_query.edit_message_text(final_message)
        elif update.message:
             await context.bot.send_message(chat_id=chat_id, text=final_message) # Send new message if last input was text
        else: # If called after frequency button press
             await context.bot.send_message(chat_id=chat_id, text=final_message)
        context.user_data.clear()
        return ConversationHandler.END

    # Call the refactored add_reminder function
    response = await reminders.add_reminder(
        context,
        user_id,
        chat_id,
        reminder_text,
        schedule_time,
        interval_days
    )

    final_message = response # Use the response from add_reminder

    # Send final confirmation message
    # Always send a new message here for clarity, especially after button presses.
    # Editing the last message (which might be the frequency choice buttons) can be confusing.
    await context.bot.send_message(chat_id=chat_id, text=final_message)

    # If the trigger was a callback query (frequency choice), we should ideally remove the buttons
    # from the previous message to avoid confusion.
    if update.callback_query:
        try:
            # Edit the message that contained the frequency buttons to show it was handled
            await update.callback_query.edit_message_text(text=f"Frequency set ({'Daily' if interval_days == 1 else f'Every {interval_days} days'}). Reminder saved.")
        except Exception as e:
            logger.warning(f"Could not edit previous message after saving reminder: {e}")


    context.user_data.clear() # Clean up user data
    logger.info(f"Reminder conversation ended for user {user_id}.")
    # Send main menu as a new message after setting reminder
    await send_main_menu(chat_id=update.effective_chat.id, context=context, user_name=update.effective_user.first_name)
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the conversation."""
    user = update.effective_user
    logger.info(f"User {user.id} canceled the conversation.")
    await update.message.reply_text('Operation cancelled.')
    context.user_data.clear()
    # Send main menu as a new message after cancelling with /cancel
    await send_main_menu(chat_id=update.message.chat_id, context=context, user_name=update.effective_user.first_name)
    return ConversationHandler.END

# --- End Conversation Handler Functions ---

def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set in the environment variables.")
        return

    job_queue = JobQueue()

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).job_queue(job_queue).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command)) # Use new help command
    # Keep command handlers as entry points or for help reference, but logic is button-driven
    application.add_handler(CommandHandler("set", set_reminder_command)) # Now triggers conversation
    application.add_handler(CommandHandler("view", view_reminders_command)) # Now shows main menu
    application.add_handler(CommandHandler("delete", delete_reminder_command)) # Now shows main menu

    # --- Setup Conversation Handler for Setting Reminders ---
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("set", set_reminder_command), # Triggered by /set command
            CallbackQueryHandler(set_reminder_start, pattern=f"^{CALLBACK_SET_START}$") # Triggered by button
        ],
        states={
            ASK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_reminder_text)],
            ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_reminder_time)],
            ASK_FREQUENCY: [
                CallbackQueryHandler(ask_reminder_frequency_choice, pattern=f"^({CALLBACK_FREQUENCY_DAILY}|{CALLBACK_FREQUENCY_SPECIFY})$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_reminder_frequency_days), # Handles number input
                CallbackQueryHandler(cancel_conversation, pattern=f"^{CALLBACK_CANCEL}$") # Cancel button within frequency choice
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CallbackQueryHandler(cancel_conversation, pattern=f"^{CALLBACK_CANCEL}$"), # General cancel button
            # Allow returning to main menu via button press as a fallback
            CallbackQueryHandler(handle_main_menu_callback, pattern=f"^{CALLBACK_MAIN_MENU}$")
            ],
        # Allow re-entry, useful if user presses "Set Reminder" button again mid-conversation
        allow_reentry=True
        # Optional: Add persistence if needed
        # name="set_reminder_conversation",
        # persistent=True,
    )
    application.add_handler(conv_handler)
    # --- End Conversation Handler Setup ---

    # Add handler for general inline button callbacks (needs to be after ConversationHandler)
    # This handles View, Delete Menu, Delete Confirm, and Back buttons NOT handled by the conversation.
    # The pattern ensures it doesn't capture callbacks used within the conversation states.
    application.add_handler(CallbackQueryHandler(button_handler, pattern=f"^(?!{CALLBACK_SET_START}|{CALLBACK_FREQUENCY_DAILY}|{CALLBACK_FREQUENCY_SPECIFY}|{CALLBACK_CANCEL}).*$")) # Exclude conversation callbacks

    application.add_handler(MessageHandler(filters.COMMAND, unknown)) # Keep this last for unknown commands

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