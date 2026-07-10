# syntax=docker/dockerfile:1

FROM python:3.14.5-alpine3.23@sha256:5a824eb82cc75361f98611f3cfc5091ea33f10a6ccea4d4ebdabbc523b9a1614 AS builder

ENV UV_NO_CACHE=true \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3 \
    SETUPTOOLS_SCM_PRETEND_VERSION_FOR_TELEGRAM_REMINDER_BOT=0.0.0

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.11.28@sha256:0f36cb9361a3346885ca3677e3767016687b5a170c1a6b88465ec14aefec90aa /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-editable

COPY . .

FROM python:3.14.5-alpine3.23@sha256:5a824eb82cc75361f98611f3cfc5091ea33f10a6ccea4d4ebdabbc523b9a1614 AS runtime

RUN apk upgrade --no-cache \
    && apk add --no-cache ca-certificates tzdata catatonit \
    && rm -rf /usr/local/lib/python3.14/site-packages/pip /usr/local/lib/python3.14/site-packages/pip-*.dist-info /usr/local/bin/pip*

WORKDIR /app

COPY --from=builder /app /app

RUN mkdir -p /app/data && chown -R nobody:nobody /app && chmod -R 755 /app && chmod 777 /app/data

USER nobody:nobody

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys;r=urllib.request.urlopen('http://localhost:8000/health',timeout=2);sys.exit(r.status!=200)"]

ENTRYPOINT ["/usr/bin/catatonit", "--", "/app/.venv/bin/python", "-m", "reminder_bot"]
