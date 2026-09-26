#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Run Django migrations.
echo "Running migrations..."
uv run python manage.py migrate

# Start the server.
echo "Starting server..."
uv run gunicorn NRMP_Simulated.wsgi:application --workers 4 --bind 0.0.0.0:"${PORT:-8000}"
