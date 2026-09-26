# Deploying NRMP Simulated

Production runs on [Railway](https://railway.com) at **https://nrmp-simulated.heteroskedastic.org**, built from
the `Dockerfile` in this repository. Every environment variable is listed in [`.env.example`](../.env.example).

## Services

| Service | Source | Config file | Start command |
|---|---|---|---|
| **web** | this repo | `railway.json` | Dockerfile `CMD` (`entrypoint.sh` → gunicorn) |
| **Postgres** | Railway PostgreSQL | – | – |
| **worker** (optional) | this repo | `railway.worker.json` | `python manage.py db_worker --queue-name default` |

`railway.json` sets:
- the pre-deploy command `python manage.py predeploy`, which applies migrations and creates the cache table before
  the new version receives traffic;
- the health check `GET /healthz`. It returns 200 only when the database answers. If the new deployment never
  becomes healthy, Railway keeps the previous one running.

## Checklist before the first deploy of this version (decision D0)

Earlier versions defaulted to `DEBUG=True` and had a fallback `SECRET_KEY` committed to the repository. This
version refuses to start without real settings. In Railway, open **web → Variables** and:

1. **Set `SECRET_KEY`** to a new random value, for example the output of
   `python -c "import secrets; print(secrets.token_urlsafe(50))"`. Do not reuse the old key from the repository:
   it is public. Everyone will have to sign in again.
2. **Check `DATABASE_URL`.** It must reference the Postgres service, for example `${{Postgres.DATABASE_URL}}`.
   Without it the app stops at startup instead of silently using a throwaway SQLite file.
3. **Remove `DEBUG`**, or set it to `False`.
4. Optional: set `LOGFIRE_TOKEN`, the email variables (below) and `CONTACT_EMAIL`.

Then deploy. The custom domain and the Railway domain are already allowed: `ALLOWED_HOSTS` defaults to
`nrmp-simulated.heteroskedastic.org`, and `RAILWAY_PUBLIC_DOMAIN` and `healthcheck.railway.app` are always added.
CSRF origins are derived from the same list.

Create an admin account from a Railway shell on the web service: `python manage.py createsuperuser`.

## HTTPS

Railway terminates TLS and forwards `X-Forwarded-Proto`. With `DEBUG` off the app:
- trusts that header (`SECURE_PROXY_SSL_HEADER`);
- redirects HTTP to HTTPS, except `/healthz`;
- sets secure session and CSRF cookies;
- sends HSTS with `max-age=3600`.

Once HTTPS is confirmed everywhere, raise `SECURE_HSTS_SECONDS` to `31536000`. Subdomains and preload stay off on
purpose. `manage.py check --deploy` therefore reports `security.W005` and `security.W021`, and those two are the
only accepted warnings.

## Email

Verification and password-reset links need outgoing email. Set:
- `EMAIL_HOST`, `EMAIL_PORT` (587), `EMAIL_HOST_USER` and `EMAIL_HOST_PASSWORD` for any SMTP provider (Postmark,
  SendGrid, Mailgun, SES…);
- `EMAIL_USE_TLS=True`;
- `DEFAULT_FROM_EMAIL`, on a domain the provider is allowed to send for.

Check delivery with `python manage.py sendtestemail you@example.com`.

Without `EMAIL_HOST`:
- emails are written to the log;
- `NRMP_REQUIRE_VERIFIED_EMAIL` defaults to off, so unverified accounts can still run simulations, with the smaller
  unverified quota.

With email configured, verification is required before a user can generate populations or start runs.

## Background jobs

Simulation runs use Django's task framework (`django.tasks`):
- `TASK_BACKEND=immediate` (default) runs a job inside the web request that starts it. Runs are then capped at
  `NRMP_MAX_PAIRS_IMMEDIATE` applicant × program pairs (2 million by default), so they finish well inside the
  gunicorn timeout.
- `TASK_BACKEND=database` stores jobs in the database (django-tasks-db), and a worker process executes them. Larger
  markets are then allowed, up to `NRMP_MAX_PAIRS_WORKER` (20 million by default).

To enable the worker:
1. Add a service from this repository and set its config file path to `railway.worker.json`.
2. Give it the same variables as the web service. Shared variables work well for this: `SECRET_KEY`,
   `DATABASE_URL`, `LOGFIRE_TOKEN`, email.
3. Set `TASK_BACKEND=database` on both services.

The worker needs no public domain or health check.

## Periodic clean-up

`python manage.py nrmp_cleanup` does four things:

- marks runs stuck in queued or running for more than two hours as failed (a worker stopped);
- deletes runs older than `NRMP_RUN_RETENTION_DAYS` (180 by default);
- deletes django-axes sign-in records older than 30 days (the privacy page promises this);
- with the database task backend, prunes finished task records.

Run it daily: add a Railway service from this repository with that start command and a cron schedule (for example
`17 4 * * *`), the same variables as the web service, and no health check.

## Operations page

Staff users see `/ops/`: runs per day, failures, run-time percentiles, the task queue, the heaviest users and the
largest markets. `/healthz` also reports the queue (without failing) when `TASK_BACKEND=database`.

## Backups and restore

- In the Postgres service, open **Backups** and enable scheduled backups (daily, keep at least 7).
- For a manual backup: `pg_dump --format=custom --no-owner "$DATABASE_URL" > nrmp-$(date +%F).dump`.
- For a restore drill, into a scratch database first:
  `pg_restore --clean --no-owner --dbname "$SCRATCH_DATABASE_URL" nrmp-YYYY-MM-DD.dump`. Then point a local run at
  it (`DATABASE_URL=… python manage.py check`) and open a few simulations.

## Rollback

Redeploy an earlier deployment from the Railway dashboard. Migrations are forward-only, so check the release notes
of the version you are rolling back from before rolling back across a migration.

## Local production-like stack

`docker compose up --build` starts PostgreSQL, the web app (DEBUG off, gunicorn) and the worker. The app is then at
http://localhost:8000. Day-to-day development uses `DEBUG=True` in `.env` with SQLite and `manage.py runserver`;
see the README.
