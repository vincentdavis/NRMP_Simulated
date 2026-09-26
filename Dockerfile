# syntax=docker/dockerfile:1

# --- Stage 1: build the Tailwind CSS -----------------------------------------------------------------------------
FROM node:24-alpine AS css
WORKDIR /src
COPY theme/static_src/package.json theme/static_src/package-lock.json theme/static_src/
RUN cd theme/static_src && npm ci --no-audit --no-fund
# Tailwind reads the templates and app code for class names (see theme/static_src/src/styles.css).
COPY templates templates
COPY theme theme
COPY nrmps nrmps
RUN cd theme/static_src && npm run build

# --- Stage 2: the application ----------------------------------------------------------------------------------
FROM ghcr.io/astral-sh/uv:python3.14-alpine

# Compile bytecode at install time; never let `uv run` re-sync at runtime; put the virtualenv on PATH.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_SYNC=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Runtime and production dependencies only (no dev tools). This layer is reused when only the code changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --group prod --no-install-project

COPY . .
COPY --from=css /src/theme/static/css/dist theme/static/css/dist

# Collect static files (WhiteNoise serves them, compressed and with hashed names). Settings refuse to load in
# production mode without a secret key and a database, so the build uses placeholders; nothing touches a database.
RUN DEBUG=False SECRET_KEY=build-only-placeholder DATABASE_URL=sqlite:///:memory: LOGFIRE_SEND_TO_LOGFIRE=false \
    python manage.py collectstatic --noinput

# Run as an unprivileged user.
RUN addgroup -S app && adduser -S -G app -H app
USER app

EXPOSE 8000
CMD ["/bin/sh", "/app/entrypoint.sh"]
