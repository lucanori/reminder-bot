## Repository research: reminder-bot (current state 2026-04-06)

### Scope and sources
- Read core runtime and orchestration: `reminder_bot/__main__.py` (lines 1-79), `reminder_bot/bot_service.py` (1-250)
- Reviewed configuration and utilities: `reminder_bot/config.py` (1-39), `reminder_bot/utils/database.py` (1-32), `reminder_bot/utils/logging.py` (1-26), `reminder_bot/utils/health.py` (1-114), `reminder_bot/utils/error_recovery.py` (1-272), `reminder_bot/utils/scheduler.py` (1-280)
- Analyzed domain and data access: `reminder_bot/models/entities.py` (1-66), `reminder_bot/models/dtos.py` (1-90), `reminder_bot/repositories/*.py` (base, user, reminder)
- Reviewed interaction layers: `reminder_bot/handlers/command_handlers.py` (1-354), `reminder_bot/handlers/callback_handlers.py` (1-768)
- Business logic: `reminder_bot/services/*.py` (reminder, notification, user; 1-302 / 1-237 / 1-289)
- Admin interface: `reminder_bot/admin/app.py` (1-290), templates `templates/dashboard.html` (1-99), `templates/login.html` (1-45)
- Tests: `tests/e2e/test_system_integration.py` (1-197), unit tests under `tests/unit/services/*.py`, integration test `tests/integration/test_database_integration.py` (1-196), fixtures `tests/conftest.py` (1-125)
- Project metadata: `README.md` (1-403), `.env.example` (1-14), `pyproject.toml` (1-82)

### Architecture overview
- Runtime entrypoint starts both Telegram bot and Flask admin: `__main__.py` spins up `BotService` then runs Flask via a daemon thread (`run_admin_interface`) and starts polling in non-blocking mode (18-85). Signals are trapped for graceful exit (61-67).
- Bot orchestration (`bot_service.py`): builds `Application` with token, wires services and handlers, creates DB tables on init, and recovers scheduled jobs from DB. Supports webhook or polling; `start_polling_non_blocking` uses `application.updater.start_polling` when no webhook is configured (66-88).
- Layering: handlers → services → repositories → database. DTOs mediate between entities and Telegram interactions. Custom exceptions wrap failures.
- Scheduler: `JobScheduler` (scheduler.py) wraps `AsyncIOScheduler` with in-memory job store, schedules per-reminder jobs, chains escalation notifications, and recovers jobs from DB on startup (20-270). Notification attempts escalate interval via `NotificationService.calculate_next_notification_interval` with a 30-minute cap (231-237 of notification_service).
- Persistence: SQLite (default) via async SQLAlchemy; session context manager commits/rolls back (database.py). Entities model users, reminders, notification history; reminder status is tracked with enum-like strings (entities.py 12-66).
- Admin interface: Flask app with login via env credentials, basic dashboard/users pages, JSON APIs for stats and user block/unblock (admin/app.py 39-232). Health endpoint responds with static version “2.0.0” (246-281). Templates are plain HTML in `/templates`.

### Implemented functionality (as coded)
- Telegram commands and flows (`command_handlers.py`):
  - `/start` presents inline menu after access check and user registration (18-58).
  - `/help` returns usage guide (59-95).
  - `/set` conversation collects text → time → interval, creates reminder via `ReminderService`, schedules via `JobScheduler`, replies with summary (96-254).
  - `/view` lists active reminders (255-314).
  - `/delete` prompts for reminder ID (315-329); numeric messages also trigger deletion via callback handler (586-768 in `callback_handlers.py`).
- Inline callbacks (`callback_handlers.py`): menu navigation, templated quick-creates, custom text/time/interval flows, delete buttons, and confirmation/snooze actions delegate to services and scheduler (15-585, 586-768). Custom flows rely on `ContextTypes.DEFAULT_TYPE.user_data` and reuse creation logic.
- Reminder service (`services/reminder_service.py`): CRUD, status transitions, snooze, scheduling math (1-302). Next notification time computed in local tz -> UTC (292-302). Confirmation resets recurring reminders and reschedules jobs if provided a scheduler (141-221).
- Notification service (`services/notification_service.py`): sends messages with inline buttons, deletes previous message if present, logs results, handles confirmation/snooze callbacks, escalates warnings after max attempts, and computes escalating intervals (1-237).
- User service (`services/user_service.py`): registers users on first access (blocklist mode default), enforces whitelist/blocklist, rate limits (30 req/min per user in-memory), and exposes block/unblock/whitelist and statistics methods (1-289).
- Health checking: `BotService.health_check` probes DB, bot.get_me, and scheduler flag (227-250). Separate `HealthChecker` utility provides composite health data when given a bot_service (health.py 11-114).
- Admin API: JSON endpoints for stats and users; POST APIs to block/unblock users (122-232). Login page and dashboard exist; routes rely on synchronous Flask templates.

### Notable gaps, risks, and inconsistencies
- Admin UI is partially broken:
  - Route `/users` renders `users.html`, but that template is missing (admin/app.py 122-126 vs templates directory).
  - Dashboard template links to `whitelist_user` / `block_user` routes that are not implemented; only `/api/...` JSON routes exist, so buttons would 404 (dashboard.html 76-88; admin/app.py lacks matching routes).
  - Health endpoint returns hardcoded version “2.0.0” and does not surface scheduler/bot checks (admin/app.py 246-281).
- Tests vs repository contents:
  - E2E test expects `scripts/deploy.sh`, `scripts/backup.sh`, `scripts/restore.sh`, `scripts/validate.sh` to exist and be executable (tests/e2e/test_system_integration.py 185-197), but the `scripts/` directory is absent. This will fail.
  - Packaging excludes `scripts*` in `pyproject.toml` (45-48), reinforcing the absence.
- Admin/bot coupling: `__main__.py` starts Flask in a background thread; Flask uses async DB calls wrapped with `asyncio.run` inside threads, which is brittle and may leak loops (admin/app.py 72-118, 128-178, 180-232).
- Scheduler persistence: APScheduler uses in-memory store; recovery relies on DB state and runs at startup, but in-memory jobs are lost on process restarts (scheduler.py 20-83, 222-270).
- Access control and preferences: User preferences exist in DTO but are stored as JSON string on `UserEntity.notification_preferences`; no admin or bot flows expose these settings, and default timezone is global (user_service.py 198-230).
- Observability: README advertises structured logging and health monitoring; logging is JSON via structlog, but no tracing/metrics exporters are implemented. Health endpoints exist but minimal; no readiness/liveness separation.
- Dependency surface: FastAPI/uvicorn listed as dependencies but unused; admin is Flask-only.
- Versioning: runtime version uses package metadata; in development it returns “dev” (utils/version.py 7-11). Admin health hardcodes 2.0.0 causing mismatch.
- Webhook mode: `_setup_webhook` sets webhook URL without certificate/support for drop_pending settings; only basic webhook configuration present (bot_service.py 185-201).
- Potential Telegram API mismatch: `Application.updater.start_polling` is used; upstream ptb v22 may not expose `.updater` by default when built without `.updater()`; risk of runtime error if updater is None (bot_service.py 66-88).
- Admin static assets: dashboard/login reference only inline styles; logo served from root templates folder, not `reminder_bot/admin/templates` (admin/app.py 234-244). Duplicate template locations may confuse Flask configuration.

### Tests and quality signals
- Unit tests cover services (notification, reminder, user) using in-memory SQLite fixtures and mocked bots; they validate CRUD, escalation, rate limiting, and callback handling (`tests/unit/services/*.py`).
- Integration test covers end-to-end reminder lifecycle, access control, status transitions, concurrency, and DB rollback (`tests/integration/test_database_integration.py`).
- E2E/system test is mostly scaffolding; it monkeypatches settings and asserts existence of config files and missing scripts (test_system_integration.py).
- Pyproject enforces strict type checking (pyright strict) and Ruff lint/format. No CI config checked yet; GitHub workflows exist for docker publish/release (not read in detail).

### Configuration and deployment
- Required env vars: `TELEGRAM_BOT_TOKEN`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `FLASK_SECRET_KEY`; optional: `DATABASE_URL`, `BOT_MODE` (blocklist/whitelist), `LOG_LEVEL`, `DEBUG`, `DEFAULT_NOTIFICATION_INTERVAL`, `MAX_NOTIFICATIONS_PER_REMINDER`, `TELEGRAM_WEBHOOK_URL`, `TIMEZONE` (README 62-145; config.py 6-22).
- Default DB path points to `/data/reminders.db`; docker-compose files provide containerization (not reviewed in depth). Entry flow uses `uv run python -m reminder_bot` per README.

### Current state snapshot
- Core reminder, notification, scheduling, and Telegram interaction flows are implemented and reasonably tested at the service layer.
- Admin interface and operational tooling are incomplete (missing templates and scripts) and will currently break advertised features and tests.
- Health/observability and webhook/polling startup exist but have rough edges and potential runtime issues.
