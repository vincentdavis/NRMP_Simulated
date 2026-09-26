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
| **worker** (optional) | this repo (Dockerfile) | `railway.worker.json` | `manage.py nrmp_worker` |
| **cleanup** (cron) | this repo (Dockerfile) | `railway.cron.json` | `manage.py nrmp_cleanup`, daily at 03:17 UTC |
| **Postgres** | Railway PostgreSQL | – | – |

`railway.json` (Railway reads it from the repository root) sets:
- the **pre-deploy command** `python manage.py migrate --noinput`. It runs once per deploy, in the new image, before
  the new version receives traffic, so replicas never race to migrate;
- the **health check** `GET /healthz`, which returns 200 only when the database answers. If a new deployment never
  becomes healthy, Railway keeps the previous one running;
- restart on failure (up to 5 times).

The worker and cron services use the same image; in each service's settings, point **Config-as-code** at its file.
Give them the same variables as the web service (at least `SECRET_KEY`, `DATABASE_URL` and `TASK_BACKEND`).

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

Every run stores the commit it ran on (docs/model_spec.md §12.11): Railway provides `RAILWAY_GIT_COMMIT_SHA`;
elsewhere build with `docker build --build-arg GIT_SHA=$(git rev-parse HEAD) .`.

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

**Phase 2 data change (decision D3).** The deploy that brings model 2.0 (migrations `0013`–`0015`) converts each
simulation's configuration to the new parameters where a field has an equivalent and **deletes the legacy
populations, interview rows and matches**, which the pre-fix model produced. Simulations, their names and owners stay.
Take a backup first if you want to keep the old rows (see [Backups and restore](#backups-and-restore)).

## Size and memory settings

| Variable | Default | Meaning |
|---|---|---|
| `NRMP_MAX_PAIRS` | 1000000 | Largest applicants × programs of one run executed inside the web request (`TASK_BACKEND=immediate`); keep it well within the gunicorn timeout. |
| `NRMP_MAX_PAIRS_WORKER` | 10000000 | The same limit when a worker executes runs (`TASK_BACKEND=database`). |
| `NRMP_BLOCK_PAIRS` | 250000 | Pairs the engine computes at a time: about 100 bytes each, so 25 MB by default. Results do not depend on it. |
| `NRMP_DRILLDOWN_MAX_PAIRS` | 2000000 | Largest market for which one agent's page shows the other side's ranks and the pairs CSV is offered (both recompute every pair). |

## HTTPS

Railway terminates TLS and forwards `X-Forwarded-Proto`. With `DEBUG` off the app:
- trusts that header (`SECURE_PROXY_SSL_HEADER`), so same-origin form posts pass Django's CSRF origin check;
- redirects HTTP to HTTPS (`SECURE_SSL_REDIRECT`, exempting a future `/healthz`);
- sets secure session and CSRF cookies;
- sends HSTS with `max-age=3600` (`SECURE_HSTS_SECONDS`).

Once HTTPS is confirmed everywhere, raise `SECURE_HSTS_SECONDS` to `31536000`. Subdomains and preload stay off on
purpose, so their deploy-check warnings (`security.W005`, `security.W021`) are silenced in the settings; CI runs
`manage.py check --deploy --fail-level WARNING`, so any other warning fails the build.

**Content Security Policy.** Every response carries a report-only policy (`SECURE_CSP_REPORT_ONLY` in the settings):
scripts, styles, images and connections from the site itself only, one nonce'd inline script, no frames. Nothing is
blocked yet; browsers report what the policy would block to `/csp-report/`, and the app logs each distinct violation
once per process as a warning ("CSP violation (report-only): ..."), in the logs and Logfire. A report there after a
deploy is worth a look: it is either a page that would break once the policy is enforced (plan step 5.5) or a
browser extension. Libraries are vendored under `static/vendor/`; nothing loads from a CDN.

## Email

Email confirmation links and password-reset links need outgoing email. Set, for any SMTP provider (Postmark,
SendGrid, Mailgun, SES…):
- `EMAIL_HOST`, `EMAIL_PORT` (587), `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` (True);
- `DEFAULT_FROM_EMAIL`, on a domain the provider may send for.

Without `EMAIL_HOST`, emails are written to the log instead: fine for development, but then nobody receives
confirmation or password-reset links, and Django 6.1's `check --deploy` reports it as an error (mail.E001; CI sets a
placeholder host for that check). Check delivery with `python manage.py sendtestemail you@example.com`.

## Background runs, clean-up and operations

**Runs in the request (default).** With `TASK_BACKEND=immediate` a run executes inside the web request that starts it,
limited to `NRMP_MAX_PAIRS` applicant × program pairs (default 1,000,000; the engine takes about 0.35 s per million
pairs). No worker is needed.

**Runs in a worker.** To take larger runs off the web process:
1. create the **worker** service from this repository with the config file `railway.worker.json`;
2. set `TASK_BACKEND=database` on **both** the web and the worker service, and optionally
   `NRMP_MAX_PAIRS_WORKER` (default 10,000,000; about 3.5 s and 100–250 MB per run at that size);
3. redeploy both. Runs are then queued in the database (django-tasks-db); the page shows their progress and offers
   an email when they finish (to confirmed addresses).

`/healthz` reports the queue and, with a worker, how long ago it was last seen (`"worker": "missing"` after two
minutes without a heartbeat). The health check still returns 200, so a stopped worker never takes the site down;
runs just stay queued, and the clean-up job marks runs queued or running for over an hour as interrupted. A queued
run's page says how many runs are ahead of it and warns its owner when no worker has been seen for two minutes, when
the worker stops during the run, or when the run has been queued for longer than `NRMP_QUEUE_WARNING_SECONDS`
(default 60).

**Clean-up.** The **cleanup** cron service (`railway.cron.json`) runs `manage.py nrmp_cleanup` daily: it marks
interrupted runs as failed, keeps the newest `NRMP_RUNS_KEPT` (50) runs per simulation, and deletes old rate-limit
counters, worker heartbeats and task records. Run it by hand the same way.

**Quotas and rate limits** (per account; staff are exempt): `NRMP_MAX_SIMULATIONS` (50), `NRMP_MAX_PRESETS` (50, saved presets), `NRMP_RUNS_PER_DAY` (200)
and `NRMP_PAIRS_PER_DAY` (200,000,000) in any 24 hours; sign-ups (10 per hour per client address), runs and uploads
(60 per hour per account) are rate-limited, counted in the database. Once outgoing email works, set
`NRMP_REQUIRE_VERIFIED_EMAIL=True` so that only accounts with a confirmed address can run simulations.

**Operations page.** Staff see `/ops/` (linked from their account page): runs per day, failures, median and 95th
percentile durations, the largest runs, the queue and workers, and quota use.

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
