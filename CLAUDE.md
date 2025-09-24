# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Dependencies
```bash
# Install dependencies using uv
uv sync

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
```bash
# Run linter (Ruff)
ruff check .

# Run linter with auto-fix
ruff check --fix .

# Run type checking
mypy .

# Run tests
pytest
```

### Docker Development
```bash
# Build Docker image
docker build -t nrmp-simulated .

# Run container
docker run -p 8000:8000 nrmp-simulated

# Run with environment variables
docker run -p 8000:8000 -e DEBUG=False -e DATABASE_URL=postgresql://... nrmp-simulated
```

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
- Django 5.2+ with custom User model
- SQLite for development, PostgreSQL for production
- Django-HTMX for dynamic UI updates
- LogFire for structured logging

**Frontend**:
- Tailwind CSS with DaisyUI components (via django-tailwind)
- HTMX for dynamic content updates
- Alpine.js for client-side interactivity

**Development Tools**:
- Ruff for linting and formatting (configured in pyproject.toml)
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

**Completed (simulation_engine.py)**:
- Interview object initialization (full cross-product) - `initialize_interview()`
- Student pre-interview rating of schools - `students_rate_schools_pre_interview()`
- School pre-interview rating of students - `schools_rate_students_pre_interview()`
- Pre-interview ranking computation - `compute_students_pre_rankings()`, `compute_schools_pre_rankings()`
- Complete pre-interview workflow - `compute_pre_interview_scores_and_rankings()`
- HTMX-based UI for interview management

**UI Templates Available**:
- Population management (students_list.html, schools_list.html)
- Interview workflow (interviews_list.html)
- Simulation management (simulation_form.html, simulation_manage.html, simulations_list.html)
- User account system (account.html, signup.html)
- Documentation page (documentation.html)

**TODO/Placeholders**:
- Post-interview rating updates - `interview()` function (line 167)
- Final ranking generation - `students_rank()`, `schools_rank()` functions (lines 175, 183)
- NRMP matching algorithm - `match()` function (line 188)
- School invitation and interview scheduling logic
- Match result visualization and analysis

**New Project Files**:
- `TODO.md` - Comprehensive task list with priorities
- `IDEAS.md` - Research ideas and feature enhancements
- `Dockerfile` - Container deployment setup
- `Procfile.tailwind` - Tailwind CSS process management