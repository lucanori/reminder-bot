# /app/data mount with postgres

## Finding

`/app/data` can be removed from `docker-compose.yml` when reminder-bot runs with PostgreSQL.

## Why

- `reminder_bot/db_bootstrap.py:64-67` exits early for PostgreSQL and runs only Alembic migrations.
- `reminder_bot/utils/database.py:14-22` creates directories only for SQLite URLs.
- `reminder_bot/config.py:53-59` builds a PostgreSQL URL from `REMINDER_BOT_DB_*` settings.
- `docker-compose.yml:19-23` sets those PostgreSQL settings explicitly.
- `docker-compose.yml:44-45` already persists Postgres data in `pgdata`.

## Risk

No runtime path in current code depends on `/app/data` for PostgreSQL mode. The only clear use is legacy or fallback SQLite storage.

## Conclusion

Safe to remove `/app/data` mount for the Postgres deployment in `docker-compose.yml`.
