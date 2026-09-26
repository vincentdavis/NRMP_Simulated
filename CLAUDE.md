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

A Django app that simulates the residency Match (NRMP) between applicants and residency programs. The interface says
"applicant" and "program"; the code keeps the original model names `Student` and `School`.

### Core Domain Models (`nrmps/models.py`)

- **Simulation**: owned by a `User`; `Simulation.objects.owned_by(user)` for access, `.with_counts()` for sizes.
  `status` is the pipeline stage (`setup` → `populations` → `initialized` → `pre_interview` → …); `set_stage()` moves
  it exactly (re-running a step invalidates later stages). Population methods (`create_*`, `upload_*`, `delete_*`)
  run in one transaction after `lock()` (a row lock) and reset the stage.
- **SimulationConfig**: generation parameters; the latest one is used. `clean()` enforces Beta feasibility.
- **Student / School** (applicant / program): base score, `score_meta` (attribute scores), `meta_preference`
  (weights over the other side's attributes); programs have `capacity`.
- **Interview**: one row per applicant-program pair with true utilities, pre/post-interview ratings and ranks.
- **Match**: unused until the match stage exists.
- **User**: custom user; email unique ignoring case, `email_verified_at` set by signed confirmation links.

### Modules

```
nrmps/
├── models.py             # domain models (above)
├── engine/               # model 2.0 (docs/model_spec.md), pure numpy, no Django: rng (streams, Philox),
│                         #   population, utility, rank, metrics, pipeline (run_pre_interview), persistence (npz)
├── params.py             # SimulationParams: typed, versioned parameter schema (pydantic), the source of truth
├── params_forms.py       # Django forms and formsets generated from the schema
├── versions.py           # version stamps stored with runs (model, engine, schema, app, git SHA, numpy, Python)
├── management/commands/  # nrmp_run: run the engine headless (--params, --seed, --out)
├── simulation_engine.py  # legacy engine: interview rows, pre/post-interview ratings and ranks (numpy, bulk SQL)
├── views.py              # simulation pages; HTMX steps through one dispatcher (STEPS) returning all stage cards
├── account_views.py      # sign-up, account page, email confirmation, data export, deletion
├── help_views.py         # /help/ (generated parameter reference) and the staff-only developer reference
├── accounts.py           # confirmation tokens and emails, the personal data export
├── population_csv.py     # CSV format for population upload/download (one module for both directions)
├── forms.py              # forms; ValidatorLimitsMixin puts model validator limits on the inputs
├── limits.py             # NRMP_MAX_PAIRS size limit
├── exceptions.py         # SimulationError and subclasses: problems shown to the user instead of a 500
├── validators.py         # attribute-list validation
├── security.py           # proxy-aware client IP (django-axes)
├── admin.py              # admin registrations
└── templatetags/         # form_tags (field_row), list_tags (sort_th), nav_tags (nav_link), simulation_tags
templates/nrmps/          # pages; partials/ (stage cards), components/ (field, pagination, breadcrumbs ...), help/
theme/                    # base template and the Tailwind/daisyUI build (theme/static_src)
static/js/site.js         # toasts, confirmation dialog, HTMX error handling, theme toggle
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
- The engine computes with numpy and writes in bulk (INSERT … SELECT, executemany, COPY on PostgreSQL); never save
  interview rows one by one.
- Steps run inside the request until background jobs exist; keep them within `NRMP_MAX_PAIRS`.

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
- `docs/model_spec.md`: the normative model 2.0 specification that the Phase 2 engine implements.

**Do not build `interview()`, `students_rank()`, `schools_rank()` or `match()` on the legacy engine in
`simulation_engine.py`.** Phase 2 replaces it with the seeded, vectorised engine in `nrmps/engine/`, and Phase 3
builds the remaining stages there. Engine rules: every random draw comes from its own stream (`engine/rng.py`,
model_spec.md §12.1); pair-level values are computed block by block with the fixed-order arithmetic of §12.7, so any
block equals the same entries of the full matrix; `nrmps/engine/` and `nrmps/params.py` are type-checked strictly. `TODO.md` and `IDEAS.md` predate the plan; Appendix H of the review says what happens to each
item.
