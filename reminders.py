import logging
from datetime import datetime, time, timedelta
import pytz
from sqlalchemy.orm import Session
from telegram.ext import ContextTypes

from models import Reminder, SessionLocal
from run_reminder_bot import TIMEZONE

logger = logging.getLogger(__name__)

async def send_reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    """Callback function executed by JobQueue to send a reminder."""
    job = context.job
    chat_id = job.chat_id
    reminder_text = job.data.get("reminder_text", "Your scheduled reminder")
    reminder_id = job.data.get("reminder_id", "N/A")

    logger.info(f"Sending reminder for reminder_id {reminder_id} to chat_id {chat_id}")
    try:
        await context.bot.send_message(chat_id=chat_id, text=f"🚨 Reminder: {reminder_text}")
        logger.info(f"Reminder message sent successfully via JobQueue for reminder_id {reminder_id} to chat_id {chat_id}.")

    except Exception as e:
        logger.error(f"Failed to send reminder via JobQueue for reminder_id {reminder_id} to chat_id {chat_id}: {e}", exc_info=True)

def calculate_initial_next_run(schedule_time_str: str, interval_days: int, timezone_str: str) -> datetime:
    """Calculates the first datetime a reminder should run."""
    tz = pytz.timezone(timezone_str)
    now_tz = datetime.now(tz)
    hour, minute = map(int, schedule_time_str.split(':'))
    scheduled_time_today = now_tz.replace(hour=hour, minute=minute, second=0, microsecond=0)

    next_run_time = scheduled_time_today
    if now_tz > scheduled_time_today:
        next_run_time += timedelta(days=interval_days)

    while next_run_time < now_tz:
         next_run_time += timedelta(days=interval_days)

    return next_run_time


async def add_reminder(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
    reminder_text: str,
    schedule_time_str: str,
    interval_days: int
) -> str:
    """Adds reminder to DB and schedules the job via JobQueue using provided details."""
    if not reminder_text:
        logger.warning(f"Attempt to add reminder with empty text for user {user_id}")
        return "Reminder text cannot be empty."
    if interval_days <= 0:
        logger.warning(f"Attempt to add reminder with invalid interval {interval_days} for user {user_id}")
        return "Interval must be a positive number of days."
    try:
        # Validate time format
        datetime.strptime(schedule_time_str, '%H:%M')
    except ValueError:
        logger.warning(f"Attempt to add reminder with invalid time format '{schedule_time_str}' for user {user_id}")
        return "Invalid time format. Please use HH:MM (e.g., 09:30)."

    db: Session = SessionLocal()
    try:
        next_run_dt = calculate_initial_next_run(schedule_time_str, interval_days, TIMEZONE)

        new_reminder = Reminder(
            user_id=user_id,
            chat_id=chat_id,
            reminder_text=reminder_text,
            schedule_time=schedule_time_str,
            schedule_interval_days=interval_days,
            next_reminder_time=next_run_dt
        )
        db.add(new_reminder)
        db.flush()

        job_id = f"reminder_{new_reminder.id}"

        job_name = f"reminder_{new_reminder.id}"
        job_data = {
            "reminder_text": new_reminder.reminder_text,
            "reminder_id": new_reminder.id
        }

        base_success_message = f"Reminder set for '{reminder_text}' at {schedule_time_str} every {interval_days} day(s)."
        next_run_message = f" Next reminder: {next_run_dt.strftime('%Y-%m-%d %H:%M:%S %Z')}"

        try:
            logger.debug(f"+++ BEFORE context.job_queue.run_repeating for job '{job_name}'")
            context.job_queue.run_repeating(
                send_reminder_callback,
                interval=timedelta(days=new_reminder.schedule_interval_days),
                first=next_run_dt,
                chat_id=chat_id,
                user_id=user_id,
                name=job_name,
                data=job_data
            )
            logger.debug(f"+++ AFTER context.job_queue.run_repeating for job '{job_name}'")
            logger.info(f"Job '{job_name}' scheduled successfully via JobQueue for reminder {new_reminder.id} starting {next_run_dt}")
            new_reminder.job_id = job_name
            db.commit()
            logger.info(f"Reminder {new_reminder.id} with job_id '{job_name}' committed to DB.")
            return base_success_message + next_run_message

        except Exception as schedule_e:
            db.rollback()
            logger.error(f"Failed to schedule job '{job_name}' for reminder {new_reminder.id}. DB changes rolled back. Error: {schedule_e}", exc_info=True)
            return "An error occurred while scheduling the reminder notification. Reminder was not saved."


    except Exception as e:
        db.rollback()
        logger.error(f"Failed to process or add reminder '{reminder_text}' for user {user_id} due to error before DB commit: {e}", exc_info=True)
        return "An error occurred while processing your request before saving."
    finally:
        db.close()

async def get_reminders_list(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> list[tuple[int, str, str]]:
    """Fetches reminders from DB and returns a list of (id, text, time_str)."""
    db: Session = SessionLocal()
    reminders_data = []
    try:
        user_reminders = db.query(Reminder).filter(Reminder.user_id == user_id).order_by(Reminder.id).all() # Order by ID for consistency
        for r in user_reminders:
            reminders_data.append((r.id, r.reminder_text, r.schedule_time))
        return reminders_data
    except Exception as e:
        logger.error(f"Failed to get reminders list for user {user_id}: {e}", exc_info=True)
        return [] # Return empty list on error
    finally:
        db.close()

async def get_reminders(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    """Fetches reminders from DB, formats them as a string, including next run time."""
    db: Session = SessionLocal()
    try:
        # Query reminders directly here to easily access job queue info
        user_reminders = db.query(Reminder).filter(Reminder.user_id == user_id).order_by(Reminder.next_reminder_time).all()
        if not user_reminders:
            return "You have no active reminders set. Use the buttons or /set to create one."

        response_lines = ["Your current reminders:"]
        for r in user_reminders:
            next_run_str = "N/A (Job missing?)"
            if r.job_id:
                jobs = context.job_queue.get_jobs_by_name(r.job_id)
                if jobs:
                    job = jobs[0]
                    next_run_time_attr = getattr(job, 'next_t', None)
                    if next_run_time_attr:
                        local_tz = pytz.timezone(TIMEZONE)
                        if isinstance(next_run_time_attr, datetime):
                             # Ensure datetime is timezone-aware before formatting
                             if next_run_time_attr.tzinfo is None:
                                 # Assume it's UTC if naive, then convert
                                 next_run_aware = pytz.utc.localize(next_run_time_attr).astimezone(local_tz)
                             else:
                                 next_run_aware = next_run_time_attr.astimezone(local_tz)
                             next_run_str = next_run_aware.strftime('%Y-%m-%d %H:%M:%S %Z')
                        else:
                             # Handle cases where next_t might not be a datetime object as expected
                             next_run_str = f"Scheduled (Type: {type(next_run_time_attr).__name__})"
                    else:
                        # next_t might be None if the job finished or hasn't run yet
                        next_run_str = "Scheduled (Next run time unavailable)"
                else:
                    # Job ID exists in DB but not in the queue (could be due to restart, error)
                    next_run_str = f"Error: Job '{r.job_id}' not found in active queue!"
                    logger.warning(f"Job '{r.job_id}' for reminder {r.id} not found in JobQueue for user {user_id}")
            else:
                 # Reminder exists but has no job_id (shouldn't normally happen after creation)
                 next_run_str = "Error: No associated job ID found!"
                 logger.warning(f"Reminder {r.id} for user {user_id} has no job_id in the database.")


            interval_str = f"every {r.schedule_interval_days} days" if r.schedule_interval_days > 1 else "daily"
            response_lines.append(
                f"- ID: {r.id} | Text: {r.reminder_text} | Time: {r.schedule_time} ({interval_str}) | Next: {next_run_str}"
            )
        return "\n".join(response_lines)
    except Exception as e:
        logger.error(f"Failed to get reminders for user {user_id}: {e}", exc_info=True)
        return "An error occurred while fetching your reminders."
    finally:
        db.close()

async def remove_reminder_by_id(context: ContextTypes.DEFAULT_TYPE, user_id: int, reminder_id_to_delete: int) -> str:
    """Finds reminder by ID, removes job from JobQueue, and deletes from DB."""
    db: Session = SessionLocal()
    try:
        reminder_to_delete = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.id == reminder_id_to_delete
        ).first()

        if not reminder_to_delete:
            return f"Reminder with ID {reminder_id_to_delete} not found or does not belong to you."

        job_id = reminder_to_delete.job_id
        reminder_text = reminder_to_delete.reminder_text # Store text before deleting

        if job_id:
            jobs = context.job_queue.get_jobs_by_name(job_id)
            if jobs:
                for job in jobs:
                    job.schedule_removal()
                logger.info(f"Scheduled removal for job(s) named '{job_id}' for reminder {reminder_id_to_delete}")
            else:
                logger.warning(f"Job '{job_id}' for reminder {reminder_id_to_delete} not found in JobQueue, proceeding with DB deletion.")
        else:
             logger.warning(f"Reminder {reminder_id_to_delete} for user {user_id} had no job_id associated in DB during deletion.")


        db.delete(reminder_to_delete)
        db.commit()
        logger.info(f"Deleted reminder {reminder_id_to_delete} for user {user_id}")
        return f"Reminder for '{reminder_text}' (ID: {reminder_id_to_delete}) has been deleted."

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete reminder {reminder_id_to_delete} for user {user_id}: {e}", exc_info=True)
        return f"An error occurred while deleting reminder ID {reminder_id_to_delete}. Please try again."
    finally:
        db.close()


async def remove_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str) -> str:
    """Parses message for /delete command and calls remove_reminder_by_id."""
    parts = text.split()
    # Expecting "delete <ID>" after command parsing in run_reminder_bot.py
    if len(parts) != 1: # Only the ID should be left after "delete " is stripped
         return "Invalid format. Use: /delete <Reminder ID> or use the buttons."

    try:
        reminder_id_to_delete = int(parts[0])
    except ValueError:
        return "Invalid Reminder ID. Please provide a number."

    # Call the refactored function
    return await remove_reminder_by_id(context, user_id, reminder_id_to_delete)