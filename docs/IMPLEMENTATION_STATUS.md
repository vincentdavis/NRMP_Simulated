# Implementation status: Phases 0–2

This records how Phases 0, 1 and 2 of the plan in [PROJECT_REVIEW.md §9](PROJECT_REVIEW.md#9-phased-implementation-plan)
were implemented. It covers the decisions adopted, every deviation from the plan and what the owner still has to do.
Plan step numbers refer to that section.

## Decisions adopted

| # | Decision | As implemented |
|---|---|---|
| D1 | Adopt the Appendix A model | Model 2.0, normative spec in [`model_spec.md`](model_spec.md). Displays show z-values and percentiles. |
| D2 | Applicant / Program vocabulary | Used in all user-visible text; new tables are `Applicant` / `Program`; legacy tables keep their names. |
| D3 | Legacy data | Existing simulations became `engine = v1`: read-only, viewable, downloadable, with a banner explaining why. **Re-create with model 2** copies the settings that have an equivalent. |
| D4 | Size budget | Applicants × programs per run is capped at 2 M in-request (immediate task backend) and 20 M with the worker. Measured on PostgreSQL: 1.3 s end to end at 2.3 M pairs, and 9.5 s with a 240 MiB peak at 20.5 M pairs. Environment variables `NRMP_MAX_PAIRS_*`. |
| D5 | Job backend | `django.tasks`. The immediate backend is the default; `django-tasks-db` with `manage.py db_worker` when `TASK_BACKEND=database`. |
| D6 | Name and trademark | Non-affiliation disclaimer in the footer, README and terms. The name is unchanged. |
| D7 | Counter-based RNG | Philox4x32-10 for every pair-level draw, with its counter layout and uniform/normal recipe specified for a future JavaScript port. It matches the three Random123 known-answer vectors. |

## Phase 0

| Step | Status | Notes |
|---|---|---|
| 0.1 Production mode | Done | DEBUG defaults off; `SECRET_KEY` and `DATABASE_URL` are required; the proxy/HTTPS settings are set; Logfire runs only with a token. A production-mode smoke test covers every public page. |
| 0.2 First run works | Done, on model 2 | Model-2 defaults are valid by construction (schema tests). The legacy interim defaults were not applied because legacy configurations can no longer be edited. `description` is optional; `public` defaults to False and existing rows were migrated to False; the pending `0006` validator change is absorbed. |
| 0.3 Patch the legacy pre-interview stage | Superseded | The legacy engine was removed (D3). The fixes are part of model 2: additive noise, σ = 0 exact, seeded tie-breaks. |
| 0.4 Atomic, bounded steps | Done, on model 2 | Population replacement and run creation happen in one transaction with a row lock; at most one active run per simulation; size caps; page sizes clamped; CSV exports stream. |
| 0.5 XSS | Done | The legacy metadata editor that used `\|safe` is gone. The new setup form escapes everything and is validated by the schema. |
| 0.6 Upload data loss | Done | Uploads are parsed and validated in memory before anything is deleted, in one transaction; size and row limits apply; nothing is written to `data/`. |
| 0.7 Honest pages | Done | Disclaimer, accurate privacy and terms pages, static error pages and a CSRF failure page, real contact links, Logfire scrubbing. |
| 0.8 Account basics | Done | Login errors are shown, password change works, and django-axes throttles logins by a proxy-aware client IP. |

## Phase 1

| Step | Status | Notes |
|---|---|---|
| 1.1 Tests, CI, linters | Done | pytest-django, hypothesis, factory-boy; CI runs ruff, format, codespell, mypy, the migrations check, `check --deploy`, tests on SQLite and PostgreSQL, Playwright + axe and a Docker build; pre-commit; one formatting commit, listed in `.git-blame-ignore-revs`. |
| 1.2 Deployment | Done | Multi-stage Docker image with a non-root user and no dev tools; `railway.json` with a pre-deploy command and `/healthz`; a worker config; `.dockerignore`; docker-compose; [`DEPLOY.md`](DEPLOY.md). |
| 1.3 Front-end dependencies | Done | daisyUI 5.7, Tailwind 4.3; htmx and Alpine vendored by version; Dependabot. |
| 1.4 daisyUI 5 migration | Done | One field component for `{{ form }}`; a check that fails when a template uses a class missing from the built CSS; no overflow at 390 px; axe baseline. |
| 1.5 Feedback and navigation | Done | Toasts (Django messages and the `toast` HTMX event), a global HTMX error handler, one confirm dialog, active navigation, skip link, theme toggle. |
| 1.6 Copy, vocabulary, unused parameters | Done | Parameter help comes from the schema; parameters the engine does not use yet carry "Not used yet"; the dead v1 engine code is deleted. |
| 1.7 CSV v2 | Done | One module for download and upload. The round trip is exact (same population digest); errors give file, line and column. |
| 1.8 View structure and admin | Done | `get_owned_simulation()`, `LoginRequiredMiddleware`, every model in the admin (runs and legacy tables read-only), counts annotated, numbered pagination with totals. |
| 1.9 Email and accounts | Done | Required, unique (ignoring case) email; confirmation links; password reset; account edit, export and deletion. Duplicate emails in existing data are cleared on the newer accounts before the constraint is added. |
| 1.10 Documentation | Done | README, `.env.example`, CLAUDE.md; `TODO.md` now points to the plan. Public `/help/` has a parameter reference generated from the schema; `/help/developer/` is staff only; `/documentation/` redirects. |

## Phase 2

| Step | Status | Notes |
|---|---|---|
| 2.0 Model spec and versions | Done | `model_spec.md` (model 2.0). Every run stores its model, engine and code versions. |
| 2.1 Parameter schema | Done | `nrmps/params.py`, pydantic, schema v1. Parameters of later stages exist and are marked `implemented=False`. **Deviation:** the editable parameters are stored on `Simulation.params`, not on `SimulationConfig` (legacy only). |
| 2.2 Seeded engine | Done | `nrmps/engine/`: pure numpy, strict mypy, 144 tests covering the Appendix A §9 acceptance tests that apply before applications. 10k × 1k takes 4.5 s on one core. Commands `nrmp_run` and `seed_demo`. |
| 2.3 Run model | Done, partly deferred | `SimulationRun`, `StageRun`, `RunArtifact` (population snapshot and names); pair-level values are recomputed rather than stored. **Deferred to Phase 3:** `RankListEntry` and `MatchResult`, which nothing writes before rank lists and the match exist. |
| 2.4 Stage state machine | Done | The pipeline service computes each stage's state (done, stale, running, blocked, planned) and why it is stale. The stepper shows the whole process, including the planned stages. |
| 2.5 Background jobs, quotas, operations | Done | Tasks with progress polling (286 stops it); one active run per simulation; rate limits on sign-up and heavy POSTs; honeypot; daily run quotas, with unverified accounts limited or blocked depending on `NRMP_REQUIRE_VERIFIED_EMAIL`; opt-in "run finished" email; Logfire span per run; queue state in `/healthz`; `nrmp_cleanup` (also deletes sign-in records after 30 days, as the privacy page says); staff ops page at `/ops/`. |

## Engine notes (from its implementation report)

- The utility contraction deliberately avoids BLAS, so results are bit-identical regardless of block shape.
- numpy's `log` can differ from libm by 1 ulp on some CPUs, so byte-for-byte reproducibility holds per platform.
- The uniform mapping's image is (0, 1]: exactly one of 2^53 inputs maps to 1.0. This is harmless and documented; changing it would need a new model version.
- With very sparse tastes (λ ≈ 0.3) the realised preference correlation sits slightly above ρ (+0.007 at ρ = 0.6); at the default λ = 10 it is within ±0.002.

## What the owner still needs to do

1. **Before deploying this branch** (D0, [`DEPLOY.md`](DEPLOY.md#checklist-before-the-first-deploy-of-this-version-decision-d0)):
   - set a new `SECRET_KEY` in Railway;
   - check that `DATABASE_URL` references the Postgres service;
   - remove `DEBUG`.

   A deploy without them fails its health check, and Railway keeps the old version running.
2. Optional:
   - configure SMTP (`EMAIL_HOST` …) so confirmation and reset links are delivered;
   - add the worker service (`railway.worker.json`, `TASK_BACKEND=database`) for larger markets;
   - add a daily `nrmp_cleanup` cron service.
3. Give this session push access to GitHub (reconnect at https://claude.ai/connect-github; install the Claude GitHub
   App on the repository), or push the branch `claude/project-review-plan-ce86lz` yourself.
