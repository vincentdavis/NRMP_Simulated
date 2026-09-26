#!/bin/sh
# Start the web server. On Railway, migrations run once per deploy as the pre-deploy command (railway.json);
# set MIGRATE_ON_START=1 to run them here instead (docker-compose does).

# Exit immediately if a command exits with a non-zero status.
set -e

if [ "${MIGRATE_ON_START:-0}" = "1" ]; then
    echo "Running migrations..."
    python manage.py migrate --noinput
fi

# exec makes gunicorn PID 1 so it receives the platform's stop signal.
echo "Starting gunicorn..."
exec gunicorn NRMP_Simulated.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --timeout "${GUNICORN_TIMEOUT:-30}"
