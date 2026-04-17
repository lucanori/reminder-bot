## Worktree status (2026-04-08)

### Modified files
- pyproject.toml, uv.lock: added croniter, reorganized dev deps.
- reminder_bot/models/{entities,dtos}.py: added weekday/cron fields and validation.
- reminder_bot/services/reminder_service.py: added cron/weekday scheduling, confirmation flow refactor, timezone recompute fixes.
- reminder_bot/utils/{scheduler,transformers}.py: cron/weekday scheduling and DTO mapping.
- reminder_bot/handlers/callback_handlers.py: weekly day picker, cron entry, interval formatting updates.
- tests/conftest.py and numerous new test modules for services, repos, handlers, scheduler, bot_service, main.

### Added files
- .coveragerc: excludes admin dashboard from coverage.
- alembic/versions/001_initial_schema.py: migration including weekday/cron columns.
- tests/unit/services/test_reminder_recurrence.py and extended suites for services, repos, handlers, scheduler.

### Notes
- Coverage now ~70% overall (handlers included); admin UI excluded.
- Pending: investigate recurrence bug causing extra notifications outside schedule (see user logs).
