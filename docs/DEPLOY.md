# Deploying NRMP Simulated

Production runs on [Railway](https://railway.com) at **https://nrmp-simulated.heteroskedastic.org**, built from
the `Dockerfile` in this repository. Environment variables are listed in [`.env.example`](../.env.example).

> **Status.** This guide describes the deployment as of the latest step in
> [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md). Sections marked *Planned* describe where later steps take
> it; they were written for an earlier implementation that was lost, and nothing in them exists yet.

## Services

| Service | Source | Config | Start command |
|---|---|---|---|
| **web** | this repo (Dockerfile) | `railway.json` | `entrypoint.sh`: gunicorn |
| **Postgres** | Railway PostgreSQL | – | – |

`railway.json` (Railway reads it from the repository root) sets:
- the **pre-deploy command** `python manage.py migrate --noinput`. It runs once per deploy, in the new image, before
  the new version receives traffic, so replicas never race to migrate;
- the **health check** `GET /healthz`, which returns 200 only when the database answers. If a new deployment never
  becomes healthy, Railway keeps the previous one running;
- restart on failure (up to 5 times).

*Planned (step 2.5):* an optional worker service for background jobs.

## The image

The multi-stage `Dockerfile`:
1. builds the Tailwind CSS in a Node stage, so Node is not in the final image;
2. installs the runtime and `prod` dependencies only (`uv sync --locked --no-dev --group prod`) in a cached layer;
3. runs `collectstatic` with placeholder settings (`DEBUG=False`, a throwaway `SECRET_KEY`, an in-memory SQLite
   `DATABASE_URL`; none of them end up in the image). WhiteNoise then serves compressed files with hashed names and
   year-long cache headers;
4. runs as an unprivileged user.

`entrypoint.sh` starts gunicorn. Variables: `WEB_CONCURRENCY` (workers, default 2; each takes roughly 150 MB),
`GUNICORN_TIMEOUT` (seconds, default 30) and `MIGRATE_ON_START=1` to run migrations at start-up instead of in the
pre-deploy command (docker-compose does this).

CI builds the image on every push, starts it with SQLite and checks `/healthz` and the home page.

## Checklist before the first deploy of this version (decision D0)

Earlier versions defaulted to `DEBUG=True` and had a fallback `SECRET_KEY` committed to the repository. This
version refuses to start without real settings. In Railway, open **web → Variables** and:

1. **Set `SECRET_KEY`** to a new random value, for example the output of
   `python -c "import secrets; print(secrets.token_urlsafe(50))"`. Do not reuse the old key from the repository:
   it is public. Everyone will have to sign in again.
2. **Check `DATABASE_URL`.** It must reference the Postgres service, for example `${{Postgres.DATABASE_URL}}`.
   Without it the app stops at startup instead of silently using a throwaway SQLite file.
3. **Remove `DEBUG`**, or set it to `False`.
4. Optional: set `LOGFIRE_TOKEN` (without it, Logfire sends nothing) and `CONTACT_EMAIL`, the address the contact
   and privacy pages give for account and data requests (without it they point to the issue tracker only).

Then deploy, and check in the deploy logs that the pre-deploy step ran the migrations. `ALLOWED_HOSTS` defaults to
`localhost,127.0.0.1,nrmp-simulated.heteroskedastic.org`; on Railway, `RAILWAY_PUBLIC_DOMAIN` and the health-check
host `healthcheck.railway.app` are always added. Set `ALLOWED_HOSTS` explicitly to serve other domains.

The number of gunicorn workers is now 2 by default (it was 4). Set `WEB_CONCURRENCY` if the plan has memory for
more.

If the deploy fails because a variable is missing, the logs say which one (`SECRET_KEY must be set when DEBUG is
off`, `DATABASE_URL must be set when DEBUG is off`).

Create an admin account from a Railway shell on the web service: `python manage.py createsuperuser`.

## HTTPS

Railway terminates TLS and forwards `X-Forwarded-Proto`. With `DEBUG` off the app:
- trusts that header (`SECURE_PROXY_SSL_HEADER`), so same-origin form posts pass Django's CSRF origin check;
- redirects HTTP to HTTPS (`SECURE_SSL_REDIRECT`, exempting a future `/healthz`);
- sets secure session and CSRF cookies;
- sends HSTS with `max-age=3600` (`SECURE_HSTS_SECONDS`).

Once HTTPS is confirmed everywhere, raise `SECURE_HSTS_SECONDS` to `31536000`. Subdomains and preload stay off on
purpose, so their deploy-check warnings (`security.W005`, `security.W021`) are silenced in the settings; CI runs
`manage.py check --deploy --fail-level WARNING`, so any other warning fails the build.

## Email (*Planned*, step 1.9)

Verification and password-reset links will need outgoing email: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` and `DEFAULT_FROM_EMAIL` for any SMTP provider.

## Background jobs, clean-up and operations (*Planned*, step 2.5)

Long simulation steps will run as `django.tasks` jobs, optionally in a worker service (`manage.py db_worker`), with a
periodic clean-up command and a staff operations page.

## Backups and restore

- In the Postgres service, open **Backups** and enable scheduled backups (daily, keep at least 7).
- For a manual backup: `pg_dump --format=custom --no-owner "$DATABASE_URL" > nrmp-$(date +%F).dump`.
- For a restore drill, into a scratch database first:
  `pg_restore --clean --no-owner --dbname "$SCRATCH_DATABASE_URL" nrmp-YYYY-MM-DD.dump`. Then point a local run at
  it (`DATABASE_URL=… python manage.py check`) and open a few simulations.

## Rollback

Redeploy an earlier deployment from the Railway dashboard. Migrations are forward-only, so check the release notes
of the version you are rolling back from before rolling back across a migration.

## Local development

Copy `.env.example` to `.env`; it sets `DEBUG=True`, which uses a development `SECRET_KEY` and a local
`db.sqlite3`. Then `uv run python manage.py runserver`. The test suite (`uv run pytest`) runs the production
configuration against an in-memory SQLite database; set `NRMP_TEST_DATABASE_URL` to run it against PostgreSQL.

`docker compose up --build` starts PostgreSQL and the production image (DEBUG off, gunicorn) at
http://localhost:8000, over plain HTTP (`SECURE_SSL_REDIRECT=False`, `SECURE_COOKIES=False`).
