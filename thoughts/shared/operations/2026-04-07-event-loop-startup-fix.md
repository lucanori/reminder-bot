---
status: completed
created_at: 2026-04-07
files_edited:
  - reminder_bot/bot_service.py
  - reminder_bot/admin/app.py
  - reminder_bot/config.py
rationale: Stabilized startup by reusing the main asyncio loop and removing per-request loop creation in the admin UI.
supporting_docs: []
---

## Summary of changes
- Stabilized non-blocking bot startup for python-telegram-bot v22+ by explicitly initializing/starting the application before polling and by tracking the polling task and main event loop.
- Added a thread-safe bridge from Flask admin routes to the bot event loop, replacing per-request loop creation and `asyncio.run` usages with a shared helper.
- Allowed Pydantic settings to ignore unrelated environment variables to avoid config validation failures in containerized environments.

## Technical reasoning
- The production crash (`Cannot close a running event loop`) and warnings about un-awaited PTB coroutines stemmed from calling `run_polling` without lifecycle setup and from creating/closing event loops inside Flask routes. By storing the main loop and running `initialize`/`start` explicitly, PTB lifecycle coroutines run to completion. A tracked polling task is cancelable during shutdown.
- Flask threads now submit coroutines to the main loop via `run_coroutine_threadsafe`, preventing thread-local loop creation/closure and avoiding `asyncio.run` within running-loop contexts.
- Pydantic now tolerates extra environment variables, avoiding startup failures when additional env keys are present in the deployment environment.

## Impact assessment
- Bot startup should no longer throw event loop closing errors; polling and scheduler initialization remain non-blocking and share the main loop.
- Admin routes execute async repository/service calls safely on the main loop, reducing the risk of loop leaks and reuse issues under threaded Flask.
- Configuration loading is resilient to additional env vars, reducing deployment brittleness.

## Validation steps
- Verified tests locally with dummy secrets:
  - `env -i PATH="$PATH" HOME="$HOME" TELEGRAM_BOT_TOKEN=dummy ADMIN_USERNAME=admin ADMIN_PASSWORD=pass FLASK_SECRET_KEY=secret uv run pytest`
- Reviewed git diff to ensure only bot_service, admin app, and config were modified.
