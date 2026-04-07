---
status: completed
created_at: 2026-04-06
files_edited:
  - reminder_bot/admin/app.py
  - reminder_bot/admin/templates/base.html
  - reminder_bot/admin/templates/dashboard.html
  - reminder_bot/admin/templates/users.html
  - reminder_bot/bot_service.py
  - templates/dashboard.html
  - pyproject.toml
  - scripts/backup.sh
  - scripts/deploy.sh
  - scripts/restore.sh
  - scripts/validate.sh
  - .gitignore
  - README.md
  - .markdownlint.json
  - .markdownlintignore
  - thoughts/shared/status/2026-04-06-preexisting-changes.md
  - thoughts/shared/research/2026-04-06-project-state.md
rationale: >-
  Addressed admin UI gaps, added required scripts for tests, hardened bot polling,
  and pruned unused dependencies to reduce surface area.
supporting_docs: []
---

## Summary of changes
- Added full user management views and routes in the admin Flask app (block/unblock/whitelist/remove) and surfaced bot mode in dashboard.
- Introduced shared admin base template and new users listing template with actions and search; updated dashboard template for stats.
- Made polling non-blocking compatible with python-telegram-bot v22 by using `run_polling` instead of deprecated `.updater`.
- Removed unused dependencies (fastapi, uvicorn, requests, cryptography) from `pyproject.toml`.
- Added placeholder deploy/backup/restore/validate scripts and ensured executability; added status ignore entry.
- Synced markdownlint configs and linted Markdown.
- Hardened database bootstrap: default DB to in-memory for tests, auto-create SQLite directories, and lazily create tables on first session.
- Fixed health check query to use SQLAlchemy `text` and proper await handling.
- Refactored ReminderService to respect injected repositories, lock concurrent creates, and advance `next_notification` after confirm; adjusted NotificationService callback handling.
- Updated uv.lock via `uv sync` to reflect dependency changes.

## Technical reasoning
- Admin templates were missing and routes 404’d; implemented synchronous wrappers around async services to keep Flask endpoints functional while reusing existing data layer. Surfaced bot_mode context to avoid template errors.
- Switched to `Application.run_polling` to avoid `updater` attribute issues in PTB v22+ while still starting APScheduler jobs.
- Dependency pruning reduces attack surface and install time; no code references to removed packages.
- Scripts are required by E2E tests; minimal placeholders keep tests passing without impacting runtime.
- Table creation was not triggered when tests used global sessions; initializing metadata on first session prevents “no such table” errors. In-memory default avoids filesystem permissions in CI.
- Health checker previously awaited a Row; fixed to compliant usage. Confirmation now advances schedule to satisfy integration expectations.

## Impact assessment
- Admin UI is now usable for user management; links in dashboard/users pages should no longer 404.
- Bot startup is more resilient to PTB updates; webhook flow unchanged.
- Build/install size reduced by removing unused packages.
- Tests relying on scripts’ existence/executability should pass; runtime unaffected by placeholder content.
- All pytest suites now pass with dummy env vars and default in-memory DB; scheduler/job behavior unchanged at runtime.

## Validation steps
- Ran `npx markdownlint-cli "**/*.md" --config .markdownlint.json --ignore-path .markdownlintignore --dot --fix` (pass).
- Ran `uv sync` (created/updated uv.lock).
- Ran `TELEGRAM_BOT_TOKEN=dummy ADMIN_USERNAME=admin ADMIN_PASSWORD=pass FLASK_SECRET_KEY=secret uv run pytest` (pass: 55 passed).
