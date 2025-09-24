#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# Install production dependencies
echo "Installing production dependencies..."
uv sync --group production

# Install Tailwind CSS dependencies and build
echo "Installing Tailwind CSS dependencies..."
uv run python manage.py tailwind install

echo "Building Tailwind CSS for production..."
uv run python manage.py tailwind build

# Run Django migrations.
echo "Running migrations..."
uv run python manage.py migrate

# Collect static files.
echo "Collecting static files..."
uv run python manage.py collectstatic --noinput

# Start the server.
echo "Starting server..."
uv run gunicorn NRMP_Simulated.wsgi:application --workers 4 --bind 0.0.0.0:"${PORT:-8000}"

