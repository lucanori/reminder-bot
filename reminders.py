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


async def add_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int, chat_id: int, text: str) -> str:
    """Parses message, adds reminder to DB, and schedules the job via JobQueue."""
    parts = text.split()
    if len(parts) < 3:
        return "Invalid format. Use: /set <Reminder Text> <HH:MM> [every <N> days]"

    try:
        interval_days = 1
        schedule_time_str = None
        reminder_text_parts = []

        if len(parts) >= 5 and parts[-3].lower() == "every" and parts[-1].lower() == "days":
            schedule_time_str = parts[-4]
            interval_days_str = parts[-2]
            reminder_text_parts = parts[1:-4]
            try:
                interval_days = int(interval_days_str)
                if interval_days <= 0:
                    raise ValueError("Interval must be positive.")
                datetime.strptime(schedule_time_str, '%H:%M')
            except (ValueError, IndexError):
                 return "Invalid format for interval. Use: ... every <N> days HH:MM"

        elif len(parts) >= 3:
            schedule_time_str = parts[-1]
            reminder_text_parts = parts[1:-1]
            try:
                datetime.strptime(schedule_time_str, '%H:%M')
            except (ValueError, IndexError):
                 return "Invalid format. Ensure time HH:MM is the last part, or use '... every N days HH:MM'."
        else:
             return "Invalid format. Use: /set <Reminder Text> <HH:MM> [every <N> days]"

        reminder_text = " ".join(reminder_text_parts)
        if not reminder_text:
             raise ValueError("Reminder text cannot be empty.")

        if not schedule_time_str:
             raise ValueError("Could not parse schedule time.")

        reminder_text = " ".join(reminder_text_parts)
        if not reminder_text:
             raise ValueError("Reminder text cannot be empty.")

    except (ValueError, IndexError):
        return "Invalid format. Use: /set <Reminder Text> <HH:MM> [every <N> days]\nExample: /set Take out trash 08:00\nExample: /set Water plants every 3 days 19:00"

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
        reminder_text_for_log = reminder_text if 'reminder_text' in locals() else "[Unknown Text]"
        logger.error(f"Failed to process or add reminder '{reminder_text_for_log}' for user {user_id} due to error before DB commit: {e}", exc_info=True)
        return "An error occurred while processing your request before saving. Please check the format and try again."
    finally:
        db.close()

async def get_reminders(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> str:
    """Fetches reminders from DB and tries to get next run time from JobQueue."""
    db: Session = SessionLocal()
    try:
        user_reminders = db.query(Reminder).filter(Reminder.user_id == user_id).order_by(Reminder.next_reminder_time).all()
        if not user_reminders:
            return "You have no active reminders set. Use /set to create one."

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
                             if next_run_time_attr.tzinfo is None:
                                 next_run_local = local_tz.localize(next_run_time_attr)
                             else:
                                 next_run_local = next_run_time_attr.astimezone(local_tz)
                             next_run_str = next_run_local.strftime('%Y-%m-%d %H:%M:%S %Z')
                        else:
                             next_run_str = f"Scheduled ({type(next_run_time_attr)})"

                    else:
                        next_run_str = "Scheduled (next time unknown)"
                else:
                    next_run_str = f"Error: Job '{r.job_id}' not found in JobQueue!"
                    logger.warning(f"Job '{r.job_id}' for reminder {r.id} not found in JobQueue for user {user_id}")


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

async def remove_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int, text: str) -> str:
    """Parses message, finds reminder by ID, removes job from JobQueue, and deletes from DB."""
    parts = text.split()
    if len(parts) != 2:
        return "Invalid format. Use: /delete <Reminder ID>"

    try:
        reminder_id_to_delete = int(parts[1])
    except ValueError:
        return "Invalid Reminder ID. Please provide a number."

    db: Session = SessionLocal()
    try:
        reminder_to_delete = db.query(Reminder).filter(
            Reminder.user_id == user_id,
            Reminder.id == reminder_id_to_delete
        ).first()

        if not reminder_to_delete:
            return f"Reminder with ID {reminder_id_to_delete} not found or does not belong to you."

        job_id = reminder_to_delete.job_id
        reminder_text = reminder_to_delete.reminder_text

        if job_id:
            jobs = context.job_queue.get_jobs_by_name(job_id)
            if jobs:
                for job in jobs:
                    job.schedule_removal()
                logger.info(f"Scheduled removal for job(s) named '{job_id}' for reminder {reminder_id_to_delete}")
            else:
                logger.warning(f"Job '{job_id}' for reminder {reminder_id_to_delete} not found in JobQueue, proceeding with DB deletion.")

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