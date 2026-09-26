# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Dependencies
```bash
# Install dependencies using uv
uv sync

# Local configuration: DEBUG defaults to off, and with DEBUG off the app refuses to start without SECRET_KEY and
# DATABASE_URL. For development copy .env.example to .env (it sets DEBUG=True).
cp .env.example .env

# Activate virtual environment (if needed)
source .venv/bin/activate
```

### Django Development
```bash
# Run development server
python manage.py runserver

# Create and apply migrations
python manage.py makemigrations
python manage.py migrate

# Run Django system check
python manage.py check

# Create superuser
python manage.py createsuperuser

# Shell access
python manage.py shell
```

### Frontend Development (Tailwind CSS)
```bash
# Start Tailwind CSS development watcher (run in separate terminal)
python manage.py tailwind start

# Build Tailwind CSS for production
python manage.py tailwind build

# Install Tailwind CSS dependencies (if needed)
python manage.py tailwind install
```

### Code Quality and Testing
CI (`.github/workflows/ci.yml`) runs all of these on every push and pull request; pre-commit
(`uvx pre-commit install`) runs the fast ones before each commit.
```bash
# Run linter and formatter (Ruff)
uv run ruff check .
uv run ruff format .

# Spelling
uv run codespell .

# Type checking (mypy with the django-stubs plugin)
uv run mypy .

# Migrations are up to date
uv run python manage.py makemigrations --check --dry-run

# Run tests (pytest-django + hypothesis; NRMP_Simulated/settings_test.py runs the production configuration
# against an in-memory SQLite database; set NRMP_TEST_DATABASE_URL=postgres://... to use PostgreSQL)
uv run pytest

# Browser tests (Playwright + axe; need the built CSS and `uv run playwright install chromium`)
uv run pytest -m e2e

# Validation report: the match engine against theory and an independent solver on random markets
uv run python manage.py nrmp_validate --markets 500 --misreport-markets 100
```

### Docker Development
```bash
# Build Docker image
docker build -t nrmp-simulated .

# Production-like local stack (PostgreSQL + the image, DEBUG off) at http://localhost:8000
docker compose up --build
```

Deployment (Railway) is described in `docs/DEPLOY.md`.

## Architecture Overview

A Django app that simulates the residency Match (NRMP) between applicants and residency programs, implementing
model 2.1 (`docs/model_spec.md`). The interface says "applicant" and "program".

### Core Domain Models (`nrmps/models.py`)

- **Simulation**: owned by a `User`; `params` holds the draft parameters (JSON of `nrmps.params.SimulationParams`,
  schema v1; `get_params()` validates). `Simulation.objects.owned_by(user)` for access, `.with_run_summary()` for
  lists; `lock()` takes a row lock inside `transaction.atomic()`.
- **PopulationUpload**: an uploaded CSV for one side (applicants or programs), parsed and stored as npz; runs use it
  instead of generating that side.
- **SimulationRun**: one execution. Frozen parameters with the seed used, the parameter hash, version stamps (model,
  engine, schema, app, git SHA, numpy, Python), population source and digest, per-stage fingerprints, sizes, status,
  progress and the diagnostics (`metrics`). At most one queued or running run per simulation.
- **StageRun**: one stage of a run with its fingerprint, timing and counts (or the error of the stage that failed).
- **RunArtifact**: npz bytes of a run: the population, the per-agent pre-interview results, and the stage decisions
  (`engine.persistence.StageRecord`: every application with its signal, invitation wave, interview, both list ranks,
  and the match).
- **Stage**: the eight pipeline stages, population to match; all are implemented.
- **User**: custom user; email unique ignoring case, `email_verified_at` set by signed confirmation links.

Continuous pair-level values (utilities, observed and post-interview views, ranks) are never stored:
`runs.RunData` recomputes them exactly from the stored population, the parameters and the seed. Only decisions are
stored.

### Modules

```
nrmps/
├── models.py             # domain models (above)
├── params.py             # SimulationParams: typed, versioned parameter schema (pydantic), the source of truth
├── params_forms.py       # Django forms and formsets generated from the schema (the parameter editor)
├── engine/               # model 2.1, pure numpy, no Django: rng (streams, Philox), population, utility, rank,
│                         #   metrics, applications, signals, invitations, interviews, rol, match (deferred
│                         #   acceptance), outcomes, validate (checks of every match), pipeline (run_pipeline),
│                         #   persistence (npz, digest, StageRecord)
├── runs.py               # start_run / dispatch_run / execute_run, fingerprints, RunData (recomputed pair values,
│                         #   stage rows and totals, CSV rows)
├── validation.py         # the validation report: random markets against theory and an independent solver
├── tasks.py              # django.tasks task that executes a run (immediate backend or django-tasks-db worker)
├── pipeline.py           # stage state machine for the stepper: done, stale (with the reason), running, planned ...
├── quotas.py             # per-account quotas (simulations, runs and pairs per day, verified email)
├── ratelimit.py          # rate limits counted in the database (sign-ups per IP, runs and uploads per account)
├── population_csv.py     # CSV format for population upload/download (one module for both directions)
├── views.py              # public pages, simulation list, the simulation page, runs and uploads (HTMX)
├── run_views.py          # run page (match, funnel, checks, diagnostics), lists, one agent's stages, downloads
├── account_views.py      # sign-up, account page, email confirmation, data export, deletion
├── help_views.py         # /help/ (reference generated from the schema) and the staff-only developer reference
├── ops_views.py          # staff-only /ops/: runs per day, failures, durations, queue, workers, quota use
├── accounts.py           # confirmation tokens and emails, the personal data export
├── versions.py           # version stamps stored with runs
├── forms.py              # account and simulation forms, the upload form
├── limits.py             # NRMP_MAX_PAIRS size limit
├── exceptions.py         # SimulationError and subclasses: problems shown to the user instead of a 500
├── security.py           # proxy-aware client IP (django-axes)
├── admin.py              # admin registrations (runs and artifacts read-only)
├── management/commands/  # nrmp_run (the engine headless), nrmp_validate (validation report), seed_demo,
│                         #   nrmp_worker (queued runs), nrmp_cleanup
└── templatetags/         # form_tags (field_row, cell), list_tags (sort_th), nav_tags (nav_link), format_tags (percent)
templates/nrmps/          # pages; partials/ (pipeline, run panel, population), components/, runs/, help/
theme/                    # base template and the Tailwind/daisyUI build (theme/static_src)
static/js/site.js         # toasts, confirmation dialog, HTMX error handling, theme toggle, list editors
static/vendor/            # htmx and Alpine.js by version (`npm run vendor` in theme/static_src)
docs/                     # review, plan, status, deployment, model spec
```

### Technology Stack

- Django 6.1 (LoginRequiredMiddleware, MAILERS email), SQLite for development, PostgreSQL in production (Railway)
- HTMX + Alpine.js, Tailwind CSS 4 + daisyUI 5 (built by django-tailwind's npm project)
- django-axes (login throttling), WhiteNoise (compressed, hashed static files), Logfire (only with a token)
- Tests: pytest-django, hypothesis, Playwright + axe; ruff, mypy (django-stubs), codespell; GitHub Actions

### Development Guidelines

**Templates**:
- Render form fields with `{% load form_tags %}{% field_row form.field %}` (daisyUI 5 fieldset with help text and
  errors wired to `aria-describedby`); sortable list headers with `{% load list_tags %}{% sort_th key label %}`.
- Use daisyUI 5 class names only; `nrmps/tests/test_css_classes.py` fails on classes missing from the built CSS.

**Code Style**:
- Line length: 120 characters
- Use double quotes for strings
- Ruff handles formatting automatically
- Docstrings required for all public functions/classes

**Performance Considerations**:
- The engine walks pairs in blocks of `NRMP_BLOCK_PAIRS` with fixed-order arithmetic (model_spec.md §12.7), so a
  block equals the same entries of the full matrix and memory stays bounded; never materialise all pairs in the
  database.
- Runs execute inside the request with `TASK_BACKEND=immediate` (default; limit `NRMP_MAX_PAIRS`) or in a worker
  with `TASK_BACKEND=database` (`manage.py nrmp_worker`; limit `NRMP_MAX_PAIRS_WORKER`). Start runs with
  `runs.start_run` + `runs.dispatch_run` so both work; `run_now` always executes in-process (commands, tests).
- Changing a formula, stream ID or draw recipe changes results: it needs a new `MODEL_VERSION` (model_spec.md §12).

**Security**:
- Every page requires login unless marked `@login_not_required`; load simulations with `get_owned_simulation()`.
- Never mark user content safe in templates (a test bans `|safe`); pass data to JavaScript with `json_script`.
- Engine and log messages identify records by id, never by participant names.

### Current Implementation Status

The project is being reworked according to a review and phased plan:

- `docs/PROJECT_REVIEW.md`: findings and the phased plan (Phases 0–8). §0 reconciles the review with this repository.
- `docs/IMPLEMENTATION_STATUS.md`: what has been done so far, step by step, and open owner decisions.
- `docs/review/`: appendices (model spec draft, stage spec, parameters, UX, visualization, help, engineering) and
  `FINDINGS.md`, the register of every finding (IDs such as SIM-1 or ENG-3) with evidence and recommendations.
- `docs/model_spec.md`: the normative model 2.1 specification that the engine implements.
- `docs/VALIDATION.md`: the validation report (`manage.py nrmp_validate`).

The engine implements every stage of the single-applicant Match, from the population to deferred acceptance, and
every run stores its checks (`outcomes.checks`: blocking pairs, capacity, list rules; all 0). New features (replicates,
couples, SOAP, charts) follow the same rules: every random draw comes from its own stream (`engine/rng.py`,
model_spec.md §12.1), pair-level draws use the counter-based Philox generator, and `nrmps/engine/` and
`nrmps/params.py` are type-checked strictly. `TODO.md` and `IDEAS.md` predate the plan; Appendix H of the review says
what happens to each item.
