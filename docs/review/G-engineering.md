# Appendix G: Engineering snippets

These are the engineering reviewer's plan and snippets, with the verifiers' corrections applied. They are starting points, not drop-in code: check every snippet against the current code and the platform documentation when implementing. The master plan schedules this work in Phases 0.1–0.2, 0.4–0.6, 0.8, 1.1–1.2, 1.5, 1.8, 1.10, 2.2, 2.5 and 5.1/5.5.

## ENG phased plan (feeds the master plan)

**Phase 0: hotfix (1 day, no behaviour change):** ENG-1 (urls/settings/logfire), ENG-2 (proxy/HTTPS settings), ENG-9 (dependency groups), ENG-7 (json_script plus server-side list validation), clamp page_size (ENG-5), fix the change-password link (ENG-20), commit migration 0006 (ENG-25).

**Phase 1: foundation (about 1 week):** ENG-12/13 (mypy plugin, ruff config, one format commit), ENG-8 test skeleton plus GitHub Actions plus pre-commit, ENG-10 (multi-stage Docker, railway.json, /healthz), ENG-11 (manifest storage, JS vendoring, Dependabot), ENG-21 (logging), ENG-24/26 (hygiene, docs).

**Phase 2: robustness (1-2 weeks):** ENG-6 (in-memory validated CSV I/O), ENG-14 (owned_by/visible_to, step dispatcher, LoginRequiredMiddleware), ENG-16 (errors and toasts), ENG-18 (config validation), ENG-19 (admin, dead fields), ENG-20 (auth flows), ENG-5 (quotas, axes/ratelimit, streaming export).

**Phase 3: scale and runs (about 2 weeks):** ENG-3 (numpy engine plus bulk/SQL persistence), ENG-15 (indexes, annotate), ENG-4 (django.tasks plus django-tasks-db, SimulationRun, HTMX polling), ENG-17 (seeded RNG, config snapshot), ENG-23 (engine/services split).

**Phase 4: hardening:** ENG-22 (partials, querystring, CSP report-only then enforce with @alpinejs/csp), Playwright smoke in CI, hypothesis property tests gating the new match().

### Snippets

**NRMP_Simulated/urls.py**
```python
from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [path("admin/", admin.site.urls), path("", include("nrmps.urls"))]
if settings.DEBUG and "debug_toolbar" in settings.INSTALLED_APPS:
    from debug_toolbar.toolbar import debug_toolbar_urls
    urlpatterns += debug_toolbar_urls()
```

**settings.py (production block)**
```python
DEBUG = os.environ.get("DEBUG", "False").lower() == "true"
SECRET_KEY = os.environ.get("SECRET_KEY") or ("dev-only-insecure-key" if DEBUG else None)
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set when DEBUG=False")
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
    SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "3600"))
    STORAGES = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
    logfire.configure(send_to_logfire="if-token-present", console=False, service_name="nrmp-simulated")
    logfire.instrument_django()
# Optional: with SECURE_PROXY_SSL_HEADER set, same-origin HTTPS POSTs pass the CSRF origin check without this (verifier note).
# CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h not in {"localhost", "127.0.0.1"}]
TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend", "QUEUES": ["default"]}}
```

**pyproject.toml additions**
```toml
[project]
dependencies = [..., "whitenoise>=6.12", "dj-database-url>=3.1", "django-tasks-db>=0.13"]
[dependency-groups]
prod = ["gunicorn>=26.2", "psycopg[binary]>=3.3"]
dev = [..., "honcho", "pytest-django>=4.14", "hypothesis>=6.168", "factory-boy>=3.3", "pytest-cov", "pre-commit"]
[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "NRMP_Simulated.settings"
python_files = ["test_*.py"]
addopts = "-ra --strict-markers"
[tool.mypy]
plugins = ["mypy_django_plugin.main"]
python_version = "3.13"
exclude = ["migrations/"]
[tool.django-stubs]
django_settings_module = "NRMP_Simulated.settings"
[[tool.mypy.overrides]]
module = ["scipy.*"]
ignore_missing_imports = true
```

**.github/workflows/ci.yml**
```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env: {POSTGRES_PASSWORD: postgres}
        ports: ["5432:5432"]
        options: --health-cmd pg_isready --health-interval 5s --health-retries 10
    env: {SECRET_KEY: ci-not-secret-0123456789abcdefghijklmnopqrstuvwxyz, LOGFIRE_SEND_TO_LOGFIRE: "false", DATABASE_URL: "sqlite:///ci.sqlite3"}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6   # pin to the current major
      - run: uv sync --locked --group prod
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run mypy .
      - run: uv run python manage.py makemigrations --check --dry-run
      - run: DEBUG=False uv run python manage.py check --deploy --fail-level WARNING
      - run: uv run pytest --cov=nrmps                       # sqlite
      - run: DATABASE_URL=postgres://postgres:postgres@localhost:5432/postgres uv run pytest
      - run: uv run ty check || true                          # informational
```

**Dockerfile (multi-stage)**
```dockerfile
FROM node:22-alpine AS css
WORKDIR /src
COPY . .
RUN cd theme/static_src && npm ci && npm run build

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_SYNC=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --group prod --no-install-project
COPY . .
COPY --from=css /src/theme/static/css/dist theme/static/css/dist
RUN DEBUG=False SECRET_KEY=build DATABASE_URL=sqlite:///:memory: LOGFIRE_SEND_TO_LOGFIRE=false .venv/bin/python manage.py collectstatic --noinput
RUN useradd -m app && chown -R app /app
USER app
CMD .venv/bin/gunicorn NRMP_Simulated.wsgi --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout 60 --preload --access-logfile -
```
**railway.json**: `{"build":{"builder":"DOCKERFILE"},"deploy":{"preDeployCommand":["python manage.py migrate --noinput"],"healthcheckPath":"/healthz"}}` (check key names against the current Railway config-as-code docs). Worker service: same image, start command `.venv/bin/python manage.py db_worker --queue-name default`. **.dockerignore**: `.git .venv **/__pycache__ db.sqlite3 *.sqlite data/ theme/static_src/node_modules staticfiles .mypy_cache .ruff_cache .pytest_cache`.

**Background run and progress (sketch)**
```python
# nrmps/tasks.py
from django.tasks import task
@task()
def run_step(run_id: int) -> None:
    run = SimulationRun.objects.select_related("simulation").get(pk=run_id)
    SimulationRun.objects.filter(pk=run_id).update(status="running", started_at=now())
    try:
        STEPS[run.step](run.simulation, rng=np.random.default_rng(run.seed),
                        progress=lambda d, t: SimulationRun.objects.filter(pk=run_id).update(progress_done=d, progress_total=t))
        SimulationRun.objects.filter(pk=run_id).update(status="succeeded", finished_at=now())
    except Exception as exc:
        SimulationRun.objects.filter(pk=run_id).update(status="failed", error=repr(exc), finished_at=now())
        raise
# views: POST creates SimulationRun, calls run_step.enqueue(run.pk), and renders the "run-status" partial:
#   <div hx-get="{% url 'nrmps:run_status' run.pk %}" hx-trigger="every 1s" hx-swap="outerHTML">…<progress value=… max=…>
# run_status returns HttpResponseStopPolling() plus trigger_client_event(resp, "runFinished") when finished.
```

**Upload (sketch)**: `PopulationCSVForm.clean_file()`: size up to 5 MB; `csv.DictReader(io.TextIOWrapper(f.file, "utf-8-sig", newline=""))`; per-row validation collects `(line, column, message)`; on errors, re-render the partial with an error table and change nothing; otherwise `with transaction.atomic(): sim.students.all().delete(); Student.objects.bulk_create(rows, batch_size=2000)`. Columns: `name,score,score_meta,meta_preference` (schools add `capacity`). Download writes the same columns and streams them.

### Evidence artifacts (from the review session; not committed)
review/ENG/perf/perf2.py (engine timings, window-function rank), perf3.py (EXPLAIN, atomic), dl.py (export memory), nplus1.py; review/ENG/upload/upload.py (CSV edge cases), forms_check.py, xss.py; review/ENG/prod/f2.py, csrf.py; review/ENG/mypy.ini; review/ENG/rufftry (ruff simulation); review/ENG/tasksvenv (django-tasks-db on Django 6.1.1); review/ENG/tests_proto/test_proto.py (prototype suite: 6 pass, 2 fail on real bugs). All paths are under scratch/.

### Corrections from verification
- The CSRF 403 on the custom domain was reproduced locally, simulating Railway's TLS proxy, not against production. Whether production is affected depends on its `CSRF_TRUSTED_ORIGINS` and `RAILWAY_PUBLIC_DOMAIN` values (decision D0).
- The OOM figures for 10M-row operations are bounded in practice by gunicorn's 30 s timeout. A request is killed after about 1.5M objects (about 1 GB). That timeout is also what leaves half-written state, because the `delete()` before `bulk_create` commits separately.
- The composite indexes proposed for per-student ranking matter less once the engine is vectorised. The list-view sorts need `(simulation, <sort column>)` indexes or keyset pagination instead.
- **Fail-fast `DATABASE_URL` (Phase 0.1).** The check must coexist with image builds and CI. Allow an explicit `sqlite:///…` URL: the `collectstatic` build step and the SQLite CI job set one, as above. Only raise when `DATABASE_URL` is absent and `DEBUG` is False. Local development runs with `DEBUG=True`.
- `.gitignore` already ignores `.venv`, `db.sqlite3`, `.hypothesis`, `staticfiles/` and `node_modules/`. What is missing is **`data/`** (uploaded CSVs).
- With the CSP change, inline `onchange="this.form.submit()"` handlers in the three list templates need to move to JS, and Alpine needs the `@alpinejs/csp` build (restructure `x-data` expressions that pass arguments).

