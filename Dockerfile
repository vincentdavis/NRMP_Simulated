FROM ghcr.io/astral-sh/uv:python3.14-alpine

# Install Node.js and npm (required for django-tailwind)
RUN apk add --no-cache nodejs npm

# Compile bytecode at install time; never re-sync the environment when `uv run` starts a command.
ENV UV_COMPILE_BYTECODE=1 \
    UV_NO_SYNC=1 \
    PYTHONUNBUFFERED=1

# Create and change to the app directory.
WORKDIR /app

# Copy local code to the container image (see .dockerignore).
COPY . .

# Install runtime and production dependencies only: no dev tools in the image.
RUN uv sync --frozen --no-dev --group prod

# Build the Tailwind CSS and collect static files (WhiteNoise serves them). Settings refuse to load in production
# mode without a secret key and a database, so the build uses placeholders; nothing here touches a database.
RUN export DEBUG=False SECRET_KEY=build-only-placeholder DATABASE_URL=sqlite:///:memory: \
        LOGFIRE_SEND_TO_LOGFIRE=false \
    && uv run python manage.py tailwind install \
    && uv run python manage.py tailwind build \
    && uv run python manage.py collectstatic --noinput

# Entrypoint script: apply migrations, then start gunicorn.
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Run the app using the script.
CMD ["/app/entrypoint.sh"]
