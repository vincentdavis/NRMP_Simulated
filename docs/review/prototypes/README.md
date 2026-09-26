# Reference prototypes (Python)

Two scripts from the project review, kept as working references. **They are not part of the app.** A local `ruff.toml` excludes them from the project's lint baseline, and their names don't match pytest's `test_*.py` pattern, so they aren't collected.

## `pipeline_proto.py`: full singles stage pipeline

Reference for Plan Phase 3 and [Appendix B](../B-stage-spec.md). It is one numpy/Python file with these stages:

| # | Stage |
|---|---|
| 1 | population |
| 2 | true utilities |
| 3 | additive pre-interview noise |
| 4 | reach/target/safety applications |
| 5 | gold/silver signals |
| 6 | screening |
| 7 | invitation waves under interview slots, with applicant accept caps |
| 8 | interview fit shock plus post-interview observation |
| 9 | strict rank order lists with do-not-rank |
| 10 | **applicant-proposing deferred acceptance** (a heap per program) |
| — | blocking-pair check |
| 11 | SOAP (4 offer rounds, ≤ 45 applications, binding) |
| — | NRMP-style statistics |

```bash
uv run python docs/review/prototypes/pipeline_proto.py   # runs 2000×200 and 5000×500, prints statistics
```

In the review:
- the DA agreed with `matching` 1.4.3 (`HospitalResident`, resident-optimal) on 20/20 random instances;
- it gave 0 blocking pairs at every scale;
- it took 0.04 s at 10k × 1k.

**Caveats.**
- It uses the reviewer's simpler utility model, not [Appendix A](../A-model-spec.md).
- Its outcome numbers are uncalibrated: it runs at about 1.29 applicants per position, versus NRMP's 1.08.
- It holds dense A × P arrays; the production engine should store applied pairs sparsely (Plan 2.3).
- Application choice uses one global `rng` rather than the per-stage streams of Appendix A §3.

## `suite_prototype.py`: starter test suite

Reference for Plan 1.1. It uses pytest-django and hypothesis:
- a non-owner gets 404 on 4 routes;
- the HTMX create-students POST returns only the `#population-counts` fragment;
- a hypothesis property test (300 random markets) checks capacity, individual rationality and no blocking pairs for a reference DA.

Two tests **fail on purpose against today's code**, because they pin real bugs:
- `test_default_config_is_valid` (SIM-2);
- `test_pre_interview_rating_adds_noise_not_scales` (SIM-1).

To adopt it:
1. Add `pytest-django`, `hypothesis` and `factory-boy` to the dev group, and `[tool.pytest.ini_options] DJANGO_SETTINGS_MODULE = "NRMP_Simulated.settings"`.
2. Move it to `nrmps/tests/test_*.py` and split it by topic (Appendix G).
3. Fix one thing on the way: the `markets()` strategy's `if draw(st.booleans()) or True` always keeps every applicant, so programs never truncate their lists. Draw a real boolean so markets with unacceptable applicants are generated too.
4. Its reference `deferred_acceptance` becomes a test oracle for `nrmps/engine/match.py` (Plan 3.6).
