#!/bin/bash

/app/.venv/bin/python -m reminder_bot.db_bootstrap
exec /app/.venv/bin/python -m reminder_bot "$@"
