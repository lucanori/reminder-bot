# syntax=docker/dockerfile:1

FROM python:3.15.0a8

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=true \
    TZ=UTC

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    tzdata \
    jq \
    coreutils \
    bash \
    catatonit \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./

RUN SETUPTOOLS_SCM_PRETEND_VERSION_FOR_TELEGRAM_REMINDER_BOT=0.0.0 uv sync --frozen --no-dev --no-editable

COPY . .

RUN mkdir -p /app/data && chown -R nobody:nogroup /app && chmod -R 755 /app && chmod 777 /app/data

USER nobody:nogroup

EXPOSE 8000

ENTRYPOINT ["/usr/bin/catatonit", "--", "/app/.venv/bin/python", "-m", "reminder_bot"]
