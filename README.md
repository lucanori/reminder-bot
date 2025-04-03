# Telegram Reminder Bot

A simple Telegram bot built with Python and Docker to help users schedule and receive reminders for any task.

## Features

*   Set reminders for any text at a given time (HH:MM).
*   Schedule reminders to repeat daily or every N days.
*   View currently active reminders.
*   Delete reminders by their ID.
*   Persistent storage of reminders using SQLite (by default).
*   Runs inside a Docker container for easy deployment.

## Tech Stack

*   Python 3.10+
*   `python-telegram-bot`
*   `APScheduler`
*   `SQLAlchemy` (with SQLite backend)
*   `python-dotenv`
*   Docker & Docker Compose

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd medi-reminder-bot
    ```
2.  **Create `.env` file:**
    Copy the example or create a `.env` file in the project root with the following content:
    ```dotenv
    TELEGRAM_BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
    DATABASE_URL=sqlite:////app/data/reminders.db
    TIMEZONE=Europe/Rome # Optional: Set your timezone (e.g., America/New_York)
    DEBUG=false # Optional: Set to true for more logs
    ```
    *   Replace `YOUR_TELEGRAM_BOT_TOKEN` with the token obtained from [BotFather](https://t.me/BotFather) on Telegram.
    *   The default `DATABASE_URL` uses SQLite and stores the database file in a `./data` directory (created automatically if it doesn't exist).
    *   Set `TIMEZONE` to a valid [TZ database name](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) for accurate scheduling.

3.  **Build the Docker image:**
    ```bash
    docker compose build
    ```

## Running the Bot

1.  **Start the container:**
    ```bash
    docker compose up -d
    ```
    The bot will start running in the background.

2.  **Check logs (optional):**
    ```bash
    docker compose logs -f reminder-bot
    ```

3.  **Stop the container:**
    ```bash
    docker compose down
    ```

## Usage (Telegram Commands)

Interact with the bot on Telegram:

*   `/start` or `/help`: Show the welcome message and command list.
*   `/set <Reminder Text> <HH:MM> [every <N> days]`: Set a new reminder. The text can be multiple words.
    *   Example (daily): `/set Take out the trash 08:00`
    *   Example (every 3 days): `/set Water the plants 18:30 every 3 days`
*   `/view`: Show all your active reminders with their IDs and next scheduled time.
*   `/delete <Reminder ID>`: Delete a reminder using the ID obtained from `/view`.
    *   Example: `/delete 12`

## Project Structure

```
.
├── Dockerfile              # Defines the Docker image build process
├── docker-compose.yml      # Docker Compose configuration
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (ignored by git)
├── .gitignore              # Specifies intentionally untracked files that Git should ignore
├── models.py               # SQLAlchemy database models
├── reminders.py            # Logic for managing reminders (add, view, delete, send)
├── run_reminder_bot.py     # Main application script
├── PROJECT_PLAN.md         # Initial project plan document
└── README.md               # This file