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
| D4 | Interim size cap | Step 0.4 | Set from a measurement in step 0.4 (see below). |
| D5 | Job backend | Step 2.5 | Open. |
| D6 | Name and trademark | Step 0.7 | Disclaimer only; a name change is the owner's call. |
| D7 | Browser Explorer approach | Step 2.2 | Open. |

## Phase 0: Stabilise production, fix the first run, stop data loss

| Step | Status | Notes |
|---|---|---|
| 0.0 Dependency upgrade (added) | Not started | |
| 0.1 Production mode | Not started | |
| 0.2 First run works | Not started | |
| 0.3 Patch the pre-interview stage | Not started | Also covers the post-interview helpers (L-1). |
| 0.4 Atomic, fast, bounded steps | Not started | Also fixes stale status after cascades (L-2). |
| 0.5 XSS | Not started | |
| 0.6 Upload data loss | Not started | |
| 0.7 Honest public pages | Not started | |
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
