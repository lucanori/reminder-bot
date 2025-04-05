# Reminder Bot

A Telegram bot built with Python and Docker to help your users to schedule and receive reminders. It also includes an admin interface for user management.

## Features

*   **Telegram Bot:**
    *   Set reminders via interactive buttons.
    *   View currently active reminders.
    *   Delete reminders.
*   **Admin Web Interface:**
    *   Accessible via a web browser (default: `http://localhost:5011/`).
    *   Login using configurable admin credentials.
    *   View users who have interacted with the bot.
    *   Manage user access: Block users (`blocklist` mode) or Whitelist users (`whitelist` mode).
*   **Dockerized:** Runs reliably using Docker Compose.
*   **User Permissions:** Runs application processes as a non-root user inside the container, configurable via environment variables.
*   **Persistent Storage:** Uses SQLite for storing reminder and user data.

## Running with Docker

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/LucaNori/reminder-bot.git
    cd reminder-bot
    ```
2.  **Create `.env` file:**
    Copy the `.env.example` file to `.env` and fill in the required values:
    ```bash
    cp .env.example .env
    # Now edit .env with your configuration
    ```
    See the [Configuration](#configuration) section below for details on the variables.
3.  **Build and Start the Container:**
    Use Docker Compose to build the image (if needed) and start the services in detached mode:
    ```bash
    docker compose up -d --build
    ```
    The bot and the admin interface will start.

4.  **Check Logs (Optional):**
    ```bash
    docker compose logs -f
    ```

5.  **Stop the Container:**
    ```bash
    docker compose down
    ```

## Configuration

Configure the bot using environment variables. You can set these directly or place them in a `.env` file in the project root.

*   `BOT_TOKEN` (Required): Your Telegram Bot API token obtained from [BotFather](https://t.me/BotFather).
*   `ADMIN_USERNAME` (Required): Username for the admin web interface login.
*   `ADMIN_PASSWORD` (Required): Password for the admin web interface login.
*   `BOT_MODE` (Optional): Controls user access. Can be `whitelist` or `blocklist`. Defaults to `blocklist`.
    *   `blocklist`: All users can interact initially, admins can block specific users.
    *   `whitelist`: Only users explicitly added by an admin can interact.
*   `FLASK_SECRET_KEY` (Required): A secret key for Flask session management in the admin interface. Generate a secure random key.
*   `UID` (Optional): User ID for the application process inside the container. Defaults to `1000`.
*   `GID` (Optional): Group ID for the application process inside the container. Defaults to `1000`.
*   `UMASK` (Optional): Umask for the application process inside the container. Defaults to `0022`.

## Admin Interface

*   **Access:** By default, the admin interface is available at `http://localhost:5011/`.
*   **Login:** Use the `ADMIN_USERNAME` and `ADMIN_PASSWORD` configured in your environment variables.
*   **Functionality:**
    *   View a list of all users who have started the bot.
    *   Depending on the `BOT_MODE`:
        *   In `blocklist` mode: Block specific users from interacting with the bot.
        *   In `whitelist` mode: Add specific users to allow them to interact with the bot.

## Usage (Telegram Bot)

Interact with the bot directly in your Telegram chat:

1.  Start a chat with your bot.
2.  Use the interactive buttons provided:
    *   **Set Reminder:** Guides you through setting the medication name and time.
    *   **View Reminders:** Displays your currently scheduled reminders.
    *   **Delete Reminder:** Allows you to select and delete an existing reminder.
3.  The main menu buttons reappear after most actions for easy navigation.

## Dependencies

Python dependencies are listed in `requirements.txt`. The application relies on:

*   `python-telegram-bot`: For Telegram Bot API interaction.
*   `APScheduler`: For scheduling reminders.
*   `Flask`: For the admin web interface.
*   `SQLAlchemy`: For database interaction (SQLite).
*   `python-dotenv`: For loading environment variables.
*   `supervisor`: For process management within the container.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.