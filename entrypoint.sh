#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Run Django migrations.
echo "Running migrations..."
uv run --no-sync python manage.py migrate --noinput

# Start the server. exec makes gunicorn PID 1 so it receives the platform's stop signal.
echo "Starting server..."
exec uv run --no-sync gunicorn NRMP_Simulated.wsgi:application \
    --workers "${WEB_CONCURRENCY:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-30}" \
    --bind 0.0.0.0:"${PORT:-8000}"
