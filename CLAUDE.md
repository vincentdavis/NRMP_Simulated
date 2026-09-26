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

This is a Django-based web application that simulates the National Resident Matching Program (NRMP). The application models a complex matching process between medical students (applicants) and residency programs (schools) through multiple stages: application, interview, ranking, and matching.

### Core Domain Models

**Simulation**: The top-level container for a matching simulation
- Owned by a User (custom auth model extending AbstractUser)
- Contains configurations, populations of students/schools, interviews, and matches
- Can generate populations programmatically or via CSV upload

**SimulationConfig**: Configuration parameters for population generation
- Defines population sizes, score distributions, meta-preference fields
- Controls interview limits and rating error parameters
- Multiple configs can exist per simulation (latest used for generation)

**Student/School**: The two participant types in the matching
- Both have base scores and meta-scores (JSON field for flexible attributes)
- Both have meta-preferences (JSON field defining preference weights)
- Students apply to schools; schools have capacity limits

**Interview**: Represents the interview stage between student-school pairs
- Tracks application, invitation, and interview completion status
- Stores pre- and post-interview observed scores and rankings
- Created as full cross-product of students × schools per simulation

**Match**: Final matching results between students and schools
- Contains final ranking preferences from both sides
- Used for running the matching algorithm

### Key Features

**Population Management**:
- Programmatic generation using Gaussian distributions for scores
- CSV upload/download for custom populations
- Bulk operations for performance

**Multi-stage Simulation Process**:
1. Population creation (students + schools) ✓
2. Interview initialization (creates all possible pairings) ✓
3. Pre-interview rating (students rate schools, schools rate students) ✓
4. Pre-interview ranking computation ✓
5. School invitation process (TODO)
6. Interview phase and post-interview rating updates (TODO)
7. Final ranking generation (TODO)
8. NRMP matching algorithm execution (TODO)

**Meta-preferences System**:
- Flexible JSON-based system for modeling complex preferences
- Students can weight factors like "program_size", "prestige"
- Schools can weight factors like "board_scores", "research"
- Configurable standard deviations for preference weights

### Technology Stack

**Backend**:
- Django 6+ with custom User model
- SQLite for development, PostgreSQL for production
- Django-HTMX for dynamic UI updates
- LogFire for structured logging

**Frontend**:
- Tailwind CSS with DaisyUI components (via django-tailwind)
- HTMX for dynamic content updates
- Alpine.js for client-side interactivity

**Development Tools**:
- Ruff for linting and formatting (configured in ruff.toml)
- mypy for type checking
- pytest for testing
- django-debug-toolbar for development debugging

### File Structure

```
nrmps/                     # Main Django app
├── models.py             # Core domain models
├── views.py              # HTTP views and HTMX endpoints
├── forms.py              # Django forms
├── simulation_engine.py  # Simulation logic (partially implemented)
├── urls.py               # URL routing
└── templatetags/         # Custom template tags

theme/                    # Tailwind CSS theme app
├── templates/            # Base templates (base.html)
├── static_src/          # Tailwind source files
└── ...

templates/nrmps/          # Application-specific HTML templates
├── partials/             # HTMX partial templates
└── ...

static/                   # Static files (CSS, JS, images)
NRMP_Simulated/          # Django project settings
data/                    # CSV upload storage location
```

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
- Use `bulk_create()` for large population generation
- Use `select_related()` for foreign key queries
- Pagination implemented for large data sets (students, schools, interviews)

**Security**:
- User ownership checks on all simulation operations
- CSRF protection enabled
- Debug mode should be False in production

### Current Implementation Status

The project is being reworked according to a review and phased plan:

- `docs/PROJECT_REVIEW.md`: findings and the phased plan (Phases 0–8). §0 reconciles the review with this repository.
- `docs/IMPLEMENTATION_STATUS.md`: what has been done so far, step by step, and open owner decisions.
- `docs/review/`: appendices (model spec draft, stage spec, parameters, UX, visualization, help, engineering) and
  `FINDINGS.md`, the register of every finding (IDs such as SIM-1 or ENG-3) with evidence and recommendations.
- `docs/model_spec.md`: the proposed model 2.0 for the Phase 2 engine (not implemented yet).

**Do not build `interview()`, `students_rank()`, `schools_rank()` or `match()` on the current per-row ORM engine in
`simulation_engine.py`.** Phase 2 replaces it with a seeded, vectorised engine, and Phase 3 builds the remaining
stages on that engine. `TODO.md` and `IDEAS.md` predate the plan; Appendix H of the review says what happens to each
item.
