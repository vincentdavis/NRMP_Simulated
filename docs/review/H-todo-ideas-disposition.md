# Appendix H: Disposition of `TODO.md` and `IDEAS.md`

The phased plan in [PROJECT_REVIEW.md §9](../PROJECT_REVIEW.md#9-phased-implementation-plan) replaces `TODO.md` as the backlog (CRIT-15). This table maps every item to one of these outcomes:

- **Plan N.N**: scheduled in that plan step.
- **Done**: already true.
- **Superseded**: replaced by a better-specified item, which is named.
- **Re-scoped**: kept, with the scope changed as described.
- **Backlog**: sound idea, not scheduled.
- **Dropped**: not pursued, with the reason.

Phase 1.10 replaces `TODO.md` with a short pointer to the plan, so the two can't diverge.

## TODO.md

| # | Item (TODO.md line) | Disposition |
|---|---|---|
| 1 | Implement interview phase (`simulation_engine.py:167`) | **Superseded → Plan 3.4** on the Phase 2 engine. Don't build it on the per-row ORM engine (SIM-24). |
| 2 | Implement student final ranking (:175) | **Plan 3.5.** "Ranking limits and cutoffs" become ROL policies: top-k, reservation utility, ≤ 300 (STG-14, OPT-18). |
| 3 | Implement school final ranking (:183) | **Plan 3.5**, corrected. Capacity limits the *match*, not the length of a program's rank list; programs rank many more applicants than they have positions (STG-1). |
| 4 | Implement NRMP matching algorithm (:21 cites line 189; `match()` is at 188) | **Plan 3.6.** Our own applicant-proposing DA with an oracle test. Write `MatchResult` rows, not the current `Match` model (SIM-21, STG-16, STG-19). |
| 5 | School invitation logic, plus "invitation limits per school" | **Plan 3.3**, corrected. The unit is *interviews per position* (≥ 1, default about 10), not a fraction of capacity (OPT-6). |
| 5b | "Create UI for schools to manage interview invitations" | **Re-scoped → Plan 7.3.** Invitations are simulated behaviour. Manual decisions belong only in classroom mode. |
| 6 | Interview scheduling system (date/time fields, slots, calendar views) | **Superseded → Plan 3.3.** Invitation waves plus an optional date-conflict constraint (`interview.n_dates`) model the same effect. A calendar UI adds nothing to the simulation (OPT-17, SIM-16). |
| 7 | Simulation workflow UI (progress, wizard, status dashboard) | **Plan 2.4 + 4.1** (stage state machine, workspace stepper; UX-6, UX-7). |
| 8 | Data visualization (population charts, match outcomes, ranking distributions) | **Superseded → Plan 5** ([Appendix E](E-visualization.md) catalog). |
| 9 | Bulk operations UI: CSV experience, validation feedback | **Plan 0.6 + 1.7** (atomic validated upload, CSV v2, row-level errors). |
| 9b | Bulk edit capabilities | **Backlog.** Download → edit → upload (lossless after 1.7) covers most needs. |
| 10 | Database query optimization (indexes, bulk operations, caching) | **Plan 0.4** (`bulk_update`), **2.2** (vectorised engine), **2.3** (indexes, sparse rows), **5.2** (payload cache). |
| 11 | Pagination: search/filter, large datasets | **Plan 1.8 + 4.1** (filters, numbered pagination, detail pages). |
| 11b | Virtual scrolling for very large lists | **Dropped.** Server-side pagination and aggregated charts; keyset pagination if needed (ENG-15). |
| 12 | Multiple matching rounds: SOAP, couples, specialty rules | **Plan 8.1, 8.3, 8.5.** |
| 13 | Preference modeling: sophisticated generation, correlation, geography | **Plan 2.1–2.2** ([Appendix A](A-model-spec.md): correlation knobs, Dirichlet weights, correlated attributes); geography **Plan 8.6**. |
| 14 | Simulation analysis: statistics, scenario comparison, reproducible reports | **Plan 3.7** (metrics), **6.1–6.2** (replicates, sweeps, A/B), **6.5** (bundles, citation). |
| 15 | User management: roles, sharing permissions | **Plan 7.1** (visibility, share links, collaborators) and **7.3** (classroom roles). |
| 15b | User activity tracking | **Re-scoped → Plan 2.5.** A staff-only ops page in the admin (runs per day, failures, p95 duration, quota use; CRIT-11), built once runs and quotas exist. No per-user tracking. |
| 16 | System monitoring: performance, error tracking, health dashboards | **Plan 1.2** (`/healthz`, backups) and **2.5** (a Logfire span per engine stage, worker heartbeat in `/healthz`, cleanup task, ops page; CRIT-11). |
| 17 | Unit tests (engine, models, forms) | **Plan 1.1**, plus property tests in **3.7** and model acceptance tests in **2.2**. |
| 18 | Integration tests (workflows, API endpoints, CSV) | **Plan 1.1 + 1.7.** API tests come with the API in **5.2**. |
| 19 | Refactoring: service layers, error handling, docstrings | **Plan 0.4 + 1.5** (error handling, ENG-16), **1.8** (ENG-14), **2.2** (ENG-23), **1.6** (docstrings). |
| 20 | Type safety: hints, stricter mypy | **Plan 1.1** (django-stubs plugin: 138 → 22 real errors) and **2.2** (strict mypy for the new `nrmps/engine/`). |
| 21 | API documentation | **Re-scoped.** No API exists today. Staff-only developer reference in **1.10 / 4.4**; document the JSON API when it ships in **5.2**. |
| 22 | User documentation: guide, CSV format, troubleshooting | **Plan 4.4** (`/help/` guide, FAQ) and **1.7** (CSV spec and samples). |
| 23 | Production: configure PostgreSQL | **Supported in code** (`DATABASE_URL` via dj-database-url). Verify it is actually set in production (**D0**). **Plan 0.1** adds a startup failure when it is missing. |
| 23b | Set up Redis for caching/sessions | **Dropped for now.** `django-tasks-db` plus `DatabaseCache` need no new infrastructure. Revisit only if load requires it (ENG-4, VIZ-13). |
| 23c | Proper logging configuration | **Plan 1.2** (one handler, logfire `console=False`, no per-POST INFO noise; ENG-21). |
| 24 | Containerization: Dockerfile optimization, docker-compose, deployment docs | **Plan 1.2** (multi-stage image, `.dockerignore`, pre-deploy migrate). docker-compose with Postgres is optional in 1.2; deployment docs in **1.10** (README, `.env.example`). |
| 25 | Monitoring and observability: APM, structured logging, health checks | **Plan 1.2.** |
| 26 | Fix typo `meta_preferances` (`simulation_engine.py:4`) | **Plan 1.6** (SIM-23; codespell with a project dictionary). |
| 27 | Edge cases: validation for empty populations | **Plan 0.3** (`validate_population()`; STG-11). |
| 27b | Edge cases: division by zero in scoring | **Dropped (moot).** `_score` does no division. The real edge cases are noise semantics and missing keys (SIM-1, SIM-4). |
| 27c | Improve error messages | **Plan 1.5 + 1.6** (toasts, error summary, domain exceptions; HELP-17). |
| 28 | Security: rate limiting for API endpoints | **Re-scoped.** There is no API; the exposed surfaces are login, signup and heavy actions. Login throttling in **0.8** (django-axes); signup and heavy-action limits plus quotas in **2.5** (ENG-5, CRIT-6). |
| 28b | Implement proper CSRF protection | **Done.** CSRF middleware is on, and HTMX sends the token via `hx-headers`. **Plan 0.1** adds `SECURE_PROXY_SSL_HEADER` for the TLS proxy. |
| 28c | Input sanitization for CSV uploads | **Plan 0.6 + 1.7**; CSV *export* formula-injection sanitising in **7.1** (CRIT-3). |

## IDEAS.md

| Idea | Disposition |
|---|---|
| Alternative matching mechanisms (TTC, RSD, compare outcomes) | **Plan 8.2** (CRIT-14). Add program-proposing DA first, which is cheap and the classic comparison (STG-19). |
| Preference revelation strategies (strategic vs. truthful reporting) | **Plan 3.5** (ROL strategy variants: truthful, truncated, likelihood-weighted) and **8.2** (incentive comparison across mechanisms). Manipulation *detection* and game-theoretic tooling: **Backlog.** |
| Bounded rationality (satisficing, limited information) | Partly **Plan 3.1 / 3.5** (noisy self-assessment in application strategy; reservation-utility ROL policy). Cognitive-load models: **Backlog.** |
| Social influence (peer effects, herding) | Herding in beliefs: the **halo** error share ψ (Appendix A §6, **Plan 2.2**). Peer and network effects: **Backlog.** |
| Information asymmetry (disclosure, signal quality, withholding) | **Plan 2.2 / 3.2 / 3.4** (pre/post noise, interview informativeness, signals with boosts). Experiments run with sweeps and A/B in **6.2**. |
| Capacity constraint experiments (over/under-subscription, dynamic capacity) | **Plan 2.1** (applicants-per-position as an input) plus **6.2** (sweeps); reversions in **8.4**. Mid-match capacity expansion: **Backlog.** |
| Geographic constraints (distance, regional clustering, two-body problem) | **Plan 8.6** (regions, home bonus, geographic signals) and **8.3** (couples with geographic constraints). |
| Specialty-specific features (research vs. clinical track preferences, fellowships, subspecialties, IMG constraints) | Research vs. clinical *orientation* is a program attribute plus applicant taste weights (Appendix A §4–5, **Plan 2.2**). IMG groups and visa screens: **Plan 6.3**. Specialties: **8.5**. NRMP C/P/A/R tracks and supplemental lists are a separate matter: **8.4**. Fellowship pipeline and subspecialty match: **Backlog.** |
| Dynamic preference evolution (during the season, interview effects, cascades) | Interview fit shock **Plan 3.4**; invitation waves **3.3**. Information cascades and social media: **Backlog.** |
| SOAP round simulation | **Plan 8.1** (STG-17: 4 offer rounds, ≤ 45 applications, binding acceptance). |
| Couples matching | **Plan 8.3** (STG-18, Roth–Peranson-style). |
| Match outcome prediction (ML, early warning, list optimisation) | **Backlog, with a caveat.** Keep this to research on *simulated* markets. Presenting it as personal predictions conflicts with the "results are not predictions" disclaimer (CRIT-5). |
| Market clearing analysis (imbalance, bottlenecks, utilisation) | **Plan 3.7** (metrics: unfilled, zero-interview share, wasted slots) and **5.3** (dashboards). |
| Network analysis tools (preference network, stability, blocking pairs) | **Plan 5.4** (bipartite and ego networks) and **3.7** (stability and true-preference blocking pairs; VIZ-10, VIZ-11). |
| Real-time dashboards (monitoring, sensitivity, scenario comparison, A/B) | **Plan 5.3 + 6.2** (VIZ-6, VIZ-14). |
| External data integration (ERAS import, USMLE scores, school rankings) | **Dropped for individual-level data.** It conflicts with the privacy and terms positions and with data-use rules (CRIT-4, CRIT-15). *Aggregate* public statistics feed calibration in **Plan 6.4**. |
| Research data-sharing APIs | **Plan 6.5** (experiment bundles) plus the read-only JSON API (**5.2**; CRIT-8). |
| Machine-learning pipeline | **Backlog** (low priority). |
| Multi-researcher workspaces (shared environments, experiment versioning, annotations) | **Plan 7.1** (collaborators); experiment versioning via runs and bundles (**2.3, 6.5**). Paper generation: exports in **5.5**. |
| Reproducible research (versioning, auto documentation, significance testing, publication output) | **Plan 2.2–2.3** (seed, snapshot, hashes), **6.1** (t-based CIs), **6.5** (bundles, CITATION, DOI), **5.5** (publication exports). |
| Gamification for education (sandbox, what-if builders, competitions) | **Plan 7.2** (public Explorer) and **7.3** (classroom mode, DA step-through). |
| Role-playing simulations (switch perspectives, historical recreation) | **Plan 7.3** (participants as applicants or programs); historical recreation via calibrated presets (**6.4**). Crisis scenarios: **Backlog.** |
| Multi-language support | **Backlog.** Help registry strings use `gettext_lazy` from Plan 4.3, so i18n stays possible (HELP-25). |
| Bias detection and mitigation (fairness constraints, diversity outcomes) | Group-level outcome metrics **Plan 6.3**. Fairness-constrained mechanisms: **Backlog** (research). |
| Regulatory change simulation | Enabled by presets plus paired A/B with common random numbers (**Plan 6.2, 6.4**): signals on/off, application caps, interview caps. |
| Market expansion scenarios | Specialties **Plan 8.5**; the rest **Backlog.** |
| Other matching markets (school choice, kidney exchange, housing) | **Out of scope.** The Django-free engine package (CRIT-8) could be reused. |
| Cross-market analysis | **Out of scope.** |
| Distributed simulation engine | **Dropped for now.** Vectorisation gives about three orders of magnitude (SIM-7), and background jobs cover long runs. Revisit after Phase 6 if sweeps need it. |
| Blockchain integration | **Dropped.** No value for a simulator. |
| Causal inference tools (RCT simulation, natural experiments, IV) | A paired A/B with common random numbers *is* a simulated RCT (**Plan 6.2**). The rest: **Backlog.** |
| Synthetic data generation (privacy-preserving, rare scenarios, validation datasets) | The population generator plus experiment bundles provide this (**Plan 2.2, 6.5**). Estimating parameters from data: **Backlog.** |
| Research collaboration and conference ideas | Not plan items. The validation report (**3.7**), CITATION/DOI (**6.5**) and the classroom mode (**7.3**) make the project presentable to the economics, CS and medical-education audiences listed. |
