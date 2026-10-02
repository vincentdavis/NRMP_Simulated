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
| D0 | Check the production environment | Deploying step 0.1 | **Done (2026-09-30)** with the first deploy of this branch: a new `SECRET_KEY`, `DATABASE_URL` on a new Railway PostgreSQL database, `DEBUG` removed. See [DEPLOY.md](DEPLOY.md). |
| D1 | Adopt the Appendix A model | Phase 2 | **Adopted (2026-09-25):** model 2.0 as written in [model_spec.md](model_spec.md), with percentile or 0–1 displays. |
| D2 | Applicant / Program vocabulary | Step 1.6 | **Adopted (2026-09-25):** Applicant / Program in all user-facing text; existing model and table names stay. |
| D3 | Legacy data | Phase 2 | **Decided (2026-09-25): nothing in production needs keeping.** Phase 2 may replace the legacy tables outright; no read-only legacy view. |
| D4 | Interim size cap | Step 0.4 | **250,000 applicant × program pairs** (`NRMP_MAX_PAIRS`), from the step 0.4 measurements below. Enforced by the configuration form and by "Initialize interviews" (which also covers uploaded populations). |
| D5 | Job backend | Step 2.5 | **Adopted (2026-09-25):** `django.tasks` with the `django-tasks-db` backend and an optional worker service; no Redis. |
| D6 | Name and trademark | Step 0.7 | Disclaimer only; a name change is the owner's call. |
| D7 | Browser Explorer approach | Step 2.2 | **Adopted (2026-09-25):** counter-based Philox4x32-10 for pair-level draws (model_spec.md §12.3), so a JavaScript port can reproduce runs. |

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
| 0.8 Account basics | Done | The login page shows Django's own error message and has autocomplete hints. Password change at `/account/password/` (the account page no longer links to the admin). django-axes 8.3: the 5th failed sign-in for a username from one client locks that pair for 15 minutes (HTTP 429 with a friendly page); success clears earlier failures; successful sign-ins are not logged. The client address comes from `nrmps.security.client_ip`: the `X-Forwarded-For` entry added by our own proxy (`TRUSTED_PROXY_COUNT`, 1 in production), which a client cannot forge; django-ipware is not needed. The privacy page describes the failed-sign-in records. |

**Also fixed in Phase 0:** L-4 (step buttons disabled until their own stage was reached, so the workflow could not be
completed from the page), found while checking the UI in a browser.

**Phase 0 exit criteria:** the production-mode smoke test passes; `check --deploy` reports only `security.W005` and
`security.W021`; a new simulation goes from the defaults to pre-interview ranks in the browser; every step at the
250k-pair cap took at most 3.4 s locally on PostgreSQL; σ = 0 gives observed == true and σ > 0 gives Spearman < 1;
no `|safe` in templates; a failed upload changes nothing. The manage page still overflows at 375 px (UX-9, step 1.4).

## Phase 1: Quality foundation and UI hygiene

| Step | Status | Notes |
|---|---|---|
| 1.1 Tests, CI, linters | Done | pytest-django, hypothesis (strict-rank and CSV round-trip properties); GitHub Actions: ruff, format, codespell, mypy (django-stubs plugin; clean), `makemigrations --check`, `check --deploy --fail-level WARNING` (the two deliberate HSTS warnings are silenced in the settings), pytest on SQLite and PostgreSQL 17, ty as information only; pre-commit (ruff, codespell, file checks, migrations). ruff: Google docstring convention, rule sets fixed (DOC/TRIO/FAST dropped; DTZ and PT added), migrations and `docs/` excluded; every finding fixed, including dead `generate_meta_scores` and nullable `User.full_name` (migration `0010`, NULL → ""). `prod` is a default uv group so local runs can use PostgreSQL. **Deviations:** the one formatting commit came earlier (before step 0.3); factory-boy was not needed (fixtures suffice); the review's DA property test waits for the match in step 3.6. The workflow was run step by step locally, not yet on GitHub. |
| 1.2 Deployment and operations | Done | Multi-stage Dockerfile (Node only in the CSS stage, cached dependency layer, `collectstatic` at build time, non-root user); `railway.json` with the pre-deploy migrate and the `/healthz` health check (200 when the database answers, 503 otherwise, exempt from the HTTPS redirect; `healthcheck.railway.app` allowed on Railway); `entrypoint.sh` only migrates with `MIGRATE_ON_START=1`; gunicorn workers default to 2 (`WEB_CONCURRENCY`); WhiteNoise compressed manifest storage; persistent, health-checked database connections; one log handler and no per-POST INFO logs (ENG-21); Tailwind scans only `templates/`, `theme/templates/` and `nrmps/` (VIZ-5; CSS 93 → 85 KB); docker-compose with PostgreSQL; CI builds the image and checks `/healthz`; stray files removed and `.junie` points to CLAUDE.md. The Docker build could not run here (no Docker); the runtime path was checked locally (production `collectstatic`, `entrypoint.sh`, gunicorn, `/healthz`, gzip and immutable caching of hashed CSS). **Owner:** enable Postgres backups in Railway (DEPLOY.md). |
| 1.3 Front-end dependencies | Done | After 1.4, as planned: Tailwind 4.1.13 → 4.3.3, daisyUI 5.1.12 → 5.7.46, postcss-cli 11 → 12, cross-env 7 → 10; the unused postcss-nested and postcss-simple-vars plugins removed. htmx 2.0.6 → 2.0.11 and Alpine 3.14.9 → 3.17.4 are npm dependencies copied by `npm run vendor` into `static/vendor/<package>/<version>/` (versions listed in `static/vendor/README.md`); Tailwind no longer scans static files at all (1.2), so no `@source not` is needed. Dependabot: weekly grouped updates for uv, npm and GitHub Actions. Logo 363 KB → 11 KB (128 px) and favicon 363 KB → 5 KB (64 px). One regression from the daisyUI bump (the current-page indicator's contrast) was caught by the axe tests and fixed; new browser tests drive the workflow through the HTMX buttons and the Alpine tag editor. |
| 1.4 daisyUI 5 migration | Done | One field component (`{% field_row %}`, `nrmps/templatetags/form_tags.py`): a daisyUI 5 fieldset with the widget class and its error variant, help text and errors carrying the ids that Django's `aria-describedby` points to. Every daisyUI 4 / Bootstrap class is gone (`form-control`, `label-text[-alt]`, `*-bordered`, `card-header`, `hover` rows); `test_css_classes.py` fails on any class missing from the built CSS (strict in CI). Manage page, create form, sign-up, login, password change, list pages and the documentation page rebuilt: base `grid-cols-1`, wrapping headers, shared sort headers with `aria-sort`, pagination with `aria-current`, labelled file inputs and tag-editor inputs, an error summary linking to each invalid field, the password rules shown on sign-up. Contrast: no outline success/error buttons, no `opacity-50` dimming, hints at 70 % opacity; a global `:focus-visible` ring. Browser tests (`pytest -m e2e`, Playwright + axe, 31 checks over 15 pages): every page fits 390 px and has no serious or critical axe violations; CI runs them in their own job. |
| 1.5 Feedback and navigation | Done | Toasts: Django messages on page loads, and a `toast` event in the `HX-Trigger` header of every step response ("Created 200 students.", or the error). A global handler turns HTMX server and network errors into error toasts. Spinners in every step and upload button. One `<dialog>` confirms every destructive action (`hx-confirm` and forms with `data-confirm`), and each question states what will be deleted, with counts. Navigation: active item with `aria-current`, no Account link when logged out, a skip link, `<main id="main">`, breadcrumbs on the simulation pages. Tables: three-decimal numbers, attribute chips instead of dict reprs, id order by default, true utilities beside the ratings, a legend. Dark mode: the theme follows the system unless the visitor toggles it (saved in localStorage, applied before first paint); primary-colored text replaced where it failed contrast in the dark theme. Shared JavaScript is in `static/js/site.js`. Browser tests: 40 (workflow with the dialog and toasts, cancel, a server error, the theme toggle, axe in the dark theme). |
| 1.6 Copy, vocabulary, unused parameters | Done | D2 applied: Applicant / Program in every user-facing text (headings, table headers, form labels from Appendix F, confirmations, toasts, file names, sample files, export file names, URL paths such as `/simulations/<pk>/applicants/`, step names, admin names); code and table names stay `Student` / `School` (D3 lets Phase 2 replace them). The six parameters the engine ignores carry a "Not used yet" badge, and the four planned configuration fields sit in a collapsed "Planned parameters" group. Dead code deleted: the `students_rank` / `schools_rank` / `match` stubs, `Student.meta_stddev`, `School.meta_stddev`, `User.disabled`, `User.status` (migration `0012`). Model docstrings rewritten. The corrected help text and the error summary came with steps 0.2 and 1.4. |
| 1.7 CSV v2 | Done | The module, symmetric columns, validation with line numbers and the round-trip test came with step 0.6. Added here: `static/samples/students_sample.csv` and `schools_sample.csv` (synthetic, with the default attribute keys), linked beside each upload input and tested to upload and rate together; the upload toast reports how many rows were loaded. The full CSV reference goes on the help page (step 1.10). |
| 1.8 View structure and admin | Done | `Simulation.objects.owned_by(user)` and `get_owned_simulation()` replace every inline ownership check; `LoginRequiredMiddleware` protects every page not marked `@login_not_required` (home, contact, privacy, terms, documentation, sign-up, `/healthz`); one dispatcher, `/simulations/<pk>/steps/<step>/` with a `STEPS` table, replaces the seven step views (step 2.5 turns it into the job queue). Admin: users with full name, simulations with counts and an inline configuration, configurations editable; students, schools, interviews and matches view-and-delete only, without full result counts. The simulations list counts populations with one subquery each (no N+1). Sort and page links use `{% querystring %}`; numbered pagination with "Showing a–b of N". **Deviation:** stage cards stay separate partial files rather than `{% partialdef %}` blocks, since both the page and the HTMX responses already render the same files. Filters and detail pages are step 4.1. |
| 1.9 Email and accounts | Done | Email through Django 6.1 `MAILERS` (SMTP from `EMAIL_*` variables; the log without `EMAIL_HOST`). Sign-up requires an email address that no other account uses, ignoring case, enforced by a conditional unique index (`Lower(email)`, empty addresses exempt); migration `0011` first clears duplicates on the newer accounts (tested on real pre-migration data). Signed confirmation links (3 days, tied to the address they were sent to; resend at most once a minute); password reset; account page with details, confirmation status, edit (a new address must be confirmed again), "Download my data" (a ZIP with account.json and each simulation's settings, populations and interview rows) and deletion with the password. The privacy page describes all this. Not done: verified-only features (quotas, step 2.5) and a prompt beyond the account page for existing accounts without an email. Old files in `data/` lived on the container's ephemeral disk and disappear with each deploy, so nothing had to be deleted. |
| 1.10 Documentation | Done | `README.md`; `.env.example` (step 0.1, extended since); CLAUDE.md architecture, modules, commands and conventions rewritten; `TODO.md` points to the plan and Appendix H. Public `/help/`: quick start, how the model works, a parameter reference generated from the forms (labels, meaning, limits, defaults, "Not used yet"), CSV formats with the sample files, current limitations. The generated reference moved to staff-only `/help/developer/` and lists only the project's models, fields, own methods and engine functions (no `User` or inherited Django internals); `/documentation/` redirects permanently to `/help/`; the navigation item is now Help. |

**Phase 1 exit criteria:** the GitHub Actions workflow is written and every job was run step by step locally (it
has not run on GitHub yet: the branch is not pushed); Playwright and axe pass with no serious or critical violations
on every page, in the light and dark themes; the dead-class check passes; no page overflows at 390 px; every action
shows a spinner and a result toast; download → upload is lossless (tested, including a hypothesis property);
password reset and account deletion work end to end.

## Phase 2: Model spec, typed parameters, seeded engine, runs and background jobs

| Step | Status | Notes |
|---|---|---|
| 2.0 Decisions and the model spec | Done | D1, D3, D5 and D7 decided (table above). [model_spec.md](model_spec.md) is normative for `model_version = "2.0"`; one ambiguity was settled while adopting it (the tie order of the largest-remainder rule, §12.5). The version-stamping scheme is §12.11: every run stores the model, engine, schema and app versions, the git SHA and the numpy and Python versions. **Legacy data (D3):** the v1 generator, its populations and interview rows are removed when the new tables arrive (step 2.3); simulations keep their owner, name and description, and their configuration is converted to model 2.0 parameters where a field has an equivalent (market size, attribute names). |
| 2.1 Typed parameter schema | Done | `nrmps/params.py`: pydantic `SimulationParams` (schema v1) with the groups of Appendix C §3 and model_spec.md §11: run, market, applicants (groups, attributes), programs (quality, tiers, attributes), prefs, info, and the planned apps, signals, invites, interview, rol and match groups. Every field has a label, help text, unit, level (basic or advanced) and an `implemented` flag; ranges are errors, NaN, infinity and unknown keys are rejected. Cross-field errors: group and tier shares add up to 1, unique names and keys, M ≤ P, N·M ≤ 5×10⁷; `warnings()` reports unusual tightness, a side with one attribute and the planned-stage rules. Canonical JSON and a SHA-256 hash, `implemented_data()` (planned fields removed) and `stage_inputs()` for the stage fingerprints of step 2.4, `load_params()` with a place for schema upgrades. `nrmps/params_forms.py` generates the editor from the schema: one form for the scalar parameters and a formset per list, validated by Django and then pydantic, with each pydantic error attached to its field, table cell, list or section. Tests: 34, including a hypothesis round trip through the form. **Deviations:** the COULD parameters (specialties, regions, fees, couples, SOAP) are left out of schema v1, since adding fields later needs no schema upgrade; the tier-based size distribution of Appendix C is not in the model spec, so it is not offered. The schema replaces `SimulationConfig` in step 2.3, together with the engine that reads it. |
| 2.2 Seeded engine | Done | `nrmps/engine/` implements model_spec.md §3–6, §8 and §10 with numpy and no Django: `rng` (stream IDs, SeedSequence population streams, a vectorised Philox4x32-10 that matches the three Random123 known-answer vectors, the uniform and Box–Muller recipes), `population` (groups and tiers by largest remainder, correlated attributes, program_size from capacity, capacities by fixed, lognormal or shifted-multinomial split, log-space Dirichlet weights, `validate_population`), `utility` (common term, residualised attributes, analytic taste moments, the fixed-order block computation, pre-interview observation with visibility and halo), `rank` (strict ranks, tie keys drawn only for tied rows), `metrics` (market, generation, consensus by the O(N·M) identity, fidelity, first choices, histograms), `pipeline` (`run_pre_interview`, walking each side in blocks of `block_pairs`; `agent_view` recomputes one agent's row) and `persistence` (byte-reproducible npz, `population_digest`). `manage.py nrmp_run --params --seed --out` runs it headless and writes params, population, per-agent results and metrics with version stamps (`nrmps/versions.py`; the image takes a `GIT_SHA` build argument). Acceptance tests 1–6 and 8 of §9 pass (72 engine tests), for example a mean pairwise correlation of 0.602 at ρ = 0.6 and a pooled fidelity of 0.894 against 0.894 expected; the engine and the schema pass strict mypy. **Measured** (Apple-silicon laptop, one core): 0.06 s for the default 1,000 × 142 market, 0.09 s at 250k pairs, 3.4 s and a 232 MB peak at 10,000 × 1,000. **Deviation:** `seed_demo` needs the run tables, so it comes with step 2.3. |
| 2.3 Runs and storage | Done | Legacy tables replaced (D3): migration `0014` converts each simulation's configuration to model 2.0 parameters where a field has an equivalent (market size, tightness, program size, attribute names; tested on legacy data), `0015` drops `SimulationConfig`, `Student`, `School`, `Interview` and `Match`. `Simulation.params` holds the draft (a fresh nine-digit seed by default, so runs repeat until the seed changes). `SimulationRun` freezes the parameters with the seed used, the parameter hash, the version stamps (§12.11), the population source and digest, the stage fingerprints, sizes, progress and the diagnostics; one queued or running run per simulation (row lock plus a partial unique constraint; tested with concurrent starts on PostgreSQL). `StageRun` records each stage, `RunArtifact` stores npz arrays (the population, per-agent pre-interview results), `PopulationUpload` one uploaded side. `nrmps/runs.py` starts runs (validates, builds and stores the population, checks the size limit) and executes them; `RunData` recomputes pair-level values for the pages. New pages: the simulation page (parameter editor generated from the schema with table editors for groups, attributes and tiers; populations; runs), the run page (summary, stages, diagnostics, histograms, parameters, version stamps), applicants and programs lists (sort, paginate), one agent's view of the other side and the other side's view of it, and downloads (applicants, programs and pairs CSV, metrics and parameters JSON). CSV format v2: z-scale values, attribute columns from the parameters, optional `weight:` columns (drawn by the model when absent), program_size from capacity; a download uploads back unchanged (tested, also as a hypothesis property). Help page, data export, admin, privacy text and samples rewritten; `manage.py seed_demo`. **Deviations:** pair-level values are recomputed, not stored (model 2.0 makes that exact), so there are no per-pair rows and no `Applicant`/`Program` tables: populations are arrays in run artifacts, and uploads are stored per side; `RankListEntry` and `MatchResult` come with the stages that write them (Phase 3); runs still execute in the request until step 2.5, within `NRMP_MAX_PAIRS`. |
| 2.4 Stage state machine | Done | `nrmps/pipeline.py`: every stage of the eight (two implemented, six planned) is done, stale, queued, running, failed, ready, blocked or planned, from the draft parameters and the runs. "Done" compares stage fingerprints (a hash of the model version, seed, the parameters the stage reads, the upstream stage and the population sources), so changing a noise parameter keeps the population done and makes only the pre-interview stage stale, with the reason ("Changed since run 1: information (noise)"); planned parameters never make anything stale. The stepper on the simulation page shows the states and reasons and is refreshed out of band by HTMX actions; the Run button says "Run again" when nothing is stale. Re-running is always the whole pipeline: stages whose fingerprint is unchanged reproduce their results exactly. **Deviation:** committed together with step 2.3, since the new page needed the stepper. |
| 2.5 Background jobs and operations | Done | `django.tasks` with django-tasks-db 0.13 (D5): with `TASK_BACKEND=immediate` (the default) a run executes in the request; with `database` it is queued and a worker service runs it (`manage.py nrmp_worker`: django-tasks-db's `db_worker` plus a heartbeat thread). One active run per simulation (step 2.3). HTMX progress: the run panel polls every second and says when the run finished; the run page reloads itself when done; "Email me when it finishes" for confirmed addresses. Tested with a real worker on SQLite and PostgreSQL, and checked in the browser. Quotas (`nrmps/quotas.py`, staff exempt): simulations per account, runs and applicant × program pairs per 24 hours, and `NRMP_REQUIRE_VERIFIED_EMAIL` (off until outgoing email works). Rate limits (`nrmps/ratelimit.py`): sign-ups per client address, runs and uploads per account, with a 429 page or toast. A sign-up honeypot. Size caps raised: 1,000,000 pairs in the request (0.35 s end to end), 10,000,000 with a worker (3.2 s end to end on PostgreSQL, 226 MB process peak). Logfire spans for both stages. `/healthz` reports the queue and the worker's last heartbeat (still 200 when the worker is missing). `manage.py nrmp_cleanup` marks interrupted runs failed, keeps the newest 50 runs per simulation and prunes counters, heartbeats and task records; `railway.worker.json` and `railway.cron.json` configure the worker and a daily clean-up; docker-compose has a worker. Staff `/ops/` page: runs per day, failures, median and p95 durations, largest runs, queue, workers and quota use. **Deviations:** no django-ratelimit and no DatabaseCache: django-ratelimit's own system check rejects the database cache as non-atomic (E003) and D5 excludes Redis, so the limits count in a small table with atomic UPDATEs instead (no cache table to create). The ops page is a staff page in the app, linked from the account page, rather than part of the admin. |

**Phase 2 exit criteria:** the same seed gives byte-identical results (engine acceptance test 1; repeated runs have identical population digests and diagnostics); changing a noise parameter leaves the population unchanged (engine CRN tests, run and pipeline tests, a browser test of the stepper); a 10k × 1k pre-interview run completes in a worker in 3.2 s with a 226 MB process peak, within the D4 budget; legacy simulations follow D3: their results are dropped and their settings converted (migration test on legacy rows).

## Phase 3: Complete singles pipeline to a validated match

Steps 3.1–3.6 were built together in the engine (commit "Steps 3.1-3.6 (engine)") as model 2.1: `docs/model_spec.md`
§7–8 give the exact recipe and random stream of every stage, and §3–6 are unchanged, so every result up to the
pre-interview ranks is reproduced exactly. Applications are chosen during the pre-interview pass; the later stages
work on the sparse set of applied pairs with pair-wise values equal to the block computation bit for bit. Only
decisions are stored (`engine.persistence.StageRecord`); continuous values are recomputed.

| Step | Status | Notes |
|---|---|---|
| 3.1 Applications | Done | `engine/applications.py`: counts `fixed`, `poisson` or `negbin` around `apps.mean` or a group's `applications_mean`; strategies `top_n`, reach/target/safety `portfolio` (prestige = quantile of the applicants' common view; self-assessed competitiveness = quantile of the programs' common view plus `apps.self_assessment_noise_sd` noise; `target_band`), `all` and `random`, all from the strict pre-interview ranks. |
| 3.2 Signals | Done | `engine/signals.py`: tiers with counts and screening boosts, per-group `n_signals` limits, allocation `top_utility`, `realistic` (non-reach first) or `random`; a `program_use_share` of programs read them. Signals affect screening and, only with `signals.use_in_ranking`, programs' rank order lists. |
| 3.3 Screening, invitations and acceptance | Done | `engine/invitations.py`: slots ⌈interviews per position × positions⌉; screening score = pre-interview view + signal boost, or minus `yield_protection` for applicants who look overqualified; strategies `top_score`, `threshold_then_top`, `threshold_then_random` (hard screen on an attribute percentile) and `signal_first`; `invites.rounds` waves, each inviting ⌈1.2 × open slots⌉ (exactly the open slots in the last); applicants respond in a random order per wave, `best_first` or `first_come`, up to `interview.applicant_cap`. Exact integer arithmetic for the rounding (spec §7.3). **Deviation:** interview date conflicts (`interview.n_dates`) stay planned and are marked "Not used yet". |
| 3.4 Interviews | Done | `engine/interviews.py`: fit shocks for both sides (streams `FIT`, and the new `FIT_P`), and the post-interview view shrinks the same pre-interview error by κ (`interview_informativeness`; κ = 1 reveals the realised utility exactly, tested). **Deviation:** no-shows are not modelled. |
| 3.5 Rank order lists | Done | `engine/rol.py`: applicant policies `all_interviewed` (truthful), `top_k`, `truncate_k`, `above_reservation` and `likelihood_weighted`; program policies `all_interviewed`, `dnr_quantile` (⌈n(1−q)⌉, at least 1) and `dnr_threshold`; strict orders with seeded tie keys; certification (a non-empty list). Applicant lists hold at most 300 programs, the NRMP limit. **Change in step 3.7:** program lists were capped at 300 too; there is no such NRMP limit, and in a market of 500 programs with 40 positions on average (about 330 interviews each) the cap removed 28% of program list entries and lowered the fill rate from 92.9% to 83.7%, so it was removed (model 2.1 was not yet released). |
| 3.6 Match | Done | `engine/match.py`: our own applicant-proposing and program-proposing deferred acceptance with capacities (heaps, work proportional to list length), blocking-pair count, and `match.compare_both` for the proposing-side comparison. The `matching` package is a dev-only oracle: 200 hypothesis markets agree for both sides. **Deviation:** no `RankListEntry` or `MatchResult` tables: the lists and the match (every applicant, matched or not) are arrays in the run's stage artifact, which the pages and downloads read. |
| 3.7 Validation and metrics | Done | `engine/validate.py` checks every run and stores the result in `outcomes.checks`: blocking pairs, programs over capacity, matches not on both lists, list entries without an interview, lists that are not a strict 1..k, applicant lists beyond 300 (all 0), and with `compare_both` the rural hospitals theorem and applicant optimality. `engine/outcomes.py` computes the NRMP-style metric set (match rate of certified applicants, fill rate, unfilled positions and programs, first and top-3 choice shares, the matched-rank distribution, list lengths), the funnel, signal rates, welfare (realised-utility rank of the match among the applicant's interviews, regret, post-interview fidelity) and results by group and strength decile. `nrmps/validation.py` and `manage.py nrmp_validate` produce the validation report ([VALIDATION.md](VALIDATION.md)): 500 random markets with random policies for every stage, both proposing sides, all checks, agreement with the `matching` solver, and a strategy-proofness check (no applicant gains by submitting another list under applicant-proposing DA; 4,745 applicants; the same search finds gains under program-proposing, so it has power). CI runs it. **App:** runs execute every stage (`runs.execute_run` via `run_pipeline`, a `StageRun` per stage, a failure recorded on the stage where it happened) and store the decisions as a new artifact; the stepper has no planned stages left, and a stale stage names the change among its inputs or in the stage before it. The run page shows the match (headline numbers, the matched-rank distribution, list lengths, the comparison, the checks), the funnel, signals, welfare and who matched; run summaries show the match rate. The lists gain applications, interviews and the match (programs: positions filled); an applicant's or program's page opens on its stages (signal, invitation wave, interview, both post-interview views, both list ranks, the match), with the pre-interview view as the second tab. New downloads: `match.csv` (every applicant), `program_results.csv` and `applications.csv` (every application, from signal to match, with both sides' true, pre-interview, realised and post-interview values). `nrmp_run` runs every stage and writes `stages.npz`. Help page, developer reference and README describe the full pipeline. Runs from before the match still open. **Also fixed:** `LOGFIRE_SEND_TO_LOGFIRE=false` was ignored because the settings passed `send_to_logfire` explicitly, so local test runs with a `.logfire` credentials file could export spans; the variable is now honoured (tested). |
| 3.8 Diagnostic charts | Done | ECharts 6.1.0 is vendored like htmx and Alpine (`npm run vendor` now copies it, with each library's licence, into `static/vendor/echarts/6.1.0/`) and loads only on run pages with results. `static/js/nrmp-charts.js` is a small registry: `[data-chart]` elements are drawn from `json_script` payloads, colours come from the daisyUI theme (converted from oklch, which ECharts cannot parse) and follow the light/dark toggle, charts resize with their box and are disposed of on HTMX clean-up, tooltips are escaped, and animation respects reduced motion. `nrmps/charts.py` builds the payloads: **POP-1** strength and quality histograms with the counts the parameters ask for (a mixture of the groups' or tiers' normals, for generated sides) and the largest deviation in standard errors, flagged above 4; **POP-4** positions per program; **RAT-1** true against observed utility for 1,500 sampled pairs before interviews and 1,500 interviews after, both sides, with the identity line; **RAT-3** first-choice demand per program against its positions (dataZoom above 60 programs) and the Lorenz curve with the Gini coefficient; **INT-1** a Sankey diagram from applications to matches with the drop-offs (vertical on narrow screens); plus the two per-agent fidelity histograms. Each chart has a question as its title, a summary sentence linked with `aria-describedby`, and "The numbers" as a table; without JavaScript nothing is lost. The payloads take 35 ms for a 20,000 × 500 run. Tests: payloads (requested counts sum to the population, a large generated market deviates by less than 4 standard errors, uploaded sides have no request, the funnel adds up, the sample repeats), the page, and a browser test that all ten charts draw without script errors in both themes and fit a phone. **Deviations:** payloads are embedded in the page rather than fetched from a chart API (enough for fixed per-run charts; the API comes with the Phase 5 suite); RAT-1 uses samples rather than a density heatmap of every pair; RAT-3 shows first choices only, not top-5 demand; INT-1 has no per-decile small multiples; POP-4 has no capacity-0 flag, since every program has at least one position in model 2.x. Chart export and footers, and the chart catalog for help, are Phase 5 (step 5.1). |

**Measured** (Apple-silicon laptop, local PostgreSQL 18): a full 10,000 × 1,000 run through the run service takes
4.5 s end to end (pre-interview pass 3.8 s, every later stage together 0.34 s) with a 295 MB process peak; the stage
artifact is 1.5 MB. 20,000 × 500 through the worker: 5.0 s. `applications.csv` for 600,000 applications streams in
4.2 s (89 MB).

**Phase 3 exit criteria:** the full pipeline runs at 10k × 1k in 4.5 s with a 295 MB peak, well within the D4
budget and the ≤ 60 s example; every run stores `blocking_pairs = 0` and the metric set (with all checks); the oracle,
property and validation tests are green on SQLite and PostgreSQL. The diagnostic charts show no degenerate inputs:
there are no presets yet (Phase 4), so the default parameters and a 10,000 × 1,000 market were checked over seeds 1–3,
with largest requested-against-realised deviations of 1.4 to 2.6 standard errors (strength and quality), first-choice
Gini 0.85–0.96, match rates 92–93%, fill rates 95–97% and every check passed.

## Phase 4: Workspace UX and help system

Appendix D was written for the legacy app, where every stage was a separate step the user ran. In the rebuilt app a
run computes every stage at once (Phase 2), so the workspace is split in two: the simulation page (parameters,
populations, runs, and the stepper with each stage's state) and the run's pages (the results of every stage).

| Step | Status | Notes |
|---|---|---|
| 4.1 Simulation workspace | Done | The run page became tabbed pages (links, `tabs tabs-border`, `aria-current`): **Summary** (key numbers, the checks, downloads, stages, version stamps, parameters), **Population** (the market as generated against the request, distribution charts), **Before interviews** (agreement, fidelity, first choices, true against observed, first-choice demand), **Applications and interviews** (the funnel, signals, interview outcomes, and every application in a table with filters: stage reached, signal, applicant and program name, plus sorting and pagination; 55–82 ms per page for 600,000 applications), **Match** (headline numbers, where applicants matched on their lists, the comparison, the checks, who matched), **Applicants** and **Programs**. Each tab opens with its key numbers (daisyUI `stats`) and loads only its own charts. The stepper on the simulation page links every stage with results to its tab of the latest successful run. The rows-per-page selector keeps the filters. Tested: every tab links to the others, filters and sorting (a numpy casting overflow in the rank sort was caught by these tests), stepper links, runs from before the match (no Applications or Match tab), axe and phone width on every tab. **Deviations:** no "Next step" or "Run all remaining" buttons and no separate job bar: a run always computes every stage, the Run button is "run all", and the run panel already shows progress while a run is queued or running. The applicant and program detail pages already existed (step 3.7). |

| 4.2 Setup form | Done | **Presets** (`nrmps/presets.py`): seven named starting points (NRMP-like, small classroom market, competitive specialty, more positions than applicants, preference signals, perfect information, everyone wants the same programs), each listing only what it changes from the defaults, validated by the tests and small enough to run without a worker. The new-simulation page offers them as cards; the parameter form can start again from one (after a confirmation; the seed is kept). **Sliders:** bounded float parameters up to 10 wide get a range slider under their number input (`params_forms.slider_step`, step about a hundredth of the range; a progressive enhancement in `static/js/site.js`). The number input stays the labelled, keyboard-accessible control; the slider is hidden from assistive technology. **Live preview** (`nrmps/previews.py`, `simulation_manage` panel "What these parameters give"): applicants, programs, positions, tightness, interview slots, applications, signals and the interview cap per applicant, the pairs against the size limit, the parameters' warnings, and inline-SVG pictures of applicant strength and program quality (the normal mixtures asked for) and positions per program (drawn from the seed as a run would). It is computed on the server from the form as edited (HTMX, 600 ms after typing stops, nothing saved), so it cannot drift from the engine; uploaded sides are shown as uploaded. The panel stays in view on wide screens. **Unsaved changes:** the parameter form shows an "Unsaved changes" badge once edited and the browser asks before leaving with changes unsaved. Tested: presets (valid, within the limit, change only what they say, keep the seed), creation from a preset, applying one, the preview (numbers, uploads, errors, the size limit, ownership), slider steps, and in the browser the preview following the form, slider and input in sync, the badge, and applying a preset. **Deviation:** distribution previews are pictures of the requested distributions, not previews of a generated population (that is the Population tab of a run). |

| 4.3 Help registry and "?" | Done | Parameters are described by the typed schema (title, description, unit, range, default), so `nrmps/help_registry.py` covers the rest: **actions** (Run, Save, Save and run, Apply preset, Upload, Remove, Delete run, Delete simulation, Download CSV), **columns** (every column of the applicant, program, agent and application tables) and **pages** (a Help panel for each page: what it is, what to do there, its buttons and columns, and a link into the guide). Strings use `gettext_lazy`. `nrmps/checks.py` adds system checks, so gaps fail `manage.py check` and CI: H001 a parameter (or list column) without a title or description, H002 a page naming an unknown action or column, H003 a link to a section the help page does not have. `{% help_icon %}` renders a "?" button with a popover (native Popover API: top layer, so a scrolling table never clips it; Escape and a click outside close it; anchored next to its button where the browser supports anchor positioning, centred elsewhere); an unknown key raises, so a page using one fails its tests. `{% page_help %}` renders the Help button and panel. Every parameter field now also shows its range, unit and default, with a link to its row in the guide's parameter reference (each row has an anchor). Tested: the checks (and that they catch gaps), every link and parameter anchor resolves on the help page, the popover markup, a Help panel on every page, column and action help, field facts, a guard that popover elements carry no display class, and in the browser keyboard use (Enter opens, Escape closes) with an axe scan while a popover is open. **Found and fixed while testing:** daisyUI's `card` class on a popover element overrode the browser's hiding of closed popovers, so every popover showed; the popover element now carries no display class. **Deviations:** no separate `help/` package, markdown content files or per-field popovers (field help is visible under each field, which the schema already provides); per-page panels are rendered into the page rather than fetched with HTMX. |

| 4.4 The /help/ guide | Done | The single help page became a guide of nine pages (`/help/` and `/help/<slug>/`): Help (quick start, the guide, limitations), How the Match works (participants, timeline, deferred acceptance, stability and why truthful ranking is safe, what is and is not modelled), The simulation model (every stage of model 2.1 with its formulas, randomness and reproducibility, and a worked example), Reading the results (every tab and metric), Parameter reference (generated from the schema, with an anchor per parameter), CSV files (upload rules and every download's columns), Glossary, Questions and About and citing. Pages are Markdown in `nrmps/help_content/` rendered by `nrmps/guide.py` with markdown-it (raw HTML off) and cached; formulas written in TeX become **MathML on the server** (`latex2mathml`), so they need no script or fonts and screen readers read them. Shortcodes keep numbers in step with the code: `{{name}}` values (default market, limits, versions, CSV columns) and `[[name]]` blocks (the parameter reference, and a worked example computed by the engine: one applicant's utility term by term, which the tests check adds up to the engine's own). Help links now target guide pages ("model", "index#quick-start"); check H003 verifies each page and section exists. `CITATION.cff` added. Tested: every page renders with no shortcode left, formulas become MathML with no TeX left, raw HTML is escaped, the worked example, every internal link resolves, and axe and phone width on seven guide pages (a scrolling formula needed keyboard focus, and a long URL needed to wrap). **Deviations:** MathML instead of KaTeX (no JavaScript, fonts or vendored files; MathML Core is supported by current browsers); the executable examples are computed live rather than written into the text and verified by a test. |

| 4.5 Onboarding | Done | **Landing page:** what the simulator does, the seven stages of a run (daisyUI `steps`), questions to explore with the presets, the guide, and your three latest simulations with their match rate. **Try a demo** (`/demo/`): pick a market (NRMP-like, small classroom, preference signals); the demo creates a simulation from the preset, runs it and opens its results, within the usual quotas and rate limits. Visitors reached it through sign-up: `signup?next=/demo/` continues to the demo after the account is created (only same-site `next` URLs are followed); since a later owner request they can see it without an account (see "Visitors see the demos" below). **Getting started** checklist in the run panel of a simulation until it has two successful runs (choose the parameters, run, explore the results, change a parameter and compare), updated with the panel after each run. The empty simulations list offers the demo. Tested: the landing page for visitors and users, the sign-up redirect (and that a foreign `next` is ignored), the demo (markets, fallback, quotas, login), the checklist through two runs, the empty list, and in the browser the demo from the landing page to its results, with axe and phone width on `/demo/`. **Deviations:** no guided tour (optional in the plan); the exit criterion (3 of 3 first-time testers reach the results through "Try a demo" without help) needs people and is left to the owner. |

| 4.6 Organise and reuse | Done | **Simulations list:** market size, a one-word state from the pipeline (up to date, out of date, not run yet, running, failed, invalid parameters), the latest run with the latest successful run's match rate, and Open, Duplicate and Delete. **Duplicate** copies the details, parameters (with the seed, so runs are comparable) and uploaded populations, not the runs, within the simulation quota. **Parameter files:** download a simulation's parameters as JSON and load them into any simulation (a parameters download or a run's `params.json`; validated, with the errors listed; the file's seed is used when it has one; within the size limit). **Saved presets** (`SavedPreset`, migration 0018; quota `NRMP_MAX_PRESETS`, 50): save a simulation's saved parameters, without the seed, under a name; they appear as "Yours" beside the built-in presets on the new-simulation page and in Apply preset, are listed (and deletable) on the simulations page, are included in the personal data export and are shown in the admin. A saved preset that no longer fits the schema is reported rather than applied. Tested: the list, the state summary, duplicate (copies, ownership, quota), parameter files (round trip, keeping the seed, bad files, privacy), presets (saving, names, quota, starting a simulation and applying one, other users' presets, deleting, schema drift) and the export. |

| 4.7 Help quality gates | Done | In CI: the help system checks H001–H003 (every parameter described, every page's actions and columns in the registry, every help link resolving to a guide page and section) run with `manage.py check --deploy --fail-level WARNING`; a coverage test fails when a column of a results table (applicants, programs, applications, both views of an agent) has no "?" help (only "#" and "Name" are exempt); the guide's tests check that every page renders without leftover shortcodes, that formulas become MathML and that every internal link resolves; the browser suite runs axe and the 390 px check on every guide page, taken from the guide's page list so a new page is covered without editing the test; codespell covers the guide's Markdown. |

**Phase 4 exit criteria:** the help checks pass in CI (above). The onboarding test with first-time testers (3 of 3
reach the results through "Try a demo" without help) needs people and is an owner action; the browser test of the
same path (landing page, Try a demo, the demo's results) passes.

**After Phase 4 (owner feedback): waiting runs.** A queued run's page looked half done: "Queued, 0%" above a stages
table with only the population finished (it is built when the run starts). The stages table now lists every stage:
finished, in progress, waiting, or not run (after a failure, or for a run from before the stage existed). It
refreshes while the page polls, and the worker records each stage as it finishes, with its own start time. The
progress block says what the run waits for: the population is ready, and N runs are ahead of it. It warns when no
worker is running (at once, from the heartbeats), when the worker stops during a run, and when a run has been queued
for longer than `NRMP_QUEUE_WARNING_SECONDS` (60), with the command to start a worker in development and a link to
/ops/ for staff. The run panel and the stepper on the simulation page show the same (stepper states finished,
running and waiting replace "queued" on every stage). Tested: stages recorded as they finish, every row state, the
polled table, runs ahead, each warning, and the stepper.

## Phase 5: Visualization suite

Step 3.8 had already vendored ECharts and started `static/js/nrmp-charts.js` (a registry of chart kinds, resizing,
clean-up on HTMX swaps, escaped tooltips, theme-aware colours) with nine charts; 5.1 completes that foundation.

| Step | Status | Notes |
|---|---|---|
| 5.1 Foundations | Done | **Registry** (`static/js/nrmp-charts.js`): one registry for ECharts charts and sigma.js networks (`register(kind, build, {engine})`); charts are drawn when they come near the screen (`IntersectionObserver`), resize with their box, redraw when the theme or the patterns setting changes, and are disposed of when HTMX removes them; a chart that cannot be drawn (no WebGL, say) is marked and leaves the others alone. **Safe tooltips:** every tooltip is built by `tip()`, which escapes every value, and numbers by `format.*` (`Intl.NumberFormat` in the page's language); a browser test uploads a program named `<img src=x onerror=...>` and shows its tooltip: the name stays text (and with escaping disabled the test fails). **Chart tokens and dark mode** (`styles.css`, `--viz-*`): series 1 applicants, series 2 programs, series 3 a match, neutral grey for everything else, a blue ramp for stages; separate dark values; every colour at least 3:1 against the card in its theme (checked by script). **Display settings** replace the dark-mode toggle: the theme (the system's, light or dark; the old toggle could not go back to the system's) and "Patterns as well as colours" (ECharts decals, also on with the system's "more contrast" preference). **sigma.js 3.0.3 + graphology 0.26.0** vendored (`npm run vendor`, MIT, with licences), with a first network: on each applicant's and program's page, its applications on rings by how far each got (not invited, invited, interviewed, ranked, matched), with a key of counts and a summary sentence; hover labels follow the theme; no zooming or panning, so scrolling the page never gets caught (`charts.ego_network`, at most 2,000 applications, the furthest first). **Chart catalog** (`help_registry.CHARTS`): each chart's question (its caption), what it shows, how to read it and caveats, its place and colour; `{% chart_figure %}` renders a chart from its entry with a "?" popover; the guide's Reading the results page lists them all (`[[chart_catalog]]`), and the popovers link there; check `nrmps.H004` fails incomplete entries. **Help search** (HELP-25): `/help/search/` and a search box on every guide page search one index of the guide's sections (with their text), the glossary (terms now have anchors), every parameter (list tables too), the charts, and the columns and buttons of the registry; every word must match, titles rank first. **CSP, report-only** (`SECURE_CSP_REPORT_ONLY`, Django's `ContentSecurityPolicyMiddleware`): `'self'` only, a nonce on the one inline script (the theme), no inline handlers (the rows-per-page select moved to `site.js`), `'unsafe-eval'` until 5.5 moves the list editors to Alpine's CSP build; browsers report to `/csp-report/`, which logs each distinct violation once per process. Every browser test now fails on any policy violation (none today), and one checks the policy is live. **Found and fixed while testing:** graphology's minified file points to a source map, which Django's manifest storage must resolve, so collectstatic (and the Docker build) failed until the map was vendored too (`npm run vendor` now copies referenced maps; a test guards it); and CI's deploy check had been failing since step 4.4 without anyone seeing it (the branch was never pushed): the help checks render guide pages whose sample-file links need the static manifest, so CI now runs collectstatic first, as the Docker build does. **Deviations:** the ego network (MAT-7, planned for 5.4) is 5.1's first network so that the sigma integration is tested on real data; 5.4 adds the market-wide views. graphology-library (layouts, communities) waits for 5.4, which needs it. Help search is on the server (a results page) rather than an Alpine filter over a JSON index: it needs no script, works under the strict policy and is testable without a browser. No "keep the previous render at 55% opacity while refetching": charts are not refetched until the data API (5.2). |
| 5.2 Data API | Not started | |
| 5.3 P0 dashboards | Done, except warnings | The Match tab's charts and the two that followed (see "The Match tab's charts" and "Interviews per applicant, and the match rate by list length" below): the choice matched to, the match rate by the length of the rank order list, who matched where (the assortativity heatmap, with the sorting), positions filled by program quality, who matched by strength decile, and, on the Applications and interviews tab, who gets the interviews. With the charts of steps 3.8 and 5.1 (population, true against observed, first-choice demand, the funnel, the applicants' flow) and the key numbers on each tab, every P0 chart of the plan is there for a single run. Not done: warnings on degenerate inputs. |
| 5.4–5.5 | Not started | |

**After 5.1 (owner request): the funnel for one applicant or program.** The Sankey funnel of the Applications and
interviews tab also appears on each applicant's and program's page, beside its network: the same five stages over
that agent's applications, with "Ranked" meaning the agent's own rank order list (`charts.agent_funnel`; catalog
entries `funnel_applicant` and `funnel_program`). A program's funnel shows at a glance, for example, that it ranked
143 applicants yet filled 7 of 17 positions because most of them matched elsewhere. Tested: the funnel counts the
same applications as the network, stage by stage; both draw in the browser, in both themes and at phone width.

**After 5.1 (owner request): the applicants' flow, with Colour by strength.** A second flow chart on the Applications
and interviews tab counts each applicant once: Applicants → Interviewed (at least one interview) → Matched, with the
drop-offs "No interview" and "Interviewed, not matched" (`charts.applicant_flow`, chart kind `flow` in
`nrmp-charts.js`). Its **Colour by strength** switch splits every stage into fifths of applicant strength (by rank,
each rank at its centre so the leftover applicants are spread and a tie at the top is treated like one at the bottom;
ties kept together in the fifth of their middle rank; refused, with the reason beside the disabled switch, for fewer
than five applicants or ties that would leave a fifth under 10% or over 30%), so the quality of the applicants can be
followed through the stages; a key appears with it, the choice is remembered in the browser, and "The numbers" gives
every fifth's counts, splitting "No interview" into never invited and invited without an interview (which the model
allows when a program's slots fill first). Chart switches are generic: a catalog entry names the option
(`ChartHelp.switch`, checked by H004) and the figure renders the toggle. Per application, strength misleads at the
match (strong applicants hold many interviews but match once), which is why this view counts applicants. A review
workflow (three reviewers, each finding checked by a skeptic) confirmed 11 of 15 findings, all fixed: unequal or
lopsided fifths with ties, the disabled-switch reason, labels running together at 390 px, zero flows drawn as
hairlines (also in the application funnel, whose nodes are now pinned to their columns), tooltip shares without a
base, a help sentence that misdescribed strength, tests that only checked identities, the guide's colour rule, and
an untested H004 rule. A second workflow checked each fix and found three more, also fixed: the fifths still
favoured the lower ones when n was not a multiple of five (so ties at either end were still treated differently),
the phone layout was chosen only when a chart was first drawn (a chart drawn wide and then narrowed kept overlapping
labels: charts now declare the widths at which their layout changes, `register(kind, build, {widths})`, and are
redrawn when resized across one), and a drop-off's per-fifth tooltip rows did not name their base.

**After 5.1 (owner request): Colour by strength by percentile, drop-offs included.** The switch now colours the
fifths with a diverging scale (tokens `--viz-div-1` to `--viz-div-5`: red for the bottom 20%, grey for the middle, blue
for the top 20%) instead of five shades of the blue ramp, which the flow drew at 35% opacity: neighbouring fifths
differed by an OKLab delta E of 2 to 4, where about 8 is needed to tell two colours apart. As drawn (70% opacity),
neighbours now differ by at least 12.6, and by 10.1 under simulated protanopia and deuteranopia, in both themes
(checked with the dataviz palette validator); the scale's middle steps are lighter than 3:1 by design, and every number
is in the tooltips and the table. The fifths are named by percentile (Bottom 20%, 20th–40th percentile, ..., Top 20%)
and the key is a scale from weaker to stronger. Each drop-off is one bar filled with the fifths' colours in proportion,
in the order ECharts stacks the arriving links, so each fifth's link lands on its own colour. A transparent spacer node
sets it apart from its stage, and a small bar of the same mix sits beside its label. Its tooltip gives each fifth's
count, its share of the drop-off and the share of the fifth it holds, and the summary sentence says how many of each
drop-off the bottom 20% make up. Hovering highlights a band's whole path (`focus: "trajectory"`). A separate piece per
fifth for the drop-offs was tried first and dropped: at these sizes it drew 1–2 px slivers with wider gaps. Found
while testing: `decal: "none"` on a data item throws in ECharts 6.1 when the chart is first drawn with the switch on
(toggling hid it, since a failed redraw keeps the old canvas). The spacer uses a transparent decal instead, and the
browser test now checks the chart after a reload and with patterns on.

**After 5.1 (owner request): Colour by strength on a program's funnel.** The funnel on a program's page has the same
switch (the same choice, remembered with the flow's). It splits the program's applications by the applicant's
strength fifth among all applicants, the fifths and strength ranges of the applicants' flow (`charts.agent_funnel`
with `strength`), in the same colours and with the same drop-off bars. The table adds a column per fifth, and the
summary says what share of the applications, interviews and matches came from the top 20%. The splitting is shared:
`strengthSankey` in `nrmp-charts.js` draws both charts' fifths, horizontal or, for the funnel below 560 px, top to
bottom, with the stage labels in the left margin and the drop-off labels under their bars. An applicant's funnel has
no switch, since all its applications come from one applicant.

**After 5.1 (owner request): the funnels' phone labels.** Below 560 px every funnel (the Applications and interviews
tab's, and an applicant's or a program's, with the switch off) used to let ECharts place its nodes and put each label
to the right of its bar, so labels ran off the right edge and printed over each other ("Ranked" on "Not ranked",
"Matched" on "Not matched"). They now use the switch's layout: each row keeps its order (the stage, then its
drop-off), the stage names sit in the left margin and each drop-off's label under its bar. An ECharts `labelLayout`
moves a label back inside the chart when a small drop-off at the end of a full row would push it past the edge (a
program that invites everyone). Such a label can then sit on the links below it, so drop-off labels there have a halo
in the background colour. The browser test measures every label as drawn (ECharts' own geometry) at phone width,
with the switch on and off, and fails on a label outside the chart or overlapping another.

**After 5.1: "database is locked" on SQLite with the worker.** With the web server and the worker
(`TASK_BACKEND=database`) on one SQLite file, starting a run sometimes failed with a 500, "database is locked". The
simulation was saved but no run was created. Django opens SQLite transactions DEFERRED: `start_run` reads first, and
its write then fails at once, without waiting, while the worker is writing. SQLite databases (a `sqlite:///` URL or
development's `db.sqlite3`) now use `transaction_mode` IMMEDIATE with a 20 s timeout, so a transaction takes the write
lock at BEGIN and waits for it. A reproduction (the real `nrmp_worker` polling every 0.05 s while runs are started as
the demo view starts them) refused 10 of 40 before, and none of 200 after (40, 40 and 120). PostgreSQL, used in
production, is unaffected. Tested: the settings for both SQLite configurations, and PostgreSQL's unchanged.

**2026-09-30: first production deploy of this branch.** `main` and `production` were fast-forwarded to it (from
`64ba63c`). Its first CI run failed only because the migrations check ran before static files were collected, so
the help checks could not resolve their static links; the steps are now in the right order. Railway deploys the
`production` branch. The first deploy failed at the pre-deploy migration because `DATABASE_URL` was not set. With
it on a new PostgreSQL database, the next deploy applied every migration to the fresh database and passed its health
check, which counts runs and so needs the tables. gunicorn 26 then logged "Control server error: Permission denied:
'/home/app'" at every start: it creates a control socket in the home directory, which the image's unprivileged user
does not have. `entrypoint.sh` now starts it with `--no-control-socket`.

**After 5.1 (owner request): the flow on the summary, clearer run tabs.** The Summary tab's card now ends with the
applicants' flow, its Colour by strength switch on from the start (`{% chart_figure ... switch_on=True %}`; a choice the
reader made is still remembered and wins). The run's tabs, an easily missed underline before, are a daisyUI
`tabs-box` bar with the current page in the primary colour. The primary is darkened a fifth for it: the axe check
found the dark theme's own primary under 4.5:1 with its text. A three-line `{# #}` comment printed as text above the
tabs during the change (Django only knows one-line `{# #}` comments). A new test fails on any template comment that
spans lines.

**After 5.1 (owner request): an idealized demo market.** A new preset, `idealized`, is offered on the demo page,
second after the NRMP-like market. Each side has one measure, seen exactly at every stage:
- agreement 1 on both sides, no attribute weight and no taste;
- no noise before, at or after interviews, and none in applicants' self-assessment;
- one applicant group.

The application and interview limits of the NRMP-like market stay (the owner's choice). The choices are made
deterministic: 30 applications each, interview offers accepted best first, every interviewee ranked. At seed 2026 every
rank list follows true quality and the match sorts far more closely: Spearman's correlation of applicant strength with
the matched program's quality is about 0.94, against 0.72 in the NRMP-like market. Fewer applicants match, though:
about 82% against 88%. Because every program wants the same applicants, programs interview strong applicants who
applied to them as a safety, lose them all to better programs and leave positions empty. Noise in the NRMP-like market
spreads interviews around, and yield protection barely helps (83%). Without the limits (applications to every program,
interviews for everyone) the engine sorts perfectly: the strongest applicants fill every position, with no stronger
applicant at a worse program. A test checks that perfect sorting on a 60 × 8 market, because the interview caps cannot
reach every applicant at 1,000 × 142.

**After 5.1 (owner request): a noisy demo market.** A new preset, `noisy`, is offered third on the demo page. It is the
idealized market seen through the largest noise the parameters allow:
- pre-interview noise 3 on both sides, so each view correlates about 0.32 with the truth;
- interviews correct nothing (informativeness 0);
- self-assessment noise 2.

Both presets are built from one helper, `presets._one_measure`, and a test checks that only those four values differ.
At seed 2026 each agent's ranking agrees with the true ranking as theory predicts for that noise: a mean Spearman of
0.30 for applicants and 0.305 for programs, against 0.303 in theory. Over seeds 2026, 7 and 11 the noisy market fills
nearly every position it can: 92.3% of applicants match, where the most possible is 92.6% (82% in the idealized
market). But who goes where is close to random: Spearman's correlation of strength with the matched program's quality
is 0.26, against 0.94 idealized and 0.72 NRMP-like. Noise spreads interviews around, so people find places, and
scrambles the sorting.

**After 5.1 (owner request): signals in the idealized market, two demos.** Both are offered on the demo page after the
idealized market. Each adds 3 gold and 5 silver signals to it, sent to programs at the applicant's own level first
("realistic") and read by every program; a test checks that nothing else changes:
- **Idealized market with signals** (`idealized_signals`) adds yield protection 2: programs pass over stronger
  applicants who did not signal them.
- **Idealized market, signals first** (`signals_first`) has programs invite everyone who signalled them first.

Over seeds 2026, 7 and 11, against the idealized market's 82% of applicants matched and 88.7% of positions filled:
- with signals and yield protection, 90% are matched, 97% of positions filled and sorting stays at 0.90;
- with signals first, about 90% are matched, but the top fifth matches about 10 points less (78–85%), because strong
  applicants lose interviews to weaker ones who signalled. Over seeds 100–119 the gap is 5.7 points on average and the
  top fifth does worse on 15 of 20 seeds, so the demo's description says "usually".

Signals sent to applicants' top choices instead (`top_utility`) change no invitation: they go to programs 47
percentile points above the applicant on average, and a boost of 0.8 never reaches those programs' invitation range.
The same 8,000 signals sent at the applicant's level change 3,074 invitations.

**The demo button's spinner.** "Run the demo" had a gap before its label: the loading spinner of a button is an
`htmx-indicator`, which htmx only makes transparent, and the demo form is a plain form, so it never showed. Indicators
now take no room until their request runs (`styles.css`), which also closes the same gap on the run panel's Run button.
Plain forms opt in with `data-busy` to show theirs while they submit and to ignore a second submission (`site.js`).

**After 5.1 (owner request): noise on one side only, two demos.** Both are the idealized market with the noisy
market's noise (3, kept through interviews) on one side, and applicants knowing where they stand. A test checks that
nothing else changes, and that the blind side's rankings agree with the truth as theory predicts (0.30) while the other
side's are exact:
- **Noisy applicants, perfect programs** (`noisy_applicants`): programs cannot judge applicants. Strength stops paying
  off. Over seeds 2026, 7 and 11 the top fifth matches 75% and the bottom fifth 96% (idealized: 96% and 32%). Applicants
  still apply where they belong, and the most sought-after programs draw 70.6 applications per position against 22–25
  for the others. Picking almost at random there, those programs leave the strongest applicants unmatched most often.
  Interviews even out: 7.6 per applicant in the bottom fifth instead of 3.8, 7.9 in the top fifth instead of 9.6.
  Over seeds 100–119 the top fifth matches less often than the bottom fifth on 19 of 20 seeds, and least of all five on
  14, so the demo's description says "usually".
- **Noisy programs, perfect applicants** (`noisy_programs`): applicants cannot judge programs. Programs still take the
  strongest (the top fifth all match, the bottom fifth 5%), but where applicants match follows strength much less
  (sorting 0.61 against 0.94), and 78% match against 82%.

**After 5.1 (owner request): visitors see the demos.** "Try a demo" on the landing page now opens the demo page for
visitors too, instead of the sign-up page, so anyone can read the markets. In place of "Run the demo" a visitor gets
"Log in to run the demo" and "Sign up". Both keep the market they picked (`/demo/?preset=…` becomes the `next` page),
so after logging in or signing up they are back on the demo page with it chosen, one click from running it. A
visitor's request only redirects: nothing is created without an account. The login page now passes `next` on to its
sign-up link, so a visitor without an account who pressed "Log in" still comes back. Tested: the page for visitors
and users, the redirects (log in, sign up, an unknown market), coming back with the market chosen, the login page's
sign-up link (a foreign `next` is dropped), and in the browser a visitor from the landing page through logging in to
the demo's results, with axe and phone width on the visitor's demo page.

**Step 5.3, in part (owner request): the Match tab's charts.** The Match tab was the one stage without charts (its
choices were plain bars in a table), and nothing in the app showed *where* applicants match by strength, which the
idealized and noisy demos are about. Four charts, each with its question, "?" help, summary sentence and table:
- **Do stronger applicants match to better programs?** A heatmap: applicants in strength fifths (rows, the top 20% at
  the top) against where they ended up (columns): not matched, or a program in each quality fifth. Each cell is its
  share of the row. The scale is fixed from 0% to 100%, so two runs compare: blue for matches, neutral grey for "Not
  matched". The summary gives the **sorting**, the rank correlation between an applicant's strength and the quality of
  the program they matched to, as the demo tests measure it. The applicants of one program share its quality, so the
  ceiling is just under 1 (0.99 with 8 programs of 6 positions, 0.99999 with 250 of 8); the help says so. On the
  local demo runs: idealized 0.96, noisy applicants 0.91, NRMP-like 0.70, noisy programs 0.51.
- **Which choice did applicants match to?** Bars for the first to the tenth choice and lower ones together, replacing
  the table with bars (its numbers are under "The numbers").
- **Which programs fill their positions?** Positions filled and unfilled by program quality fifth, with the number of
  programs that have an unfilled position.
- **Do stronger applicants match more often?** Each strength decile split into matched, not matched (with a rank
  order list) and no list; the deciles are those of the table below it (one function, `outcomes.strength_decile`).

Everything is computed when the page is shown, from the stored population and decisions, so runs made before this
change get the charts too. Three new chart kinds in `nrmp-charts.js`: `bars`, `shares` (stacked to 100%) and
`heatmap`. The heatmap's scale runs from nearly the background through the stage ramp, placed so that lightness
changes evenly with the share (the ramp passes the dataviz validator's ordinal checks in both themes); each cell's
label takes the ink or the background colour, whichever contrasts more. **Found by looking at the drawings:** a gap
between stacked parts swallowed parts of one percent, so a bar seemed to stop at 98% (the parts now touch, and both
greys show against the background); on a phone the heatmap's column labels ran into each other and its axis name was
cut off (smaller labels, "No match" for "Not matched", the name on two lines), and a legend of three wrapped onto the
bars (more room above them). Tested: the payloads against the run's own numbers (every applicant once, positions and
programs add up, the deciles agree with the table), constructed markets (perfect and reversed sorting, unmatched
applicants, unfilled positions, sides that cannot be split into fifths), the page, and in the browser the drawn
charts wide and at phone width, with patterns on, and axe in both themes.

**Step 5.3, the rest (owner request): interviews per applicant, and the match rate by list length.**
- **Who gets the interviews?** (INT-2, Applications and interviews tab): applicants by their number of interviews,
  from none to the most (numbers from 20 share a last bar). The **Colour by strength** switch stacks each bar by
  strength fifth in the diverging scale, as on the applicants' flow. The summary gives the mean, how many had none and
  how many the most, the share of all interviews held by the tenth of applicants with the most, the Gini coefficient,
  and the mean of the bottom and of the top fifth. On the local NRMP-like demo run: 8.1 interviews on average, 4.8%
  with none, 43.6% at the limit of 12, and 4.7 against 10.1 for the bottom and top fifths.
- **Does a longer rank order list help?** (ROL-1, Match tab, under the rank order lists' numbers): applicants with a
  list by the number of programs on it, matched and not, as NRMP's Charting Outcomes shows it. On the same run 55% of
  those who ranked one program matched, about 80% with two to four, and nearly all from five. The plan's split by
  strength and its uncertainty band wait for replicates (6.1): in one run the groups are too small. The help says that
  a long list is a sign of a strong application, not only a cause of matching. A chart with one bar is not drawn.

The Applications and interviews tab now has two charts with the Colour by strength switch, so turning one turns
every chart on the page with that switch (before, another chart would have followed only after a reload). The bars
chart kind gained the split by strength fifth. Tested: the payloads against the run's own numbers, constructed markets
(concentration, the last bar from 20, lists shorter than the interviews, lists all alike), the pages, and in the
browser both charts, the two switches following each other, patterns and phone width.

## Phases 6–8

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
