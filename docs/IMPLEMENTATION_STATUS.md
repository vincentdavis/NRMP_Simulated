# Implementation status

This file tracks the implementation of the plan in [PROJECT_REVIEW.md §9](PROJECT_REVIEW.md#9-phased-implementation-plan)
on the branch `implement-review-plan`. For each step it records the status, deviations from the plan and anything
the owner has to do. Step numbers refer to that section.

> **Rebuild.** A first implementation of Phases 0–2 (cloud session, branch `claude/project-review-plan-ce86lz`,
> 2026-09-24) was never pushed and cannot be recovered. This is a rebuild from local `main`, which differs from the
> reviewed code; see [PROJECT_REVIEW.md §0](PROJECT_REVIEW.md#0-reconciliation-with-this-repository). The lost
> implementation's decisions, measurements and engine notes are kept at the
> [end of this file](#notes-from-the-lost-implementation) because they are worth reusing.

## Owner decisions

| # | Decision | Needed before | Status |
|---|---|---|---|
| D0 | Check the production environment | Deploying step 0.1 | **Owner action.** Set a new `SECRET_KEY`, confirm `DATABASE_URL` points at Postgres, remove `DEBUG`. See [DEPLOY.md](DEPLOY.md). |
| D1 | Adopt the Appendix A model | Phase 2 | Open. [model_spec.md](model_spec.md) (model 2.0, from the lost implementation) is the proposed text. |
| D2 | Applicant / Program vocabulary | Step 1.6 | Open. |
| D3 | Legacy data | Phase 2 | Open. |
| D4 | Interim size cap | Step 0.4 | **250,000 applicant × program pairs** (`NRMP_MAX_PAIRS`), from the step 0.4 measurements below. Enforced by the configuration form and by "Initialize interviews" (which also covers uploaded populations). |
| D5 | Job backend | Step 2.5 | Open. |
| D6 | Name and trademark | Step 0.7 | Disclaimer only; a name change is the owner's call. |
| D7 | Browser Explorer approach | Step 2.2 | Open. |

## Phase 0: Stabilise production, fix the first run, stop data loss

| Step | Status | Notes |
|---|---|---|
| 0.0 Dependency upgrade (added) | Done | `uv lock --upgrade`, minimums raised to the locked versions: Django 6.1.1, logfire 5.1.1, gunicorn 26.2, django-debug-toolbar 8.0, numpy 2.5.3, scipy 1.18.1, ruff 0.16.9. An end-to-end smoke run passed 33/33 checks. The npm toolchain and vendored htmx/Alpine wait for steps 1.3–1.4, as planned. |
| 0.1 Production mode | Done | `DEBUG` defaults to off; with it off, a missing `SECRET_KEY` or `DATABASE_URL` stops start-up (an explicit `sqlite:///…` URL is allowed). Debug-toolbar and browser-reload URLs only load in DEBUG. Proxy/HTTPS settings, secure cookies, HSTS 3600 s. Logfire uses `send_to_logfire='if-token-present'`. Image: `--no-dev --group prod`, `UV_NO_SYNC=1`, placeholder settings at build time, `.dockerignore`, gunicorn workers and timeout from `WEB_CONCURRENCY` / `GUNICORN_TIMEOUT`. **Deviations:** tests use pytest-django from the start (`NRMP_Simulated/settings_test.py` runs the production configuration on in-memory SQLite, or on `NRMP_TEST_DATABASE_URL`); `.env` support and `.env.example` moved forward from step 1.10 so local development keeps working now that `DEBUG` defaults to off. The Docker build could not be run here (no Docker); its build steps were run locally with the same environment. |
| 0.2 First run works | Done | Migration `0008`: the Appendix C §1 interim defaults and validators (score means in [0.01, 0.99], score and attribute SDs ≤ 0.45, preference SDs ≤ 1, capacity mean ≥ 1, interview limit ≤ 50, scores ≤ 1.0), `description` optional, `public` defaults to False and existing rows were set to False. `SimulationConfig.clean()` rejects a score SD at or above the Beta limit √(μ(1−μ)) and states the limit. A new simulation gets a default configuration in the same transaction; without one, the population card says so. Number inputs take `min`/`max`/`step` from the model validators. **Deviation:** the Appendix F short help text (planned for step 1.6) went into the same migration, so these fields are not altered twice; it is not rendered yet. Configurations saved before the current validators existed (for example mean 0, SD 25) now show errors when their form is next saved, which is intended. |
| 0.3 Patch the pre-interview stage | Done | True utilities U = Σ weight × attribute are stored; observed = U + N(0, σ) with σ = 0 exact and no `or 1.0` fallbacks; strict ranks (score descending, then ascending id); stale ranks cleared. A population check (every weighted attribute has a score on the other side, nobody without weights, numeric values) raises `PopulationError`, whose message the view shows in the stage card with HTTP 200; errors name ids, never participant names. The post-interview helpers (L-1) use the same code and report that no pairs have interviewed instead of advancing the stage. Tests: `test_engine.py`. |
| 0.4 Atomic, fast, bounded steps | Done | Every step and population change runs in one transaction after `select_for_update()` on the simulation; a PostgreSQL test shows two concurrent "(re)Create" calls no longer double the population (it failed 3/3 without the lock). The engine computes with numpy and writes in bulk: interview rows with one `INSERT … SELECT`, scores and ranks with executemany on SQLite and `COPY` + `UPDATE … FROM` on PostgreSQL. Re-running a step sets the stage to exactly that step, and population changes reset it (L-2). Every step returns all stage cards plus the stepper (UX-5 in part); step controls use `hx-disabled-elt` and `hx-sync`. `page_size` is limited to the offered sizes; CSV exports stream. **Measured** (Apple-silicon laptop, local PostgreSQL 18; worst step): 1.5 s at 100k pairs, 3.4 s at 250k, 6.9 s at 500k, 15.6 s at 1M. SQLite: 0.4 s at 100k, 4.6 s at 1M. **Deviation:** the four unused single-step endpoints and the two dead partials (L-3) were deleted here rather than in step 1.8, since they would otherwise have needed rewriting. |
| 0.5 XSS | Done | The tag editors read their items from `json_script` elements; the hidden inputs' no-JavaScript fallback is autoescaped JSON; `|safe` is gone and a test bans it (and `autoescape off`) in templates. `validate_attribute_list` (migration `0009`) requires 1–10 unique names matching `^[a-z0-9_]{1,40}$` and raises `ValidationError`; the form's silent fallback to `[]` is removed. The browser editor normalises to the same rule. A payload already stored in old data renders inert. |
| 0.6 Upload data loss | Done | `nrmps/population_csv.py` parses and validates the upload in memory (≤ 5 MB, ≤ 50,000 rows, header required, unknown columns rejected, UTF-8 with or without a byte-order mark, per-cell checks with line and column, the first 20 problems listed in the card); the population is replaced in one locked transaction only if every row is valid, and only within the size cap. Nothing is written to `data/` (now git-ignored). **Deviation:** the same module writes the downloads, with symmetric columns including `meta_preference`, so a download uploads back unchanged (tested); that is most of step 1.7 (SIM-5, SIM-6). Step 1.7 keeps the sample and template files and the help text. |
| 0.7 Honest public pages | Done | Footer on every page: NRMP® non-affiliation disclaimer and "simulated outcomes are not predictions"; the same notice on the manage page and in the terms. Privacy page rewritten to match the code (database on Railway, uploads not kept as files, Logfire as a processor, two necessary cookies, deletion on request until self-service arrives in 1.9). Terms: purpose, non-affiliation, acceptable use (no real applicant data), the size limit, no warranty, MIT license. Contact: the real issue tracker, plus `CONTACT_EMAIL` when set. Home page Quick Start matches the real flow. Static 400/403/404/500 and CSRF-failure pages that need no database (tested without database access). Logfire redacts account fields and skips static files; engine errors use ids, not names (step 0.3). |
| 0.8 Account basics | Not started | |

## Phases 1–8

Not started.

---

## Notes from the lost implementation

These notes come from the unrecovered branch `claude/project-review-plan-ce86lz`. None of the code they describe
exists in this repository. They are kept as design input for the rebuild, not as a description of this code.

**Decisions it adopted.** It took the recommendation for every decision:

- D1: model 2.0 as written in [model_spec.md](model_spec.md), with displays in z-values and percentiles.
- D2: Applicant / Program in all user-visible text and for the new tables `Applicant` / `Program`; the legacy
  tables kept their names.
- D3: existing simulations became `engine = v1`: read-only, viewable and downloadable, with a banner explaining why,
  and a **Re-create with model 2** action that copied the settings with an equivalent.
- D5: `django.tasks`, with the immediate backend by default and `django-tasks-db` plus `manage.py db_worker` when
  `TASK_BACKEND=database`.
- D6: a non-affiliation disclaimer in the footer, README and terms; the name unchanged.
- D7: Philox4x32-10 for every pair-level draw, with its counter layout and uniform/normal recipe specified for a
  future JavaScript port. It matched the three Random123 known-answer vectors.

**Measurements (D4).** On PostgreSQL with the vectorised model-2 engine: 1.3 s end to end at 2.3 M applicant ×
program pairs, and 9.5 s with a 240 MiB peak at 20.5 M pairs. It capped runs at 2 M pairs in-request (immediate
backend) and 20 M with the worker, through `NRMP_MAX_PAIRS_IMMEDIATE` and `NRMP_MAX_PAIRS_WORKER`. The model-2
engine took 4.5 s for 10k × 1k on one core. These numbers do not apply to the legacy engine that Phase 0 patches.

**Deviations from the plan it made.**

- Step 0.3 was superseded: it removed the legacy engine instead of patching it, and delivered the fixes (additive
  noise, σ = 0 exact, seeded tie-breaks) as part of model 2.
- Step 0.2: legacy configurations could no longer be edited, so it did not apply the interim defaults.
- Step 2.1: the editable parameters lived on `Simulation.params` (pydantic, schema v1, `nrmps/params.py`), not on
  `SimulationConfig`, which stayed for legacy simulations only. Parameters of later stages existed with
  `implemented=False` and showed "Not used yet".
- Step 2.3: `RankListEntry` and `MatchResult` were deferred to Phase 3, since nothing writes them before rank lists
  and the match exist. Pair-level values were recomputed rather than stored; `RunArtifact` held the population
  snapshot and names.
- Step 2.4: the pipeline service computed each stage's state (done, stale, running, blocked, planned) and why it was
  stale; the stepper showed planned stages too.

**Engine notes.**

- The utility contraction deliberately avoided BLAS, so results were bit-identical regardless of block shape.
- numpy's `log` can differ from libm by 1 ulp on some CPUs, so byte-for-byte reproducibility holds per platform.
- The uniform mapping's image is (0, 1]: exactly one of 2^53 inputs maps to 1.0. This is harmless and documented;
  changing it needs a new model version.
- With very sparse tastes (λ ≈ 0.3) the realised preference correlation sits slightly above ρ (+0.007 at ρ = 0.6);
  at the default λ = 10 it is within ±0.002.

**Other features it reported.** 144 engine tests covering the Appendix A §9 acceptance tests that apply before
applications; `nrmp_run`, `seed_demo`, `nrmp_cleanup` and `predeploy` commands; `railway.json` and
`railway.worker.json`; a staff ops page at `/ops/`; quotas depending on `NRMP_REQUIRE_VERIFIED_EMAIL`; django-axes
with a proxy-aware client IP; CI with ruff, format, codespell, mypy, the migrations check, `check --deploy`, tests on
SQLite and PostgreSQL, Playwright + axe and a Docker build; a CI check that fails when a template uses a class
missing from the built CSS; a CSV round trip checked by population digest.
