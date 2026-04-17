## Worktree status (2026-04-07)

### Modified files
- .gitignore: added ruff cache ignore entry.
- docker-compose.local.yml: tweaked env block formatting and removed unused TZ passthrough.
- reminder_bot/admin/app.py: switched admin routes to share the bot event loop via run_async_safely helper.
- reminder_bot/bot_service.py: stored main event loop, initializes/starts PTB before polling, tracks polling task, and added thread-safe coroutine runner.
- reminder_bot/config.py: pydantic settings now ignore extra env vars.

### Added files
- AGENTS.md: project rules (no code comments; always run lint and tests).
- thoughts/shared/operations/2026-04-07-event-loop-startup-fix.md: operation record for event loop fixes.

### Notes
- Pending: investigate current container logs from docker-compose.local and address runtime errors reported after user test.
