# Findings register

Every finding from the review, grouped by dimension. Each entry gives the verified evidence (file:line refers to commit `01b1eb5`), the recommendation, the skeptical verifier's verdict and note, and the plan step(s) that close it. **Severity is the verifier-corrected value** (the original is shown when it changed). Where a verifier marked a finding *partially* confirmed, **the verifier note takes precedence** over the original text. A **lead note** records a later correction from the final document check.

Evidence paths under `scratch/` refer to scripts run during the review and are not committed (the prototypes in `docs/review/` are the exception).

| Dimension | Findings |
|---|---|
| [SIM: Simulation engine & data-model correctness (implemented steps)](#sim) | 24 |
| [STG: Missing & incomplete simulation stages vs. the real NRMP process](#stg) | 25 |
| [UX: UI/UX review](#ux) | 26 |
| [VIZ: Visualization suite: plots, graphs, networks, sliders](#viz) | 21 |
| [HELP: Help page and in-context "?" help](#help) | 25 |
| [OPT: Improved simulation options / parameter model](#opt) | 27 |
| [ENG: Engineering: security, performance, reliability, testing, deployment, code quality](#eng) | 26 |
| [CRIT: Completeness critic (cross-cutting)](#crit) | 15 |

## Index

| ID | Severity | Kind | Title | Verdict | Plan |
|---|---|---|---|---|---|
| [SIM-1](#sim-1) | 🔴 critical | defect | Pre-interview 'rating error' multiplies instead of adding noise, so observed ranks equal true ranks and an error of 0 becomes 1 | partially | 0.3 |
| [SIM-2](#sim-2) | 🟠 high | defect | Default SimulationConfig violates its own validators, and the score/stddev defaults are infeasible on a 0-1 Beta scale | confirmed | 0.2 |
| [SIM-3](#sim-3) | 🟠 high | defect | get_beta_parameters silently clamps sd and floors alpha/beta at 0.1, so realised mean/sd differ from what was requested | confirmed | 2.1 |
| [SIM-4](#sim-4) | 🟠 high | defect | A meta-key mismatch between the two sides crashes rating with a masked exception (500) and leaves partial writes | confirmed | 0.3 |
| [SIM-5](#sim-5) | 🟠 high | defect | CSV download/upload round trip loses meta_preference, so every observed score is 0 and every rank is an arbitrary tie | confirmed | 1.7 |
| [SIM-6](#sim-6) | 🟠 high | defect | CSV parser drops rows, reads schools' positional columns wrongly, mishandles Excel BOM, and silently accepts garbage | confirmed | 1.7 |
| [SIM-7](#sim-7) | 🟠 high | defect | Per-row .save() makes pre-interview cost about 4.4 ms per pair and hit the 30 s gunicorn timeout at about 7k pairs; a vectorised version is about 900x faster | partially | 0.4 |
| [SIM-8](#sim-8) | 🟠 high | gap | initialize_interview materialises the full N x M cross-product in memory and in the DB, for pairs that mostly never interact | confirmed | 2.3 |
| [SIM-9](#sim-9) | 🟠 high | gap | True utilities are never stored, so rating error, regret and information effects cannot be measured | confirmed | 0.3 |
| [SIM-10](#sim-10) | 🟡 medium | defect | Ranking breaks ties by DB row order, ranks over the whole cross-product, and runs N+M queries | confirmed | 0.3 |
| [SIM-11](#sim-11) | 🟡 medium | defect | Interview and config help_text is swapped or copy-pasted wrong, and field names are inconsistent; /documentation/ publishes the errors | partially | 1.6 |
| [SIM-12](#sim-12) | 🟡 medium | defect | Preference weights from clamped gauss(1, sd) are effectively random on/off switches at default settings | confirmed | 2.1 |
| [SIM-13](#sim-13) | 🟡 medium | gap | Preferences are almost identical across participants (Spearman 0.99): no idiosyncratic or horizontal component | partially | 2.2 |
| [SIM-14](#sim-14) | 🟡 medium | defect | Attribute (meta-score) generation cannot control the correlation with base quality and collapses under defaults | partially | 2.1 |
| [SIM-15](#sim-15) | 🟡 medium | defect | Capacity generation allows 0-seat and negative-mean programs, and the seats/applicants balance is never checked | confirmed | 2.1 |
| [SIM-16](#sim-16) | 🟡 medium | defect | The interview-limit fields have unworkable semantics, and application/signal/rank-list limits are missing | confirmed | 2.1 |
| [SIM-17](#sim-17) | ⚪ low | defect | Config form: meta-list validation gaps can crash population creation, and the comma-separated parsing is dead code | partially | 2.1 |
| [SIM-18](#sim-18) | 🟡 medium | gap | 'Latest config wins' but the UI edits one config in place, so there is no provenance of which parameters produced a population or result | confirmed | 2.3 |
| [SIM-19](#sim-19) | 🟡 medium | gap | No seed and mixed RNGs (random + scipy/global numpy) make simulations irreproducible and unsuitable for scenario comparison | confirmed | 2.2 |
| [SIM-20](#sim-20) | 🟡 medium | gap | No pipeline state machine: statuses never change, there are no guards, and destructive steps are non-atomic | confirmed | 0.4, 2.4 |
| [SIM-21](#sim-21) | 🟡 medium | gap | The Match model and Simulation.iterations/public are unused and cannot support multiple runs; a Run/RankList/MatchResult model is needed | confirmed | 2.3 |
| [SIM-22](#sim-22) | ⚪ low | gap | Docstrings claim steps the code does not perform (application choice); the rating stage ignores applications entirely | partially | 1.6, 3.6 |
| [SIM-23](#sim-23) | ⚪ low | defect | Dead, no-op and mis-typed code in models.py and simulation_engine.py | confirmed | 1.6 |
| [SIM-24](#sim-24) | 🟠 high | recommendation | Rebuild the engine as a seeded, vectorised, tested core before building the remaining stages | confirmed | 2.2 |
| [STG-1](#stg-1) | 🔴 critical | gap | No outcome stages: interview(), students_rank(), schools_rank() and match() are empty stubs, and the Match table is never written | confirmed | 3.6 |
| [STG-2](#stg-2) | 🔴 critical | defect | There is no true-utility stage, and observation error has no effect (multiplied in, not added) | confirmed | 0.3 |
| [STG-3](#stg-3) | 🟠 high | defect | Preferences are purely vertical: under default settings every applicant has the same #1 school | partially | 2.2 |
| [STG-4](#stg-4) | 🟠 high | gap | No application stage: student_applied is never set, and every student is treated as having applied everywhere (full cross-product) | partially | 3.1 |
| [STG-5](#stg-5) | 🟠 high | gap | No preference-signaling stage (gold/silver tiers); the student_signal field is unused | partially | 3.2 |
| [STG-6](#stg-6) | 🟠 high | defect | school_interview_limit allows fewer than 1 interview per position, and there is no invitation or accept/decline stage | confirmed | 2.1, 3.3 |
| [STG-7](#stg-7) | 🟠 high | gap | There is no stage state machine: status fields never change and steps can run in any order | partially | 2.4 |
| [STG-8](#stg-8) | 🟠 high | gap | No random seed anywhere, so no run can be reproduced | confirmed | 2.2 |
| [STG-9](#stg-9) | 🟠 high | gap | Simulation.iterations is editable in the UI but nothing uses it; there is no run table or aggregation | confirmed | 6.1 |
| [STG-10](#stg-10) | 🟠 high | defect | Stages read the latest, mutable config, so editing the config between stages silently mixes parameters | confirmed | 2.3 |
| [STG-11](#stg-11) | 🟡 medium | defect | Pre-interview scoring fails on common inputs: uploaded populations have no preferences, and mismatched meta keys cause an HTTP 500 | confirmed | 0.3 |
| [STG-12](#stg-12) | ⚪ low | gap | Rankings have no deterministic tie-break, but NRMP rank lists must be strict orders | partially | 0.3 |
| [STG-13](#stg-13) | 🟡 medium | gap | No post-interview update stage (interview() is a stub, although the fields exist) | confirmed | 3.4 |
| [STG-14](#stg-14) | 🟡 medium | gap | Rules for building rank order lists are not defined (students_rank/schools_rank are stubs) | confirmed | 3.5 |
| [STG-15](#stg-15) | 🟡 medium | gap | No checks that a match is valid, and no NRMP-style statistics | confirmed | 3.7 |
| [STG-16](#stg-16) | 🟡 medium | gap | The Match and Interview models cannot store per-run results, 'unmatched', SOAP rounds, couples or supplemental lists | confirmed | 2.3 |
| [STG-17](#stg-17) | 🟡 medium | gap | SOAP (the post-Match placement process) is not modeled | confirmed | 8.1 |
| [STG-18](#stg-18) | 🟡 medium | gap | Couples matching is not modeled; stable matchings may not exist, so the algorithm needs a Roth-Peranson-style procedure | confirmed | 8.3 |
| [STG-19](#stg-19) | 🟡 medium | recommendation | Write our own DA engine; use the 'matching' package only as a test oracle | confirmed | 3.6 |
| [STG-20](#stg-20) | 🟡 medium | gap | The engine runs as per-row ORM saves in a web request; stages need a vectorized engine and a background task | confirmed | 2.2 |
| [STG-21](#stg-21) | 🟡 medium | gap | No applicant types or eligibility screening (IMG status, visa sponsorship, score cutoffs) | confirmed | 6.3 |
| [STG-22](#stg-22) | ⚪ low | gap | No program tracks, supplemental (PGY-1 + advanced) rank lists, reversions or partial matches | confirmed | 8.4 |
| [STG-23](#stg-23) | ⚪ low | gap | Single-specialty market: no dual-specialty applications, so 'contiguous ranks' cannot be computed | confirmed | 8.5 |
| [STG-24](#stg-24) | ⚪ low | defect | Help texts for stage fields are wrong or swapped, and they feed the auto-generated documentation page | confirmed | 1.6 |
| [STG-25](#stg-25) | ⚪ low | recommendation | Model applicant self-assessment and the size of the applicant pool relative to positions | confirmed | 2.1 |
| [UX-1](#ux-1) | 🟠 high | defect | First-run path is broken: no config on create, silent no-op, and the default config fails validation | partially | 0.2 |
| [UX-2](#ux-2) | 🟠 high | defect | HTMX actions give no feedback: no spinner, buttons stay enabled, no success message, errors hidden | partially | 1.5 |
| [UX-3](#ux-3) | 🔴 critical | defect | Long synchronous steps run with no progress and will exceed the production timeout | partially | 2.5 |
| [UX-4](#ux-4) | 🟠 high | defect | CSV upload silently coerces bad data and deletes existing data before a failed parse | confirmed | 0.6 |
| [UX-5](#ux-5) | 🟠 high | defect | Panels go stale after cascades, and config changes never mark results out of date | confirmed | 1.5 |
| [UX-6](#ux-6) | 🟠 high | gap | No visible stage, and prerequisites are neither enforced nor explained | confirmed | 2.4 |
| [UX-7](#ux-7) | 🟠 high | recommendation | Replace the single manage page with a tabbed simulation workspace | confirmed | 4.1 |
| [UX-8](#ux-8) | 🟠 high | defect | daisyUI 4 class names are dead in daisyUI 5.1 and break forms and layout | partially | 1.4 |
| [UX-9](#ux-9) | 🟠 high | defect | Mobile horizontal overflow and header overlap: four root causes identified | confirmed | 1.4 |
| [UX-10](#ux-10) | 🟡 medium | defect | Meta-preference editor: stored XSS, plus data loss when JavaScript is off | partially | 0.5 |
| [UX-11](#ux-11) | 🟠 high | gap | No in-context help: model help_text exists for 17 fields but is never shown | confirmed | 4.3 |
| [UX-12](#ux-12) | 🟡 medium | gap | The 'Documentation' page is a developer API dump, not user help | partially | 1.10, 4.4 |
| [UX-13](#ux-13) | 🟡 medium | defect | Table data is hard to read: 16-digit floats, raw Python dicts, redundant columns, natural-sort errors | partially | 1.5 |
| [UX-14](#ux-14) | 🟡 medium | gap | Tables have no filtering, sticky headers, total counts or drill-down, and the sort code is copy-pasted | confirmed | 1.8, 4.1 |
| [UX-15](#ux-15) | 🟡 medium | defect | Auth and account problems: wrong-password message missing, password change dead-ends in admin | confirmed | 0.8 |
| [UX-16](#ux-16) | 🟡 medium | defect | Navigation: hard-coded URLs, links shown in the wrong state, no active item, headings out of order | confirmed | 1.5 |
| [UX-17](#ux-17) | 🟡 medium | gap | Home page is inaccurate and doesn't explain the product or offer a demo | confirmed | 0.7, 4.5 |
| [UX-18](#ux-18) | 🟡 medium | defect | Create/edit simulation form: hidden required field, unused Iterations, 'Public' checked by default | confirmed | 0.2 |
| [UX-19](#ux-19) | 🟡 medium | defect | Accessibility: low-contrast buttons, unlabeled inputs, missing ARIA state | confirmed | 1.4 |
| [UX-20](#ux-20) | 🟡 medium | recommendation | Use one consistent, informative pattern for destructive actions | confirmed | 1.5 |
| [UX-21](#ux-21) | 🟡 medium | recommendation | Rebuild the config form with presets, sliders and live derived values | confirmed | 4.2 |
| [UX-22](#ux-22) | 🟡 medium | recommendation | Results dashboard: KPIs, charts, a network view and scenario sliders in the workspace | confirmed | 5.3 |
| [UX-23](#ux-23) | ⚪ low | defect | Dark theme is compiled but can never be reached | confirmed | 1.5 |
| [UX-24](#ux-24) | ⚪ low | defect | Placeholder content and missing error pages | confirmed | 0.7 |
| [UX-25](#ux-25) | ⚪ low | defect | Logo and favicon are 1024x1024 PNGs (363 KB each) shown at 32 px | confirmed | 1.3 |
| [UX-26](#ux-26) | ⚪ low | gap | Simulations list doesn't help users pick, compare or clone simulations | confirmed | 4.6 |
| [VIZ-1](#viz-1) | 🟠 high | gap | The engine writes almost none of the data the stage and outcome charts need | partially | 3.7 |
| [VIZ-2](#viz-2) | 🟠 high | gap | Schema can't hold multiple runs, iterations or scenarios, so Monte-Carlo bands, sweeps and A/B are impossible | confirmed | 2.3 |
| [VIZ-3](#viz-3) | 🟠 high | recommendation | Aggregate on the server and never send per-pair rows to the browser; store runs sparsely | confirmed | 2.3 |
| [VIZ-4](#viz-4) | 🟠 high | recommendation | Library choice: Apache ECharts 6.1.0 for charts, sigma.js 3.0.3 + graphology 0.26.0 for networks | confirmed | 5.1 |
| [VIZ-5](#viz-5) | 🟡 medium | defect | Static pipeline isn't ready for a 1.1 MB chart library: no compression, 60 s cache, Tailwind would scan vendored JS, stale vendored htmx/Alpine | partially | 1.3, 1.2 |
| [VIZ-6](#viz-6) | 🟠 high | recommendation | What-if sliders: three tiers with stage-aware recomputation, common random numbers and measured latency budgets | partially | 6.2, 7.2 |
| [VIZ-7](#viz-7) | 🟠 high | gap | Current data would give degenerate charts, so the first charts should be built to catch that | confirmed | 3.8, 5.3 |
| [VIZ-8](#viz-8) | 🟡 medium | recommendation | Live config-preview charts next to the config form, computed in the browser | confirmed | 4.2 |
| [VIZ-9](#viz-9) | 🟡 medium | defect | school_interview_limit semantics rule out a useful interview-slots slider (programs can never interview as many applicants as they have positions) | partially | 2.1 |
| [VIZ-10](#viz-10) | 🟡 medium | recommendation | Define and precompute stability, welfare and friction metrics; they are the most insightful outcome views | partially | 3.7 |
| [VIZ-11](#viz-11) | 🟡 medium | recommendation | Network view: sorted two-column layout by default, ego networks as the main interaction, tier graph for scale, force layout only for clustered markets | confirmed | 5.4 |
| [VIZ-12](#viz-12) | 🟡 medium | defect | XSS risk: custom chart tooltip formatters will run HTML from CSV-uploaded student/school names | partially | 5.1 |
| [VIZ-13](#viz-13) | 🟡 medium | recommendation | JSON data API with columnar payloads, ETags, gzip on API responses only, and a shared cache | partially | 5.2 |
| [VIZ-14](#viz-14) | 🟡 medium | recommendation | Monte-Carlo iterations, parameter sweeps and A/B scenarios as first-class, precomputed experiments | confirmed | 6.1 |
| [VIZ-15](#viz-15) | 🟡 medium | recommendation | Dashboard page and HTMX integration: lazy chart cards, a JS chart registry, and cleanup on swap | partially | 5.1 |
| [VIZ-16](#viz-16) | 🟡 medium | recommendation | Chart design system: validated palette tokens, real dark mode, accessibility (aria/decal/table view), number formatting, mobile variants | confirmed | 5.1 |
| [VIZ-17](#viz-17) | ⚪ low | gap | Interview stage isn't queryable: free-form status string, only FK indexes | partially | 2.3 |
| [VIZ-18](#viz-18) | ⚪ low | recommendation | Reproducible, shareable charts: PNG/SVG export, data CSV, run citation, slider-state permalinks | confirmed | 5.5 |
| [VIZ-19](#viz-19) | ⚪ low | recommendation | Every chart card gets a '?' popover from a single chart registry, shared with the documentation page | confirmed | 5.1 |
| [VIZ-20](#viz-20) | ⚪ low | recommendation | Test the viz stack: pure-numpy metric tests, payload snapshots, Playwright render smoke, and JS/Python parity via a portable RNG | confirmed | 5.5, 7.2 |
| [VIZ-21](#viz-21) | ⚪ low | recommendation | Add NRMP-report-style charts that medical-education users already know | confirmed | 5.3 |
| [HELP-1](#help-1) | 🟠 high | defect | No field help is rendered anywhere; 17/17 aria-describedby references dangle; CSV-format and password-rule hints are invisible | partially | 1.4 |
| [HELP-2](#help-2) | 🟠 high | defect | Default configuration fails its own validators, and several defaults are meaningless for the 0-1 Beta model | confirmed | 0.2 |
| [HELP-3](#help-3) | 🟠 high | defect | Help and docstrings describe behaviour the engine lacks; 6 user-facing parameters do nothing and are not marked | confirmed | 1.6 |
| [HELP-4](#help-4) | 🟡 medium | defect | Inaccurate, swapped or typo-ridden help_text on 25+ model fields | confirmed | 1.6 |
| [HELP-5](#help-5) | 🟡 medium | defect | /documentation/ is a public, developer-facing dump that exposes User internals and omits the simulation engine | confirmed | 1.10, 4.4 |
| [HELP-6](#help-6) | 🟡 medium | defect | Documentation page overflows horizontally on mobile, and its custom CSS is broken under daisyUI 5 | partially | 1.4 |
| [HELP-7](#help-7) | 🟡 medium | defect | Action buttons are unexplained, and their confirmation text hides destructive side effects | partially | 1.5 |
| [HELP-8](#help-8) | 🟡 medium | recommendation | Create a single-source-of-truth help registry with automatic consistency checks | partially | 4.3 |
| [HELP-9](#help-9) | 🟠 high | recommendation | Accessible per-field '?' popover built on daisyUI 5 (not hover-only tooltips) | confirmed | 4.3 |
| [HELP-10](#help-10) | 🟠 high | gap | No user guide: nothing explains the NRMP, the stages, the model, CSV formats or terms | confirmed | 4.4 |
| [HELP-11](#help-11) | 🟡 medium | recommendation | Model & formulas page with executable worked examples tied to the engine | confirmed | 4.4 |
| [HELP-12](#help-12) | 🟡 medium | recommendation | Per-page help panel (navbar '?' plus the '?' key) loaded lazily via HTMX | confirmed | 4.3 |
| [HELP-13](#help-13) | 🟡 medium | recommendation | Live parameter previews and a market-summary strip next to the config inputs | confirmed | 4.2 |
| [HELP-14](#help-14) | 🟡 medium | gap | First-run guidance is wrong or missing: fix the home Quick Start, add a stage checklist, an example preset and an optional tour | confirmed | 0.7, 4.5 |
| [HELP-15](#help-15) | 🟡 medium | gap | CSV formats are undocumented in the UI and inconsistent in code; a download-then-upload round trip silently drops preferences | confirmed | 1.7 |
| [HELP-16](#help-16) | 🟡 medium | gap | List-page column headers are ambiguous and unexplained | confirmed | 1.5 |
| [HELP-17](#help-17) | 🟡 medium | gap | Validation and error messages are not user-friendly, not linked to help, and some are missing | confirmed | 1.6 |
| [HELP-18](#help-18) | 🟡 medium | recommendation | Glossary and inline term definitions | confirmed | 4.4 |
| [HELP-19](#help-19) | 🟡 medium | recommendation | Choose one UI vocabulary: Applicant/Program vs Student/School | confirmed | 1.6, 2.3 |
| [HELP-20](#help-20) | ⚪ low | defect | Docstring and comment inaccuracies that feed the generated docs | partially | 1.6 |
| [HELP-21](#help-21) | ⚪ low | defect | Placeholder contact details and a dead-end 'Change password' link | confirmed | 0.7 |
| [HELP-22](#help-22) | ⚪ low | gap | No README, and developer docs are duplicated and stale | partially | 1.10 |
| [HELP-23](#help-23) | ⚪ low | recommendation | 'About this model' page: assumptions, limitations, version, reproducibility and citation | partially | 4.4 |
| [HELP-24](#help-24) | ⚪ low | recommendation | Automated quality gates for help content | partially | 1.1, 4.7 |
| [HELP-25](#help-25) | ⚪ low | recommendation | Extend the registry to chart help, help search and i18n | confirmed | 5.1 |
| [OPT-1](#opt-1) | 🟠 high | defect | MUST: The default config fails its own validation, and population actions silently do nothing without a saved config | partially | 0.2 |
| [OPT-2](#opt-2) | 🟠 high | defect | MUST: 'Rating error' is a multiplier, not noise; rating_error=0 is silently turned into 1.0; true scores are never stored | partially | 0.3 |
| [OPT-3](#opt-3) | 🟠 high | defect | MUST: Beta-based generation with undefined SD units gives 0/1 populations and does not honour the requested mean | partially | 2.1 |
| [OPT-4](#opt-4) | 🟠 high | gap | MUST: No explicit preference-correlation model; heterogeneity is an accident of clamping and meta noise | partially | 2.2 |
| [OPT-5](#opt-5) | 🟠 high | gap | MUST: No application stage: every applicant is rated against every program (full cross-product) and there are no options for how many or which programs to apply to | confirmed | 3.1 |
| [OPT-6](#opt-6) | 🟠 high | defect | MUST: Interview-limit parameters are unused, and school_interview_limit has the wrong unit | confirmed | 2.1 |
| [OPT-7](#opt-7) | 🟠 high | gap | MUST: No random seed; generation uses the global `random` module and scipy's global RNG | confirmed | 2.2 |
| [OPT-8](#opt-8) | 🟠 high | gap | MUST: The config is edited in place; runs and populations keep no snapshot of the config that produced them | confirmed | 2.3 |
| [OPT-9](#opt-9) | 🟠 high | recommendation | MUST: Replace the 20 flat model fields with a versioned, typed parameter schema that drives validation, the form, '?' help, docs and JSON import/export | confirmed | 2.1 |
| [OPT-10](#opt-10) | 🟠 high | gap | MUST: Simulation.iterations is exposed but unused; no Monte-Carlo replicates, aggregated metrics or confidence intervals | partially | 6.1 |
| [OPT-11](#opt-11) | 🟠 high | recommendation | MUST (enabler): Vectorised array engine with sparse persistence, so the new options, replicates and sweeps are feasible | partially | 2.2 |
| [OPT-12](#opt-12) | 🟡 medium | defect | MUST: Validation ranges are meaningless or missing, there are no cross-field checks, and several help texts are wrong | confirmed | 1.6, 2.1 |
| [OPT-13](#opt-13) | 🟡 medium | defect | SHOULD: Meta-attribute keys are coupled across the two populations; editing one list crashes rating; CSV round-trip drops preferences | partially | 1.7 |
| [OPT-14](#opt-14) | 🟡 medium | defect | SHOULD: Capacity model makes zero-position programs, and market tightness is an accident of three unrelated inputs | confirmed | 2.1 |
| [OPT-15](#opt-15) | 🟡 medium | gap | SHOULD: Program signals: the model has a field but no config and no behaviour | confirmed | 3.2 |
| [OPT-16](#opt-16) | 🟡 medium | gap | SHOULD: Program screening and invitation behaviour: thresholds, strategy, yield protection, waves and backfill | partially | 3.3 |
| [OPT-17](#opt-17) | 🟡 medium | gap | SHOULD: Interview-stage options: acceptance cap and order, scheduling conflicts, information revealed | confirmed | 3.3 |
| [OPT-18](#opt-18) | 🟡 medium | gap | SHOULD: Rank-list and match options: ROL policies, do-not-rank, proposing side, stability check | confirmed | 3.5 |
| [OPT-19](#opt-19) | 🟡 medium | gap | SHOULD: Applicant groups (US MD / DO / US-IMG / non-US-IMG) and program tiers, with group-level outcomes | confirmed | 6.3 |
| [OPT-20](#opt-20) | 🟡 medium | recommendation | SHOULD: Presets and templates, including one calibrated to NRMP 2026 aggregates, plus a calibration report | partially | 4.2, 6.4 |
| [OPT-21](#opt-21) | 🟡 medium | recommendation | SHOULD: Parameter sweeps (1-D/2-D) and paired scenario comparison with common random numbers | partially | 6.2 |
| [OPT-22](#opt-22) | 🟡 medium | recommendation | SHOULD: Clone/duplicate simulation, import/export config JSON, save as preset | partially | 4.6 |
| [OPT-23](#opt-23) | ⚪ low | recommendation | SHOULD: Use NRMP domain vocabulary: 'School' is really a residency Program; use clearer parameter names | confirmed | 1.6, 2.3 |
| [OPT-24](#opt-24) | ⚪ low | gap | COULD: Multiple specialties with different competitiveness, backup specialties and supplemental (prelim/advanced) lists | confirmed | 8.5 |
| [OPT-25](#opt-25) | ⚪ low | gap | COULD: Couples fraction and SOAP post-match round | confirmed | 8.3, 8.1 |
| [OPT-26](#opt-26) | ⚪ low | gap | COULD: Geography and region preference on both sides | confirmed | 8.6 |
| [OPT-27](#opt-27) | ⚪ low | recommendation | COULD: Application cost, budget and adaptive (strategic) application behaviour | partially | 8.7 |
| [ENG-1](#eng-1) | 🟠 high | defect | Production mode is broken and insecure by default: debug_toolbar URLs crash every request, logfire crashes at import, DEBUG defaults to True, and a hard-coded SECRET_KEY is used as fallback | confirmed | 0.1 |
| [ENG-2](#eng-2) | 🟡 medium | defect | No HTTPS/proxy security settings; CSRF fails on the custom domain behind Railway's TLS proxy | partially | 0.1 |
| [ENG-3](#eng-3) | 🟠 high | defect | Engine steps do one query plus one autocommitted UPDATE per row; 10k interviews exceed gunicorn's 30 s timeout | confirmed | 0.4 |
| [ENG-4](#eng-4) | 🟡 medium | gap | No background execution or progress reporting; recommend the built-in django.tasks API with the django-tasks-db backend, a SimulationRun model and HTMX polling | confirmed | 2.5 |
| [ENG-5](#eng-5) | 🟡 medium | defect | Anyone can sign up and trigger 10M-row operations that exhaust memory; no quotas or rate limiting | partially | 0.4, 2.5 |
| [ENG-6](#eng-6) | 🟠 high | defect | CSV upload deletes the population before parsing, silently coerces bad values, loses data on round-trip, and stores user files forever on shared ephemeral disk | confirmed | 0.6 |
| [ENG-7](#eng-7) | 🟡 medium | defect | XSS and broken markup: meta-preference lists rendered as Python repr with \|safe inside HTML attributes | partially | 0.5 |
| [ENG-8](#eng-8) | 🟠 high | gap | No tests, CI or pre-commit; a prototype suite immediately catches 2 real bugs | confirmed | 1.1 |
| [ENG-9](#eng-9) | 🟡 medium | defect | Dependency groups are wrong: a fresh `uv sync` dev env cannot start, and the Docker image installs the dev group in production | confirmed | 0.1 |
| [ENG-10](#eng-10) | 🟡 medium | defect | Dockerfile/entrypoint installs, builds and migrates at every container start; Node in the runtime image; no .dockerignore; root user; fixed gunicorn settings | confirmed | 1.2 |
| [ENG-11](#eng-11) | ⚪ low | gap | Static assets: whitenoise without compression or manifest; vendored htmx and Alpine outside dependency management | confirmed | 1.2 |
| [ENG-12](#eng-12) | ⚪ low | defect | mypy runs without the django-stubs plugin (138 mostly bogus errors); with the plugin, 22 real errors remain | confirmed | 1.1 |
| [ENG-13](#eng-13) | ⚪ low | recommendation | Ruff configuration is miswired; after a config fix plus format/--fix, 138 findings drop to 54, of which 7 are real | confirmed | 1.1 |
| [ENG-14](#eng-14) | 🟡 medium | recommendation | Ownership check and step views are copy-pasted 20 times; centralise them in a queryset/helper and a step dispatcher | confirmed | 1.8 |
| [ENG-15](#eng-15) | ⚪ low | defect | N+1 queries on the simulations list, missing composite indexes, redundant index, unbounded page_size | partially | 1.8, 2.3 |
| [ENG-16](#eng-16) | 🟡 medium | defect | Silent failures: errors hidden by broad excepts, swallowed HTMX 4xx/5xx, no user feedback, double-submit possible | confirmed | 0.4, 1.5 |
| [ENG-17](#eng-17) | 🟡 medium | gap | Runs are not reproducible: unseeded global RNGs and in-place config edits leave no record of what produced a population | confirmed | 2.2 |
| [ENG-18](#eng-18) | 🟡 medium | defect | Model defaults violate the model's own validators, so saving the untouched default config fails; widget and validator mismatches | partially | 0.2 |
| [ENG-19](#eng-19) | 🟡 medium | recommendation | Admin is empty and several model fields are dead (public, iterations, Simulation.status, User.status/disabled) | confirmed | 1.8 |
| [ENG-20](#eng-20) | 🟡 medium | defect | Account page 'Change password' goes to the admin (non-staff are bounced to admin login); no password reset | confirmed | 0.8 |
| [ENG-21](#eng-21) | ⚪ low | recommendation | Logging is noisy and duplicated in production | partially | 1.2 |
| [ENG-22](#eng-22) | 🟡 medium | recommendation | Adopt Django 6.x features verified in the installed source: template partials, {% querystring %}, built-in CSP, LoginRequiredMiddleware, django.tasks | partially | 1.8, 5.1, 5.5 |
| [ENG-23](#eng-23) | ⚪ low | recommendation | Code organisation: fat models, duplicated student/school code, dead code, inline imports, and a 150-line introspection view | confirmed | 2.2 |
| [ENG-24](#eng-24) | ⚪ low | defect | Repository hygiene: generic .NET .gitignore missing data/, tracked stray files, unwired dev apps, undocumented env vars | partially | 1.2 |
| [ENG-25](#eng-25) | ⚪ low | defect | Migration drift: model validators changed without a migration (0006 pending) | confirmed | 0.2 |
| [ENG-26](#eng-26) | ⚪ low | defect | CLAUDE.md and TODO.md contain inaccurate or stale statements | confirmed | 1.10 |
| [CRIT-1](#crit-1) | 🟠 high | defect | Running the same step concurrently corrupts data: two (re)Create Students calls double the population, and two Initialize Interviews calls give an IntegrityError 500 | critic (self-verified) | 0.4, 2.5 |
| [CRIT-2](#crit-2) | 🟠 high | recommendation | Write a single versioned model specification before the engine rewrite; the reviewers' prototypes use three different utility models | critic (self-verified) | 2.0 |
| [CRIT-3](#crit-3) | 🟡 medium | gap | No sharing, visibility or collaboration model; the dead 'public' flag defaults to True on every existing simulation, so a future gallery would leak them | critic (self-verified) | 0.2, 7.1 |
| [CRIT-4](#crit-4) | 🟡 medium | defect | Privacy and terms pages are inaccurate: uploads outlive deletion, participant names reach logs and Logfire, Logfire is undisclosed, and users cannot delete their account or export their data | critic (self-verified) | 0.7, 1.9 |
| [CRIT-5](#crit-5) | 🟡 medium | gap | No NRMP trademark or non-affiliation disclaimer, and no statement that results are not predictions | critic (self-verified) | 0.7 |
| [CRIT-6](#crit-6) | 🟡 medium | defect | No protection against login brute force or bot signups | critic (self-verified) | 0.8, 2.5 |
| [CRIT-7](#crit-7) | 🟡 medium | gap | Email is not configured and is optional at signup, which blocks password reset, verification and job-finished notifications | critic (self-verified) | 1.9, 2.5 |
| [CRIT-8](#crit-8) | 🟡 medium | gap | There is no headless or programmatic interface (CLI, Python API, notebooks) and no experiment bundle export/import | critic (self-verified) | 2.2, 6.5 |
| [CRIT-9](#crit-9) | ⚪ low | gap | The project is not citable or versioned: no README, CITATION.cff or CHANGELOG, and the version is never shown or recorded with results | critic (self-verified) | 2.0, 6.5, 3.7 |
| [CRIT-10](#crit-10) | 🟡 medium | gap | No teaching or classroom mode, 'explain my match' view, or demo that works without signing up, although the site advertises educational use | critic (self-verified) | 7.3 |
| [CRIT-11](#crit-11) | 🟡 medium | gap | Ops is not ready for the planned architecture: no health check, no worker service, a silent SQLite fallback in production, no backups and no engine telemetry | critic (self-verified) | 0.1, 1.2, 2.5 |
| [CRIT-12](#crit-12) | 🟡 medium | gap | Front-end dependencies were not part of the upgrade, and nothing automates dependency updates | critic (self-verified) | 1.3 |
| [CRIT-13](#crit-13) | 🟡 medium | gap | No plan for migrating existing deployed data through the proposed schema rework | critic (self-verified) | 2.0, 2.3 |
| [CRIT-14](#crit-14) | ⚪ low | recommendation | Add mechanism comparison (RSD, immediate acceptance/Boston, TTC, program-proposing DA, decentralised scramble) on the same market | critic (self-verified) | 8.2 |
| [CRIT-15](#crit-15) | ⚪ low | recommendation | Triage TODO.md and IDEAS.md explicitly in the plan so obsolete or conflicting items don't resurface | critic (self-verified) | 1.10 |

<a id="sim"></a>

## SIM: Simulation engine & data-model correctness (implemented steps)

> **Reviewer summary.** The pipeline runs from start to finish, but none of the pre-interview results mean what the UI says they mean, and several steps crash or lose data silently. (1) The rating "error" multiplies the score by a constant instead of adding noise, so observed rankings equal the true rankings (30/30 students). An error of 0 is treated as 1. (2) The default config fails its own validators, so the untouched form cannot be saved. The stddev defaults (2/3/10 on a 0-1 Beta) are silently clamped into U-shaped distributions: 43% of generated students break Student.score's 0.99 cap, and a requested school mean of 0 comes out as about 0.30. (3) A CSV round trip drops preferences, so every score is 0 and every rank is a tie. Headerless files lose their first row, and Excel-BOM files or the documented positional school layout lose score_meta. Any mismatch in meta keys causes an unhandled 500 that leaves the step half-written. (4) Every step saves one row at a time, about 4.4 ms per interview row across the four steps. Anything over about 7k pairs will pass gunicorn's default 30 s timeout. A scratch numpy + executemany prototype does the whole stage for 100k pairs in about 0.5 s instead of about 440 s (roughly 900x faster) and gives identical ranks. (5) The model itself has flaws: preferences are almost fully shared (Spearman 0.99 between students), weights are effectively on/off, there is no seed, no config provenance, no true scores, and Simulation.status, iterations, public and the Match model are unused. Before building the interview, ranking and match stages, the engine needs a seeded, vectorised rewrite with stored true utilities and Run/RankList/MatchResult models. All experiment scripts are in scratch/review/sim/ (t1..t8), run against an isolated SQLite DB.

<a id="sim-1"></a>

### SIM-1: Pre-interview 'rating error' multiplies instead of adding noise, so observed ranks equal true ranks and an error of 0 becomes 1

**Severity:** 🔴 critical · **Kind:** defect · **Effort:** S · **Plan:** 0.3 · **Verification:** partially

**Evidence.** nrmps/simulation_engine.py:10 `return sum(...) * rating_error`; :50 and :81 `float(getattr(cfg, '..._pre_interview_rating_error', 1.0) or 1.0)`. review/sim/t3_pipeline.py section A (realistic config 30x5): 'students whose observed ranking == true ranking: 30/30; observed score range [0.0001,0.0918]'. Section B: setting applicant_pre_interview_rating_error=0.0 gives observed 0.7615825461514107 == noiseless 0.7615825461514107, because `0 or 1.0` evaluates to 1.0. Matches F5.

**Why it matters.** Multiplying by a positive constant is a monotone rescaling, so every observed pre-interview ranking is exactly the noiseless ranking. The core research question (how noisy information affects the match) cannot be studied. Every stored score is also shrunk to about 0-0.1, which is why the UI shows 0.03-0.08. Because of the `or 1.0` fallback, the valid value 0 silently means 'x1', and a missing config also means 'x1'. The docstrings at simulation_engine.py:8,46,77 document the wrong formula, so /documentation/ repeats it.

**Recommendation.** Replace _score with additive noise from a seeded generator: `U_true = w·y`, `U_obs = U_true + sigma * rng.standard_normal()`. Read sigma as `cfg.applicant_pre_interview_rating_error if cfg else 0.0` with no `or` fallback, and make sigma=0 mean no error. Store U_true in student_true_score_of_school / school_true_score_of_student (see SIM-9). Optionally add a 'reliability' r in (0,1] slider mapped to sigma = sd(U)*sqrt((1-r)/r), plus heteroskedastic options (see extra, section 2.6). Fix the docstrings. Add a pytest check that sigma=0 gives U_obs == U_true and that sigma>0 gives Spearman(U, U_obs) < 1. This corrects TODO.md 'Handle division by zero in scoring functions': there is no division in _score. The real edge cases are noise semantics and missing keys (SIM-4).

**Verifier note (partially).** Core claim reproduced exactly (simverify/v1.py, realistic 30x5 config): 30/30 students' observed pre-ranking equals the noiseless w·y ranking, observed range is 0.029-0.059, and with applicant_pre_interview_rating_error=0.0 the observed score (0.5191419968651242) equals the noiseless one, because `0 or 1.0` gives 1.0 (simulation_engine.py:50,81). getattr(None, ..., 1.0) also makes a missing config mean x1. TODO.md:152 'Handle division by zero' is indeed moot. One side claim is false: /documentation/ does not repeat the engine docstrings. views.py:15/639/682 inspects only `nrmps.models`, and the rendered page has no simulation_engine text (checked with curl on :8800). Only models.py help_text and functions appear. Critical severity is justified: the noise mechanism is the core of the simulation and does nothing.

**Lead note (document check).** The additive-noise fix ships in Plan 0.3 using an unseeded numpy Generator. Seeds arrive with the Phase 2 engine.

<a id="sim-2"></a>

### SIM-2: Default SimulationConfig violates its own validators, and the score/stddev defaults are infeasible on a 0-1 Beta scale

**Severity:** 🟠 high · **Kind:** defect · **Effort:** S · **Plan:** 0.2 · **Verification:** confirmed

**Evidence.** nrmps/models.py:560-567: school_meta_preference_stddev default=2 and school_meta_scores_stddev default=2, both with MaxValueValidator(0.99). review/sim/t1_config.py: `SimulationConfig().full_clean()` gives 'DEFAULT CONFIG INVALID: school_meta_preference_stddev, school_meta_scores_stddev <= 0.99', and resubmitting the unbound form's initial values gives 'form valid ... False'. Also models.py:535-539 school_score_mean default=0; :499-503/:540-544 score stddev default 2 with max 99 (feasible max is 0.5); :518-522 applicant_meta_scores_stddev default 10; :513-516 applicant_meta_preference_stddev max 99 vs school's max 0.99 (asymmetric). models.py:602,633 Student/School.score MaxValueValidator(0.99) although Beta values reach 1.0. t3 section J (defaults, 500x50): 'students failing full_clean: 215/500', 'student score mean 0.626 (requested 0.7) frac>=0.99 0.43', 'school score mean 0.227 (requested 0)'. Migration drift F3 (pending 0006 for Student.score) comes from the same inconsistency.

**Why it matters.** A first-time user who presses 'Save Configuration' without changes gets two validation errors on fields whose help text does not explain the 0-1 scale. Every default stddev (2, 3, 10) is far above the Beta maximum of sqrt(mu(1-mu)) <= 0.5, so all defaults end up in the silent-clamp path (SIM-3) and produce degenerate, bimodal populations. A school mean of 0 is not a valid Beta mean. Generated objects break the model's own validators, which works only because bulk_create skips full_clean.

**Recommendation.** Change the defaults to realistic values: applicant 0.6/0.15, school 0.5/0.15, meta-score sd 0.1 (or rho, see SIM-14), preference heterogeneity via Dirichlet concentration (SIM-12). Set Min/Max validators consistently: mean in (0,1) exclusive, sd in [0,0.5). Add SimulationConfigForm.clean() to enforce sd < sqrt(mu(1-mu)) with a message that shows the maximum. Change Student/School.score to MaxValueValidator(1.0). Create one migration that also absorbs the pending 0006. Add a test that `SimulationConfig(simulation=s).full_clean()` passes.

**Verifier note (confirmed).** `SimulationConfig(simulation=s).full_clean()` fails on school_meta_preference_stddev and school_meta_scores_stddev (<=0.99). Reproduced in the real UI: I created a new simulation (pk=5) with Playwright on :8800 and pressed 'Save Configuration' without changes. It stayed on the page with two errors, 'Ensure this value is less than or equal to 0.99.' 0.7/2 gives about 40% of draws >0.99 (N=20000; the reviewer's 43% is a 500-row sample). A requested mean of 0 gives 0.300. Two small imprecisions. (a) The preference stddevs (3, 2) are not Beta sds and go through the gauss clamp (SIM-12), not the Beta clamp, so 'every default ends up in the SIM-3 clamp' applies only to the score/meta-score sds. (b) Pending 0006 (F3) only adds the [0, 0.99] validators to Student.score that were never migrated. It is related to the 0.99 cap, not caused by the default inconsistency. Separately found: SimulationForm makes description required (models.py:94 TextField(default='') without blank=True), so creating a simulation with an empty description fails with 'This field is required.'

<a id="sim-3"></a>

### SIM-3: get_beta_parameters silently clamps sd and floors alpha/beta at 0.1, so realised mean/sd differ from what was requested

**Severity:** 🟠 high · **Kind:** defect · **Effort:** S · **Plan:** 2.1 · **Verification:** confirmed

**Evidence.** nrmps/models.py:28 (mean clipped to [0.001,0.999]), :34-35 (sd set to 0.9*max if too large), :53-54 (alpha, beta >= 0.1). review/sim/t2_beta.py, N=20000 draws: req 0.7/2 gives alpha=0.164, beta=0.100, realised mean 0.618 sd 0.432, 39.6% >0.99, 18.7% <0.01. Req 0.0/2 gives realised mean 0.301. Req 0.5/0.49 gives alpha=beta=0.1, 32% >0.99 and 32% <0.01. Realistic requests are exact: 0.5/0.15 gives 0.500/0.149, 0.7/0.1 gives 0.701/0.100, 0.3/0.2 gives 0.300/0.201.

**Why it matters.** The method is correct in the feasible region, but out-of-range requests are rewritten without any feedback. The 90% rule always gives alpha,beta < 1 (U-shaped). The 0.1 floor then moves the mean (0.7 becomes 0.62). Users see a 'mean' field that is not the mean. Near 0 or 1, the per-attribute Beta(mean=base, sd) draws are clamped differently for each entity, which makes attribute spread depend on base score in hidden ways.

**Recommendation.** Remove the silent clamp and floor, and raise ValueError. The form rejects infeasible values beforehand (SIM-2). Offer a (mean, concentration kappa) parameterisation as an alternative that is always valid. Show the implied alpha/beta and a live histogram preview next to the fields (this ties to the visualisation dimension). Vectorise with `rng.beta(a, b, size=N)`: scipy beta.rvs per call measured 19.6 us vs 2 ms for 40,000 vectorised draws. Add a pytest check that the realised mean and sd fall within 4*sd/sqrt(N) of the targets.

**Verifier note (confirmed).** Reproduced with np.random.beta on get_beta_parameters output (N=20000). 0.7/2 gives a=0.164, b=0.100, mean 0.617, sd 0.432, 39.7% >0.99, 18.4% <0.01. 0/2 gives mean 0.300. 0.5/0.49 gives a=b=0.1, 32% at each tail. 0.5/0.15 and 0.7/0.1 are exact. The algebra holds: the 90% rule gives temp = 1/0.81 - 1 = 0.235, so alpha and beta are always < 0.235 and are then floored to 0.1, which moves the mean. Feasibility caveat on the fix: 'raise ValueError instead of clamping' would break per-attribute generation (models.py:146,232), which uses mean=base_score near 0/1 with a fixed sd. It only works together with the SIM-14 copula or a concentration parameterisation.

<a id="sim-4"></a>

### SIM-4: A meta-key mismatch between the two sides crashes rating with a masked exception (500) and leaves partial writes

**Severity:** 🟠 high · **Kind:** defect · **Effort:** S · **Plan:** 0.3 · **Verification:** confirmed

**Evidence.** nrmps/simulation_engine.py:10 indexes `meta_scores[meta]` for every preference key; :62-63 and :93-94 `raise Exception(...) from None`. review/sim/t3_pipeline.py C: changing config.applicant_meta_preference after creating students, then recreating only schools, gives 'Exception Error computing pre-interview score for Student 1 - School 1 | __cause__: None | suppress_context: True'. E: uploading students with score_meta {'usmle':..} next to generated schools gives HTTP POST /compute-pre-interview-all/ 'Internal Server Error ... Exception: Error computing pre-interview score for Alice - School 1'. The steps are not wrapped in transaction.atomic (simulation_engine.py:55-66), so rows saved before the failure stay updated.

**Why it matters.** The model depends on an implicit cross-mapping: student.score_meta keys = config.school_meta_preference and school.score_meta keys = config.applicant_meta_preference. That mapping is coherent when both populations come from the same config version, but nothing enforces it. Editing the config lists, recreating one side, or uploading a CSV breaks it. The generic Exception with `from None` hides the missing key, the user gets a bare 500 with no HTMX error, and the DB is left half-rated.

**Recommendation.** Before any rating step, run `validate_population(sim)`. It should compare the key sets (student.score_meta ⊇ school.meta_preference keys, and the reverse) and raise a domain error `PopulationMismatch(missing={...})`. Show that error in _interview_counts.html via an HTMX error partial (or HX-Retarget to an alert). Store the attribute key lists on the population/Run (SIM-18) and flag the population 'stale' when the config lists change. Run each stage inside transaction.atomic(). Drop the `from None` so the cause is kept.

**Verifier note (confirmed).** Reproduced two ways. (1) Changing config.applicant_meta_preference and recreating only the schools gives 'Exception: Error computing pre-interview score for Student 1 - School 1' with __cause__ None and __suppress_context__ True. (2) Over HTTP with the Django test client: uploading a students CSV with score_meta {'usmle':..} next to generated schools, then POST /compute-pre-interview-all/, returns 500. Afterwards 5/5 student-side rows were already written (the students step succeeded, the schools step crashed), so the partial state is real. No transaction.atomic or ATOMIC_REQUESTS exists anywhere (grep). The key cross-mapping described is correct: student.score_meta keys come from school_meta_preference, school.score_meta keys from applicant_meta_preference.

<a id="sim-5"></a>

### SIM-5: CSV download/upload round trip loses meta_preference, so every observed score is 0 and every rank is an arbitrary tie

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 1.7 · **Verification:** confirmed

**Evidence.** nrmps/views.py:293-296 students CSV writes only name,score,score_meta; :309-312 schools CSV writes name,capacity,score,score_meta. nrmps/models.py:329-336, 354-361, 426-433, 461-468: uploaded rows get no meta_preference. review/sim/t3_pipeline.py D: before 'meta_preference sample: {program_size: 0.378, ...}', after round trip '{}', school meta_stddev_preference 1.0 (model default instead of the config value). Rating afterwards gives 'student->school distinct scores=1 (min 0.0, max 0.0); school->student distinct=1 (min 0.0, max 0.0)'.

**Why it matters.** A user who downloads the population, edits a few names or scores, and re-uploads silently destroys every preference. _score then sums over an empty dict, all scores are 0.0, and the ranks come from DB row order (see SIM-10). Nothing tells the user. The upload help texts ('CSV: name, score, [score_meta]') do not mention preferences either.

**Recommendation.** Define CSV schema v2 in one module (nrmps/io_csv.py) used by both download and upload. Students: name, score, score_meta (JSON), meta_preference (JSON). Schools: name, capacity, score, score_meta, meta_preference. Alternatively offer a spreadsheet-friendly wide format with columns 'attr:<key>' and 'pref:<key>'. On upload, add an option 'generate missing preferences from the current config distribution'. Otherwise reject files whose preference keys do not cover the other side's attributes. Add a round-trip test: download, upload, then assert population equality.

**Verifier note (confirmed).** Reproduced over HTTP: download the students/schools CSV, then upload both. meta_preference goes from {program_size:..} to {} for both sides, and School.meta_stddev_preference becomes 1.0 (the model default). After init + compute-all, the distinct observed scores are {0.0} on both sides. The download writers are at views.py:293-296 and 309-312, and the upload constructors at models.py:329-336, 354-361, 426-433, 461-468 set no meta_preference.

<a id="sim-6"></a>

### SIM-6: CSV parser drops rows, reads schools' positional columns wrongly, mishandles Excel BOM, and silently accepts garbage

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 1.7 · **Verification:** confirmed

**Evidence.** nrmps/models.py:308-313: the positional fallback always skips the first row. t3 F: headerless 'Alice,0.8/Bob,0.6/Carol,0.4' gives [('Bob',0.6),('Carol',0.4)]. models.py:397-423: the schools positional path expects name,capacity,score,meta_stddev,score_meta, but forms.py:74 documents 'name, capacity, score, [score_meta]'. t3 G: 'School,Capacity,Score,Meta' with JSON meta gives score_meta {}. models.py:301,390 open with encoding='utf-8', not 'utf-8-sig'. review/sim/t7_bom.py: re-uploading the app's own schools CSV with an Excel BOM loses score_meta ({'program_size':0.07,...} becomes {}). t3 H: 'X,abc,{bad json' / 'Y,250' / 'Z,-3' are all accepted as scores 0.0/250.0/-3.0 with HTTP 200, and 3/3 rows fail full_clean(). views.py:250-260: an invalid form or bad file re-renders the counts partial with no message. The upload is persisted to data/simulation_{id}_*.csv (views.py:253-258) before parsing.

**Why it matters.** Uploads are the only way to model real populations, and today they corrupt data without telling anyone. Wrong column offsets and BOM handling lose attributes. Invalid numbers become 0.0, which then acts as a real score. Out-of-range scores (for example a raw USMLE 250) break the 0-1 utility scale. Nothing is atomic: models.py:298 and :387 delete the old population first, so a file that fails halfway leaves a partial population.

**Recommendation.** Replace upload_students/upload_schools with a parser class (nrmps/io_csv.py) that works on the in-memory UploadedFile (io.TextIOWrapper(file, encoding='utf-8-sig')). It should require a header, map columns by name only, and validate each row: score in [0,1], capacity an integer >= 1, JSON objects with numeric values and keys matching the config. It should collect row-level errors like 'line 7: score "abc" is not a number', and only on zero errors delete and bulk_create inside transaction.atomic(). Return a result object rendered in the partial (created N, errors list, warnings such as 'keys not used by any preference'). Stop writing to data/. Put a size limit on uploads. Add tests for each case above. This covers TODO.md 'Input sanitization for CSV uploads' and 'Add data validation feedback'.

**Verifier note (confirmed).** All cases reproduced over HTTP. Headerless 'Alice,0.8/Bob,0.6/Carol,0.4' gives only Bob and Carol. 'School,Capacity,Score,Meta' with JSON meta gives score_meta {}, because the positional path reads index 3 as meta_stddev and index 4 as score_meta. A BOM on the app's own schools CSV gives score_meta {}. Nuance: a BOM on the students CSV keeps score_meta, because the students positional fallback reads row[2], so the loss is schools-only, as the evidence says. 'X,abc,{bad json / Y,250 / Z,-3' is accepted with scores 0.0/250.0/-3.0 and status 200. An empty POST returns 200 with just the counts partial. data/simulation_1_*.csv persists. Minor: X fails full_clean because of blank JSON fields, not because of its score.

<a id="sim-7"></a>

### SIM-7: Per-row .save() makes pre-interview cost about 4.4 ms per pair and hit the 30 s gunicorn timeout at about 7k pairs; a vectorised version is about 900x faster

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 0.4 · **Verification:** partially

**Evidence.** nrmps/simulation_engine.py:55-66, 86-96 (one UPDATE per row, autocommit); :110-119, :133-142 (one query per student/school plus one UPDATE per row). review/sim/t4_perf.py: 200x20=4000 rows: stu_rate 4.41 s, sch_rate 4.34, stu_rank 4.15, sch_rank 4.18 (4.27 ms/row). 500x40=20000 rows: 21.8/23.0/22.6/21.1 s = 88.6 s (4.43 ms/row). Extrapolated: 1000x100 ≈ 440 s; the config maximum of 10M rows ≈ 12 h. entrypoint.sh last line runs gunicorn without --timeout (default 30 s), so 'Compute Pre-Interview' dies after about 30 s / 4.4 ms ≈ 6.8k pairs with partial state. review/sim/t6_mid.py (20000 rows, one step): as-is 22.60 s, same code in transaction.atomic 3.88 s, loop + bulk_update 3.20 s. review/sim/t5_vector.py (numpy utilities+noise+ranks, then cursor.executemany of 7 columns): 20000 rows 10 ms + 0.10 s; 100000 rows 22 ms + 0.47 s. SQL ROW_NUMBER() rank update 0.58 s, and its ranks agree with numpy 1.000.

**Why it matters.** Performance is the main blocker for realistic sizes and for any slider-driven visualisation. The per-row pattern costs about 1.1 ms per row per step on local SQLite, and more on networked PostgreSQL. With no transaction, a timed-out request leaves some rows rated and others not.

**Recommendation.** Phase 1 (hours): wrap each stage in transaction.atomic() (about 6x faster) and cap N*M in SimulationConfigForm.clean() (for example 250k pairs). Phase 2: add a pure-numpy engine module nrmps/engine/pre_interview.py following the extra spec (load_population_arrays, compute_utilities, add_noise, rank_rows). Persist with a single executemany UPDATE (or COPY/UPDATE FROM VALUES on PostgreSQL), or rank in the DB with `UPDATE nrmps_interview SET ... FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY score DESC, tie_break) rn ...)`, which SQLite 3.33+ (here 3.45.1) and PostgreSQL both support. Phase 3: run stages as background jobs. Django 6.1 ships django.tasks, but only with Immediate/Dummy backends (checked .venv/.../django/tasks/backends), so add the django-tasks DatabaseBackend worker and poll progress via HTMX. This matches and specifies TODO.md 'Optimize bulk operations for large populations'. IDEAS.md 'Distributed simulation engine' is premature: vectorisation alone removes about 3 orders of magnitude.

**Verifier note (partially).** Performance defect confirmed independently. At 200x15 = 3000 rows: 1.10/1.12/1.09/1.17 ms per row per step, about 4.5 ms per pair in total. One step inside transaction.atomic runs at 0.21 ms/row (about 5x faster). All four steps on 20k rows inside one atomic block take 15.5 s. The reviewer's vectorised prototype, which I re-ran at 500x40, takes 7.9 ms (numpy) + 0.07 s (executemany). gunicorn's default timeout is 30 (config.py Timeout.default), and entrypoint.sh:27 passes no --timeout. django/tasks/backends contains only dummy and immediate. SQLite is 3.45.1. One recommendation detail is outdated. Since django-tasks 0.12.0 the database backend is no longer in django-tasks, which is now only a backport. It lives in the separate package django-tasks-db (INSTALLED_APPS 'django_tasks_db', BACKEND 'django_tasks_db.DatabaseBackend', `manage.py db_worker`), which declares Django 5.2/6.0 classifiers (requires django>=5.2, no 6.1 classifier yet). This is from PyPI metadata.

**Lead note (document check).** The example cap of 250k pairs does not fit a synchronous request: even with `atomic` and `bulk_update`, the legacy engine needs roughly 0.35–0.8 ms per pair per step, so a 30 s request handles about 15–40k pairs. Size the interim cap from a measurement after Plan 0.4 (see D4). 250k+ belongs to the vectorised engine or a background job.

<a id="sim-8"></a>

### SIM-8: initialize_interview materialises the full N x M cross-product in memory and in the DB, for pairs that mostly never interact

**Severity:** 🟠 high · **Kind:** gap · **Effort:** L · **Plan:** 2.3 · **Verification:** confirmed

**Evidence.** nrmps/simulation_engine.py:20-35 builds one list of all Interview objects before bulk_create. review/sim/t4_perf.py tracemalloc: 4000 rows peak 7.7 MB (1926 B/row), 20000 rows 21.2 MB (1058 B/row). Init time 0.94 s/4k and 4.79 s/20k (t4); 1.4 s/20k and 8.1 s/100k (t5): 70-240 us/row. nrmps/models.py:483-492 allow 10000x1000 = 10M pairs, which is about 10-19 GB RAM and 13-40 min in one synchronous request. Delete+create is not atomic (simulation_engine.py:19 then :35). models.py:720-721 uses legacy unique_together.

**Why it matters.** Real NRMP applicants apply to tens of programs, not all of them. Storing every pair as an ORM row makes storage and compute O(N*M) at every later stage (invitations, post-interview, rank lists). Dense matrices do not need to be DB rows at all, and the Interview table should hold only pairs that reach application or interview.

**Recommendation.** Split the data. (a) Dense per-Run matrices (true utilities, observed pre scores, pre ranks) stored as arrays: np.savez_compressed into a FileField/BinaryField on Run (10M float32 ≈ 40 MB), loaded straight by numpy for plots and sliders. (b) A sparse Application/Interview table created only for applied pairs (N x applications_per_applicant). Until then: iterate with itertools.batched (Python 3.13 in .venv) to bound memory, wrap in transaction.atomic(), change to Meta.constraints=[UniqueConstraint(fields=['simulation','student','school'])], and cap the pair count in the form.

**Verifier note (confirmed).** simulation_engine.py:20-35 builds the full list before bulk_create. I measured a tracemalloc peak of 6.7 MB for 3000 rows (about 2.2 KB/row) and 0.72 s init time, consistent with the reviewer. The config allows 10000x1000 (models.py:483-492). The delete at :19 and the create at :35 are not atomic. The Python 3.13.12 venv has itertools.batched. unique_together at models.py:720-721 works; Django docs say it 'may be deprecated in the future', so 'legacy' is fair.

<a id="sim-9"></a>

### SIM-9: True utilities are never stored, so rating error, regret and information effects cannot be measured

**Severity:** 🟠 high · **Kind:** gap · **Effort:** S · **Plan:** 0.3 · **Verification:** confirmed

**Evidence.** nrmps/models.py:681-683 student_true_score_of_school and :698-700 school_true_score_of_student exist but nothing writes them (grep shows no writers). t3 A: 'true_score fields populated: 0'.

**Why it matters.** Every planned analysis (fidelity of observed rankings, welfare loss from noise, 'would the student have preferred another match', blocking pairs under true preferences) needs the noise-free utility next to the observed one. Today only a scaled copy of it is stored, and under the wrong name.

**Recommendation.** In the rating stage, compute and persist U_true and V_true (Interview fields or the Run arrays from SIM-8), then the observed values. Add derived diagnostics to a Run.metrics JSON: mean and quantiles of Spearman(U_i., Uobs_i.) per student and per school, and the fraction of top-k agreement. These feed the visualisation dimension (for example a 'rating fidelity vs noise' slider plot).

**Verifier note (confirmed).** grep finds no writer for student_true_score_of_school or school_true_score_of_student. After a full pipeline, 0 rows have them populated (simverify/v1.py).

<a id="sim-10"></a>

### SIM-10: Ranking breaks ties by DB row order, ranks over the whole cross-product, and runs N+M queries

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 0.3 · **Verification:** confirmed

**Evidence.** nrmps/simulation_engine.py:112-114 / :135-137 `.order_by('-student_pre_observed_score_of_school')` with no secondary key; :117-119 enumerate plus per-row save. Ties are common: t3 D (round trip) gives one distinct score for all 150 pairs; any config with sd=0 gives all-equal scores. Ranks are assigned to all M schools per student and all N students per school, including students who never applied (no application stage exists). Rows with NULL scores are skipped, but any old rank on them is not cleared.

**Why it matters.** On PostgreSQL, ties come back in an undefined order, so results are not reproducible across runs or backends and quietly favour low primary keys. Ranking every student against every school conflicts with NRMP semantics, where programs rank only applicants they interviewed.

**Recommendation.** Define ordinal ranks with an explicit seeded tie-break (extra, section 2.8): numpy `np.lexsort((tie, -score))` per row, or DB `Window(RowNumber(), partition_by=[F('student')], order_by=[F('score').desc(), F('tie_break')])`. The ORM Window read of 100k rows took 0.18 s in review/sim/t5_vector.py. Clear the rank columns before recomputing. Record the ranking domain explicitly (all schools pre-application vs applied set) and document it on the page.

**Verifier note (confirmed).** With all scores tied at 0.5, the ranks follow ascending school id on SQLite (v3.py). This is undefined on PostgreSQL. After setting one student's scores to NULL and re-ranking, 15/15 stale ranks remain. Ranking runs over the full cross-product, and there are N+M filtered queries plus per-row saves (simulation_engine.py:108-119, 131-142). Note: the ORM cannot UPDATE with a Window expression directly, so the Window option works only as a read followed by a bulk write, or as raw SQL UPDATE...FROM. The reviewer measured the read variant.

<a id="sim-11"></a>

### SIM-11: Interview and config help_text is swapped or copy-pasted wrong, and field names are inconsistent; /documentation/ publishes the errors

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 1.6 · **Verification:** partially

**Evidence.** nrmps/models.py:692-697: student_pre_observed_score_of_school help 'Pre interview "total" score of student' and school_pre_observed_score_of_student help '... score of school' (swapped). :703-704 students_pre_rank_of_school 'Pre interview rank of student', schools_pre_rank_of_student 'rank of school' (swapped). :707-718 same for post. :686-689 school_invited 'Whether the school has been invited to the interview' (should be: school invited the student). :674 'has been applied'. :531 applicant_post_interview_rating_error help 'Pre-interview rating error stddev'. :572/:577 school pre and post share one text ('scoreing'). :560-563 school_meta_preference_stddev has no help_text. :554 'In percent of capacity' but stored as a fraction <= 0.99. :609 example '{"USMLE Setp 2":5, "Grades": 10}' implies a 0-10 scale while values are 0-1. views.py:669-673 renders help_text on /documentation/. Naming mixes students_pre_rank_of_school (plural) with student_pre_observed_score_of_school (singular).

**Why it matters.** These strings are the only in-context help today (and the basis for any future '?' tooltips), and for the most confusing fields they state the opposite of the truth. Users will read ranks the wrong way round.

**Recommendation.** Rewrite each help_text with its meaning, scale and direction, for example students_pre_rank_of_school: "Rank (1 = most preferred) that the student gives this school before interviews, based on the student's observed score of the school." Rename fields consistently in one migration (RenameField keeps the data): student_rank_of_school_pre/post, school_rank_of_student_pre/post, student_score_of_school_{true,pre,post}, school_score_of_student_{true,pre,post}. Update views.py:486-495 sort keys, templates and CSV headers. Add a test that every config/Interview field has a non-empty help_text.

**Verifier note (partially).** All cited strings exist and are published on /documentation/ (confirmed in the rendered HTML): 'Pre interview rank of student' on students_pre_rank_of_school, the copy-pasted 'Pre-interview rating error stddev' on the post field (models.py:531), the shared 'scoreing' text (:572/:577), no help_text on school_meta_preference_stddev (:560-563), 'percent' for a value stored as a <=0.99 fraction (:554), the 'USMLE Setp 2':5 example (:609), and the wrong school_invited text. 'Swapped' is one reading, though. 'score of student' / 'rank of student' can be read as 'by the student', so the pre/post texts are ambiguous rather than definitively reversed. They read as reversed under the 'of = about' convention the adjacent true-score fields use ('True score of school with respect to student'). Either way they need rewriting, as recommended.

<a id="sim-12"></a>

### SIM-12: Preference weights from clamped gauss(1, sd) are effectively random on/off switches at default settings

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** M · **Plan:** 2.1 · **Verification:** confirmed

**Evidence.** nrmps/models.py:156-166 and :242-252: w = clip(gauss(1, sd), 0.01, 2.0) then normalised. With default applicant sd 3 (models.py:515), review/sim/t3_pipeline.py J reports 'raw gauss(1,3) clamp: P(=0.01) 0.37 P(=2.0) 0.371', 'frac of weights < 0.01 after normalize: 0.278', 'frac of students with a single weight > 0.9: 0.274'.

**Why it matters.** With sd much greater than 1, three quarters of the draws land on a clamp bound, so the 'heterogeneity' knob behaves like choosing a random subset of attributes, and small values of the knob are the only usable range. There is also no way to say that one attribute matters more on average (for example reputation more than size). Weights cannot express 'prefers small programs' because attributes enter only positively.

**Recommendation.** Draw weights from a Dirichlet: w_i ~ Dirichlet(lambda * m), where m is the per-attribute mean importance (editable next to each tag in the metaEditor, default uniform) and lambda > 0 is a 'consensus' slider (Var w_k = m_k(1-m_k)/(lambda+1)). They are always positive, sum to 1 and never need clipping. Optionally support signed or ideal-point attributes (utility -|y_jk - ideal_ik|) for size and location. Migrate the *_meta_preference_stddev fields to *_preference_concentration.

**Verifier note (confirmed).** Replicated models.py:156-166 with sd=3: P(raw = 0.01) 0.368, P(raw = 2.0) 0.375, 28.2% of weights below 0.01 after normalisation, 27.8% of participants with one weight > 0.9. The Dirichlet variance formula m_k(1-m_k)/(lambda+1) is correct for concentration lambda·m with sum m = 1.

**Lead note (document check).** In the normative spec (Appendix A §4.4–5) the taste term is standardised, so the Dirichlet concentration λ sets the *shape* of tastes, not the amount of consensus. Consensus is controlled by the preference correlation ρ.

<a id="sim-13"></a>

### SIM-13: Preferences are almost identical across participants (Spearman 0.99): no idiosyncratic or horizontal component

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 2.2 · **Verification:** partially

**Evidence.** nrmps/simulation_engine.py:10: utility = sum_k w_ik * y_jk with nonnegative weights. School attributes y_jk are all drawn around the school's own base score (models.py:226-233). review/sim/t5_vector.py (realistic config, meta sd 0.1): 'mean Spearman between two students' TRUE rankings of schools: 0.990' (500x40) and 0.991 (1000x100).

**Why it matters.** If every student ranks schools almost the same way (and every school ranks students the same way), the stable match is close to strictly assortative whatever the other parameters are. Many interesting effects (interview hoarding, signalling value, unmatched rates by tier) vanish or become artefacts. 'location' is modelled as a vertical quality of the school instead of a student-specific fit. This matches TODO.md 'Implement preference correlation modeling' and IDEAS.md 'Geographic constraints', and should be done first because it changes every later result.

**Recommendation.** Add an idiosyncratic term: U_ij = w_i·y_j + tau_A * eps_ij and V_ji = v_j·x_i + tau_S * eta_ji (extra, section 2.5). Expose it as a 'preference correlation / common-value share' slider in [0,1] that solves for tau. Add an optional region attribute: school region r_j, student home region h_i, utility bonus b if r_j == h_i. Report the consensus metric (mean pairwise Spearman) in Run.metrics so users can see where they sit.

**Verifier note (partially).** The structural point holds: there is no idiosyncratic term, weights are nonnegative, and school attributes are drawn around the school's base score (models.py:226-233), so consensus cannot be controlled independently. The headline 0.99 is specific to the reviewer's low-heterogeneity config (meta sd 0.1, preference sd 0.3). I reproduced 0.99 there. With the same scores but preference sd 3 it is 0.86, under the shipped defaults (U-shaped, meta sd 2, preference sd 3) 0.79, and with meta sd 0.3 and preference sd 3 it is 0.66 (simverify/v4.py). So preferences are not 'almost identical' in general. Consensus is high and tied to the attribute-generation knobs. The recommended idiosyncratic term is still the right fix.

<a id="sim-14"></a>

### SIM-14: Attribute (meta-score) generation cannot control the correlation with base quality and collapses under defaults

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** M · **Plan:** 2.1 · **Verification:** partially

**Evidence.** nrmps/models.py:140-147 / :226-233: x_ik ~ Beta(mean=base_score, sd=meta_std). review/sim/t2_beta.py: with the default base (0.7/2): corr(base, meta) = 0.409 at meta_std=10, 0.442 at 0.5, 0.572 at 0.1, 0.647 at 0.05. Meta values are about 32% >0.99 because both levels are U-shaped. Student/School.meta_stddev (models.py:604-606, 635-639) is never written.

**Why it matters.** The only knob (meta sd) mixes marginal spread with correlation, and near 0 or 1 it is clamped differently for each entity. Researchers cannot say 'board scores track overall quality with rho=0.8 but research only with rho=0.3', and every attribute shares the base score's mean.

**Recommendation.** Use a Gaussian copula (extra, section 2.2): latent z_i ~ N(0,1); attribute z_ik = rho_k z_i + sqrt(1-rho_k^2) e_ik; x_ik = BetaPPF(Phi(z_ik); mu_k, sd_k). Store per-attribute (rho_k, mu_k, sd_k) in the config as a JSON list of objects edited in the tag editor. Keep the current method as a 'legacy' option for existing simulations. Remove the unused meta_stddev fields.

**Verifier note (partially).** Under the defaults (0.7/2 base, meta sd 10): corr(base, meta) 0.41 and 31.7% of meta values > 0.99, reproduced. Student/School.meta_stddev are never written (grep). The title's 'cannot control the correlation' overstates it. The meta sd knob does move the correlation (0.41 at the defaults, 0.83 at base 0.5/0.15 with meta sd 0.1). The real defect is that one knob controls both marginal spread and correlation, with no per-attribute rho/mean and bound-dependent clamping. The copula recommendation stands.

<a id="sim-15"></a>

### SIM-15: Capacity generation allows 0-seat and negative-mean programs, and the seats/applicants balance is never checked

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 2.1 · **Verification:** confirmed

**Evidence.** nrmps/models.py:221-224: capacity = max(0, round(gauss(mean, sd))), so P(0) ≈ 2.6% at 20/10. review/sim/t3_pipeline.py J: 'capacities: zero: 3 total seats: 913 applicants: 500'. models.py:545 school_capacity_mean has no validators. review/sim/t8_form.py: school_capacity_mean=-5 gives form valid=True. Uploads coerce missing or invalid capacity to 0 (models.py:407-409, 441-443).

**Why it matters.** Zero-capacity programs still get interviews and rankings, and will distort match-rate statistics. The ratio of total positions to applicants, the main driver of unmatched rates, is not shown and not controlled.

**Recommendation.** Use capacity >= 1: a lognormal or 1 + negative-binomial draw with the requested mean and sd. Add MinValueValidator(1) on the capacity mean and on School.capacity. Show 'positions per applicant = sum(c_j)/N' live on the config form, with an optional 'target ratio' mode where capacities are rescaled to hit it.

**Verifier note (confirmed).** P(capacity = 0) is 2.58% at gauss(20,10) (N=100k). SimulationConfigForm with school_capacity_mean=-5 is valid with no errors (models.py:545 has no validators). School.capacity has no validators, and uploads coerce invalid or missing values to 0 (models.py:407-409, 441-443).

<a id="sim-16"></a>

### SIM-16: The interview-limit fields have unworkable semantics, and application/signal/rank-list limits are missing

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 2.1 · **Verification:** confirmed

**Evidence.** nrmps/models.py:551-555: school_interview_limit is a FloatField 0-0.99 described as 'percent of capacity'. With capacity 20 and default 0.1, a school can interview 2 applicants for 20 positions. models.py:504-508 applicant_interview_limit is an int with no max, and the widget uses step 'any' (forms.py:167). Neither field is read anywhere in nrmps/simulation_engine.py. Interview.student_signal (models.py:676) has no config counterpart.

**Why it matters.** Once the invitation stage (TODO.md 'School invitation logic') is built on these fields, every program will be structurally unable to fill (real programs interview several applicants per position). The pipeline also needs applications per applicant, signals per applicant and rank-list length caps to reproduce well-known NRMP dynamics (application inflation, signalling).

**Recommendation.** Replace school_interview_limit with interviews_per_position (FloatField >= 1, default about 10, calibrated from the NRMP Program Director Survey). Add applications_per_applicant, signals_per_applicant, applicant_rank_list_max and program_rank_list_max (0 = unlimited). Give each field help_text stating its unit. Drop TODO.md 'Interview scheduling system (date/time fields, calendar views)': calendar realism adds nothing to the simulation and costs a lot.

**Verifier note (confirmed).** school_interview_limit is a FloatField with max 0.99 documented as a percent of capacity (models.py:551-555), so interviews <= 0.99 x capacity. applicant_interview_limit has no max, and its widget uses step 'any' (forms.py:167). Neither interview_limit field is referenced in simulation_engine.py (grep: only models, forms and the template). Interview.student_signal has no config counterpart. The recommended fields (applications, signals, ROL caps) match real ERAS/NRMP mechanics. The ~10 interviews per position is a reasonable order of magnitude, but I could not check it against a specific NRMP PD Survey table offline.

<a id="sim-17"></a>

### SIM-17: Config form: meta-list validation gaps can crash population creation, and the comma-separated parsing is dead code

**Severity:** ⚪ low (originally medium) · **Kind:** defect · **Effort:** S · **Plan:** 2.1 · **Verification:** partially

**Evidence.** review/sim/t8_form.py: applicant_meta_preference='program_size, prestige' gives 'Enter a valid JSON.' because forms.JSONField rejects it before clean_applicant_meta_preference (forms.py:91-112, 115-136) runs, so that CSV branch is unreachable. '5' gives valid=True with cleaned=5, and create_students then runs list(5) (models.py:129/132), a TypeError and 500. '{"a":1}' is valid (dict). '[]' gives 'This field is required' although the engine accepts empty lists. An infeasible sd (0.9/0.45), negative capacity and 10000x1000 pairs are all accepted. forms.py:163-164 widget min=0 vs validator min 1. simulation_manage.html:172,194 injects the list via `|safe` into x-data and a single-quoted value attribute (Python repr uses single quotes).

**Why it matters.** The config is the entry point to every step, and today its validation is either too loose (non-list JSON, infeasible parameters) or too strict (empty list), with an error message that suggests a CSV format the field cannot accept.

**Recommendation.** Use a custom `MetaKeyListField(forms.Field)` that accepts a JSON list or comma-separated text and normalises it to unique [a-z0-9_] keys with 1-10 items. Render the hidden input with `{{ value|json_script }}` instead of `|safe`. Add SimulationConfigForm.clean() covering sd feasibility (SIM-2), a pair-count cap (SIM-7), a capacity balance warning and non-overlapping attribute names. Add form unit tests for each case above.

**Verifier note (partially).** Form behaviour reproduced: 'program_size, prestige' gives 'Enter a valid JSON.', so the CSV branch in clean_* is unreachable. '5' is valid (cleaned=5). '[]' gives 'This field is required.' '{"a":1}' is valid. Infeasible sds, a negative capacity and 10M pairs are all accepted. The widget min is 0 while the validator min is 1. Impact is overstated, though. In the UI the hidden input is always filled by metaEditor.jsonValue() (simulation_manage.html:355-357), which posts a deduplicated JSON list normalised to [a-z0-9_-]. So the '5' TypeError crash is reachable only by a crafted POST (or with JS disabled, where the single-quoted value attribute is broken anyway). The UI-reachable problems are removing all tags, which is rejected as 'required', and the missing cross-field feasibility checks, which overlap with SIM-2 and SIM-15.

<a id="sim-18"></a>

### SIM-18: 'Latest config wins' but the UI edits one config in place, so there is no provenance of which parameters produced a population or result

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 2.3 · **Verification:** confirmed

**Evidence.** nrmps/views.py:102 and :119-121 bind the POST to the existing latest config (instance=config_instance), so a simulation never gets a second SimulationConfig row. models.py:118, 200 and simulation_engine.py:49, 80 each re-read `configs.order_by('-id').first()` at run time. Student/School have no FK or snapshot of the config or seed. t3 C shows an edit after population creation silently desynchronising the population, which then crashes (SIM-4).

**Why it matters.** Because rating steps re-read the config, one pipeline can mix parameters from different edits, and after any edit nobody can say what generated the current data. That rules out reproducible reports, scenario comparison, and any 'compare slider positions' feature.

**Recommendation.** Make configs immutable versions: on save, create a new SimulationConfig row when a population exists, or add a Run.config_snapshot JSONField plus config FK. Stamp the population with population_config_id, seed and attribute key lists. Compare the current config with the population's and show a 'population is stale, regenerate?' banner. The existing ForeignKey(related_name='configs') already supports versions, so only the view and engine need to change.

**Verifier note (confirmed).** views.py:102 and :119-121 bind the POST to the latest config instance, so a SimulationConfig is only ever updated in place (a second row is never created). The engine re-reads configs.order_by('-id').first() at models.py:118, :200 and simulation_engine.py:49, :80. Student/School have no config FK or snapshot. An edit made after population creation desynchronised the keys and crashed in my SIM-4 reproduction.

<a id="sim-19"></a>

### SIM-19: No seed and mixed RNGs (random + scipy/global numpy) make simulations irreproducible and unsuitable for scenario comparison

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** S · **Plan:** 2.2 · **Verification:** confirmed

**Evidence.** nrmps/models.py:156, 221, 242 random.gauss (Python Mersenne Twister, global); :62 scipy beta.rvs (global numpy RandomState); :116, :198 re-import random locally. There is no seed field on Simulation or SimulationConfig.

**Why it matters.** Two runs with identical settings give different populations. When a user moves a noise slider, the population is also redrawn, so differences mix the parameter effect with sampling noise. Common random numbers are needed for meaningful sliders and for Simulation.iterations. This matches IDEAS.md 'Reproducible research features' and TODO.md 'Create reproducible simulation reports'.

**Recommendation.** Add seed (BigIntegerField, default random, editable, shown). Use numpy.random.default_rng(SeedSequence(seed).spawn(k)) with one child stream per stage (student pop, school pop, weights, idiosyncratic, pre-noise per side, tie-break). Iteration r uses SeedSequence(seed, spawn_key=(r,)). Remove all uses of the random module. Add a test that the same seed gives byte-identical arrays and that changing only the noise sd leaves the population arrays unchanged.

**Verifier note (confirmed).** random.gauss is at models.py:156, 221, 242, and scipy beta.rvs without random_state at :62 (global numpy RandomState). There is no seed field on Simulation or SimulationConfig. numpy's SeedSequence does accept spawn_key=(r,), so the recommendation is technically valid.

<a id="sim-20"></a>

### SIM-20: No pipeline state machine: statuses never change, there are no guards, and destructive steps are non-atomic

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 0.4, 2.4 · **Verification:** confirmed

**Evidence.** nrmps/models.py:97 Simulation.status default 'pending', never written (grep); t3 A: 'Simulation.status after pipeline: pending'. models.py:670 Interview.status is always 'initialized' (t3 A Counter({'initialized': 150}), F5). Views accept any step in any order (views.py:405-472). models.py:124 and :204 delete before bulk_create outside a transaction. Recreating students cascades a delete of all interviews, but the HTMX response only refreshes #population-counts (views.py:229-230), so the interview count on the page goes stale. views.py:224-241 with no config returns count 0 silently (t3 I).

**Why it matters.** Users can compute rankings before scores, rate an empty interview set, or lose their population when generation fails halfway. A fast double click on '(re)Create' can interleave two delete+create sequences. Without a stage indicator the UI cannot show progress or disable invalid actions, which is also a UI/UX dependency.

**Recommendation.** Add Simulation.stage = TextChoices(CREATED, CONFIGURED, POPULATED, INTERVIEWS_INITIALIZED, PRE_RATED, PRE_RANKED, INVITED, INTERVIEWED, RANKED, MATCHED), with each engine function asserting its precondition and setting the next stage, and upstream changes resetting downstream stages. Run every stage inside transaction.atomic() with Simulation.objects.select_for_update().get(pk=...). Return an out-of-band HTMX swap (hx-swap-oob) so population actions also refresh #interview-counts. Show a clear message when no config exists.

**Verifier note (confirmed).** Simulation.status is never written (grep; still 'pending' after the pipeline). Interview.status stays 'initialized' on 150/150 rows. No view guards step order. The population actions target only #population-counts (partials/_population_counts.html:16,23,31,55,62,70), while Student/School deletion cascades to Interview, so #interview-counts goes stale. With no config, create_students returns 0 and nothing is shown. The double-click race is plausible with 4 gunicorn workers on PostgreSQL, though hx-confirm reduces the risk. I did not reproduce it. select_for_update is a no-op on SQLite.

<a id="sim-21"></a>

### SIM-21: The Match model and Simulation.iterations/public are unused and cannot support multiple runs; a Run/RankList/MatchResult model is needed

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 2.3 · **Verification:** confirmed

**Evidence.** nrmps/models.py:727-745 Match(student, school, students_rank_of_school, schools_rank_of_student) with unique_together(student, school) and no run/iteration or matched flag; never written. models.py:95 iterations (1-100) is only displayed (simulations_list.html:31). models.py:93 public default=True is only displayed (simulations_list.html:33); every view enforces owner-only access (for example views.py:98).

**Why it matters.** Match mixes up two things: rank-order-list entries and match outcomes. With unique_together(student, school) and no run key it cannot hold several iterations or scenarios. 'iterations' suggests Monte-Carlo replication that does not exist. public=True by default is misleading today and a privacy risk once sharing is added. TODO.md 'Implement NRMP matching algorithm ... Create Match model instances' should not build on the current Match model.

**Recommendation.** Introduce: Run(simulation FK, iteration int, seed, config_snapshot JSON, stage, status {queued,running,done,failed}, started_at, finished_at, error text, metrics JSON, arrays FileField). RankListEntry(run FK, side {student,school}, student FK, school FK, rank int; UniqueConstraint(run, side, student, school)). MatchResult(run FK, student FK, school FK null, round {main,soap}, student_rank_of_match, school_rank_of_match). Implement iterations as N Runs with spawned seeds, each with mode 'fixed population, resample noise' or 'resample all'. Change public to default False until a public listing exists. Delete Match through a migration once RankListEntry and MatchResult exist.

**Verifier note (confirmed).** Match (models.py:727-745) is never written, has unique_together(student, school) and no run or iteration key. iterations appears only in forms and simulations_list.html:31. public defaults to True (models.py:93) and only affects the display, since simulation_list filters owner=request.user (views.py:73) and every view checks ownership.

<a id="sim-22"></a>

### SIM-22: Docstrings claim steps the code does not perform (application choice); the rating stage ignores applications entirely

**Severity:** ⚪ low · **Kind:** gap · **Effort:** S · **Plan:** 1.6, 3.6 · **Verification:** partially

**Evidence.** nrmps/simulation_engine.py:39 docstring 'Students choose which schools they would like to apply to.', but the function only writes student_pre_observed_score_of_school. Interview.student_applied (models.py:673), student_signal (:676), student_accepted (:677), school_invited (:686) are never set. The school rating (:69-96) scores every student, applicant or not.

**Why it matters.** Readers of /documentation/ and future contributors will assume an application stage exists. This is the boundary between the implemented pre-interview stage and the missing application, invitation, interview, rank-list and match stages covered by the completeness review.

**Recommendation.** Correct the docstrings now. Add an explicit apply_stage(run) (top-k by observed utility with k = applications_per_applicant, optionally with a 'safety' mix across quality tiers) that sets student_applied, before a school-side rating restricted to applicants.

**Verifier note (partially).** The docstring mismatch is real: simulation_engine.py:39 says 'Students choose which schools they would like to apply to' but only writes scores. student_applied, student_signal, student_accepted and school_invited are never set (grep). The school side scores every student. But the stated impact on '/documentation/' readers is wrong: the documentation view only introspects nrmps.models (views.py:639, 682), and simulation_engine docstrings do not appear on the rendered page. The impact is on code readers only.

<a id="sim-23"></a>

### SIM-23: Dead, no-op and mis-typed code in models.py and simulation_engine.py

**Severity:** ⚪ low · **Kind:** defect · **Effort:** S · **Plan:** 1.6 · **Verification:** confirmed

**Evidence.** nrmps/models.py:141-144, 152-155, 227-230, 238-241 `try: k = str(key) except Exception: k = str(key)` (both branches identical). :584-590 generate_meta_scores(self, ...) is a module-level function with a self parameter, an invalid annotation `dict[str:float]`, returns None, and is never called. :116, :198 re-import random, shadowing :1. :270-276 delete_students/delete_schools are annotated -> int but return None. :414-417 parse meta_stddev and discard it; :449 bare `pass`. simulation_engine.py:52, 83, 105, 128 re-import Interview as InterviewModel although it is imported at :1; :64 commented-out code; :167 `def interview(self)` at module level; typo meta_preferances at :4/:10 (already in TODO.md). Student/School.meta_stddev never written; meta_stddev_preference only copies the config value.

**Why it matters.** This inflates the ruff/mypy counts (F6), misleads readers, and generate_meta_scores still shows up in the docs machinery through __doc_exclude__ hacks (views.py:585).

**Recommendation.** Delete the no-op blocks and generate_meta_scores (along with the views.py:585 exclusion), fix the return annotations, and move all stage code into nrmps/engine/ with typed dataclasses for the population arrays. Remove the meta_stddev fields in the SIM-2 migration. Fix the meta_preferances typo as TODO.md already lists.

**Verifier note (confirmed).** Each item verified by reading. The identical try/except branches are at models.py:141-144, 152-155, 227-230, 238-241. generate_meta_scores (:584-590) takes self, is annotated dict[str:float], returns None and has no callers. random is re-imported at :116 and :198. delete_* are annotated -> int but return None. meta_stddev is parsed and discarded at :414-417, and :449 is a bare `pass`. The engine re-imports Interview at :52, :83, :105, :128, has commented-out code at :64, and defines `def interview(self)` at module level (:167). The meta_preferances typo is TODO.md:147-148.

<a id="sim-24"></a>

### SIM-24: Rebuild the engine as a seeded, vectorised, tested core before building the remaining stages

**Severity:** 🟠 high · **Kind:** recommendation · **Effort:** L · **Plan:** 2.2 · **Verification:** confirmed

**Evidence.** Combines SIM-1, 3, 7, 8, 9, 10, 19. Prototype review/sim/t5_vector.py (load_population_arrays, Wst @ Q.T + noise, argsort-based rank_rows, executemany persist) reproduces the current ranks exactly (ROW_NUMBER agreement 1.000) at 20k rows in 0.11 s vs 88.6 s. nrmps/tests.py is empty (F6).

**Why it matters.** The unfinished stages (invite, interview, rank, match) will all inherit the current engine's problems if built on it. The visualisation goal (sliders) also needs sub-second recomputation, which only an array-based engine can provide.

**Recommendation.** Create package nrmps/engine/ with: rng.py (SeedSequence streams), population.py (Beta/copula/Dirichlet generation to numpy arrays), utilities.py (true U/V with an idiosyncratic term), observe.py (pre/post noise models, extra 2.6-2.7), rank.py (ordinal ranks with seeded tie-break), persist.py (array artifact per Run plus sparse executemany for Interview rows), and later match.py (applicant-proposing deferred acceptance with capacities, vectorised or via a small pure-Python loop that is O(total rank-list length)). Keep Django models as thin persistence. Add pytest suites: statistical properties (mean/sd tolerance), invariants (ranks are permutations, sigma=0 gives identity), reproducibility, CSV round trip, and a view smoke test per endpoint. Run large sizes through django-tasks.

**Verifier note (confirmed).** The cited 'ROW_NUMBER agreement 1.000' in t5 compares numpy ranks with SQL ROW_NUMBER ranks on the new noisy scores, not with the current engine, so it does not show what it is cited for. I checked the actual claim separately. The same prototype with sigma=0 at 500x40 matches the current engine's ranks 1.0/1.0 on both sides (simverify/v6.py). It takes 0.08 s versus 15.5 s for the current engine inside atomic, or about 88 s without. Capacitated applicant-proposing deferred acceptance runs in O(total rank-list length) proposals, which is correct. Real NRMP uses the Roth-Peranson variant with couples, which a later stage would need. Use django-tasks-db, not django-tasks, for a DB worker (see SIM-7).

<a id="stg"></a>

## STG: Missing & incomplete simulation stages vs. the real NRMP process

> **Reviewer summary.** The simulator implements only the first 4 of about 12 stages in the real process: population, the full student x school cross-product, pre-interview scoring and pre-interview ranking. Everything that produces an outcome is a stub (interview(), students_rank(), schools_rank(), match() in nrmps/simulation_engine.py:167-190), and the model fields for application, signal, invitation, acceptance, true score and post-interview score, the Match table, Simulation.status and Simulation.iterations are never written. Several stages that do exist are wrong in ways that would invalidate a match once one is added. Observation error has no effect (0 of 120 applicants' observed orders differ from their true orders). Preferences are purely vertical: under default settings every applicant has the same #1 school. school_interview_limit is capped below 1 interview per position, and no stage uses a seed or a config snapshot. I built a scratch numpy prototype of the full proposed pipeline (applications, gold/silver signals, invitation waves under interview caps, post-interview update, ROLs, applicant-proposing DA, stability check, SOAP, NRMP-style stats). Its DA matched the 'matching' 1.4.3 reference on 20/20 random instances with 0 blocking pairs. The whole pipeline runs at the config maximum of 10,000 x 1,000 in 8.5 s, of which DA takes 0.04 s. A Roth-Peranson-style couples extension found a stable matching in 9 of 10 markets at the 2026 real couples share (5.2% of applicants) using random restarts. The recommended path is to fix the observation model, stage state machine, seeds and config snapshot first; then build the singles pipeline through to a validated match; then add Monte-Carlo runs; then SOAP and applicant types; and last couples, supplemental ROLs, reversions and multiple specialties. The full stage specification is in 'extra'.

<a id="stg-1"></a>

### STG-1: No outcome stages: interview(), students_rank(), schools_rank() and match() are empty stubs, and the Match table is never written

**Severity:** 🔴 critical · **Kind:** gap · **Effort:** L · **Plan:** 3.6 · **Verification:** confirmed

**Evidence.** nrmps/simulation_engine.py:167-172 (`def interview(self): pass` — a module-level function that takes `self`), :175-180, :183-185, :188-190. nrmps/models.py:727-745 (Match model): grep shows no code creates Match rows. templates/nrmps/partials/_interview_counts.html has buttons only for Initialize and Compute Pre-Interview. TODO.md:6-25 lists the same four items.

**Why it matters.** The simulation stops after pre-interview rankings, so there is no match result, no statistics and nothing to visualize. Every other goal (plots, sliders, Monte-Carlo) depends on this. The TODO items are needed but under-specified. TODO.md:18 ('Respect school capacity constraints' when programs rank) should be corrected: capacity limits the match, not the length of a program's rank list, and programs rank many more applicants than they have positions.

**Recommendation.** Implement stages S8 (interview), S9 (rank lists), S10 (match) and S12 (analyze) as specified in extra sections 2-3. Put them in a new package nrmps/engine/ with modules interviews.py, rol.py, match.py, validate.py and metrics.py. Keep simulation_engine.py as a thin facade the views call. Do singles first, using the DA pseudo-code in extra section 3.1 (the prototype at scratch/review/STG/proto_engine.py:deferred_acceptance is about 30 lines and validated). Add a 'Run Match' step button and a match-results partial.

**Verifier note (confirmed).** Checked nrmps/simulation_engine.py:167-190. interview(self), students_rank(), schools_rank() and match() are all `pass`. A grep over all .py files (excluding migrations) finds no code that creates Match rows, only the model at models.py:727-745. _interview_counts.html has only the Initialize and Compute Pre-Interview buttons. One small citation error: 'Respect school capacity constraints' is at TODO.md:19, not :18. The correction itself is right: capacity limits the match, not the length of a program's rank list.

<a id="stg-2"></a>

### STG-2: There is no true-utility stage, and observation error has no effect (multiplied in, not added)

**Severity:** 🔴 critical · **Kind:** defect · **Effort:** S · **Plan:** 0.3 · **Verification:** confirmed

**Evidence.** nrmps/simulation_engine.py:4-10: `_score` returns sum(meta*pref) * rating_error. Probe (scratch/review/STG/probe1.py, isolated DB, 120x8): 'students whose observed pre-rank order != true order: 0/120'; observed range 2.4e-06..0.0997; 'true score fields null: 960' (Interview.student_true_score_of_school / school_true_score_of_student at models.py:681-683 and 698-700 are never set). Builds on lead fact F5.

**Why it matters.** Because the error term only rescales scores, 'observed' rankings always equal true rankings. The fields that should hold the ground truth are empty. Any later match would therefore have no information friction, and welfare measures (regret, how well the matched program actually fits) cannot be computed.

**Recommendation.** Add stage S3 'preferences'. First compute true utilities u_app[i,j] and u_prog[i,j], persisting them to the existing *_true_score_* fields. Then compute observed = true + N(0, sigma_pre) with additive Gaussian noise from a seeded numpy Generator. Rename the private helper to `_utility(attrs, weights)` and remove the rating_error argument. Relabel the config fields as 'observation noise SD (additive)'. See extra section 2, S3.

**Verifier note (confirmed).** _score (simulation_engine.py:10) multiplies by rating_error, and a positive scalar cannot change rank order. My own run (100x20, default config): 0 of 100 students had an observed order different from the true order. Observed scores ranged from 8.7e-07 to 0.0997. The true-score fields were null on 2000 of 2000 rows. Also, `or 1.0` at simulation_engine.py:50 and :81 turns rating_error=0 into 1.0.

<a id="stg-3"></a>

### STG-3: Preferences are purely vertical: under default settings every applicant has the same #1 school

**Severity:** 🟠 high · **Kind:** defect · **Effort:** S · **Plan:** 2.2 · **Verification:** partially

**Evidence.** scratch/review/STG/probe2.py (default config, 100x20): 'share of students with the same #1 school: 1.0'; mean pairwise Spearman correlation between students' school rankings 0.713, and between schools' student rankings 0.841. probe1: school scores [0.343, 0.934, 0.0, 0.994, 0.170, 0.0, 1.0, 0.402]. Cause: defaults school_score_mean=0 and school_score_stddev=2 (models.py:535-544) give a U-shaped beta distribution, so some schools score exactly 1.0 on every meta attribute. That also violates MaxValueValidator(0.99) (models.py:632-634). The utility has no idiosyncratic term (simulation_engine.py:10).

**Why it matters.** When every applicant proposes first to the same program, at most cap/N of them can get their first choice. The real benchmark is 73.5% of 2026 US MD seniors matching to one of their top 3 programs (NRMP, Mar 2026). Real preferences combine a common prestige component with pair-specific fit (geography, program culture). Without the fit component, match-rate and rank-distribution results are artifacts of the model, not findings.

**Recommendation.** Use u_app[i,j] = w_common*(sum_k w_ik*a_jk) + beta_prestige*prestige_j + eps_ij with eps ~ N(0, fit_sd_app), and the same form for programs. Optionally subtract a geography term, lambda*distance(region_i, region_j). This extends IDEAS.md:47. New SimulationConfig fields: common_weight (default 0.6), applicant_fit_sd (0.15), program_fit_sd (0.15), n_regions, geo_weight. Fix the degenerate school_score_mean default (for example 0.5) and clamp generated scores to the validator range.

**Verifier note (partially).** The core holds: preferences are highly vertical and the utility has no idiosyncratic term. The headline is overstated. Over 30 default draws at 100x20, the share of students with the same #1 school had a median of 0.68 (range 0.37-1.00) and reached 1.0 in only 30% of draws (13% at 100x8). Mean pairwise Spearman was about 0.73 for students and 0.75 for schools, close to the reviewer's figures. The root cause and the fix are also wrong. The U-shape does not come from school_score_mean=0. get_beta_parameters (models.py:33-35) caps any stddev above sqrt(m(1-m)) at 0.9x that maximum, which always gives alpha+beta of about 0.235 (a U-shaped Beta) whatever the mean. The defaults applicant_score_stddev=2, applicant_meta_scores_stddev=10, school_score_stddev=2 and school_meta_scores_stddev=2 all trigger this cap. With school_score_mean=0.5 the meta-score histogram is still [228,25,25,16,10,14,11,20,29,222]; with SDs of 0.1-0.15 it is unimodal. So the proposed 'school_score_mean 0.5' fix alone does not help. The validator point is also larger than stated: School.score exceeds 0.99 in 0-3 of 20 schools, but Student.score exceeds 0.99 in 31-44% of students, because bulk_create bypasses validators.

<a id="stg-4"></a>

### STG-4: No application stage: student_applied is never set, and every student is treated as having applied everywhere (full cross-product)

**Severity:** 🟠 high · **Kind:** gap · **Effort:** M · **Plan:** 3.1 · **Verification:** partially

**Evidence.** nrmps/models.py:673-675 (student_applied, never written). nrmps/simulation_engine.py:13-35 creates Student x School rows for all pairs. Lead fact F4: up to 10M rows in one synchronous request. AAMC ERAS 2025-26: on average 81.8 applications per applicant, 36 per specialty.

**Why it matters.** In the real process an applicant applies to a small, strategically chosen subset of programs (reach, target and safety programs, filtered by eligibility). Who applies where is the main driver of interview concentration and of unmatched applicants. The prototype shows that applicants with 0 interviews (169 of 2000) make up most of the unmatched. A full cross-product also makes storage O(A x P) instead of O(A x apps).

**Recommendation.** Add stage S4 'applications' (pseudo-code in extra, S4) with strategies 'top_k' and 'portfolio' (reach/target/safety, based on a noisy self-assessment of competitiveness). Create Interview rows only for pairs that applied, or add an Application table. Keep all-pairs utilities in memory, optionally saved as a compressed .npz blob per run for plotting. New config fields: apps_mean (36), apps_sd, apps_max, application_strategy, reach_share, safety_share, self_assessment_sd.

**Verifier note (partially).** Confirmed: student_applied (models.py:673-675) is never written, and initialize_interview builds the full cross-product. The ERAS 81.8 total / 36 per specialty figures are confirmed via a secondary source. The supporting prototype stat is false. Rerunning proto_engine at 2000x200, zero-interview applicants are 169 of 467 unmatched (36%), 126 of 431 (29%) and 125 of 374 (33%) for seeds 1-3, which is not 'most of the unmatched'. That figure is also an artifact of the uncalibrated prototype, not evidence about the real process.

<a id="stg-5"></a>

### STG-5: No preference-signaling stage (gold/silver tiers); the student_signal field is unused

**Severity:** 🟠 high · **Kind:** gap · **Effort:** M · **Plan:** 3.2 · **Verification:** partially

**Evidence.** nrmps/models.py:676 (`student_signal = IntegerField(default=0)`, never written). AAMC: 27 or more specialties use signals in 2026; Internal Medicine uses 3 gold + 12 silver (AAIM 2025-26); Dermatology uses 3 gold + 25 silver. AAMC 2025 anesthesiology data: median interview rate 61% with a gold signal vs 1-3% with no signal; 96% of programs used signals when choosing interviewees (2026 ERAS). AAIM says programs should not use signals for rank-list decisions.

**Why it matters.** Signaling is the biggest change to the process since 2021 and a key research lever: how does the number of signals affect interview spread and match rate? The model has an integer field but no tiers, no limits and no effect on screening.

**Recommendation.** Add stage S5 'signals': among each applicant's applied programs, assign gold to the top n_gold and silver to the next n_silver by observed utility (or by a 'target' strategy). Store student_signal in {0 none, 1 silver, 2 gold} as IntegerChoices. Screening adds signal_boost_gold or signal_boost_silver. Add signal_rank_boost (default 0) for the post-interview effect. Validate count(gold) <= n_gold, count(silver) <= n_silver, and signal implies applied. Config: signals_enabled, n_gold (3), n_silver (12), signal_boost_gold, signal_boost_silver, signal_strategy.

**Verifier note (partially).** Confirmed: student_signal (models.py:676) is never written. Also confirmed: IM 3 gold + 12 silver (AAIM 2025-26), Dermatology 3 gold + 25 silver, at least 27 specialties accept signals in 2026, 96% of programs used signals to choose interviewees (AAMC 2026 survey), and AAIM advises programs not to use signals for rank lists. I could not verify the anesthesiology figure ('median interview rate 61% with gold vs 1-3% no signal'), and it looks misquoted. Published anesthesiology data give 56.7% for gold vs 31% for silver (2023-24, 5 gold + 10 silver), and '3%' is the no-signal share of the interview pool, not an interview rate. The recommendation itself is sound.

<a id="stg-6"></a>

### STG-6: school_interview_limit allows fewer than 1 interview per position, and there is no invitation or accept/decline stage

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 2.1, 3.3 · **Verification:** confirmed

**Evidence.** nrmps/models.py:551-555: `school_interview_limit = FloatField(default=0.1, validators=[Min 0, Max 0.99])` 'In percent of capacity'. probe1: capacities [11,35,10,17,16,3,14,32] give slots [1.1,3.5,1.0,1.7,1.6,0.3,1.4,3.2]. models.py:686-689 school_invited and :677-680 student_accepted are never written. applicant_interview_limit (models.py:504-508, default 5) is never read. TODO.md:27-35 asks for date/time/calendar scheduling.

**Why it matters.** Programs can only rank people they interviewed. With fewer than 1 interview per position, positions go unfilled by construction. Real programs interview roughly 10 or more applicants per position (see the NRMP Program Director Survey; confirm the exact figure per specialty). Applicants accept invitations only up to a personal cap, and invitations go out in waves: specialties such as ophthalmology (4 release dates), urology (1) and dermatology (3) use coordinated release dates. Calendar dates and times (TODO.md:32) are unnecessary for a simulation; discrete waves and slots model the same thing more simply.

**Recommendation.** Replace school_interview_limit with interviews_per_position (FloatField >= 1, default 10), migrating existing values. Add stage S6/S7 'invitations' with waves (pseudo-code in extra, S6-S7): each wave, programs invite the top uninvited applicants by screen score up to open_slots x over_invite. Applicants accept, best first, up to applicant_interview_limit (default 12). Slots fill first-come-first-served, with remaining invitations waitlisted. Optionally applicants cancel lower-valued interviews when a better one arrives. Persist school_invited, invite_wave and invite_response (accepted/declined/waitlisted/cancelled). Validate accepted <= cap per applicant and accepted <= slots per program.

**Verifier note (confirmed).** models.py:551-555: default 0.1 with max 0.99 'in percent of capacity'. In my run the slots were 0.4-3.1 for capacities 4-31. applicant_interview_limit, school_invited and student_accepted are never read or written (grep). Caveats: the field is not read by any stage today, so the under-one-interview-per-position problem is latent until invitations are built. The release-date counts are correct (ophthalmology 4, urology 1, dermatology 3), but ophthalmology (SF Match) and urology (AUA) run matches outside the NRMP. They illustrate interview-season practice, not NRMP rules.

<a id="stg-7"></a>

### STG-7: There is no stage state machine: status fields never change and steps can run in any order

**Severity:** 🟠 high · **Kind:** gap · **Effort:** M · **Plan:** 2.4 · **Verification:** partially

**Evidence.** nrmps/models.py:97 `Simulation.status = CharField(default='pending')` is never updated. Interview.status stays 'initialized' (models.py:670; simulation_engine.py:30; lead fact F5). views.py:405-472: each step view runs unconditionally, so rankings can be computed before scores exist, and '(re)Initialize' silently deletes all later results (simulation_engine.py:19).

**Why it matters.** Without a state machine the UI cannot show progress, cannot stop invalid actions, and cannot detect stale results after the population or config changes. Monte-Carlo runs need the same stage list executed per run.

**Recommendation.** Add `class Stage(models.TextChoices)` with DRAFT, CONFIGURED, POPULATED, PREFERENCES, APPLIED, SIGNALED, INVITED, INTERVIEWED, RANKED, MATCHED, SOAP_DONE, ANALYZED, plus RUNNING and FAILED flags. Add a StageRun log (run, stage, started_at, finished_at, params_hash, counts JSON, error). Add a helper `engine.pipeline.run_stage(run, stage)` that checks the prerequisite stage, holds a select_for_update lock, clears later fields with queryset.update(), and advances status. Interview.status should become an enum (applied, invited, scheduled, interviewed, ranked, matched). Diagram in extra section 1.

**Verifier note (partially).** The core holds. Simulation.status and Interview.status never change (my run: {'initialized'}, 'pending'), and each step view at views.py:404-472 runs unconditionally. Two details are wrong. (Re)Initialize is not silent: it has an hx-confirm, 'This will replace existing interviews' (_interview_counts.html:18). Computing rankings before scores does not corrupt anything: it returns 200 and ranks 0 rows because it filters out null scores. The real silent case the reviewer missed: regenerating students or schools cascade-deletes every Interview row (FK CASCADE, models.py:667-668), while the confirm text only says 'replace existing students'.

<a id="stg-8"></a>

### STG-8: No random seed anywhere, so no run can be reproduced

**Severity:** 🟠 high · **Kind:** gap · **Effort:** S · **Plan:** 2.2 · **Verification:** confirmed

**Evidence.** nrmps/models.py:62 `beta.rvs(...)` with no random_state; models.py:156, 221, 242 use the global `random.gauss`; no seed field on Simulation or SimulationConfig. TODO.md:82 asks for 'reproducible simulation reports'.

**Why it matters.** Monte-Carlo iterations, debugging, 'replay iteration k in detail' and fair scenario comparisons (for example signals on vs off with the same random numbers) all need deterministic, independent random streams for each stage.

**Recommendation.** Add Simulation.seed (BigIntegerField, random default at creation) and SimulationRun.seed. Derive one numpy Generator per stage: `np.random.default_rng(np.random.SeedSequence([sim.seed, iteration, STAGE_ID]))`, so changing one stage's parameters does not shift another stage's draws. Pass the rng explicitly: generate_beta_score(..., rng) should call rng.beta(a, b) instead of scipy's global state.

**Verifier note (confirmed).** models.py:62 calls beta.rvs without random_state, and models.py:156, 221 and 242 use the global random.gauss. A grep finds no seed, random_state or default_rng anywhere in nrmps/ or NRMP_Simulated/. The proposed np.random.SeedSequence([sim.seed, iteration, STAGE_ID]) and rng.beta are valid numpy APIs.

<a id="stg-9"></a>

### STG-9: Simulation.iterations is editable in the UI but nothing uses it; there is no run table or aggregation

**Severity:** 🟠 high · **Kind:** gap · **Effort:** L · **Plan:** 6.1 · **Verification:** confirmed

**Evidence.** nrmps/models.py:95 (iterations 1-100); nrmps/forms.py:42; templates/nrmps/simulation_manage.html:36-37; templates/nrmps/simulations_list.html:31. grep finds no engine code reading iterations.

**Why it matters.** Users can set Iterations=100 and nothing happens, which misleads them. Monte-Carlo repetition is what makes outcomes meaningful: the chance that a given applicant matches, confidence intervals on match rate, and scenario comparisons for sliders.

**Recommendation.** Add SimulationRun (simulation, iteration, seed, status, config_snapshot, config_hash, metrics JSON, outcome_npz BinaryField, is_representative). Iteration 0 keeps full per-pair detail; iterations 1..N-1 run the in-memory engine and keep only MatchResult rows or a compact npz plus metrics. Add iteration_mode ('process' re-draws noise and behavior on a fixed population; 'population' also re-draws the population). Aggregate mean, SD, P5/P50/P95 and 95% CI for each metric, plus per-applicant P(match) and expected matched rank, and per-program P(fill). Full semantics in extra section 4.

**Verifier note (confirmed).** iterations is defined at models.py:95, exposed at forms.py:42 and shown in simulation_manage.html:36-37, simulations_list.html:31 and simulation_form.html:42-46. A grep shows no engine code reads it.

<a id="stg-10"></a>

### STG-10: Stages read the latest, mutable config, so editing the config between stages silently mixes parameters

**Severity:** 🟠 high · **Kind:** defect · **Effort:** S · **Plan:** 2.3 · **Verification:** confirmed

**Evidence.** nrmps/simulation_engine.py:49 and :80 and nrmps/models.py:118 and :200 all use `simulation.configs.order_by('-id').first()`. nrmps/views.py:119-121 edits that same config row in place (SimulationConfigForm(instance=config_instance)). Neither Student nor School records which config generated it.

**Why it matters.** A user can generate the population with one noise level, edit the config, then compute ratings with another, and nothing warns them. The results then match no single parameter set, so they cannot be reproduced.

**Recommendation.** When a run starts, freeze `config_snapshot = model_to_dict(cfg)` and a `config_hash` on SimulationRun, and have every stage read the snapshot. Record population_config_hash on Simulation when the population is generated. When the live config's hash differs, show a 'results are stale, re-run from stage X' banner. Alternatively, make configs append-only (a new row on each save) and link each run to its config_id.

**Verifier note (confirmed).** simulation_engine.py:49 and :80 and models.py:118 and :200 all read configs.order_by('-id').first(). views.py:121 binds SimulationConfigForm to that same instance, so the config is edited in place. Student and School have no config FK or hash. django.forms.models.model_to_dict exists for the snapshot.

<a id="stg-11"></a>

### STG-11: Pre-interview scoring fails on common inputs: uploaded populations have no preferences, and mismatched meta keys cause an HTTP 500

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 0.3 · **Verification:** confirmed

**Evidence.** nrmps/models.py:329-336 and :354-361: upload_students builds Student without meta_preference (same for schools at :427-433 and :462-468). probe1: after uploading, 'uploaded students' pre-scores: {0.0}', so every score ties and the ranking falls back to database order. probe1 key mismatch (students regenerated after editing applicant_meta_preference): 'Exception: Error computing pre-interview score for Student 1 - School 1', raised from simulation_engine.py:62-63 with `from None`, which hides the KeyError.

**Why it matters.** Any population uploaded by CSV produces meaningless rankings, and a routine config edit crashes the step. These are preconditions for every later stage.

**Recommendation.** Add a guard to the preferences stage, `validate_population(sim)`: require at least 1 student, at least 1 school, total capacity of at least 1, every student.meta_preference key present in every school.score_meta (and the reverse), and no empty preferences. Return a user-facing HTMX error instead of a 500. On upload, accept optional meta_preference columns, or generate preferences from the config. Always break ties with a seeded random 'lottery number' per agent (see STG-12).

**Verifier note (confirmed).** Reproduced in an isolated DB. Uploaded students get meta_preference {} (models.py:329-336, 354-361; schools likewise at 427-433 and 462-468). Every student-side observed score is 0.0, and ranks fall back to row order (U0 and U1 both School 1..4 = 1..4). The key mismatch reproduced as HTTP 500 through the Django test client: POST compute-pre-interview-all raised 'Exception: Error computing pre-interview score for Student 1 - School 1', and `from None` hides the KeyError. The root cause is cross-wired keys: Student.score_meta keys come from school_meta_preference and School.score_meta keys from applicant_meta_preference (models.py:129, 211).

<a id="stg-12"></a>

### STG-12: Rankings have no deterministic tie-break, but NRMP rank lists must be strict orders

**Severity:** ⚪ low (originally medium) · **Kind:** gap · **Effort:** S · **Plan:** 0.3 · **Verification:** partially

**Evidence.** nrmps/simulation_engine.py:112-119 and :135-142 sort only by `-score`. NRMP rank lists allow no ties and at most 300 ranks.

**Why it matters.** When scores tie (which always happens after a CSV upload, STG-11), rank order depends on database row order and can change between SQLite and Postgres. DA needs strict preferences for its applicant-optimality and stability guarantees, and for results to be reproducible.

**Recommendation.** Sort with a secondary key: `np.lexsort((lottery[j], -score))` where lottery comes from the stage's seeded rng. Persist ranks as consecutive integers 1..k. Add a validation that ranks are unique and consecutive for each agent.

**Verifier note (partially).** The claim holds: sorting is by -score only (simulation_engine.py:112-119, 135-142), and NRMP lists are strict with at most 300 ranks (confirmed). The severity is overstated. With continuous random draws ties essentially never occur: my 100x20 run had 0 tied score groups on either side. The only practical tie case is the missing-preferences upload, which STG-11 already covers. A seeded lexsort tie-break is a one-line part of the rank-list stage.

<a id="stg-13"></a>

### STG-13: No post-interview update stage (interview() is a stub, although the fields exist)

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** S · **Plan:** 3.4 · **Verification:** confirmed

**Evidence.** nrmps/simulation_engine.py:167-172; post-interview fields at nrmps/models.py:706-718 are never written; applicant/school_post_interview_rating_error (models.py:528-532, 574-578) are never read.

**Why it matters.** Interviews do two things: they reveal new information about fit (the true utility itself changes) and they reduce observation error. Both matter for how much the pre-interview and final rank lists differ, a key visualization. AAMC recommends virtual interviews while some surgical specialties are returning to in-person, so interview mode is a realistic option to model.

**Recommendation.** Stage S8: for each scheduled pair, draw shock ~ N(0, interview_shock_sd), set u_final = u + shock, and post = u_final + N(0, sigma_post * (virtual_error_mult if virtual else 1)). Optionally model no-shows with probability p_no_show. Set status to 'interviewed'. Config: interview_shock_sd (0.05), virtual_share (0.8), virtual_error_mult (1.2), p_no_show (0).

**Verifier note (confirmed).** The post-interview fields (models.py:706-718) are never written. applicant_post_interview_rating_error and school_post_interview_rating_error are only referenced in forms and templates, never in the engine. The proposed shock-plus-noise model is technically sound.

<a id="stg-14"></a>

### STG-14: Rules for building rank order lists are not defined (students_rank/schools_rank are stubs)

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** S · **Plan:** 3.5 · **Verification:** confirmed

**Evidence.** nrmps/simulation_engine.py:175-185. NRMP: rank lists contain only programs where the applicant interviewed (in practice), use strict order, have at most 300 ranks (20 are included in the fee, then $30 each), and should reflect true preference. Research cited in the NRMP context (PMC6948682, 'Misunderstanding the Match') shows some students do not rank by true preference.

**Why it matters.** Stage S9 has to decide which interviewed pairs get ranked (acceptability thresholds, programs' 'do not rank' cutoffs) and how, so that truthful and strategic behavior can be compared (matches IDEAS.md:12).

**Recommendation.** Stage S9, singles: ROL_i = interviewed programs with post_app >= acceptability_i, sorted descending, tie-broken, truncated to rol_max (300). Program ROL_j = interviewees above the do_not_rank percentile. Store the positions in students_post_rank_of_school / schools_post_rank_of_student, with null meaning not ranked. Strategy options: truthful (default), truncate_k, likelihood_weighted. Add a 'certified' flag; applicants with an empty rank list do not take part in the match (2026: 53,373 registered vs 48,050 certified).

**Verifier note (confirmed).** Stubs confirmed. Verified: the NRMP 300-rank maximum, 20 programs included in the fee with $30 per extra program code, 2026 registration of 53,373 vs 48,050 certified, and PMC6948682 (WestJEM 2020, 'Misunderstanding the Match: Do Students Create Rank Lists Based on True Preferences?').

<a id="stg-15"></a>

### STG-15: No checks that a match is valid, and no NRMP-style statistics

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 3.7 · **Verification:** confirmed

**Evidence.** There is no stability, capacity or optimality check anywhere (the repo has no match code; nrmps/tests.py is empty, F6). NRMP publishes: 2026 match rate, positions filled by the algorithm (93.5%, 41,482 of 44,344), 2,862 unfilled positions in 941 programs, 99.3% filled after SOAP, 73.5% of US MD seniors matched to a top-3 choice, and contiguous ranks for matched vs unmatched applicants. Prototype: 0 blocking pairs at every scale; applicant- vs program-proposing results differ for 0-4 of 2000 applicants, with the same matched set and the same fill per program (scratch/review/STG/pp_own.py).

**Why it matters.** A match implementation needs automatic proof that it is correct: no blocking pairs, capacities respected, applicant-optimal. The statistics are the dashboard's core KPIs and the calibration targets.

**Recommendation.** nrmps/engine/validate.py: blocking_pairs(), check_capacity(), check_rol_consistency(), and check_rural_hospitals() comparing against a program-proposing DA. nrmps/engine/metrics.py computes the metric list in extra section 5. pytest: property tests on random markets, and an oracle test against matching.games.HospitalResident (dev dependency only; small instances, see STG-19). Every run records blocking_pairs=0 in its metrics.

**Verifier note (confirmed).** No validation code exists. 2026 figures verified: 41,482 of 44,344 filled (93.5%), 2,862 unfilled positions in 941 programs, 99.3% overall fill after SOAP, US MD seniors 93.5% with 73.5% matched to a top-3 program. I reran pp_own.py: applicant- vs program-proposing outcomes differ for 3, 0, 0, 0 and 4 of 2000 applicants, with the same matched set and fill (consistent with the rural hospitals theorem), and 0 blocking pairs.

<a id="stg-16"></a>

### STG-16: The Match and Interview models cannot store per-run results, 'unmatched', SOAP rounds, couples or supplemental lists

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 2.3 · **Verification:** confirmed

**Evidence.** nrmps/models.py:727-745: Match has unique_together (student, school), no run FK, no round, no track, and no way to record an unmatched applicant. nrmps/models.py:720-721: Interview unique_together (student, school) prevents keeping rows for more than one run.

**Why it matters.** The existing tables can support the singles pipeline for one representative run, but not iterations, SOAP, couples or supplemental rank lists.

**Recommendation.** Add SimulationRun, MatchResult (run, student, school nullable, round main/soap, soap_round, student_rank, school_rank; UniqueConstraint(run, student, round)), Couple, CoupleRankEntry, and SupplementalRankEntry. Add a run FK to Interview with UniqueConstraint(run, student, school) and indexes on (run, student) and (run, school). Either drop the old Match table or migrate it into MatchResult. The support matrix is in extra section 6.

**Verifier note (confirmed).** Match (models.py:741-742) and Interview (models.py:720-721) both have unique_together (student, school) with no run FK. Match has no round or unmatched representation.

<a id="stg-17"></a>

### STG-17: SOAP (the post-Match placement process) is not modeled

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 8.1 · **Verification:** confirmed

**Evidence.** TODO.md:69-70 and IDEAS.md:66 list it as low priority. NRMP/AAMC 2026: SOAP ran Mar 16-19 with 4 offer rounds; applicants apply to at most 45 programs, have 2 hours to respond, and an accepted offer is binding; about 60% of positions fill in round 1 and about 80% by round 2. The NRMP May 2026 report says 2,632 of 2,851 SOAP positions filled (99.3% overall fill); the March release gave 2,581 positions offered.

**Why it matters.** SOAP is what takes the overall fill rate from 93.5% to 99.3%. Leaving it out overstates unfilled positions and cannot answer questions about what happens to unmatched applicants.

**Recommendation.** Stage S11 (pseudo-code in extra, S11): eligible applicants are the unmatched ones who certified a list; positions are those unfilled after the match. Each applicant applies to up to soap_max_apps programs by observed utility. Each program ranks its applicants by observed score. In each of soap_rounds rounds, programs make offers up to their open positions, and each applicant accepts their best offer with probability soap_accept_prob (binding) and declines the rest. Persist MatchResult(round='soap', soap_round=r). Suggest moving it up to Phase D (medium priority).

**Verifier note (confirmed).** Verified: SOAP ran Mar 16-19 2026 with 4 offer rounds and 2-hour response windows; the 45-program limit and binding acceptance; about 60% of positions fill in round 1 and about 80% by round 2 (NRMP SOAP data); 2,632 of 2,851 filled for 99.3% overall fill (May report); 2,581 offered (March release).

<a id="stg-18"></a>

### STG-18: Couples matching is not modeled; stable matchings may not exist, so the algorithm needs a Roth-Peranson-style procedure

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** L · **Plan:** 8.3 · **Verification:** confirmed

**Evidence.** TODO.md:71 and IDEAS.md:51, 71-76. 2026: 1,258 couples, 93% with at least one partner matched. Couples rank pairs of programs; if a couple does not match as a unit, NRMP does not process the partners' lists separately (NRMP 'Couples in the Match'). Prototype scratch/review/STG/proto_couples.py with 52 couples in 2000 applicants (5.2%): a stable matching found in 7/10 markets with one insertion order and 9/10 with up to 8 random restarts (couples_restart.py). The code with 0 couples reproduces plain DA exactly.

**Why it matters.** Couples make pairs of positions complements, so a stable matching may not exist. Kojima, Pathak and Roth (2013) show one exists with high probability when couples are few and rank lists short. NRMP uses the Roth-Peranson (1999) procedure: run DA for singles, add couples one at a time, repair instabilities, and detect cycles.

**Recommendation.** Phase E. Add Couple(run, a, b), CoupleRankEntry(couple, rank, school_a nullable, school_b nullable), and config couple_share and couple_rol_pairs_max (300). Algorithm in extra section 3.4: singles DA, insert couples in random order, a repair loop capped at R rounds, K random restarts, and if no stable matching is found, return the one with the fewest blocking pairs with a flag. Report couples' match rate separately.

**Verifier note (confirmed).** Verified 1,258 couples in 2026 with 93% having at least one partner matched. I reran proto_couples.py (7/10 stable) and couples_restart.py (9/10 stable with up to 8 restarts), and couples_check shows the 0-couple path equals plain DA. Kojima-Pathak-Roth (2013) and Roth-Peranson (1999) are cited correctly. Caveats: 'stable' is judged by the prototype's own blocking check, not an independent oracle. The prototype's couples both-matched rate (44-65%) shows its couples rank-list generator is uncalibrated.

<a id="stg-19"></a>

### STG-19: Write our own DA engine; use the 'matching' package only as a test oracle

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** S · **Plan:** 3.6 · **Verification:** confirmed

**Evidence.** PyPI: matching 1.4.3 (MIT, last release 2023-10-04) installs with numpy 2.5.3. HospitalResident gave the same resident-optimal result as the prototype DA on 20/20 instances of 400x40 (crosscheck.py). At 2000x200 it raises RecursionError inside copy.deepcopy (pp_compare.py). It has no couples, supplemental lists or reversions. The prototype DA takes 0.043 s at 10,000x1,000. There is also a small, unmaintained GitHub implementation, J-DM/Roth-Peranson.

**Why it matters.** The library does not scale to the config's own maximum and has none of the NRMP extensions. The core algorithm is short and easy to verify.

**Recommendation.** nrmps/engine/match.py: applicant_proposing_da(app_rol, prog_rank, cap), program_proposing_da(...) (the pre-1998 NRMP design, cheap to compare with; correct IDEAS.md:7 to add this before TTC/RSD), plus the couples, supplemental and reversion extensions. Add `matching` to the dev dependency group for oracle tests on small instances only.

**Verifier note (confirmed).** PyPI: matching 1.4.3, MIT, uploaded 2023-10-04, installed alongside numpy 2.5.3 in the reviewer's venv. I reran crosscheck.py: 0 of 20 instances differ from the resident-optimal result, and 10k x 1k DA took 0.035 s. I reran pp_compare.py: RecursionError in copy.deepcopy at 2000x200 reproduced. The program-proposing design was indeed the NRMP algorithm before 1998. I did not check the J-DM/Roth-Peranson repository.

<a id="stg-20"></a>

### STG-20: The engine runs as per-row ORM saves in a web request; stages need a vectorized engine and a background task

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 2.2 · **Verification:** confirmed

**Evidence.** probe1: all 4 pre-interview steps take 3.97 s for 960 pairs, about 1 ms per row per step, so the 10M-pair maximum would take roughly 2.8 hours per step (extends F4). Prototype numpy engine: all 11 stages at 10,000x1,000 in 8.5 s. Django 6.1.1 ships django.tasks with only the dummy and immediate backends (.venv/.../django/tasks/backends); django-tasks-db 0.13.0 (2026-08-28) provides an ORM-backed worker.

**Why it matters.** Adding more stages and N iterations on top of the current design will time out. The algorithms are cheap; the ORM round-trips are what is slow.

**Recommendation.** Each stage should load arrays once (Student and School indexes, then numpy matrices), compute in memory, and persist with bulk_create/bulk_update(batch_size=5000) only for the relevant sparse rows. Run the pipeline and iterations as a django.tasks task with the django-tasks-db backend, and poll progress with HTMX (hx-trigger='every 2s') from the StageRun rows.

**Verifier note (confirmed).** Measured 1.03-1.11 s per step for 960 pairs (about 1.1 ms per row), which extrapolates to about 3 h per step at 10M pairs. Django 6.1 django/tasks/backends contains only dummy.py and immediate.py. django-tasks-db 0.13.0 was uploaded 2026-08-28 and requires django>=5.2. The prototype full pipeline at 10k x 1k took 6.7-7.2 s (reviewer: 8.5 s). Omitted caveat: peak RSS was about 1.1 GB because the prototype holds dense float64 A x P matrices, so the in-memory design needs float32 or sparse storage, or a lower config maximum, on small containers.

<a id="stg-21"></a>

### STG-21: No applicant types or eligibility screening (IMG status, visa sponsorship, score cutoffs)

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 6.3 · **Verification:** confirmed

**Evidence.** IDEAS.md:57. NRMP 2026: foreign-born IMGs needing a visa had a 54.4% PGY-1 match rate, vs 67.9% for those who did not need one; US MD seniors 93.5%. All students in the model are of one kind (nrmps/models.py:593-620).

**Why it matters.** The biggest real gaps in match rate are between applicant types and come from hard screens (visa sponsorship, score cutoffs) at the invitation stage. These are policy questions users will want to study.

**Recommendation.** Add Student.applicant_type (US_MD, US_DO, US_IMG, NON_US_IMG), Student.needs_visa, School.sponsors_visa, and School.score_floor. S6 screening sets screen = -inf for ineligible pairs, and S4 lets applicants skip programs they know are ineligible (config aware_of_screens_p). Config gives the mix of applicant types and the score offset for each type. Report metrics by type.

**Verifier note (confirmed).** Verified the 2026 NRMP figures: foreign-born IMGs needing a visa matched at 54.4%, vs 67.9% for those not needing one; US MD seniors 93.5%. The Student and School models have no type, visa or eligibility fields.

<a id="stg-22"></a>

### STG-22: No program tracks, supplemental (PGY-1 + advanced) rank lists, reversions or partial matches

**Severity:** ⚪ low · **Kind:** gap · **Effort:** L · **Plan:** 8.4 · **Verification:** confirmed

**Evidence.** NRMP: an applicant who ranks an advanced program can attach a supplemental list of preliminary programs, which is used only if they match that advanced program. Reversions let a donor program's unfilled positions move to a receiver program during the match, approved by the Institutional Official before the ROL certification deadline. School (nrmps/models.py:623-655) has no track or reversion fields.

**Why it matters.** This matters for realistic multi-track markets (for example, a preliminary year plus an advanced specialty) and for the 'partially matched' group that is eligible for SOAP. Lower priority for a single-specialty simulator.

**Recommendation.** Phase E. Add School.track (C, P, A, R), School.reversion_to (FK to itself, nullable) and School.reversion_count, plus SupplementalRankEntry. Treat an applicant with a supplemental list as a couple-like joint request (advanced, prelim-or-none) and reuse the couples machinery. Handle reversions by re-running DA from scratch with the updated capacities until no more reversions trigger (extra section 3.5).

**Verifier note (confirmed).** NRMP reversion rules verified: unfilled donor positions are added to a receiver program's quota during the match, the Institutional Official must approve, and reversions must be finalized by the rank-order-list certification deadline. The supplemental-list semantics match NRMP. School has no track or reversion fields.

<a id="stg-23"></a>

### STG-23: Single-specialty market: no dual-specialty applications, so 'contiguous ranks' cannot be computed

**Severity:** ⚪ low · **Kind:** gap · **Effort:** L · **Plan:** 8.5 · **Verification:** confirmed

**Evidence.** AAMC ERAS 2025-26 averages (81.8 applications in total, 36 per specialty) imply about 2.3 specialties per applicant. NRMP Charting Outcomes reports contiguous ranks in the preferred specialty for matched vs unmatched applicants. IDEAS.md:53-57.

**Why it matters.** Backup-specialty strategies and competition across specialties are central to real outcomes, but they need a specialty dimension. For now, ROL length can stand in for 'contiguous ranks'.

**Recommendation.** Phase E: add School.specialty, Student.preferred_specialty and Student.backup_specialty, with applications and signals budgeted per specialty. In the meantime, report mean ROL length for matched vs unmatched applicants. The prototype shows the NRMP pattern: 9.5 vs 2.1.

**Verifier note (confirmed).** 81.8 / 36 is about 2.3 specialties per applicant (a reasonable inference). The prototype's ROL-length pattern reproduced: 9.51 for matched vs 2.06 for unmatched.

<a id="stg-24"></a>

### STG-24: Help texts for stage fields are wrong or swapped, and they feed the auto-generated documentation page

**Severity:** ⚪ low · **Kind:** defect · **Effort:** S · **Plan:** 1.6 · **Verification:** confirmed

**Evidence.** nrmps/models.py:531 (applicant_post_interview_rating_error help text says 'Pre-interview rating error stddev'); :688 (school_invited: 'Whether the school has been invited to the interview'); :694 and :697 (student_pre_observed... 'total score of student' and school_pre_observed... 'total score of school', swapped); :703-704 (students_pre_rank_of_school 'Pre interview rank of student', swapped); :572-578 (school pre and post error help texts identical). views.py:669-673 shows help_text on /documentation/.

**Why it matters.** The stage semantics shown to users are wrong on the only documentation page. This is minor but misleading when the new stages are added.

**Recommendation.** Rewrite the help texts as part of the stage migrations. For example, students_post_rank_of_school: 'Position of this program on the applicant's certified ROL (1 = most preferred; null = not ranked)'.

**Verifier note (confirmed).** All cited help texts are wrong as described; the line numbers are off by one at 693/696 (help_text lines). The live /documentation/ page renders 'Pre interview rank of student', 'Pre interview rank of school', 'Pre-interview rating error stddev' (twice) and 'Whether the school has been invited to the interview'. The post-interview fields (708, 711, 716, 718) have the same swaps.

<a id="stg-25"></a>

### STG-25: Model applicant self-assessment and the size of the applicant pool relative to positions

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** S · **Plan:** 2.1 · **Verification:** confirmed

**Evidence.** NRMP 2026: 48,050 active applicants for 44,344 positions (1.08 per position). Default config: 200 applicants for 10 schools of mean capacity 20 (1.0 per position); probe1 had 138 positions for 120 applicants. Capacity is drawn from a Gaussian (nrmps/models.py:221-224) and can be 0.

**Why it matters.** Market tightness is the most important driver of match rate. It should be an explicit, visible control rather than a side effect of three separate distributions.

**Recommendation.** Show the derived applicants-per-position ratio in the config UI, optionally as its own input (with capacity then derived). Draw capacity from a right-skewed distribution (lognormal or negative binomial, minimum 1). This also feeds the slider design in the visualization dimension.

**Verifier note (confirmed).** 48,050 certified applicants for 44,344 positions is 1.08 per position (verified). The defaults 200 / (10 x 20) give 1.0. Capacity comes from a truncated Gaussian that can be 0: my run had a 0-capacity school. The reviewer's own prototype runs at 2000 applicants for 1555 positions (1.29), so its metrics are not calibrated to 1.08.

<a id="ux"></a>

## UX: UI/UX review

> **Reviewer summary.** Pages render and the implemented steps work, but the UI makes a new user fail before they see any results. A new simulation has no config, so "(re)Create Students" does nothing and says nothing. Saving the untouched default config fails validation. HTMX actions show no spinner, never disable their buttons, show no success message and hide server errors. A 300x30 pre-interview computation took 38.6 s in one request, longer than gunicorn's default 30 s timeout. An unreadable CSV upload deleted the existing students and then returned a 500, with no message on screen. The manage page is one long page that mixes two separately saved forms with actions whose prerequisites are neither enforced nor shown. The simulation's stage is not shown anywhere, and panels go stale (after recreating students, the Interviews panel still said 9000 when the real count was 0). Templates still use daisyUI 4 class names (form-control, label-text, card-header, *-bordered, about 150 uses) that daisyUI 5.1 no longer has. This breaks form layout, lets error messages overlap each other, and adds to the mobile overflow. The overflow comes from three things: grid containers with no grid-cols-1, nowrap .label text, and header rows whose buttons cannot wrap. The meta-preference editor has a demonstrated stored XSS. In-context help is missing even though model help_text already exists for 17 fields. I recommend first fixing the defects above (S/M effort), then a workspace with a stepper (Setup, Population, Applications, Interviews, Rank lists, Match, Results) backed by background jobs, presets, "?" field help and a results dashboard.

<a id="ux-1"></a>

### UX-1: First-run path is broken: no config on create, silent no-op, and the default config fails validation

**Severity:** 🟠 high (originally critical) · **Kind:** defect · **Effort:** S · **Plan:** 0.2 · **Verification:** partially

**Evidence.** Checked live on my own scratch simulation (pk=3, since deleted). (1) Right after New Simulation, clicking '(re)Create Students' returns 200 and the count stays 0 with no message. Cause: Simulation.create_students returns 0 when no config exists (nrmps/models.py:118-121), and views.simulation_create (nrmps/views.py:79-90) never creates a SimulationConfig. (2) Clicking 'Save Configuration' without changing anything gives: 'School_meta_preference_stddev: * Ensure this value is less than or equal to 0.99. School_meta_scores_stddev: * Ensure ...'. The defaults are default=2 but the validators allow at most 0.99 (nrmps/models.py:560-567). (3) Other defaults make no sense for scores bounded to [0,1] by a beta distribution: applicant_score_stddev default=2 (models.py:499-500), school_score_mean default=0 (models.py:535-536), school_score_stddev default=2 (models.py:541). Screenshot: scratch/review/ux/default_config_errors.png

**Why it matters.** A new user's first three actions all fail, and the first one fails silently. This hits exactly the people the app needs to win over (students, researchers trying it out). It also means TODO.md's 'Add validation for empty populations' and 'Improve error messages' are live problems, not future work.

**Recommendation.** (a) In simulation_create, create a SimulationConfig in the same transaction, using the chosen preset or the defaults (see UX-21). (b) Fix the model defaults to valid, realistic values, for example applicant_score_stddev=0.1, school_score_mean=0.5, school_score_stddev=0.1, school_meta_preference_stddev=0.3, school_meta_scores_stddev=0.1, and add a migration. Add a unit test that SimulationConfigForm(data=model_to_dict(SimulationConfig())) is valid. (c) Redirect after create to the Setup step. Show a 'Next: generate population' call-to-action, and disable population buttons with a tooltip while no config exists.

**Verifier note (partially).** I reproduced every fact in an isolated DB (scratch/review/uxv/v1.py). simulation_create (views.py:79-90) creates no config, so configs=0 after create. POST create-students then returns 200 with count 0. SimulationConfigForm(data=model_to_dict(SimulationConfig())) is invalid, and only two fields fail: school_meta_preference_stddev and school_meta_scores_stddev (default 2, max 0.99, models.py:560-567). applicant_score_stddev=2 passes validation (max 99) but makes no sense, as the finding's point (3) says. Severity: I lowered it to high. Nothing crashes or loses data, and the save error names the fields and the limit, so a user can recover by editing two fields. It remains a serious first-run blocker and belongs in phase 0.

<a id="ux-2"></a>

### UX-2: HTMX actions give no feedback: no spinner, buttons stay enabled, no success message, errors hidden

**Severity:** 🟠 high (originally critical) · **Kind:** defect · **Effort:** M · **Plan:** 1.5 · **Verification:** partially

**Evidence.** grep finds no hx-indicator, hx-disabled-elt, htmx-indicator, htmx:responseError or HX-Trigger in templates/ or theme/templates/. Checked live during '(re)Create Students': button.disabled=false and no loading element was present. A garbage CSV upload returned 500 (POST /simulations/3/upload-students/) and the page showed nothing; only the console logged 'Response Status Error Code 500'. django.contrib.messages is installed (NRMP_Simulated/settings.py:62,87,108), but base.html (theme/templates/base.html:67-71) never renders messages, and no view calls messages.*. A config save redirects with no confirmation (checked: no .alert-success or .toast element).

**Why it matters.** Users can't tell whether a click did anything. They double-submit destructive or long operations, and failures look like successes. htmx 2.0.6 (static/js/htmx.mini.js) does not swap 4xx/5xx responses by default, so every server error is invisible.

**Recommendation.** In theme/templates/base.html add a fixed toast region `<div id="toasts" class="toast toast-end toast-top z-50">`. Render `{% for m in messages %}<div class="alert alert-{{ m.tags }}">` into it, and add a small Alpine/JS listener for a custom 'toast' event. In views, use django_htmx.http.trigger_client_event(resp, 'toast', {'level':'success','text':'Created 300 students'}). On every hx-post button add hx-disabled-elt="this" and an inline `<span class="loading loading-spinner loading-xs htmx-indicator">`. Add a global `document.body.addEventListener('htmx:responseError', ...)` and 'htmx:sendError' handlers that raise an error toast. In DEBUG, add `{% django_htmx_script %}` so HTMX 500s show the Django debug page.

**Verifier note (partially).** Every fact checks out. grep finds no hx-indicator, hx-disabled-elt, htmx-indicator, responseError or HX-Trigger anywhere in templates or views. No view calls messages.*, and base.html never renders messages. htmx is 2.0.6, and its default responseHandling sets {code:'[45]..', swap:false, error:true}. django_htmx_script does inject the debug error handler, but only in DEBUG (django_htmx/jinja.py). htmx:confirm's detail.issueRequest(skip) exists. Severity: high, not critical. The real damage happens only together with UX-4 (the upload that deletes data) and the missed compute 500s. Also note that django-htmx 1.29's {% htmx_script %} can replace the hand-vendored static/js/htmx.mini.js and adds the debug script automatically.

<a id="ux-3"></a>

### UX-3: Long synchronous steps run with no progress and will exceed the production timeout

**Severity:** 🔴 critical · **Kind:** defect · **Effort:** L · **Plan:** 2.5 · **Verification:** partially

**Evidence.** Checked live: 300 students x 30 schools, 'Compute Pre-Interview Scores and Rankings' took 38,637 ms in a single request, and 'Initialize Interviews' took 1,028 ms. The UI showed nothing the whole time. entrypoint.sh:27 starts gunicorn with no --timeout (default 30 s), so the worker would be killed and the user gets a dropped request. Config allows 10000x1000 (nrmps/models.py number_of_applicants/number_of_schools validators; F4).

**Why it matters.** Even medium-sized realistic markets can't finish inside one request. The planned steps (interviews, rank lists, match, iterations>1) will make this worse. 'Run all remaining steps' cannot be built without background execution.

**Recommendation.** Add a SimulationJob model (simulation FK, kind, status queued/running/done/failed, progress 0-100, current_step, message, started/finished). Run steps with Django 6's django.tasks API (@task) on the django-tasks package's DatabaseBackend plus a `manage.py db_worker` process (Railway/Procfile worker). Django 6 ships only the dummy and immediate backends (.venv/.../django/tasks/backends). Action buttons POST and get back a job partial that polls with hx-get=/simulations/<pk>/jobs/<id>/ hx-trigger="every 1s". It shows a daisyUI `<progress class="progress progress-primary" value=..>` with the step name and a Cancel button, stops polling with HX-Trigger/HTTP 286, and raises a toast when done. Pair this with engine bulk_update work (ENG dimension) so jobs run in seconds, not minutes.

**Depends on.** UX-2

**Verifier note (partially).** Timing reproduced. In an isolated sqlite DB, 300x30 initialize took 0.87 s and compute-pre-interview-all took 52.4 s (the reviewer measured 38.6 s). entrypoint.sh:27 runs gunicorn with no --timeout, and gunicorn 26.2's default is 30 s (config.py Timeout default=30). Django 6.1.1 ships only the dummy and immediate backends. One library detail is outdated: django-tasks 0.12.0 (current on PyPI) no longer includes the DatabaseBackend. It now lives in the separate django-tasks-db package (INSTALLED_APPS 'django_tasks_db', BACKEND 'django_tasks_db.DatabaseBackend', command `manage.py db_worker`), and on Django 6 you don't need the django-tasks backport at all. The time goes almost entirely to per-row .save() (simulation_engine.py:66 and similar lines), so the ENG bulk_update fix would bring 300x30 down to about a second. Background jobs are still needed for large markets and 'run all'. The steps also run without transaction.atomic, so a gunicorn kill mid-step leaves interviews half-rated.

<a id="ux-4"></a>

### UX-4: CSV upload silently coerces bad data and deletes existing data before a failed parse

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 0.6 · **Verification:** confirmed

**Evidence.** Live check on the scratch simulation. Uploading bad.csv (rows 'Alice,abc' / ',0.5' / 'Bob,1.7') returned 200 and created 3 students with no warning: 'abc' became 0.0, the blank name became 'Student 2', and 1.7 (outside [0,1]) was accepted (nrmps/models.py:309-345). Uploading 2 KB of random bytes returned 500. The panel still said 'Count: 3', but after a reload the list read 'No students found.' The cause: self.students.all().delete() runs before parsing (models.py:297), with no transaction.atomic. The view writes the upload to a fixed path, data/simulation_<id>_students.csv (nrmps/views.py:253-259). The download CSV omits meta_preference (views.py:293-296), so download followed by upload loses preferences.

**Why it matters.** Users lose data with no warning, and a bad upload looks like it worked. There is no way to see what was imported or rejected. The upload form's help_text (forms.py:60,74) is never shown, so users don't know the format.

**Recommendation.** Move parsing into StudentsUploadForm/SchoolsUploadForm.clean_file(): decode utf-8-sig, check headers, and validate each row (score 0-1, capacity >=1, score_meta is a JSON object) into a list of errors with row numbers. Show the result in a daisyUI modal (`<dialog class="modal">`): 'N valid rows, M errors', the first 20 errors in a table, and a preview of 5 rows, with Confirm replace / Cancel buttons. Perform the replace inside transaction.atomic() and add no rows at all if any row is invalid (optionally offer 'skip invalid rows'). Tell the user that downstream interviews and matches will be deleted, with counts. Add 'Download template CSV' links, include meta_preference in downloads, and never write to a shared data/ path (parse the in-memory file). Matches TODO.md 'Add data validation feedback' / 'input sanitization for CSV uploads'.

**Depends on.** UX-2

**Verifier note (confirmed).** Reproduced (uxv/v2.py). With the reviewer's bad.csv, the upload returned 200 and stored [('Alice',0.0),('Student 2',0.5),('Bob',1.7)]. 2 KB of random bytes gave a 500 (UnicodeDecodeError), and students then numbered 0. The delete sits at models.py:298 (the finding says 297), before parsing, with no atomic block. The view writes data/simulation_<id>_students.csv (views.py:253-259), and that file stays on disk after the failure. The download omits meta_preference (views.py:293-296); the upload format has no meta_preference column either, so a round trip does lose preferences. The upload form's help_text is never shown because the partial hand-writes the <input type=file> and ignores students_upload_form. Everything matches TODO.md 'Add data validation feedback'.

<a id="ux-5"></a>

### UX-5: Panels go stale after cascades, and config changes never mark results out of date

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 1.5 · **Verification:** confirmed

**Evidence.** Live: after computing interviews (9000), clicking '(re)Create Students' swapped only #population-counts. The Interviews panel kept saying 'Count: 9000', but after a reload it said 'Count: 0', because Interview.student is on_delete=CASCADE (nrmps/models.py:667). The confirm text (templates/nrmps/partials/_population_counts.html:18) says only 'This will replace existing students', not that interviews and matches go too. The config form updates the latest config in place (nrmps/views.py:117-156), and the page doesn't show whether the population was generated from the current config.

**Why it matters.** Users make decisions based on counts and results that are no longer true. In a multi-step pipeline, every upstream change has to visibly invalidate everything downstream.

**Recommendation.** (1) Every mutating view returns HX-Trigger: simulation-changed (django_htmx trigger_client_event). Each panel and the stepper refresh themselves with hx-get=<panel-url> hx-trigger="simulation-changed from:body", or the views return hx-swap-oob fragments for the stepper and all counts. (2) Confirm dialogs list downstream deletions with real counts ('Deletes 300 students, 9000 interviews, 0 matches'). (3) Store config_snapshot/config_hash on Simulation at population generation and at each step. Show a warning badge 'Out of date: config changed after population was generated' in the stepper, with a 'Re-run from here' action.

**Depends on.** UX-6

**Verifier note (confirmed).** Reproduced. After computing 9000 interviews, POST create-students returned only the #population-counts partial: no interview-counts markup, no hx-swap-oob, no HX-Trigger header. The DB then held 0 interviews because of the CASCADE at models.py:667. The confirm text at _population_counts.html:18 mentions only students. The config form edits the latest config in place (views.py:119-121). The recommendation (HX-Trigger events plus a config hash on the simulation) can be built with django_htmx.http.trigger_client_event.

<a id="ux-6"></a>

### UX-6: No visible stage, and prerequisites are neither enforced nor explained

**Severity:** 🟠 high · **Kind:** gap · **Effort:** M · **Plan:** 2.4 · **Verification:** confirmed

**Evidence.** Simulation.status (nrmps/models.py:97) is never updated or shown, and Interview.status stays 'initialized' (F5). Every action button is always enabled: on the empty simulation 2, 'Compute Pre-Interview Scores and Rankings' and '(re)Initialize Interviews' are active with 0 students and 0 interviews (templates/nrmps/partials/_interview_counts.html:14-27; screenshot desktop_sim_manage_empty.png). Per-step endpoints exist (nrmps/urls.py:43-46, students-rate/schools-rate/compute-*-rankings) but nothing in the UI reaches them. No 'what next' guidance anywhere.

**Why it matters.** Users can't tell where they are in the 8-step pipeline in CLAUDE.md, or what the next step is. Clicking out of order does nothing and gives no explanation. This matches TODO.md 'Add progress indicators for simulation stages / step-by-step wizard / status dashboard'.

**Recommendation.** Add nrmps/services/pipeline.py with get_pipeline(sim) -> list[StepState(key,label,url,state in {done,current,todo,blocked,stale},summary,blocked_reason)]. Compute the states from the data (config exists; students/schools counts; interviews count; pre-scores non-null; invitations; interviews done; rank lists; matches) and cache them on Simulation.stage. Render templates/nrmps/partials/_stepper.html with daisyUI `<ul class="steps steps-vertical lg:steps-horizontal">` and `<li class="step step-primary" data-content="✓">`. Each step links to its tab. Disable action buttons whose step is blocked, and wrap them in `<div class="tooltip" data-tip="Generate students and schools first">`. Add a primary 'Next: …' button and a 'Run all remaining steps' button (enqueues a job, UX-3). Expose the sub-steps (students rate, schools rate, rank) under an 'Advanced: run individually' collapse.

**Verifier note (confirmed).** Simulation.status (models.py:97) is only ever the default. grep shows no writes, and no template shows it. The per-step endpoints (urls.py:43-46) are referenced by no template (grep finds none). The interview buttons at _interview_counts.html:14-27 are always enabled. daisyUI 5.1.12 has steps, steps-vertical and tooltip, so the recommended markup is valid. This matches TODO.md 'progress indicators / wizard / status dashboard'.

<a id="ux-7"></a>

### UX-7: Replace the single manage page with a tabbed simulation workspace

**Severity:** 🟠 high · **Kind:** recommendation · **Effort:** L · **Plan:** 4.1 · **Verification:** confirmed

**Evidence.** templates/nrmps/simulation_manage.html is 360 lines. It holds two separate `<form>`s, each with its own Save (lines 19-50 and 52-316), so saving one throws away unsaved edits in the other and nothing warns about it. A 20-field config form sits next to population and interview actions. On mobile, every action comes after about 1,500 px of config fields (mobile_sim_manage.png). Card titles sit outside card-body (card-header is not a daisyUI class, lines 22,55), and the Save buttons sit flush against the card edge because card-actions is outside card-body (lines 47,313).

**Why it matters.** Setup, running and analysis are different jobs and belong on different screens. The current single page can't hold the missing steps (invitations, interviews, rank lists, match, results) without getting much worse.

**Recommendation.** Routes under /simulations/<pk>/: overview (redirects to the current step), setup/, population/, applications/, interviews/, rank-lists/, match/, results/, runs/ (history and compare), plus students/<id>/ and schools/<id>/ detail pages. Shared layout template templates/nrmps/workspace_base.html contains: a breadcrumbs header (daisyUI `breadcrumbs`) with name, stage badge, Run all, Duplicate, and a ⋯ dropdown with Delete; the stepper (UX-6) as `tabs tabs-border` on desktop and a horizontally scrollable steps row on mobile; a content block; and a sticky job/progress bar. Each tab has one clear primary action, KPI `stats` for that step, a 'What happens in this step?' collapse and a table. Name/description go in a small 'Edit details' modal. See the wireframe in extra.

**Depends on.** UX-6, UX-2

**Verifier note (confirmed).** simulation_manage.html is 360 lines. It has two separate forms (19-50 and 52-316), each posting a single form_id, so saving one drops unsaved edits in the other. card-header (lines 22 and 55) doesn't exist in daisyUI 5, and card-actions (47 and 313) sits outside card-body, which default_config_errors.png shows. On mobile the gap is bigger than stated: at 390 px the first config field is at y=745 and #population-counts starts at y=2754, so roughly 2,000 px of fields come before any action (the finding says about 1,500 px). The tabbed-workspace recommendation holds up.

<a id="ux-8"></a>

### UX-8: daisyUI 4 class names are dead in daisyUI 5.1 and break forms and layout

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 1.4 · **Verification:** partially

**Evidence.** I scanned the class tokens in templates and checked each against theme/static/css/dist/styles.css (script: scratch/review/ux/deadclasses.py). These have no rule: form-control, label-text, label-text-alt, card-header, input-bordered, select-bordered, textarea-bordered, file-input-bordered, menu-item, text-muted (a Bootstrap class), and hover on `<tr>` (daisyUI 5 uses row-hover; simulations_list.html:25, documentation.html:207). None exist in theme/static_src/node_modules/daisyui/components/*.css (v5.1.12). There are about 150 uses: simulation_manage.html 75, signup 20, simulation_form 15, login 8, forms.py widgets 25. Visible effects: daisyUI 5's .label is inline-flex with white-space:nowrap. So on /simulations/new/ the 'Description' label sits beside the textarea (desktop_sim_new.png); error messages under adjacent fields overlap each other (default_config_errors.png, 'Ensure this value…0.99' on top of the next field); and help text overflows on mobile. documentation.html:297,309-310 uses daisyUI 4 variables oklch(var(--b2))/--bc; the CSS has no --b2 (grep count 0), so those declarations are invalid.

**Why it matters.** The dependency bump (F1) gave the old markup new CSS, and the forms now depend on accidental layout. Every new form copies the broken pattern.

**Recommendation.** Create one include, templates/nrmps/partials/_field.html (or a django `{% field %}` inclusion tag). It renders `<fieldset class="fieldset"><legend class="fieldset-legend">{{ label }} {% help_icon %}</legend>{{ widget }}<p class="label" id="{{ id }}_helptext">{{ help_text }} (range)</p><p class="text-error text-sm">{{ errors }}</p></fieldset>`, and adds `input-error` to invalid widgets. Remove every *-bordered class (borders are the default in v5) from templates and forms.py. Replace card-header with a card-title inside card-body, and move card-actions inside card-body. Use var(--color-base-200) in documentation.html. Add a CI check that fails when templates use class tokens missing from the built CSS (port deadclasses.py).

**Verifier note (partially).** The core defect holds. form-control, label-text, label-text-alt, card-header, the *-bordered classes and menu-item have no rules in the built styles.css or in daisyui 5.1.12's components/*.css. tr.hover is dead; daisyUI 5 uses tr.row-hover. My count is 161 uses (manage 75, forms.py 25, signup 20, simulation_form 15, login 8, others 18). Computed .label style is inline-flex and nowrap, and the overlapping error messages show in the screenshot. Two details are wrong. (1) Cause: the F1 bump did not bring in new CSS. Commit 01b1eb5 touched only pyproject.toml and uv.lock, and theme/static_src/package.json (daisyui ^5.0.43) and package-lock.json (daisyui 5.1.12) have been committed unchanged since 6623367 (2025-09-24). The daisyUI 4 markup has been dead under daisyUI 5 from the start. (2) The documentation.html line numbers are wrong because that file has 155 lines: tr.hover is at :50, the badge td at :52, and oklch(var(--b2)) / --bc at :140 and :152-153 (not 207 and 297/309-310). The recommendation is sound: fieldset, fieldset-legend and p.label are the daisyUI 5 pattern, and var(--color-base-200) is correct. Tailwind v4 emits only the classes it sees used, so the 'class missing from built CSS' CI check works.

<a id="ux-9"></a>

### UX-9: Mobile horizontal overflow and header overlap: four root causes identified

**Severity:** 🟠 high · **Kind:** defect · **Effort:** S · **Plan:** 1.4 · **Verification:** confirmed

**Evidence.** Playwright at 390 px wide: scrollWidth is 452 on /simulations/1/ and /2/, 475 on /simulations/1/interviews/, and 678 on /documentation/. Causes: (a) `.grid lg:grid-cols-2` (simulation_manage.html:17) and `.grid gap-6` (documentation.html:13) have no base grid-cols-1, so the implicit track takes the content's min width (435.6 px); (b) the nowrap `.label` help text 'Enter as tags; press Enter…' (simulation_manage.html:195,306); (c) `flex justify-between` headers with button groups that can't wrap push 'Download CSV' and 'Delete Simulation' off screen (interviews_list.html:5-10, simulation_manage.html:5-15); (d) documentation's hero h1 text-5xl 'API Documentation' is 414 px wide. Injecting `.grid{grid-template-columns:minmax(0,1fr)} .flex.justify-between{flex-wrap:wrap}` brought interviews down to 390 and manage to 428 (the rest is the nowrap label). In the navbar, the brand text overlaps the Login/Logout buttons by 115 px (base.html:34-37; mobile_home.png, mobile_login.png).

**Why it matters.** Every workspace page is broken on phones, and the app will likely be shown on phones and projectors in teaching settings.

**Recommendation.** Use `grid grid-cols-1 lg:grid-cols-2` and add min-w-0 on grid children. Headers get `flex flex-wrap gap-2 justify-between items-center`. Help text uses `whitespace-normal`, or the _field.html include from UX-8. Brand: `<span class="hidden sm:inline">NRMP Simulations</span>`, and move Login/Sign-up into the dropdown below sm. Docs h1: `text-3xl md:text-5xl`, and remove the nested `container mx-auto px-4` (documentation.html:6), since main already sets it. Wide tables: keep overflow-x-auto, use `table-pin-cols`, and hide low-value columns with `hidden md:table-cell`. Add a Playwright regression check that asserts scrollWidth <= clientWidth at 390 px for every page.

**Verifier note (confirmed).** Reproduced with Playwright at 390 px. scrollWidth was 452 on /simulations/1/ and /2/, 475 on /simulations/1/interviews/ and 678 on /documentation/. Injecting a .grid minmax(0,1fr) rule and flex-wrap gave 428 on manage and 390 on interviews; also setting .label{white-space:normal} brought manage to 390. Documentation stays at 478 after those fixes, which fits the text-5xl h1 cause. The navbar brand overlaps the navbar-end buttons by 115 px when logged out and about 40 px when logged in. Minor citation error: the documentation grid is at documentation.html:17, not :13. The nested container at :6 is correct.

<a id="ux-10"></a>

### UX-10: Meta-preference editor: stored XSS, plus data loss when JavaScript is off

**Severity:** 🟡 medium (originally high) · **Kind:** defect · **Effort:** S · **Plan:** 0.5 · **Verification:** partially

**Evidence.** simulation_manage.html:172,283 put `{{ config_form.instance.applicant_meta_preference|default:'[]'|safe }}` (a Python repr) inside a double-quoted x-data attribute. Lines 194,305 put the same repr inside a single-quoted value='…' attribute, which renders as value='['program_size', 'reputation', 'location']' (broken). Demonstrated on my own scratch simulation: POSTing applicant_meta_preference=["ok","x\"><img src=x onerror=alert(document.domain)>"] made the page run alert('127.0.0.1') on the next load. If Alpine doesn't run, the broken hidden value is posted, json.loads fails, and clean_*_meta_preference returns [] (nrmps/forms.py:105-107), silently wiping preferences.

**Why it matters.** This is a security defect on a page that will be shared once 'public' simulations exist. The editor also stores whatever the server accepts, because normalization happens only in the browser.

**Recommendation.** Pass the initial values with `{{ config_form.instance.applicant_meta_preference|json_script:"applicant-meta-init" }}` and read them in Alpine via JSON.parse(document.getElementById(...).textContent). Remove |safe entirely. Let Alpine own the hidden input's value, and render the server fallback as `value="{{ value_json }}"` with value_json made by json.dumps in the view (auto-escaped). Validate on the server: a list of at most 20 unique slugs matching ^[a-z0-9_-]{1,40}$, and raise ValidationError instead of silently returning [].

**Verifier note (partially).** The injection is real. I saved applicant_meta_preference=["ok","x\"><img src=x onerror=...>"], and the manage page rendered x-data="metaEditor(..., ['ok', 'x"><img src=x onerror=alert(document.domain)>'])" unescaped (lines 172 and 283 use |safe on a Python repr). The hidden input renders value='['board_scores', 'research', 'honors']' (lines 194 and 305), which is broken, so without Alpine json.loads fails and clean_* silently returns [] (forms.py:105-107). Severity is overstated for today. Only the owner can render this page (views.py:98 ownership check), nrmps/admin.py registers nothing, no public or shared view exists, and all POSTs are CSRF-protected. So right now it is a stored self-XSS, not something one user can use against another. It becomes high once public sharing or admin display ships. The fix (json_script plus server-side slug validation) is correct and cheap.

<a id="ux-11"></a>

### UX-11: No in-context help: model help_text exists for 17 fields but is never shown

**Severity:** 🟠 high · **Kind:** gap · **Effort:** M · **Plan:** 4.3 · **Verification:** confirmed

**Evidence.** The rendered manage page has 17 aria-describedby="id_*_helptext" attributes (Django adds them because the model sets help_text) and 0 elements with those ids (scratch/review/ux/manage1.html), so every one points nowhere. No template renders {{ field.help_text }}. Some help texts are wrong: applicant_post_interview_rating_error says 'Pre-interview rating error stddev' (nrmps/models.py:531); school_interview_limit is a 0-0.99 fraction 'In percent of capacity' but is labelled 'School Interview Limit' (models.py:551-555). Labels are jargon ('Applicant Meta Preference StdDev') with no units or valid ranges. Number inputs lack max even though validators have one (number_of_applicants renders min=0 but the model minimum is 1). applicant_interview_limit is an IntegerField but its widget has step='any' (forms.py:167). The error summary shows raw field names ('School_meta_preference_stddev: * Ensure…', simulation_manage.html:69-72).

**Why it matters.** The model has at least 20 parameters whose meaning (beta-distribution means and SDs, rating error, meta preferences cross-wired between applicants and schools) is hard to guess. The user explicitly asked for '?' help on pages and fields.

**Recommendation.** Create nrmps/help_content.py: FIELD_HELP = {field: {label, short, long_md, range, unit, example, affects: [steps]}} and STEP_HELP. Make it the single source for tooltips, the /help/ glossary and the form labels (set in SimulationConfigForm.__init__). In _field.html: a `<button type="button" class="btn btn-circle btn-ghost btn-xs" popovertarget="help-{{id}}" aria-label="Help: {{label}}">?</button>` that opens a native popover card (it works on touch, unlike hover-only daisyUI tooltip), plus a desktop `tooltip` with `.tooltip-content` for short text. Add a hint line with id={{id}}_helptext so aria-describedby resolves ('0–0.99 · typical 0.1'). Set min/max/step from the validators. Build the error summary from field.label and link each item to #id_field. Add a 'What happens in this step?' `collapse` at the top of each workspace tab that links to /help/#step-x.

**Depends on.** UX-8

**Verifier note (confirmed).** Rendered manage page: 17 aria-describedby attributes and 0 matching ids. The model actually defines help_text on 19 of the 20 config fields; school_meta_preference_stddev has none, and the two meta-preference fields are hand-written hidden inputs, which is why only 17 are wired. The help texts the finding calls wrong are wrong (models.py:531 says 'Pre-interview' on the post-interview field; models.py:551-555 describes a 0-0.99 fraction as 'In percent of capacity'). Rendered inputs have no max; number_of_applicants has min=0 while the model minimum is 1 (forms.py:163), and applicant_interview_limit has step='any' (forms.py:167). The error summary prints raw field names (manage.html:69-72). The popover and tooltip-content recommendation works: the Popover API is baseline, and tooltip-content exists in daisyUI 5.1.

<a id="ux-12"></a>

### UX-12: The 'Documentation' page is a developer API dump, not user help

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 1.10, 4.4 · **Verification:** partially

**Evidence.** views.documentation (nrmps/views.py:557-705) introspects models and prints every field and method, including User internals such as password, is_superuser, check_password(), set_password() and get_all_permissions(), to anonymous users. The desktop page is 8,958 px tall (desktop_documentation.png) and has emoji headings (documentation.html:167,179,250). `<td class="badge badge-outline">` (line 209) turns table cells into inline-flex badges and breaks the table layout. There is no table of contents, no search, and no workflow, concept or CSV-format guidance.

**Why it matters.** There is no page a user can read to learn what the simulation does or how to interpret results. TODO.md 'User documentation' (user guide, CSV formats, troubleshooting) has not been started.

**Recommendation.** Add /help/ (templates/nrmps/help/index.html plus section partials). Sections: Getting started (5-minute walkthrough), How the NRMP works (rank order lists, applicant-proposing deferred acceptance, stability), each pipeline step (inputs, outputs, parameters, typical values), a parameter glossary rendered from FIELD_HELP (UX-11), CSV formats with downloadable templates, how to read the results charts, and FAQ/troubleshooting. Layout: daisyUI `drawer` or sticky `menu` TOC on the left, anchored sections, and a client-side filter box. Move the current page to /help/reference/, restrict it to staff or at least exclude User, and wrap badges in the cell (`<td><span class="badge">`). In the navbar, rename 'Documentation' to 'Help'. Add a first-visit dismissible 'New here? Take the tour' alert on the workspace.

**Depends on.** UX-11

**Verifier note (partially).** The substance holds. views.documentation (views.py:557-705) has no login_required, and excluded_models lists only 'AbstractUser', so the concrete User model with password, is_superuser, set_password and the rest is listed to anonymous users. I fetched it anonymously and got 7 hits. The desktop screenshot is 8958 px tall. Note that this is schema metadata only, not data exposure. The template line numbers are wrong (the file has 155 lines): emoji headings are at documentation.html:10 and :22, the badge td at :52, tr.hover at :50 (not 167/179/250/209). This matches TODO.md 'User documentation' (still open).

<a id="ux-13"></a>

### UX-13: Table data is hard to read: 16-digit floats, raw Python dicts, redundant columns, natural-sort errors

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 1.5 · **Verification:** partially

**Evidence.** interviews_list.html:119-120, students_list.html:214 and schools_list.html:79 print raw floats such as 0.0393147159004004 (desktop_interviews.png). Students and schools show Score Meta and Meta Preference as Python dict reprs ({'board_scores': 0.36013893065432195, …}) (students_list.html:216,218; desktop_schools.png). The 'Simulation ID' column is constant (students_list.html:203). 'Pref Stddev' is constant across the population. Name sort is lexicographic: Student 1, Student 10, Student 100, Student 101 (desktop_students.png; views.py:326 default sort=name). The mobile students page is 13,033 px tall (mobile_students.png). Interview.status is always 'initialized', and all observed scores are about 0.03-0.08 (F5). The interviews table does not show true scores, so observation error can't be seen.

**Why it matters.** Users can't scan or compare values, and results look meaningless. Much of the space is wasted on long reprs.

**Recommendation.** Add a template filter in nrmps/templatetags (num: 3 significant decimals, tabular-nums font-mono, class text-right). Show meta values as one column per key with 2-decimal formatting and an optional background heat scale (inline style from value). Drop the Simulation ID and constant columns and show them once in a summary `stats` row above the table. Add an integer `index` to Student/School (or sort by id) for natural ordering. On Interviews, add True vs Observed score columns with a delta, and show status as a `badge`. Hide meta columns below md.

**Verifier note (partially).** Content confirmed. Raw floats print at interviews_list.html:119-120 and schools_list.html:79. Dict reprs print. Name sort is lexicographic: I got Student 1, 10, 100, 101, 102 in an isolated DB. Pref Stddev is the constant config stddev. The students_list.html line citations don't exist, since the file has 96 lines: score is at :68, Simulation ID at :69, score_meta at :70, meta_preference at :72 (not 214/203/216/218). The mobile students page is 13033 px tall (measured).

<a id="ux-14"></a>

### UX-14: Tables have no filtering, sticky headers, total counts or drill-down, and the sort code is copy-pasted

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 1.8, 4.1 · **Verification:** confirmed

**Evidence.** The three list views (nrmps/views.py:317-519) support only sort and page_size, and page_size has no upper bound (?page_size=10000000 loads everything; views.py:337-342). Pagination is Previous / 'Page 1 of 10' (a disabled button) / Next, with no first/last and no 'showing 1-100 of 960' (interviews_list.html:131-145). The sortable `<th>` block is repeated 8 times in interviews_list.html:30-109 and again in students and schools, with no aria-sort. Rows don't link to a student or school, and no detail pages exist. The rows-per-page select only submits via onchange JavaScript.

**Why it matters.** With 960 to 10M interview rows, users need to answer questions like 'show School 3's applicants ranked by observed score' or 'where did Student 12 interview?', and they can't. TODO.md lists 'Add search and filtering to paginated views'.

**Recommendation.** Add templates/nrmps/partials/_sort_th.html (or a `{% sort_th 'score' 'Score' %}` inclusion tag) that emits aria-sort and preserves every other query param via a querystring helper. Django 6's {% querystring %} tag can do this. Add a filter bar (GET form, hx-get with hx-target=#table-body, hx-push-url=true, hx-trigger='input changed delay:300ms'): student name, school select, status, rank range, only-applied/invited/matched. Use daisyUI `table table-zebra table-pin-rows table-sm` in a max-h-[70vh] overflow-auto container for sticky headers, and numbered pagination with a 'Showing a-b of N' label. Clamp page_size to [10, 500]. New pages /simulations/<pk>/students/<id>/ and /schools/<id>/ show the entity's attributes, its ranked list of schools/students (pre and post interview), interview status, and match outcome. Link names in every table to them.

**Verifier note (confirmed).** The list views support only sort and page_size, and page_size has no upper clamp: ?page_size=100000000 returned 200 (views.py:337-342, 379-384, 499-504). interviews_list.html has 8 hand-written sortable <th> blocks (lines 30-100), with no aria-sort. The page indicator is a btn-disabled button (line 138). The page-size select submits via onchange (line 18). No detail pages or links exist. Django's {% querystring %} tag has existed since 5.1 and is available in 6.1.1. This matches TODO.md 'Add search and filtering to paginated views'.

<a id="ux-15"></a>

### UX-15: Auth and account problems: wrong-password message missing, password change dead-ends in admin

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** M · **Plan:** 0.8 · **Verification:** confirmed

**Evidence.** Live: a wrong password on /login/ shows only 'Please correct the errors below.' The actual 'Please enter a correct username and password' is in form.non_field_errors, which templates/registration/login.html:10-14 never renders. Account → 'Change password' links to /admin/password_change/ (account.html:12), which sent the non-staff demo user to 'Log in | Django site admin'. The account page h2 is unstyled (Tailwind preflight) and uses the dead text-muted class (account.html:4-5); it lists 'Is Staff: False'. LOGIN_REDIRECT_URL = 'nrmps:index' (settings.py:187) and signup also redirects to index (views.py:63), whose main button is 'Go to Account'. Signup doesn't show password rules (UserCreationForm help_text is not rendered). Inputs lack autocomplete=username/current-password/new-password. There is no password reset.

**Why it matters.** Users get stuck at the account basics and can't manage or recover their account without an admin.

**Recommendation.** Render {{ form.non_field_errors }} in the login alert. Add Django's PasswordChangeView and PasswordChangeDoneView at /account/password/, plus the PasswordReset* views (console/SMTP email backend), with templates in registration/. Rebuild account.html as a profile form (full_name, email) with a saved-message toast, a 'Your simulations' summary, a theme preference, and a 'Delete account' button in a danger-zone modal. Redirect after login and signup to nrmps:simulation_list, or to simulation_create when the user has none. Show the password validators' help as a `validator-hint` list, and add autocomplete attributes.

**Verifier note (confirmed).** Reproduced. A wrong-password POST to /login/ shows 'Please correct the errors below.' and not the non-field error (login.html:10-14 never renders non_field_errors). As a non-staff user, GET /admin/password_change/ returns 302 to /admin/login/?next=... account.html:12 links there, and account.html uses the dead text-muted and menu-item classes. Signup shows no password validator help, and no inputs have autocomplete attributes. LOGIN_REDIRECT_URL='nrmps:index' (settings.py:187) and signup redirects to index (views.py:63). No password reset exists.

<a id="ux-16"></a>

### UX-16: Navigation: hard-coded URLs, links shown in the wrong state, no active item, headings out of order

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 1.5 · **Verification:** confirmed

**Evidence.** Hard-coded hrefs in theme/templates/base.html:28,31,34,42,45,80-82 and templates/nrmps/index.html:14-17 ('/account/', '/contact/', '/privacy/', '/terms/', '/'), while other links use {% url %}. 'Account' shows when logged out and leads to an 'You are not logged in' page (desktop_account.png). No aria-current or `menu-active` on the current page. The hamburger is `<div tabindex=0 role=button>` with no aria-label or aria-expanded (base.html:20). 'Contact' appears in both the nav and the footer. No breadcrumbs. Page titles are h3 (simulation_manage.html:6, interviews_list.html:6, students_list.html:6), and the h2 card titles that follow put the headings out of order. There is no skip-to-content link.

**Why it matters.** Hard-coded URLs break silently when routes change. Missing active states and landmarks hurt orientation and accessibility.

**Recommendation.** Use {% url 'nrmps:...' %} everywhere. Nav when logged in: Simulations, Help; the user dropdown holds Account, Theme and Logout. When logged out: Help, Log in, Sign up. Mark the current item with `class="menu-active" aria-current="page"` via a small `{% nav_active 'simulation' %}` tag using request.resolver_match. Make the hamburger a `<button aria-label="Open menu">` or use a daisyUI `drawer`. Add `breadcrumbs` (Simulations › Demo Match 2026 › Interviews) in the workspace layout. Make each page title an h1, add `<a href="#main" class="sr-only focus:not-sr-only">Skip to content</a>`, and give `<main id="main">`.

**Verifier note (confirmed).** base.html:28,31,34,42,45 and 80-82 and index.html:14-17 hard-code their hrefs. Account shows when logged out, and anonymous /account/ renders 'You are not logged in'. There is no aria-current or active class. The hamburger is a div with role=button and no aria-label (base.html:20); daisyUI's own docs use that pattern, but the label is still missing. Page titles are h3 (manage:6, interviews:6, students:6) followed by h2 card titles. There is no skip link. menu-active exists in daisyUI 5.1.

<a id="ux-17"></a>

### UX-17: Home page is inaccurate and doesn't explain the product or offer a demo

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** S · **Plan:** 0.7, 4.5 · **Verification:** confirmed

**Evidence.** templates/nrmps/index.html:26 says 'Log in via the Admin to manage data.', which is wrong: users sign up and use /simulations/. The main button is 'Go to Account' (line 14); Privacy and Terms are shown as hero buttons (lines 16-17). Nothing explains what NRMP is, what the simulation models, or what the user will get out of it (desktop_home.png).

**Why it matters.** The landing page is the only pitch to the students, program directors and researchers who arrive at nrmp-simulated.heteroskedastic.org.

**Recommendation.** Rewrite the hero: 'Explore how the residency Match works', a one-paragraph explanation, and the buttons 'Try a demo simulation' (POST that creates a 'Small demo' preset simulation and runs all steps as a job, then opens Results) and 'Create your own'. Below it, a 7-step overview with daisyUI `steps` and a sentence per step linking to /help/#step, a results preview image or a live mini chart, and 'Built for: students / program directors / researchers' cards. Logged-in users see 'Recent simulations' (the 3 latest with stage badges) instead of the marketing copy.

**Depends on.** UX-3, UX-21

**Verifier note (confirmed).** index.html:26 says 'Log in via the Admin to manage data.' index.html:14 is 'Go to Account' (href /account/), and Contact, Privacy and Terms are hero buttons at :15-17. mobile_home.png shows the same. The recommendation is reasonable, but its 'Try a demo' step depends on UX-3 or engine speedups.

<a id="ux-18"></a>

### UX-18: Create/edit simulation form: hidden required field, unused Iterations, 'Public' checked by default

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 0.2 · **Verification:** confirmed

**Evidence.** Submitting /simulations/new/ with a name only gives 'This field is required.' next to Description. The template has no required attribute or marker (simulation_form.html:31-32); the model is TextField(default="") without blank=True (nrmps/models.py:94). The textarea lacks w-full (simulation_form.html:31) and renders inline beside its label (desktop_sim_new.png, create_no_description.png). The template hand-writes inputs instead of using the SimulationForm widgets (forms.py:43-48). 'Iterations' (1-100, models.py:95) is shown and saved, but no engine code reads it (grep shows only models.py:95). 'Public' defaults to True (models.py:93), yet no public or shared view exists.

**Why it matters.** Users meet a surprise error on the very first form. Two of its four fields don't do what they suggest, and 'Public' can create privacy expectations.

**Recommendation.** Set description blank=True, with a migration. Render fields through _field.html (UX-8). Hide Iterations behind an 'Advanced (coming soon)' collapse until multi-run Monte Carlo exists; then pair it with a random seed field, with help text explaining that each iteration re-samples noise with seed+i and Results shows the spread across iterations. Default public=False with help text 'Public simulations can be viewed read-only by anyone with the link', and build /s/<uuid>/ read-only results before turning it on. Merge create with preset selection (UX-21) so one screen produces a runnable simulation.

**Depends on.** UX-8

**Verifier note (confirmed).** Reproduced. POST /simulations/new/ with a name only gives 'This field is required.' for description, because models.py:94 is TextField(default="") without blank=True. simulation_form.html:31 textarea has no w-full and hand-writes every input (lines 18, 31, 45, 56), ignoring forms.py:43-48. 'iterations' appears only in models.py:95, forms, templates and simulations_list.html:31, and the engine never reads it. public defaults to True (models.py:93), yet no view reads 'public'.

<a id="ux-19"></a>

### UX-19: Accessibility: low-contrast buttons, unlabeled inputs, missing ARIA state

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 1.4 · **Verification:** confirmed

**Evidence.** Measured on /simulations/1/: 'Download CSV' (btn-success btn-outline) is rgb(0,211,144) on white = 1.96:1; 'Delete All' and 'Delete Simulation' (btn-error btn-outline) are 2.86:1; placeholder text is 3.40:1. WCAG AA requires 4.5:1 for text, so all fail. File inputs have no label (_population_counts.html:35,74). The meta tag inputs all share aria-label 'meta item', and the visible label's for= points at the hidden input (simulation_manage.html:173,180,192). The pagination state is a disabled `<button>`. Sort links don't expose aria-sort. Keyboard Tab through the nav showed outline-style 'none' on menu links (focus shown only by background).

**Why it matters.** The app is meant for education and research audiences, and accessibility is also on IDEAS.md's inclusivity list.

**Recommendation.** Use `btn-soft` or solid `btn-success`/`btn-error`, or neutral `btn-ghost` with an icon, for Download; keep red for confirmations inside the danger modal. Label file inputs (`<label class="fieldset-legend" for=...>Students CSV</label>`). Tag inputs get aria-label="Preference {{index+1}}" and the remove buttons aria-label="Remove {{item}}". Wrap the editor in `role=group aria-labelledby`. Show the page indicator as `<span aria-current="page">`. Add aria-sort on `<th>`. Add a global `:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px }`. Run axe-core in the Playwright suite (0 serious violations).

**Verifier note (confirmed).** Computed colors: btn-success outline oklch(0.76 0.177 163.2) is rgb(0,211,144), 1.96:1 on white. btn-error outline oklch(0.71 0.194 13.4) is rgb(255,98,125), 2.87:1. The placeholder is base-content at 50% alpha, about 3.4:1. All fail WCAG 1.4.3 (4.5:1). The file inputs are unlabeled (_population_counts.html:35,74). The tag inputs use aria-label 'meta item' (manage.html:180,292), and the visible label for= points at the hidden input (173 to 192). Tabbing through the nav gives outlineStyle 'none' on the menu links and a 2 px solid outline on the brand link and the Logout button.

<a id="ux-20"></a>

### UX-20: Use one consistent, informative pattern for destructive actions

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** S · **Plan:** 1.5 · **Verification:** confirmed

**Evidence.** There are three confirm mechanisms. hx-confirm uses the native confirm() (_population_counts.html:18,25; _interview_counts.html:17,24). Deleting a simulation uses Alpine @submit.prevent with confirm() (simulation_manage.html:9-10, simulations_list.html:46-47), so if Alpine fails to load the form submits without asking. 'Delete All' sits in the same button row as '(re)Create', at the same size. None of the messages quantify what will be lost.

**Why it matters.** Deletions cascade through students, interviews and matches, and one click can wipe expensive computations.

**Recommendation.** Add one daisyUI `<dialog id="confirm-modal" class="modal">` in base.html, driven by a global `htmx:confirm` listener (evt.preventDefault(); show the modal; on OK call evt.detail.issueRequest(true)). The message comes from hx-confirm or from an hx-get preview of the counts. Use `btn-error` for the confirm button, and require typing the simulation name to delete a simulation. Group Delete All / Delete Simulation in a 'Danger zone' collapse or a ⋯ dropdown away from the primary actions. Make simulation deletion a real form POST that still works without JavaScript.

**Depends on.** UX-2

**Verifier note (confirmed).** There are three mechanisms: hx-confirm (_population_counts.html:18,25; _interview_counts.html:17,24), an Alpine @submit.prevent confirm (manage.html:9-10, simulations_list.html:46-47; without Alpine the form submits with no prompt), and none of the messages quantify what will be lost. htmx 2.0.6 fires htmx:confirm with detail.issueRequest(skip) and detail.question, which I confirmed in the minified source. Implementation caveat: htmx:confirm fires for every request, so the listener must act only when detail.question is set.

<a id="ux-21"></a>

### UX-21: Rebuild the config form with presets, sliders and live derived values

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 4.2 · **Verification:** confirmed

**Evidence.** simulation_manage.html:88-311 shows 20 fields in a flat grid, with no grouping semantics, no presets, no reset and no indication of unsaved changes. The only sanity check is the server validators. Market-shape numbers that matter (positions per applicant, interviews per position) are never shown.

**Why it matters.** Presets and immediate feedback are what turn a parameter wall into an exploratory tool. They also match the user's request for sliders and better simulation options.

**Recommendation.** Setup tab layout: a preset `select` or card row (Small demo 50x5; Balanced market; Competitive specialty with few positions and many applicants; Oversupply of positions; NRMP-like with 12 interviews per position). Store presets in nrmps/presets.py as dicts applied client-side by Alpine, with 'Reset to preset'. Group the fields into `fieldset`s: Market size; Applicant pool; Programs and capacity; Preferences and attributes; Information noise (pre/post rating error); Interview limits; Randomness (seed, iterations). Pair each continuous parameter with a daisyUI `range range-xs` and a number input (Alpine x-model on both), with the valid range as the step and min/max. Show a live 'Market summary' `stats` card: total positions = n_schools x capacity_mean, positions per applicant, max interviews per applicant/position, and a tiny beta-distribution preview (a 40-bin SVG path computed in JS from mean and SD). Show a dirty-state badge and add a beforeunload guard. Put rarely used fields in an 'Advanced' collapse. Coordinate the parameter list with the simulation-options dimension.

**Depends on.** UX-1, UX-11

**Verifier note (confirmed).** Facts hold. manage.html:88-311 is a flat grid with no presets, reset or dirty-state marker. daisyUI 5.1 has range-xs and fieldset. Caveat for the 'NRMP-like, 12 interviews per position' preset: the current model can't express it. school_interview_limit is a fraction capped at 0.99 of capacity (models.py:551-555), so a school can interview fewer candidates than it has positions. The preset needs that field redefined (for example interviews_per_position, 1-30) together with the simulation-options dimension. The phrase 'with the valid range as the step and min/max' should read 'min/max from the validators, with a sensible step'.

<a id="ux-22"></a>

### UX-22: Results dashboard: KPIs, charts, a network view and scenario sliders in the workspace

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** L · **Plan:** 5.3 · **Verification:** confirmed

**Evidence.** No results UI exists; TODO.md 'Data visualization' and IDEAS.md 'Interactive Visualizations / Real-time simulation dashboards' are open. Matching isn't implemented yet (CLAUDE.md steps 5-8 are TODO), and the current step pages show only counts.

**Why it matters.** The user asked for plots, graphs, networks and sliders. From a UX view they need a consistent place in the workspace and a pattern that stays responsive.

**Recommendation.** Add a Results tab (and small per-step chart strips on Population and Interviews). The top row is daisyUI `stats`: match rate, unfilled positions, percent matched to 1st and top-3 choice, median rank of match, and blocking pairs (0 means stable). Below that is a responsive grid of chart cards, each with title, '?' help, a download PNG/CSV option, and the empty state 'Run the Match step to see this'. Vendor one charting library in static/js the way htmx and Alpine are vendored (Apache ECharts, or Plotly basic, with a dark and light theme). Use Cytoscape.js for the bipartite student-school network (edges = interviews, highlighted = matches, filtered by a school selector). Views return JSON at /simulations/<pk>/api/<chart>/. Client-side sliders (Alpine) filter already-loaded data. Server-side 'what-if' sliders (rating error, interview limit) use hx-post with hx-trigger="change" to enqueue a variant run (UX-3) and overlay the result for comparison. A Compare page overlays 2-4 runs. Leave the detailed chart catalog to the visualization dimension.

**Depends on.** UX-3, UX-7

**Verifier note (confirmed).** No results UI exists, and TODO.md 'Data visualization' and IDEAS.md cover the idea. ECharts, Plotly and Cytoscape.js are all plain JS bundles that can be vendored like htmx and Alpine. 'Blocking pairs = 0 means stable' is correct for deferred acceptance. Feasibility caveat: a Cytoscape bipartite view has to aggregate or filter (per school, or the top-N edges). The full cross-product (up to 10M Interview rows) or even all interviews can't be sent to the browser, and the JSON endpoints need server-side aggregation.

<a id="ux-23"></a>

### UX-23: Dark theme is compiled but can never be reached

**Severity:** ⚪ low · **Kind:** defect · **Effort:** S · **Plan:** 1.5 · **Verification:** confirmed

**Evidence.** theme/templates/base.html:4 hard-codes `<html data-theme="light">`, while the built CSS contains both the prefers-color-scheme:dark and [data-theme=dark] daisyUI themes (grep of styles.css). The page has no theme switch.

**Why it matters.** Users who prefer dark mode get a bright screen. This is an easy accessibility and comfort win, and the charts should follow the theme too.

**Recommendation.** Remove the hard-coded attribute so daisyUI follows prefers-color-scheme. Add a `theme-controller` toggle (swap sun/moon) in the user dropdown that stores the choice in localStorage and sets data-theme before first paint (a small inline script in `<head>`). Make chart palettes read CSS variables.

**Verifier note (confirmed).** base.html:4 hard-codes data-theme="light". theme/static_src/src/styles.css uses a bare `@plugin "daisyui"`, which ships light plus dark (prefersdark), and styles.css contains both prefers-color-scheme:dark and [data-theme=dark]. theme-controller exists in the build. There is no toggle.

<a id="ux-24"></a>

### UX-24: Placeholder content and missing error pages

**Severity:** ⚪ low · **Kind:** defect · **Effort:** S · **Plan:** 0.7 · **Verification:** confirmed

**Evidence.** contact.html:7-8 lists support@example.com and links to https://github.com/ (the site root). privacy.html and terms.html are three bullets each. No 404.html or 500.html exist (templates/ contains only base.html.bak, nrmps and registration), so production shows Django's bare error pages. templates/base.html.bak is a leftover Bootstrap template (it still loads bootstrap5).

**Why it matters.** Placeholder contact details look unprofessional, and there's no working way to get support or report issues.

**Recommendation.** Point Contact at the real GitHub repository's issues page and a real address (or a small contact form that emails the owner). Add templates/404.html and templates/500.html extending base (500 must not need a DB or context). Add a 403.html for ownership failures if views switch from Http404. Delete templates/base.html.bak.

**Verifier note (confirmed).** The placeholders are at contact.html:9-10 (not 7-8): support@example.com and https://github.com/. No 404, 500 or 403 templates exist outside .venv and node_modules, and templates/base.html.bak loads bootstrap5. Related (F2): while production likely runs with DEBUG=True, it shows Django's technical debug pages, not bare error pages, which is worse. Custom error templates matter once DEBUG=False is fixed.

<a id="ux-25"></a>

### UX-25: Logo and favicon are 1024x1024 PNGs (363 KB each) shown at 32 px

**Severity:** ⚪ low · **Kind:** defect · **Effort:** S · **Plan:** 1.3 · **Verification:** confirmed

**Evidence.** static/NRMP_Simulations_favcon.png and static/NRMP_Simulations_logo.png are both 1024x1024 (IHDR), 363 KB each, used at w-8 h-8 (base.html:9-10,35).

**Why it matters.** That is about 726 KB of images on every first visit, which slows mobile first paint for no visible benefit.

**Recommendation.** Generate favicon-32.png, apple-touch-icon-180.png, icon-512.png and an SVG logo (or a 64 px WebP). Reference them with sizes attributes and add a web manifest. Keep the 1024 px source outside static/.

**Verifier note (confirmed).** Both PNGs are 1024x1024 per the IHDR header: favcon 363,309 bytes and logo 362,987 bytes. They are separate files (base.html:9-10,35), about 726 KB on a first visit, and the logo displays at w-8 h-8.

<a id="ux-26"></a>

### UX-26: Simulations list doesn't help users pick, compare or clone simulations

**Severity:** ⚪ low · **Kind:** gap · **Effort:** S · **Plan:** 4.6 · **Verification:** confirmed

**Evidence.** simulations_list.html:14-21 shows Name, Iterations (unused), Public, Students, Schools and Actions, with no created/updated date, stage or result. It runs sim.students.count and sim.schools.count per row, an N+1 query pattern (lines 39-40). On mobile the Actions column is only reachable by scrolling sideways inside the card (mobile_sim_list.png). There is no Duplicate action, which scenario comparison needs.

**Why it matters.** Research use means many variants of one scenario. The list is where users organise them.

**Recommendation.** Annotate the queryset with Count('students', distinct=True) and Count('schools', distinct=True), plus a last-run timestamp. Columns: Name (link), stage (mini `steps` or badge 'Match done'), Market (300 x 30, 450 positions), headline KPI (match rate), Updated, and a ⋯ dropdown (Open, Duplicate, Compare, Delete). Duplicate copies the config and optionally the population. Use a card list below md and checkbox selection for 'Compare selected'. Empty state: preset cards plus 'Try the demo'.

**Depends on.** UX-6

**Verifier note (confirmed).** simulations_list.html:14-21 has the columns stated (Iterations is unused). Lines 39-40 run sim.students.count and sim.schools.count per row, 2 extra queries per simulation. There is no created date, stage or Duplicate action. The recommended annotate(Count(..., distinct=True)) is correct.

<a id="viz"></a>

## VIZ: Visualization suite: plots, graphs, networks, sliders

> **Reviewer summary.** Only population charts can be built today. Every stage and outcome chart the user wants depends on data the engine never writes. The true-score fields, applied/invited/accepted/signal flags and Match rows are never populated, and Interview.status never changes. The schema also has no place for runs, iterations or scenarios, so Monte-Carlo bands, sweeps and A/B comparisons have nowhere to live. On a copy of the seeded demo, the charts we'd build first would look broken: observed/true ratio is exactly 0.1, Spearman(observed, true) is 1.000 for every student, and all 120 students rank the same school first. With the default config, 153 of 200 students land in the two edge score bins and 30% of preference weights are near zero. So the first charts should double as a check that the engine output makes sense. I built and measured a working prototype outside the repo (scratch/review/VIZ/proto). It runs the whole pipeline plus deferred acceptance (DA) in a Web Worker, with 7 ECharts 6.1 charts, a sigma.js 3 network, 8 sliders, Monte-Carlo sweep bands, and light/dark/mobile views with no horizontal overflow. DA costs 1-13 ms even at 10k x 1k; the dense application stage costs 1.1 s (JS) / 4.4 s (numpy). So what-if sliders need stage-aware recomputation, plus server-side aggregation and background jobs for large markets. I recommend Apache ECharts 6.1.0 as the one chart library (368 KB gz; Sankey, heatmap, visualMap/dataZoom sliders, brush linking, timeline animation; no ternary chart, so project the points to x/y). For networks, sigma.js 3.0.3 + graphology 0.26 (109 KB gz, WebGL). All of it loads from vendored UMD files with no bundler, which fits how htmx/Alpine are vendored today. Before vendoring, the static pipeline needs fixes: no compressed static storage, a 60 s max-age, and a Tailwind @source glob that would scan vendored JS. CSV-supplied names need escaping in custom tooltip formatters (injection confirmed).

<a id="viz-1"></a>

### VIZ-1: The engine writes almost none of the data the stage and outcome charts need

**Severity:** 🟠 high (originally critical) · **Kind:** gap · **Effort:** L · **Plan:** 3.7 · **Verification:** partially

**Evidence.** nrmps/models.py:681,698 (student_true_score_of_school / school_true_score_of_student) and :673-689 (student_applied, student_signal, student_accepted, school_invited) have no writers anywhere (grep over nrmps/ and templates/). nrmps/simulation_engine.py:167-190 interview/students_rank/schools_rank/match are `pass`, so no Match rows exist. Demo copy analysis (scratch/review/VIZ/analyze_demo.py): status values {'initialized'}, applied any=False, invited any=False, true scores populated 0/960. Simulation.iterations (models.py:95) is stored and shown but never used.

**Why it matters.** Of the requested visualizations, only population distributions can be built today. True-vs-observed scatter, rank correlation, funnel/Sankey, fill rates, rank achieved, stability/welfare, network edges by stage and Monte-Carlo bands all need fields the engine never writes. If viz work starts before the engine records these values, every chart will be empty or misleading.

**Recommendation.** Treat a 'viz data contract' as part of finishing the engine (TODO.md 'Simulation Engine Completion'). Each stage must persist: true utilities (both sides), pre/post observed scores, applied/signal/invited/accepted/interviewed/ranked flags or one Interview.stage enum, post-interview ranks, and per-applicant match results including unmatched. Write a pytest per stage that asserts the contract, e.g. `assert Interview.objects.filter(simulation=s, student_true_score_of_school__isnull=True).count()==0` after rating. Build the charts in the same order as the stages land (see extra: phased plan).

**Verifier note (partially).** Re-checked on my own copy of the demo DB (scratch/review/VIZV/a1.py). All 960 rows have status 'initialized'. applied, invited and accepted are 0/960 and signal!=0 is 0/960. Both true-score fields are NULL in 960/960 rows, post-observed is NULL in 960/960, and there are 0 Match rows. Grep finds no writers of those fields; simulation_engine.py:167-190 is all `pass`, and Simulation.iterations (models.py:95) is only used by forms and templates. The overstatement is 'only population distributions can be built today'. Pre-interview observed scores and pre-ranks are populated for every row. True utilities can be derived now from Student.meta_preference x School.score_meta: the reviewer's own analyze_demo.py does this, and VIZ-7 proposes RAT-1/RAT-3 on current data. So true-vs-observed, pre-rank correlation and first-choice-demand charts are buildable today. Downgraded to high: the missing engine stages are a documented TODO (CLAUDE.md steps 5-8), and the critical item there belongs to SIM, not to the viz layer.

<a id="viz-2"></a>

### VIZ-2: Schema can't hold multiple runs, iterations or scenarios, so Monte-Carlo bands, sweeps and A/B are impossible

**Severity:** 🟠 high · **Kind:** gap · **Effort:** L · **Plan:** 2.3 · **Verification:** confirmed

**Evidence.** nrmps/models.py:721 and :742 `unique_together = ["student","school"]` on Interview and Match, with no run or iteration FK. nrmps/views.py:121 `SimulationConfigForm(request.POST, instance=config_instance)` edits the latest config in place, so results can't be tied to the parameters that produced them. No seed is stored; generation uses the global `random` / scipy `beta.rvs` (models.py:62,156,221). Simulation.iterations (models.py:95) is unused.

**Why it matters.** Uncertainty bands, parameter-sweep curves and scenario comparisons all need many immutable results, each tagged with the exact config, seed and engine version. Today there is one mutable result per student-school pair, and editing the config silently relabels existing results.

**Recommendation.** Add `SimulationRun(simulation FK, scenario CharField, sweep FK null, iteration int, seed BigInt, config_snapshot JSON, engine_version, status choices, started_at, finished_at, duration_ms, arrays FileField/BinaryField (np.savez_compressed: apps CSR, invited, interviewed, ROL CSR, match))`. Add `RunMetric(run FK, key, value, unique(run,key), Index(key,run))` in tidy long format for sweeps and bands. Add `RunArtifact(run FK, kind, data JSON, unique(run,kind))` for precomputed chart payloads. Add `ParameterSweep(simulation, parameter, values JSON, reps)`. Keep Interview/Match as the 'detail run' view, or replace them with per-run rows keyed (run, student, school). Seed numpy `default_rng(seed)` per run, and snapshot the config when the run starts.

**Depends on.** VIZ-1

**Verifier note (confirmed).** Confirmed: unique_together on (student, school) at models.py:721 and :742, with no run or iteration key. views.py:121 binds SimulationConfigForm to the latest config and saves it in place (views.py:140-143), so existing students and interviews stay attached to changed parameters. No seed is stored. Generation uses the global scipy beta.rvs and random.gauss (models.py:62,156,221,242). iterations is unused. The proposed SimulationRun/RunMetric/RunArtifact design is feasible on SQLite and Postgres.

<a id="viz-3"></a>

### VIZ-3: Aggregate on the server and never send per-pair rows to the browser; store runs sparsely

**Severity:** 🟠 high · **Kind:** recommendation · **Effort:** M · **Plan:** 2.3 · **Verification:** confirmed

**Evidence.** F4: the config allows 10,000 x 1,000 = 10M Interview rows. Even 3 rounded floats per pair is roughly 250-300 MB of JSON. Measured numpy dense pipeline at 10k x 1k (scratch/review/VIZ/py_bench.py): gen 2,222 ms + stages 2,186 ms + ROL 106 ms + DA 20 ms = 4,534 ms, with 38 MB per float32 n x m matrix and about 10 such arrays live. Engine loops call per-row .save() (simulation_engine.py:55-66, 117-119). No pandas installed; numpy 2.5 and scipy 1.18 present.

**Why it matters.** Charts need at most a few thousand marks. Per-pair data at 10k x 1k can't be serialized, sent or drawn, and dense n x m matrices will exhaust memory on a small Railway instance.

**Recommendation.** Create `nrmps/analytics/`. `loaders.py` pulls ORM data into numpy via values_list, or loads a run's npz. `metrics.py` holds pure functions (rank_achieved(), decile_match(), fill_by_program(), spearman_by_student() via scipy.stats.spearmanr, blocking_pairs(), heat_bins() via np.histogram2d or bin-means). `payloads.py` builds columnar JSON. Rules: histograms at most 100 bins; heatmaps bin-mean to at most 200x200 (full resolution only when n*m <= 250k); scatters stratified-sample at most 5k points or switch to density mode; networks via filtered subgraphs at most 20k edges. Store per-run structures sparsely: applications as CSR n x A (300k int32 = 1.2 MB at A=30), not the full cross-product. Use SQL GROUP BY (Postgres width_bucket) for funnels and counts.

**Depends on.** VIZ-2

**Verifier note (confirmed).** I reran py_bench.py. At 10k x 1k: gen 2,140 ms, stages 2,223 ms, ROL 108 ms, DA 21 ms, total 4,492 ms. One float32 n x m array is 38 MiB. pandas is not installed; numpy 2.5.3 and scipy 1.18.1 are. The per-row .save() loops are at simulation_engine.py:55-66 and 117-119. The 250-300 MB JSON estimate checks out: 10M pairs x 3 floats at about 7 bytes each is 210 MB, plus ids. CSR at 300k int32 is 1.2 MB. One caveat: width_bucket exists only on Postgres. Dev runs on SQLite, so binning needs a portable form, e.g. Floor(F('score')*bins) or numpy after values_list.

<a id="viz-4"></a>

### VIZ-4: Library choice: Apache ECharts 6.1.0 for charts, sigma.js 3.0.3 + graphology 0.26.0 for networks

**Severity:** 🟠 high · **Kind:** recommendation · **Effort:** S · **Plan:** 5.1 · **Verification:** confirmed

**Evidence.** npm view (2026-09-24): plotly.js 4.1.1, echarts 6.1.0, echarts-gl 2.1.0, vega 6.4.0, vega-lite 6.4.3, vega-embed 7.3.0, @observablehq/plot 0.6.17, d3 7.9.0, chart.js 4.5.1, cytoscape 3.34.3, cytoscape-fcose 2.2.0, sigma 3.0.3, graphology 0.26.0, graphology-library 0.8.0, vis-network 10.1.2. Measured gzip -9 of npm-pack dist files: plotly full 1,468 KB, cartesian 496 KB (README: bar, box, contour, heatmap, histogram*, image, pie, scatter, scatterternary, violin; no sankey/splom/scattergl), basic 395 KB. echarts.min 368 KB, echarts.common 240 KB (index.common.js: line/bar/pie/scatter only), echarts-gl 175 KB. vega+vega-lite+embed 280 KB. plot 69 KB + d3 92 KB. chart.js 70 KB. cytoscape 136 KB (dist contains webgl* renderer options). sigma 47 + graphology 14 + graphology-library 48 KB (UMD globals Sigma/graphology/graphologyLibrary incl. layoutForceAtlas2, FA2Layout worker, louvain, noverlap). vis-network 63-154 KB. Prototype loads echarts + sigma + graphology via plain <script> with no bundler (proto/index.html).

**Why it matters.** The catalog needs Sankey, heatmap, SPLOM/brush linking, range sliders, animation frames, large-data rendering and dark mode. ECharts covers all of these natively except ternary charts, at a quarter of Plotly's full bundle size. Vega-Lite has the best linked selection but no Sankey, ternary or WebGL. Chart.js and Plot are too limited for linked interaction. For networks at 10^4-10^5 edges, sigma's WebGL renderer is the right tool. Cytoscape is better for small graphs with a rich analysis API.

**Recommendation.** Vendor `static/vendor/echarts/6.1.0/echarts.min.js` (+LICENSE, NOTICE). Draw ternary charts as a projected scatter (x = w2 + w3/2, y = w3*sqrt(3)/2) with the triangle drawn via `graphic`. Vendor `static/vendor/sigma/3.0.3/sigma.min.js`, `graphology/0.26.0/graphology.umd.min.js` and `graphology-library/0.8.0/graphology-library.min.js`. Keep echarts-gl optional and only add it if a 100k+ point scatterGL/graphGL view is really needed. Don't add Plotly, Vega or Chart.js as well: one chart grammar keeps theming, tooltips and help consistent. Server-side Python chart builders (plotly.py 7.1, altair 6.3, pyecharts 2.1) aren't needed. Build ECharts option objects in a small JS registry from columnar JSON (VIZ-15).

**Verifier note (confirmed).** `npm view` today gives echarts 6.1.0, echarts-gl 2.1.0, plotly.js-dist-min 4.1.1, sigma 3.0.3, graphology 0.26.0, graphology-library 0.8.0, vega 6.4.0, vega-lite 6.4.3, vega-embed 7.3.0, @observablehq/plot 0.6.17, d3 7.9.0, chart.js 4.5.1, cytoscape 3.34.3, vis-network 10.1.2. The echarts, sigma and graphology-library tarball sha1s match npm. My gzip -9 sizes: echarts.min 367,915 B; common 239,503 B; echarts-gl 174,733 B; plotly full 1,467,745 B; cartesian 495,604 B; sigma 47,132 B; graphology 13,895 B; graphology-library 47,604 B; cytoscape 136,419 B. index.common.js registers only line, bar, pie and scatter. The plotly-cartesian README lists scatterternary and no sankey. ECharts 6.1 types/src/chart has sankey, heatmap and graph but no ternary (the only 'ternary' hits are 'quaternary' theme tokens). Loaded in Chromium, the UMD bundles expose Sigma, graphology and graphologyLibrary with FA2Layout, layoutForceAtlas2, communitiesLouvain and layoutNoverlap, with no errors. The ternary projection formula is correct. Minor nit: ECharts has no native SPLOM series; you build one from several grids plus brush.

<a id="viz-5"></a>

### VIZ-5: Static pipeline isn't ready for a 1.1 MB chart library: no compression, 60 s cache, Tailwind would scan vendored JS, stale vendored htmx/Alpine

**Severity:** 🟡 medium (originally high) · **Kind:** defect · **Effort:** S · **Plan:** 1.3, 1.2 · **Verification:** partially

**Evidence.** NRMP_Simulated/settings.py:171-184 has no STORAGES, so WhiteNoise serves uncompressed files with unhashed names. .venv/.../whitenoise/middleware.py:44-49 sets `max_age = 60` when not DEBUG. echarts.min.js is 1,121,883 B raw vs 367,915 B gzipped. theme/static_src/src/styles.css:11 `@source "../../../**/*.{html,py,js}"` scans every .js under the project root, including static/. The installed Tailwind is 4.1.13, which supports `@source not`. Vendored static/js/htmx.mini.js reports version 2.0.6 and alpine_mini.js 3.14.9; the npm latest are htmx.org 2.0.11 and alpinejs 3.17.4 (F1 bumped only Python deps).

**Why it matters.** Without compressed, hashed static files, every visitor downloads about 1.1 MB of ECharts uncompressed and revalidates it every minute. Tailwind would also parse minified library code for class names, which slows builds and can emit junk CSS.

**Recommendation.** Set `STORAGES = {"staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}, "default": {...}}` so files get hashed names, immutable caching and gz/br variants. Put libraries under `static/vendor/<lib>/<version>/` and add `@source not "../../../static/vendor";` to styles.css. Load chart libraries only on viz pages via the existing `{% block extra_js %}` (theme/templates/base.html:90), not in base.html. Refresh htmx to 2.0.11 and Alpine to 3.17.4 in the same PR. Record vendored versions in a `static/vendor/README.md` so uv-bump-style reviews can include them.

**Verifier note (partially).** The facts are confirmed. There is no STORAGES in settings.py:171-184. WhiteNoise max_age is 60 when not DEBUG (middleware.py:44-49), and 0 in DEBUG, which F2 says prod probably runs. WhiteNoise only serves precompressed files, which this default storage never produces. styles.css:11 globs the whole project. static/ is not gitignored, so static/js and any static/vendor get scanned. Tailwind is 4.1.13. Vendored htmx is 2.0.6 vs 2.0.11 on npm; Alpine is 3.14.9 vs 3.17.4. I measured the Tailwind side effect myself: with echarts.min.js in a scanned tree, the build emitted 64 extra junk selectors (.diff, .indicator, .loading, .list-row, ...), 83,333 B vs 64,992 B with `@source not` on the vendor dir, so that fix works. Severity is overstated. Nothing breaks today and the static assets are small (about 83 KB CSS). Whether an edge compresses is unverifiable: the proxy blocks the deployed host. It is a prerequisite to fix before vendoring, not a high-severity defect.

<a id="viz-6"></a>

### VIZ-6: What-if sliders: three tiers with stage-aware recomputation, common random numbers and measured latency budgets

**Severity:** 🟠 high · **Kind:** recommendation · **Effort:** L · **Plan:** 6.2, 7.2 · **Verification:** partially

**Evidence.** Prototype measurements in Chromium, full pipeline in a Web Worker (scratch/review/VIZ/shoot.js, probe.js). 1000x100: worker 34-81 ms + ECharts render 45-67 ms per update. 5000x500: 467-593 ms. 10000x1000: 1,792-1,905 ms, DA 6.8 ms. Node: DA 2.4-13 ms at every size, true-preference blocking-pair scan 493 ms at 10k x 1k. Python DA 20 ms, ROL build 106 ms, dense stages 4.4 s. Django 6.1 ships django.tasks with only ImmediateBackend/DummyBackend (.venv/.../django/tasks/backends/), so real async needs django-tasks 0.12.0 (PyPI, DatabaseBackend + db_worker). Pyodide is 314.0.7 on npm, and its JS package alone unpacks to 13.9 MB before numpy/scipy wheels.

**Why it matters.** No single architecture fits every slider. A post-interview-error slider only needs ROL + DA to rerun (tens of ms), while an applications-per-applicant slider reruns the whole cross-product stage (seconds at scale). Without common random numbers (CRN: every slider position reuses the same noise draws, the prototype hashes (seed, stream, i, j)), dragging a slider mixes the parameter's effect with fresh noise, and curves jitter.

**Recommendation.** (a) Client-side filtering/brushing of precomputed payloads for display-only controls and for scrubbing across precomputed sweep values. (b) Server recompute of the user's real population via HTMX: `hx-trigger="input changed delay:400ms"` for small markets or `change` (on release) otherwise, `hx-sync="this:replace"`, cache keyed on sha256(population_version, stage params, seed, engine_version). Run synchronously up to about 2k x 200; above that, use a django-tasks job with an `hx-trigger="every 1s"` progress partial. (c) In-browser JS port in a Web Worker for a teaching 'Match Explorer' on synthetic markets, with continuous drag up to about 1k x 100 and on-release up to 5k x 500. Use a DAG cache in both (b) and (c) (population, utilities, pre-observed, applications/signals, invitations, interviews, post-observed, ROLs, DA, metrics) and recompute only from the earliest stage a slider touches. Skip Pyodide for now; the full slider and latency table is in extra.

**Depends on.** VIZ-2, VIZ-3

**Verifier note (partially).** Most checks hold. Node bench: DA 1.5-7.6 ms; totals 52 ms at 1k x 100, 577 ms at 5k x 500 and 1,733 ms at 10k x 1k; the O(nm) blocking scan is 575 ms. Django 6.1.1 django/tasks/backends has only dummy and immediate. pyodide 314.0.7 unpackedSize is 13,879,282 B. The htmx syntax is valid. Factual error: django-tasks 0.12.0 no longer ships a DatabaseBackend or db_worker. Its PyPI README says 'Prior to 0.12.0, django-tasks-db and django-tasks-rq were also included'. On Django 6.x, use `django-tasks-db` (0.13.0, INSTALLED_APPS 'django_tasks_db', BACKEND 'django_tasks_db.DatabaseBackend', `manage.py db_worker`) with the built-in django.tasks API. Also, the tier (b) sync budget of about 2k x 200 assumes a vectorized rewrite of the engine; today's per-row .save() engine takes about 0.5 s per step for 360 rows (F4).

<a id="viz-7"></a>

### VIZ-7: Current data would give degenerate charts, so the first charts should be built to catch that

**Severity:** 🟠 high · **Kind:** gap · **Effort:** M · **Plan:** 3.8, 5.3 · **Verification:** confirmed

**Evidence.** analyze_demo.py on a copy of demo sim pk=1: observed/true ratio min=max=0.1 (= rating_error, F5); per-student Spearman(observed,true) min=mean=1.000; all 120 students' #1 school = school 4 (capacity 12, total seats 113 < 120 applicants); programs' student rankings Kendall tau vs program 1 = 0.88-0.99. Default-config population (SimulationConfig() defaults): student score histogram over 10 bins 0..1 = [58,10,3,4,6,5,7,7,5,95]; student meta-scores [218,...,257] at the extremes; school score min 3.2e-10 (school_score_mean default 0, models.py:535-539); 30% of preference weights <0.02 after normalization (default stddev 3, clamp [0.01,2.0], models.py:156-166); stddev defaults above the beta's max sd are silently reduced (models.py:33-35).

**Why it matters.** The first charts (score histogram, preference ternary, true-vs-observed, first-choice popularity) will look broken until the engine and defaults are fixed. That's useful: they are the fastest way to spot generator and engine mistakes. It also means the market has no preference heterogeneity, so fill, rank and network charts will show one dominant program.

**Recommendation.** Ship POP-1 (score histograms with a requested-vs-realized overlay: requested mean/sd, effective sd after clamping, realized mean/sd), POP-3 (weight ternary with the clamp floor marked), RAT-1 and RAT-3 (first-choice demand vs capacity, with a Gini value) as P0, each with an automatic warning banner (e.g. 'effective sd reduced from 2.0 to 0.41', 'observed = true x 0.1: rating error is multiplicative'). Add preference-correlation parameters (common vs idiosyncratic utility, as in the prototype's rhoApplicant/rhoProgram) so markets can show realistic heterogeneity; coordinate with the SIM reviewer.

**Depends on.** VIZ-1

**Verifier note (confirmed).** Reproduced on a demo copy. observed/true ratio is 0.1 on both sides. Every one of the 120 students ranks school 4 first; capacities sum to 113 for 120 applicants. Kendall tau vs program 1 ranges 0.883-0.992. School 4 wins because meta-scores are drawn around one base score, so it nearly Pareto-dominates, and that is the real cause of zero heterogeneity. Default-config runs (3 trials): 154-156 of 200 students fall in the two edge bins; 29-31% of weights are below 0.02; the minimum school score is about 1e-14 to 2e-4. Also worth adding to the banners: the alpha,beta>=0.1 floor shifts the realized mean. Requested school mean 0 gives an expected 0.30 (0.10-0.39 observed); requested student mean 0.7 gives 0.62 with sd 0.43. Effective sd 0.412 for mean 0.7 is correct.

<a id="viz-8"></a>

### VIZ-8: Live config-preview charts next to the config form, computed in the browser

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** S · **Plan:** 4.2 · **Verification:** confirmed

**Evidence.** Config form (templates/nrmps/simulation_manage.html:88-311) has 20 bare numeric inputs with no feedback. Generation clamps silently: beta sd reduction (models.py:33-35), capacity floor at 0 (models.py:222-224), weight clamp [0.01,2.0] then normalization (models.py:156-166). Screenshot scratch/ui/shots/desktop_sim_manage.png.

**Why it matters.** Users can't see what a mean/stddev pair means until they generate a population and download a CSV. A small chart next to each group that updates as the user types is the cheapest, highest-value slider in the product and needs no server.

**Recommendation.** Add `static/js/nrmp-config-preview.js`: port get_beta_parameters() and draw the beta pdf (ECharts line with an area) for applicant/school score and meta-scores, a capacity pmf with the mass clamped at 0, and simulated preference-weight distributions (1k draws, same clamp and normalization). Add a 'positions per applicant' tile (sum capacity mean x schools / applicants), which is the key market-tightness number. Update on Alpine `@input.debounce.100ms`. Show the effective sd and any clamping inline, next to the field's '?' help popover.

**Depends on.** VIZ-5

**Verifier note (confirmed).** The config form (forms.py:139-160; template form at simulation_manage.html:52-316) has 20 fields: 18 numeric inputs plus 2 tag editors, not '20 numeric'. No help_text or feedback is rendered. The clamps are at the cited lines. Porting get_beta_parameters to JS is trivial. The preview should also flag that the model defaults fail their own validators. SimulationConfig().full_clean() rejects school_meta_preference_stddev=2 and school_meta_scores_stddev=2 against MaxValueValidator(0.99) (models.py:560-568). Positions per applicant should use the realized mean of the clamped capacity, not cap_mean.

<a id="viz-9"></a>

### VIZ-9: school_interview_limit semantics rule out a useful interview-slots slider (programs can never interview as many applicants as they have positions)

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 2.1 · **Verification:** partially

**Evidence.** nrmps/models.py:551-555: `school_interview_limit = FloatField(default=0.1, validators=[MinValueValidator(0), MaxValueValidator(0.99)], help_text="Max number of interviews each school can conduct In percent of capacity.")`. applicant_interview_limit (models.py:504-508) has no max.

**Why it matters.** If interviews per program are capped at 0.99 x capacity (default 0.1 x), no program can fill, and fill-rate and unfilled-position charts will show about 10% fill by construction. Real programs interview many applicants per position, and interview slots per position is one of the most informative sweep axes (sweep curves in extra).

**Recommendation.** Replace it with `interview_slots_per_position = FloatField(default=10, validators=[MinValueValidator(0.5), MaxValueValidator(30)])` via a data migration (new = old x 100 or reset to the default). Add MaxValueValidator(50) to applicant_interview_limit. Expose both as sweep and slider parameters (slider table in extra). Coordinate with SIM.

**Verifier note (partially).** Confirmed at models.py:551-555 (FloatField, default 0.1, max 0.99, help text 'In percent of capacity'). applicant_interview_limit has no max (models.py:504-508). If implemented as documented, interviews would be capped below capacity. But the field is latent: grep shows it is used only in forms and templates, since the interview stage is not implemented, so no current output is affected. The suggested data migration 'new = old x 100' is not a unit conversion: 0.1 of capacity is 0.1 interviews per position, not 10. Reset to the new default instead. Otherwise sound; coordinate with SIM before implementing the interview step.

<a id="viz-10"></a>

### VIZ-10: Define and precompute stability, welfare and friction metrics; they are the most insightful outcome views

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 3.7 · **Verification:** partially

**Evidence.** Prototype DA check (bench.js): 0 blocking pairs w.r.t. submitted rank lists over 200 random instances, as expected. At 1000x100 with defaults: 72.5% matched, 81.0% of positions filled, 170 unfilled, 67.1% of applicants in at least one true-preference blocking pair (a pair who both truly prefer each other but never interviewed or ranked each other). O(n*m) scan: 9-11 ms at 1000x100, 493-596 ms at 10k x 1k (node).

**Why it matters.** DA is always stable with respect to submitted lists, so 'blocking pairs' only says something relative to true preferences. That number measures how much the application and interview frictions cost. Regret, an oracle benchmark and a comparison of proposing sides turn the simulator into a research tool. These fit the IDEAS.md items 'Match stability analysis / Blocking pair identification' and 'Compare outcomes across different matching algorithms'.

**Recommendation.** In `nrmps/analytics/metrics.py`, compute per run and store as RunMetric: stable_wrt_rol (must be 0; shown as a correctness badge), blocking_pairs_true, share_applicants_in_bp_true, regret (true rank of the matched program among all programs: histogram artifact), welfare = mean true utility of matches, oracle_gap = the same metrics from DA on full true preferences with no interview constraint, proposing_side_diff = number of applicants whose match changes between applicant- and program-proposing DA, unmatched_reason counts (no applications accepted / no interviews / interviewed but unranked / ranked but outcompeted). Charts MAT-6 and MAT-8 in the catalog.

**Depends on.** VIZ-1, VIZ-2

**Verifier note (partially).** I reran bench.js. There are 0 violations of stability w.r.t. submitted ROLs over 200 instances, and the DA and brute-force checker logic are correct. At 1000x100: 72.5% matched, 81.0% filled, 671 applicants in true-preference blocking pairs, blocking scan 10 ms. The metric set is sound, and the IDEAS.md:9 and :96-97 references are right. Two corrections. First, the parenthetical definition is too narrow. A true-preference blocking pair can also be a pair that did interview and rank each other but whose post-interview noisy rankings misordered them, not only pairs that 'never interviewed or ranked each other'. Second, every number comes from the prototype's own rho/Gaussian utility model, not this repo's meta-score x weight model, so they illustrate magnitude only.

<a id="viz-11"></a>

### VIZ-11: Network view: sorted two-column layout by default, ego networks as the main interaction, tier graph for scale, force layout only for clustered markets

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 5.4 · **Verification:** confirmed

**Evidence.** Prototype sigma view (proto/index.html drawNet; shots/proto_desktop.png, shots/proto_net_fa2.png): 300 applicants + 100 programs + 1,695 interview edges. The two-column layout sorted by score/prestige is readable. ForceAtlas2 (150 iterations, sync, 403 ms) gives an unreadable hairball because random markets have no community structure. Rebuilding the sigma instance each update cost 33-625 ms (software GL). The nodeReducer/edgeReducer ego filter works on click.

**Why it matters.** The user asked for bipartite graphs with edges by stage and ego filters, plus a layout for large graphs. On a full market, a force layout shows nothing, and 10k x 30 application edges (300k) exceed what anyone can read even in WebGL.

**Recommendation.** Endpoint `GET /api/runs/<id>/network?focus=student:<id>|program:<id>&min_stage=interviewed&deciles=...&limit=20000` returns columnar nodes and edges. Default layout: two columns sorted by score/prestige (preset x,y). Ego view: the focus node's edges colored by stage (ordinal ramp: applied < invited < interviewed < ranked < matched). Tier graph: decile-to-decile super-nodes with weighted edges (shared payload with MAT-5). Offer ForceAtlas2 in a worker (graphologyLibrary FA2Layout) only when a clustering attribute exists (future region/specialty). Keep one Sigma instance and update graph attributes with reducers instead of kill/recreate. Add node search (combobox) and click-through to the student's detail page.

**Depends on.** VIZ-2, VIZ-4

**Verifier note (confirmed).** The sigma/graphology UMD globals load and FA2Layout exists (checked in Chromium). The prototype screenshot shows a readable two-column layout with 400 nodes and 1,695 edges. The hairball claim for markets without community structure is plausible and consistent with the prototype's model. The endpoint design depends on a run model (VIZ-2), which the finding correctly lists.

<a id="viz-12"></a>

### VIZ-12: XSS risk: custom chart tooltip formatters will run HTML from CSV-uploaded student/school names

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 5.1 · **Verification:** partially

**Evidence.** Names come straight from uploaded CSVs (nrmps/models.py:339 students, :437 schools). Probe scratch/review/VIZ/xss_probe.js with name `<img src=x onerror=...>`: ECharts default tooltip executed 0 times; custom formatter `${p.name}` executed 2 times; custom formatter with `echarts.format.encodeHTML(p.name)` executed 0 times.

**Why it matters.** Nearly every catalog chart needs a custom tooltip (student, school, rank, score). A single unescaped template literal turns a shared or public simulation (Simulation.public defaults True, models.py:93) into stored XSS.

**Recommendation.** In the shared `nrmp-charts.js`, provide `tip(rows)` helpers that build tooltip DOM with textContent, or always wrap names in echarts.format.encodeHTML. Embed server data with Django's `json_script` filter, never with `|safe` (simulation_manage.html:172,283 already uses `|safe` for meta lists). Add a Content-Security-Policy (Django 6 has built-in CSP support) disallowing inline event handlers. Add a Playwright regression test that uploads a malicious-name CSV.

**Depends on.** VIZ-4

**Verifier note (partially).** Reproduced independently: in ECharts 6.1.0, default item and axis tooltips escape HTML (0 executions), a custom string formatter executes the payload (2), and echarts.format.encodeHTML exists. Three corrections. (1) It is a prospective rule, not a current chart defect. Every view is owner-only and Simulation.public is never read by any view, so 'shared/public simulation' does not exist yet. (2) The |safe pattern already is a live self-XSS. I saved applicant_meta_preference=['a"><img src=x onerror=alert(1)>'] and GET /simulations/<pk>/ returned the raw <img> inside x-data at simulation_manage.html:172 (and likewise at 283). Lines 194/305 (value='{{ list|safe }}') render a Python repr with single quotes, which breaks the attribute even for benign values. (3) The CSP advice must account for the Alpine standard build needing 'unsafe-eval' (or use @alpinejs/csp), the inline onchange handlers (students_list.html:15, schools_list.html:15, interviews_list.html:18) and the inline <script> at simulation_manage.html:331 (needs a csp_nonce). Django 6.1's built-in ContentSecurityPolicyMiddleware and SECURE_CSP are confirmed.

<a id="viz-13"></a>

### VIZ-13: JSON data API with columnar payloads, ETags, gzip on API responses only, and a shared cache

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 5.2 · **Verification:** partially

**Evidence.** NRMP_Simulated/settings.py:80-91 has no GZipMiddleware and no CACHES setting (so each gunicorn worker gets its own LocMemCache). TODO.md 'Set up Redis for caching/sessions' and 'API documentation' items exist. Prototype payload sizes: 120x8 19 KB, 1000x100 120 KB, 10k x 1k 449 KB with 10k per-applicant scores; aggregated payloads are single-digit KB.

**Why it matters.** Charts need stable, cacheable, versioned endpoints. Finished runs are immutable, so their chart payloads can be cached indefinitely and served with ETags. Gzipping HTML that carries CSRF tokens exposes it to BREACH, so compression should apply to JSON only.

**Recommendation.** Add `nrmps/api/urls.py` and `views.py` (plain JsonResponse, no DRF needed): endpoints in extra ('Backend data API'). Payload envelope `{meta:{simulation, run, seed, engine_version, config_hash, generated_at}, columns:{...}}` with floats rounded to 4 decimals. Decorate views with `@gzip_page` and `@condition(etag_func=...)`, where the etag is run id + engine_version + kind + params hash. Use `CACHES = DatabaseCache` (no new infra) or Redis when available; key = `viz:{run}:{kind}:{params_hash}:{engine}`. Invalidate on population regeneration via a Simulation.population_version counter.

**Depends on.** VIZ-2, VIZ-3

**Verifier note (partially).** Confirmed: settings.py:80-91 has no GZipMiddleware, and there is no CACHES setting anywhere, so the default is a per-process LocMemCache under gunicorn --workers 4 (entrypoint.sh:47). TODO.md:120 and :133 exist. gzip_page and condition(etag_func) exist. The BREACH rationale is outdated. Django masks CSRF tokens per response, and GZipMiddleware in this venv adds 'Heal The Breach' random-length padding (django/middleware/gzip.py:16, max_random_bytes=100; utils/text.py:347-361). Gzipping HTML is not the exposure the finding claims. Gzipping only API JSON is still a fine choice. DatabaseCache also needs `createcachetable` in the entrypoint.

<a id="viz-14"></a>

### VIZ-14: Monte-Carlo iterations, parameter sweeps and A/B scenarios as first-class, precomputed experiments

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** L · **Plan:** 6.1 · **Verification:** confirmed

**Evidence.** Prototype sweep (worker): 8 values x 10 seeds = 80 runs at 1000x100 in 2,792 ms. Median match rate by applications per applicant: 38% at 3, about 80% at 30, 82% at 45, 78% at 60, so it is not monotone. Node, 5 seeds: A=45 median 0.82, A=60 0.775. In the prototype model, pre-interview error 0 to 2.0 raised match rate 67.9% to 86.5% (fewer applicants crowd the same programs). IDEAS.md lists 'Parameter sensitivity analysis', 'Scenario comparison tools', 'A/B testing framework'; TODO.md lists 'Implement scenario comparison tools'.

**Why it matters.** Single runs are noisy, and the most interesting effects (application inflation, congestion, signaling value) only show up as curves with uncertainty bands. The model's `iterations` field suggests this was intended but it isn't implemented.

**Recommendation.** Add an 'Experiments' tab. Monte-Carlo: run `iterations` seeds per scenario, store RunMetric, and show strip + box per metric and a running-mean ± 95% CI convergence plot (EXP-5) so users know when to stop. Sweep: pick a parameter, a value list and reps; enqueue a django-tasks job; show a median line with a p10-p90 band (stacked-area band as in the prototype); one metric per small multiple, never dual axes. A/B: two scenarios share seeds (CRN), with delta tiles and a paired CI, small multiples on shared axes, and a diverging per-decile difference bar. A 2-parameter grid shows as a heatmap (EXP-4). The rendered sweep then becomes a precomputed client-side slider (tier a).

**Depends on.** VIZ-2, VIZ-6

**Verifier note (confirmed).** Node rerun, 5 seeds at 1000x100: median match rate 0.362 at A=3, 0.792 at 30, 0.82 at 45, 0.775 at 60 (40 runs in 1.39 s). sigmaPre 0 to 2 gives 67.9% to 86.5%. TODO.md:81-82 and IDEAS.md:102-104 exist, and iterations is unused. Caveats: the non-monotonicity is a property of the prototype's model and may not hold for this engine. The job queue should be django-tasks-db, not django-tasks 0.12 (see VIZ-6).

<a id="viz-15"></a>

### VIZ-15: Dashboard page and HTMX integration: lazy chart cards, a JS chart registry, and cleanup on swap

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 5.1 · **Verification:** partially

**Evidence.** The only simulation pages are manage/list/table pages (nrmps/urls.py:21-47). base.html provides `extra_head`/`extra_js` blocks (theme/templates/base.html:12,90). HTMX partials are swapped with outerHTML (templates/nrmps/partials/_interview_counts.html:16-17). ECharts instances must be disposed or they leak when their container is swapped out.

**Why it matters.** There's nowhere to show results, and the HTMX partial-swap pattern needs a small amount of glue so charts initialize and dispose correctly.

**Recommendation.** Add `simulations/<pk>/dashboard/` with tabs Population · Ratings · Applications & Interviews · Match · Experiments; the active tab is kept in the URL via hx-push-url. Each card is `<div hx-get="/api/..." hx-trigger="revealed" data-chart="rank_achieved">`, or server-rendered with `{{ payload|json_script:id }}`. `static/js/nrmp-charts.js` exposes `NRMPCharts.register(kind, buildOption)`, initializes on `htmx:afterSettle` and on load, calls `echarts.getInstanceByDom(el)?.dispose()` on `htmx:beforeCleanupElement`, uses a ResizeObserver, and keeps the previous render at reduced opacity while refetching (as in the prototype). Add mini-charts (a sparkline histogram, a funnel bar) to each stage card on simulation_manage, next to a stage stepper.

**Depends on.** VIZ-4, VIZ-5, VIZ-13

**Verifier note (partially).** Checked: urls.py has only manage, list and table routes; base.html:12 and :90 have the blocks; _interview_counts.html:16-17 uses outerHTML swaps; htmx 2.0.11 emits htmx:beforeCleanupElement and htmx:afterSettle. One technical flaw: `<div hx-get="/api/..." hx-trigger="revealed">` against a JsonResponse endpoint would swap raw JSON text into the card. htmx expects HTML, so you need either an HTML partial endpoint that embeds the payload with json_script, or a plain fetch() in nrmp-charts.js (or an htmx:beforeSwap handler). The json_script alternative the finding also offers works.

<a id="viz-16"></a>

### VIZ-16: Chart design system: validated palette tokens, real dark mode, accessibility (aria/decal/table view), number formatting, mobile variants

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 5.1 · **Verification:** confirmed

**Evidence.** theme/templates/base.html:4 hard-codes `data-theme="light"`. F5: floats shown with about 16 decimals. The prototype uses a validated categorical/sequential palette via CSS custom properties with separately chosen dark steps (shots/proto_desktop_dark.png). At 390 px, the Sankey node labels collide (shots/proto_mobile.png) while page overflow is 0 px. ECharts 6 includes aria and decal components (types/src/component/aria).

**Why it matters.** Without shared rules, 30+ charts will drift in colors, formats and accessibility. Color-only encoding of stages or outcomes fails for colorblind users, and a light-only theme clashes with OS dark mode.

**Recommendation.** Define chart tokens in styles.css (--viz-series-1..3, the --viz-seq-* ramp, --viz-neutral, surface/ink/grid) with separately chosen dark values, and read them in nrmp-charts.js at init and on theme change. Add a light/dark/auto toggle that sets data-theme. Rules: a fixed categorical order (student=slot1, program=slot2, matched=slot3); ordinal blue ramp for funnel stages; gray for 'unmatched/other'; no dual axes; legends for ≥2 series. Enable `aria: {enabled:true, decal:{show:<user pref>}}`, a 'table view' toggle per card, and Intl.NumberFormat (3 significant digits, % for rates). On mobile, switch the Sankey to `orient:'vertical'` or a funnel bar list below 480 px.

**Depends on.** VIZ-4

**Verifier note (confirmed).** base.html:4 hard-codes data-theme="light" (the daisyUI plugin is loaded in styles.css:2). ECharts 6.1 ships the aria component, which includes decal. The prototype mobile screenshot shows the Sankey labels 'Invited/Interviewed/Rank' colliding at 390 px. Sankey supports orient:'vertical'. The recommendations are feasible.

<a id="viz-17"></a>

### VIZ-17: Interview stage isn't queryable: free-form status string, only FK indexes

**Severity:** ⚪ low (originally medium) · **Kind:** gap · **Effort:** S · **Plan:** 2.3 · **Verification:** partially

**Evidence.** nrmps/models.py:670 `status = models.CharField(max_length=50, default="initialized")` with no choices. Interview Meta has only `unique_together` (models.py:720-721). Funnel counts would need several boolean filters across 10M rows.

**Why it matters.** The funnel, per-stage counts and network 'min_stage' filters are all GROUP BY stage queries. Without an ordered enum and composite indexes, they are slow and error-prone.

**Recommendation.** Add `class Stage(models.IntegerChoices): INITIALIZED=0, APPLIED=10, SIGNALED=15, INVITED=20, DECLINED=25, INTERVIEWED=30, RANKED=40, MATCHED=50`, `stage = PositiveSmallIntegerField(choices=Stage, default=0, db_index=False)`, and `indexes=[Index(fields=['simulation','stage']), Index(fields=['simulation','student']), Index(fields=['simulation','school'])]`. The funnel then becomes `values('stage').annotate(n=Count('id'))`. Keep the booleans only if they carry independent meaning (e.g., signal).

**Verifier note (partially).** Confirmed: status is a free-form CharField at models.py:670 that is never updated, and Meta has only unique_together (models.py:720-721). The FK on simulation is indexed automatically. Overstated: the booleans are queryable. A funnel is one query, aggregate(applied=Count('id', filter=Q(student_applied=True)), ...). A single linear Stage enum also loses information: ranking is two-sided (student ranked program vs program ranked student), and DECLINED/SIGNALED are not points on a line. Keep per-side flags or a bitmask, and use the enum only as a derived 'furthest stage' convenience. Useful, but low severity.

<a id="viz-18"></a>

### VIZ-18: Reproducible, shareable charts: PNG/SVG export, data CSV, run citation, slider-state permalinks

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** S · **Plan:** 5.5 · **Verification:** confirmed

**Evidence.** IDEAS.md 'Reproducible research features' and 'Publication-ready output generation'; TODO.md 'Create reproducible simulation reports'. The existing CSV downloads cover raw tables only (nrmps/views.py:284-313, 522-554).

**Why it matters.** Researchers will want to put charts in papers and share exact what-if states. Without run IDs and seeds shown on charts, nobody can reproduce a figure.

**Recommendation.** Use the ECharts toolbox `saveAsImage` (SVG renderer for publication export), plus a 'Download data (CSV)' link that serves the same payload the chart uses. Add a footer on every chart card: 'Run #id · seed · engine vX · config hash'. Encode slider state in URLSearchParams with hx-push-url so a URL restores the view. Offer a 'Snapshot to report' action that saves a RunArtifact set for later comparison.

**Depends on.** VIZ-2, VIZ-15

**Verifier note (confirmed).** CSV downloads exist only for raw tables (views.py:286,302,524). IDEAS.md:128 and :132 and TODO.md:82 exist. ECharts toolbox saveAsImage exports SVG when the SVG renderer is used. Feasible.

<a id="viz-19"></a>

### VIZ-19: Every chart card gets a '?' popover from a single chart registry, shared with the documentation page

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** S · **Plan:** 5.1 · **Verification:** confirmed

**Evidence.** The documentation page is generated from model docstrings (nrmps/views.py:557-705), and nothing explains what a chart shows. The prototype attaches help text to each slider label (title/aria-label on the '?' badge).

**Why it matters.** Metrics like 'true-preference blocking pair' or 'rank achieved' need a one-paragraph explanation and a caveat. Writing that text in two places (chart and docs) will drift.

**Recommendation.** Add `nrmps/viz_catalog.py` with CHARTS = {kind: {title, question, how_to_read, caveats, stage, priority}}. Render it in each card's DaisyUI dropdown/popover '?' (keyboard-focusable, not hover-only) and as a 'Charts & metrics' section on the documentation page. Coordinate with the HELP reviewer.

**Depends on.** VIZ-15

**Verifier note (confirmed).** The documentation view (views.py:557+) builds its content from model docstrings. No chart or metric help exists anywhere. A single registry rendered in both places is feasible and avoids drift.

<a id="viz-20"></a>

### VIZ-20: Test the viz stack: pure-numpy metric tests, payload snapshots, Playwright render smoke, and JS/Python parity via a portable RNG

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** M · **Plan:** 5.5, 7.2 · **Verification:** confirmed

**Evidence.** F6: nrmps/tests.py is empty. Prototype harnesses scratch/review/VIZ/shoot.js and probe.js check load, slider round-trip, console errors and mobile overflow. rng_parity.py shows the prototype's counter-based RNG reimplemented in numpy matches JS to max |diff| = 5.55e-17. bench.js DA stability check: 0 violations over 200 instances.

**Why it matters.** Chart bugs are usually data bugs. A JS port for the Explorer (tier c) is only trustworthy if it is tested against the Python engine on identical inputs.

**Recommendation.** Add pytest cases for nrmps/analytics (golden values on 10x3 hand-built markets, DA stability property test via hypothesis) and JSON-schema snapshots of each API payload. Add a Playwright smoke that loads each dashboard tab, asserts zero console errors, one canvas per card and no horizontal overflow at 390 px. For parity, share the counter-based RNG (seed, stream, i, j) between numpy and JS, and assert identical matches for fixed seeds on 200x20 markets in CI.

**Depends on.** VIZ-3, VIZ-6

**Verifier note (confirmed).** nrmps/tests.py is only a comment. I regenerated the JS gaussians from proto/sim.js and ran rng_parity.py: max |py-js| = 5.55e-17. Note that this is not bit-identical: Math.log/cos vs numpy can differ in the last ulp, so an 'identical matches' parity test can in principle flake on near-ties, though that is practically negligible at 200x20. hypothesis is not installed and would be a new dev dependency.

<a id="viz-21"></a>

### VIZ-21: Add NRMP-report-style charts that medical-education users already know

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** S · **Plan:** 5.3 · **Verification:** confirmed

**Evidence.** The planned stages (applications, signals, invitations, interviews, rank lists, match) mirror NRMP/ERAS practice. The project targets NRMP simulation (CLAUDE.md), and IDEAS.md lists AAMC/medical-education audiences.

**Why it matters.** Users from medical education read 'probability of matching vs number of contiguous ranks' (the NRMP 'Charting Outcomes' style) and 'positions offered vs filled' at a glance. Leading with familiar forms builds trust before the research metrics.

**Recommendation.** Catalog ROL-1: P(match) vs rank-list length with lines by applicant score tercile and a Monte-Carlo band. MAT-4: offered vs filled positions per program tier. Also a 'signals sent vs interview offers' grouped bar (APP-2) once signals exist. Label axes in NRMP vocabulary (applicants, programs, positions, rank order list).

**Depends on.** VIZ-1

**Verifier note (confirmed).** 'Probability of matching vs number of contiguous ranks' is the standard NRMP Charting Outcomes chart, and positions offered vs filled appears in NRMP Main Match results. IDEAS.md:244-249 names medical education and ERAS/AAMC audiences. Signals are an ERAS/AAMC feature, not an NRMP one, so label APP-2 accordingly.

<a id="help"></a>

## HELP: Help page and in-context "?" help

> **Reviewer summary.** The app has almost no working help. The only "Documentation" page is an auto-generated dump of models.py internals. It is open to anonymous visitors, shows the User model's password and permission fields plus 30 Django auth methods, leaves out simulation_engine.py (where the model math lives), overflows on mobile, and its styling is broken under daisyUI 5. None of the help_text written in models.py/forms.py reaches the screen. The config form renders widgets by hand, so all 17 aria-describedby references point at elements that don't exist, and the CSV-format and password-rule hints are never shown. The help text that does exist is often wrong: 8 Interview fields have student/school wording swapped, "Pre-interview" is used on a post-interview field, "percent" is used for a fraction, there are typos (scoreing/Setp/preferacnes/stdsdev), and the rating-error formula describes the bug rather than the intent. The parameter semantics are also a trap. Saving an untouched default config fails its own validators, a requested 0.7 +/- 2 silently becomes 0.62 +/- 0.43 (U-shaped), six parameters are never used, and "(re)Create Students" silently deletes every interview. The recommended design has five parts: (1) a typed help registry (nrmps/help/registry.py) as the single source of truth, with numbers read from model metadata and a Django system check against drift; (2) an accessible "?" popover plus a field_row component built on daisyUI 5 fieldset/dropdown; (3) a per-page help panel in a native dialog; (4) a markdown user guide at /help/ with KaTeX formulas, generated parameter/CSV/glossary tables, FAQ and a worked example; (5) guided first-run help (a stage checklist, an example preset, and live distribution/market previews). The auto-generated docs move to a staff-only developer reference.

<a id="help-1"></a>

### HELP-1: No field help is rendered anywhere; 17/17 aria-describedby references dangle; CSV-format and password-rule hints are invisible

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 1.4 · **Verification:** partially

**Evidence.** templates/nrmps/simulation_manage.html:88-311 renders each widget manually ({{ config_form.x }}) with a label but never field.help_text. Logged-in GET /simulations/1/ plus a parse of the HTML: '17 aria-describedby refs; 17 point to nonexistent ids' (e.g. id_applicant_score_mean_helptext); Django adds these automatically for fields with help_text. Grep for help_text|tooltip|data-tip in templates/ finds only documentation.html:53. Upload hints 'CSV: name, score, [score_meta]' (nrmps/forms.py:60,74) are never shown: views.py:183-184 passes students_upload_form/schools_upload_form, but templates/nrmps/partials/_population_counts.html:35,74 hard-code a bare <input type=file>. Signup never shows the 4 AUTH_PASSWORD_VALIDATORS rules (NRMP_Simulated/settings.py:143-156; templates/nrmps/signup.html:61-85 renders password1/password2 without help_text). Screenshot scratch/review/help/config_form_defaults_error.png shows no hints on any of the 20 inputs.

**Why it matters.** Users meet 20 unexplained statistical parameters with no units, ranges or meaning, and screen-reader users hit broken ARIA references (WCAG 1.3.1 / 4.1.2). The help that was written is wasted, and users cannot find out the CSV format or the password policy until an upload silently misparses or signup fails.

**Recommendation.** Add one field component, templates/nrmps/components/_field.html, used via {% field_row form.field %} (nrmps/templatetags/help_tags.py). It renders a daisyUI 5 <fieldset class='fieldset'>, a <legend class='fieldset-legend'> label plus the {% help_icon %} popover (HELP-9), the widget, then <p class='label' id='{{ field.auto_id }}_helptext'>{{ field.help_text }}</p> so Django's aria-describedby resolves, and the errors. Replace the ~220 lines of hand-written blocks in simulation_manage.html with about 20 field_row calls. Render the upload forms from the form objects so their help and a 'Download sample CSV' link appear (HELP-15). In signup.html, render {{ form.password1.help_text }} (Django's password_validators_help_text_html) under the password field. Add a test that renders the manage page and asserts every aria-describedby id exists.

**Depends on.** HELP-8

**Verifier note (partially).** Reproduced by logging in as demo and parsing /simulations/1/ and /simulations/2/: 17 aria-describedby references, all 17 pointing at missing *_helptext ids. No help_text strings are rendered, the 'CSV:' hints are absent (_population_counts.html:35,74 hard-code the file inputs), and signup.html:61-85 hard-codes the password inputs, so the validator rules never appear. The title's 'no field help anywhere' and the evidence's 'no hints on any of the 20 inputs' go too far: simulation_manage.html:195,306 render a static hint ('Enter as tags; press Enter to add...') under both meta-preference inputs, and the cited screenshot shows it. Two problems with the recommended markup. (a) In Django 6.1, BoundField.aria_describedby (django/forms/boundfield.py:306-316) also adds '<auto_id>_error' when a field has errors, and the template's errors.0 output has no such id. POSTing iterations=150 produced aria-describedby="id_iterations_error" with no matching element. field_row must render {{ field.errors }} (Django's ul carries id=..._error) or set that id itself. (b) daisyUI 5's .label sets white-space:nowrap (daisyui/components/label.css), which is why the inline errors overflow into the next column in the screenshot. A long help sentence in <p class='label'> would overflow the same way, so it needs whitespace-normal or a plain text class.

<a id="help-2"></a>

### HELP-2: Default configuration fails its own validators, and several defaults are meaningless for the 0-1 Beta model

**Severity:** 🟠 high · **Kind:** defect · **Effort:** S · **Plan:** 0.2 · **Verification:** confirmed

**Evidence.** nrmps/models.py:560-563 has school_meta_preference_stddev default=2 with MaxValueValidator(0.99) and no help_text; :564-568 has school_meta_scores_stddev default=2 with max 0.99. Playwright on a throwaway simulation I created and then deleted: saving the untouched config returns 'There are errors in the configuration form: School_meta_preference_stddev: * Ensure this value is less than or equal to 0.99. School_meta_scores_stddev: * Ensure ...' (config_form_defaults_error.png; the inline errors also overflow into the neighbouring column). Scratch script check_defaults.py: 'DEFAULTS VALID? False'. Other defaults: school_score_mean=0 (:536) gives effective mean 0.299 with 46% of schools below 0.01; applicant_score_stddev=2 (:500) with mean 0.7 gives alpha=0.164, beta=0.100, effective mean 0.621 and sd 0.431 (U-shaped); applicant_meta_scores_stddev=10 (:519); applicant_meta_preference_stddev=3 (:515) leaves 74% of weights exactly 0.01 or 2.0.

**Why it matters.** First-time users cannot save the defaults and get errors keyed by raw field names. The defaults that do validate produce degenerate populations the help never warns about. Help can only describe the valid ranges once the validators and defaults agree with them.

**Recommendation.** Change the defaults to the 'Sensible default' column in extra §C: score SDs 0.1, school_score_mean 0.5, meta score SDs 0.1, preference SDs 0.3, capacity 18±4, interview multiplier 5. Tighten the validators: score SDs max 0.45, preference SDs max 1.0, capacity_mean MinValueValidator(1). Add SimulationConfigForm.clean() cross-field checks such as sd < sqrt(mean*(1-mean)), with messages that give the computed limit. Add a unit test that builds SimulationConfigForm from model defaults and asserts is_valid(). The HELP-8 system check guards the same invariant.

**Verifier note (confirmed).** In an isolated DB, SimulationConfigForm built from the model defaults is invalid, with errors on school_meta_preference_stddev and school_meta_scores_stddev ('<= 0.99'). The defaults are 2 (models.py:560-568), and :560 has no help_text. My runs match every number: get_beta_parameters(0.7,2) gives alpha 0.164, beta 0.100, mean 0.621, sd 0.431; (0,2) gives mean 0.299 with P(<0.01)=45.7%; N(1,3) clamps 74.0% of weights. The screenshot shows the errors keyed by raw field name and the inline error overflow. High severity is justified. On a new simulation the form shows these defaults, and create_students() silently returns 0 until a config is saved (verified: 200, Count 0), so a first-time user is blocked twice. The 'sd < sqrt(mean(1-mean))' cross-field check is the correct Beta feasibility condition.

<a id="help-3"></a>

### HELP-3: Help and docstrings describe behaviour the engine lacks; 6 user-facing parameters do nothing and are not marked

**Severity:** 🟠 high · **Kind:** defect · **Effort:** S · **Plan:** 1.6 · **Verification:** confirmed

**Evidence.** The rating-error help says 'error stddev' (nrmps/models.py:526,531,572,577), but simulation_engine.py:10 multiplies the utility by it, and simulation_engine.py:50,81 use `x or 1.0`, so 0 becomes 1.0 (verified: float(0.0 or 1.0) = 1.0). The docstrings at simulation_engine.py:8,46,77 document that multiply formula as intended. A grep of simulation_engine.py and views.py finds no reference to applicant_interview_limit, school_interview_limit, applicant_post_interview_rating_error, school_post_interview_rating_error, Simulation.iterations or Simulation.public; the Interview fields student_signal, student_true_score_of_school, school_true_score_of_student and Student/School.meta_stddev are also never written. Lead fact F5: observed rankings equal the true rankings.

**Why it matters.** Researchers will vary these parameters, see no change, and draw wrong conclusions. The help text does not say that a parameter is inactive or that the current behaviour is a known bug.

**Recommendation.** Give each registry entry a status field: 'active' | 'planned' | 'deprecated' | 'known-issue'. For 'planned', field_row renders a daisyUI badge 'Not used yet - Stage N' and groups those inputs in a collapsed 'Planned parameters' fieldset. For 'known-issue', show a short warning linking to the FAQ. Rewrite the engine docstrings to the intended formula (observed = U + ε, ε ~ N(0, σ)) when F5 is fixed. Until then, keep a 'Current behaviour' note in the guide, removed by the same PR that fixes the engine and enforced by the executable example test in HELP-11. Mark Student/School.meta_stddev as deprecated or drop them.

**Depends on.** HELP-8

**Verifier note (confirmed).** A grep of nrmps/simulation_engine.py, nrmps/views.py and the templates finds no engine or view use of applicant_interview_limit, school_interview_limit, applicant/school_post_interview_rating_error, Simulation.iterations or Simulation.public. They are only rendered or listed. student_signal, the *_true_score_* fields and meta_stddev are never written. simulation_engine.py:10 multiplies the score by rating_error, and :50/:81 use `or 1.0`, so a value of 0 becomes 1.0 (float(0.0 or 1.0)=1.0 verified). The docstrings at :8, :46 and :77 state the multiplied formula. The finding understates the problem: a constant multiplier cannot change any ranking, so the two pre-interview rating-error parameters also have no effect on rankings. In practice 8 of the 20 config inputs cannot change any output ordering.

<a id="help-4"></a>

### HELP-4: Inaccurate, swapped or typo-ridden help_text on 25+ model fields

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 1.6 · **Verification:** confirmed

**Evidence.** Swapped subject/object on Interview fields: nrmps/models.py:693 student_pre_observed_score_of_school is described as 'Pre interview "total" score of student', :696 as '... of school', :703 students_pre_rank_of_school as 'Pre interview rank of student', :704, :708, :711, :716 and :718 likewise. Copy-paste error: :531 applicant_post_interview_rating_error says 'Pre-interview rating error stddev'. :554 says 'Max number of interviews each school can conduct In percent of capacity' for a 0-0.99 fraction. :572 and :577 share an identical 'scoreing' text for pre and post. :609 and :651 say 'USMLE Setp 2', with keys and a 5/10 scale that don't match the generated data (keys come from school_meta_preference; values are 0-1; preference weights sum to 1). :642 and :616 have the same problem. :675 has 'has been applied to the school'; :679 'has been accepted to the school invitation'; :688 'Whether the school has been invited'. :502/:543 say '(>= 0)', implying no upper bound. No help_text at all on school_meta_preference_stddev (:560), Simulation.* (:92-97), Interview.status (:670) or Match ranks (:738-739). A codespell run with a custom dictionary flags models.py:517,527,532,559,572,577,609,651.

**Why it matters.** Wrong wording on the Interview table inverts the meaning of every score and rank column, which is the core output users interpret. The examples teach an attribute scale and naming that the generator never produces.

**Recommendation.** Move all copy into the registry (HELP-8) and apply it at the form layer. Extra §C gives the corrected text for every SimulationConfig field and §D for Simulation, Student, School, Interview and Match fields. For example, students_pre_rank_of_school becomes 'Where this program falls in the applicant's pre-interview ordering (1 = applicant's favourite).' and Student.score_meta becomes 'Applicant attribute scores (0-1) keyed by School Meta Preference names, e.g. {"board_scores": 0.72, "research": 0.55}.'

**Depends on.** HELP-8

**Verifier note (confirmed).** All cited texts checked in nrmps/models.py. The 8 Interview help_texts (693, 696, 703, 704, 708, 711, 716, 718) say 'score/rank of student' on *_of_school fields and the reverse, which reads as swapped. :531 says 'Pre-interview' on a post-interview field. :554 says 'percent' for a value capped at 0.99. :572 and :577 are identical, both with 'scoreing'. 'Setp' appears at :609 and :651. The 5/10 example scale doesn't match the data (the generator produces 0-1 attributes and weights that sum to 1). '(>= 0)' appears at :502/:543. Missing help_text confirmed for :560, Simulation fields, Interview.status and the Match ranks. One line is off by one: the 'has been applied' text is on :674, not :675. The school_interview_limit semantics are worse than a wording problem: with capacity 20, a fraction capped at 0.99 means fewer interviews than positions.

<a id="help-5"></a>

### HELP-5: /documentation/ is a public, developer-facing dump that exposes User internals and omits the simulation engine

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 1.10, 4.4 · **Verification:** confirmed

**Evidence.** nrmps/views.py:557 has @require_GET and no login check (anonymous GET /documentation/ returns 200). The rendered page lists 7 models including User, with the fields password, is_superuser, groups and user_permissions and 30 methods (set_password, check_password, get_session_auth_hash, email_user ...). There are 8 Django-generated get_next_by_*/get_previous_by_* partialmethods with signatures like 'field=<django.db.models.fields.DateTimeField: created_at>', and 11 'ManyToOneRel' reverse-relation rows. excluded_models only lists 'AbstractUser' (views.py:564-567), which isn't what shows. Only the models module is inspected (views.py:639,682), so simulation_engine.py is missing. templates/nrmps/documentation.html:10 is titled '📚 API Documentation' although no API exists; :128-129 tells end users to 'modify the docstrings in your source code'. The nav calls it 'Documentation' (theme/templates/base.html:30,44).

**Why it matters.** This page is the app's only help entry point, and it answers none of an end user's questions (what the NRMP is, what the parameters mean, what to do next). It also discloses implementation detail publicly. TODO.md:120-123 ('API documentation ... interactive API docs') assumes an API that doesn't exist.

**Recommendation.** Rename the nav item to 'Help', pointing at the new /help/ guide (HELP-10), and redirect /documentation/ there with a 301. Move the generator to /help/developer/ behind staff_member_required (or login_required plus settings.SHOW_DEV_DOCS) as nrmps/views_help.py:developer_reference. Exclude User, reverse relations and inherited Django methods, keeping members where inspect.getmodule(obj) is nrmps.models and the qualname owner is the class. Add simulation_engine and nrmps.help.registry as documented modules. Re-scope TODO.md:120-123 to 'developer reference'.

**Verifier note (confirmed).** An anonymous GET of /documentation/ returns 200 (views.py:557 has only @require_GET). Counts from the parsed page: 7 models, and User shows 20 fields and 30 methods (password, is_superuser, groups, user_permissions, set_password, check_password, get_session_auth_hash, email_user). There are 8 get_next_by/get_previous_by entries, 8 'field=<django...' signatures and 11 ManyToOneRel rows. Only the models module is inspected (views.py:639,682), so simulation_engine is absent. The title (documentation.html:10) and the footer text (:128-129) are as cited. One caveat: the listed items are Django's stock AbstractUser field and method names, not user data, so the 'disclosure' is negligible as a security issue. The real defect is that the page is written for developers and is the only help entry point.

<a id="help-6"></a>

### HELP-6: Documentation page overflows horizontally on mobile, and its custom CSS is broken under daisyUI 5

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 1.4 · **Verification:** partially

**Evidence.** Playwright at 390px: documentElement.scrollWidth = 678. Injecting grid-template-columns:minmax(0,1fr) on the outer .grid brings it to 478; shrinking the hero h1 brings it to 390 (no overflow); remaining table cells scroll inside their overflow-x-auto wrapper. Root causes: templates/nrmps/documentation.html:17 '<div class="grid gap-6">' has an implicit auto column that grows to the tables' min-content width, and :10 '<h1 class="text-5xl">' sits in a max-w-md hero. :137-155 uses the daisyUI 4 variables oklch(var(--b2)) and var(--bc). In daisyUI 5.1.12 getComputedStyle gives --b2 = '' while --color-base-200 = 'oklch(98% 0 0)', and code/pre backgrounds compute to rgba(0,0,0,0), overriding the bg-base-300 utility on <pre>. 'prose' has no effect because @tailwindcss/typography isn't installed (theme/static_src/package.json; theme/static/css/dist/styles.css contains only daisyUI's .prose variable hooks).

**Why it matters.** On phones the help page is barely usable (lead fact F7 lists documentation among the overflowing pages). Every future markdown help page will inherit the same unstyled prose.

**Recommendation.** Use 'grid grid-cols-1 gap-6' (or min-w-0 on the cards) and 'text-3xl sm:text-5xl' on the heading. Delete the inline <style> or switch it to var(--color-base-200)/var(--color-base-content). Add break-words / overflow-x-auto to signature <code>. Add '@plugin "@tailwindcss/typography";' to theme/static_src/src/styles.css plus the npm devDependency so the guide's prose renders. Add a Playwright check (scrollWidth <= innerWidth at 390px) for every help page.

**Verifier note (partially).** Reproduced with Playwright at 390px: scrollWidth is 678. With grid-template-columns:minmax(0,1fr) on the outer .grid it becomes 478, matching the finding. getComputedStyle confirms --b2='' while --color-base-200='oklch(98% 0 0)'. code and '.prose pre' backgrounds compute to rgba(0,0,0,0), overriding bg-base-300. There is no @tailwindcss/typography in package.json or in the built CSS. One claim does not reproduce: after also setting the h1 to text-3xl (1.875rem), scrollWidth stays at 462, not 390. The remaining overflow is the collapse-title method signatures, e.g. get_next_by_created_at(self, *, field=<django...>), which extend to about 481px outside any overflow-x-auto wrapper. The recommended fix for signatures (break-words / overflow-x-auto) is therefore required, not optional.

<a id="help-7"></a>

### HELP-7: Action buttons are unexplained, and their confirmation text hides destructive side effects

**Severity:** 🟡 medium (originally high) · **Kind:** defect · **Effort:** S · **Plan:** 1.5 · **Verification:** partially

**Evidence.** templates/nrmps/partials/_population_counts.html:18 confirms '(Re)create students ... This will replace existing students.' In an isolated DB, 80 interviews became 0 after sim.create_students() (Student FK cascade, nrmps/models.py:667). views.py:229-230 only re-renders #population-counts, so the Interviews card keeps showing the stale count. _interview_counts.html:14-27 buttons ('(re)Initialize Interviews', 'Compute Pre-Interview Scores and Rankings') say nothing about prerequisites (config, both populations) or what they compute, and there is no success or failure message after any HTMX action.

**Why it matters.** Users lose downstream results without warning and cannot tell which step to run next or whether a step worked. Contextual help on actions matters as much as help on fields.

**Recommendation.** Add ACTION_HELP entries (key, label, what_it_does, prerequisites, destroys, next_step, anchor) to the registry. Render a '?' next to each button and generate a precise hx-confirm, e.g. 'This deletes 120 students AND 960 interviews with their scores.' with counts from the context. Return hx-swap-oob updates for #interview-counts, and a daisyUI toast via the messages framework or an HX-Trigger header ('Created 120 students'). Disable buttons with a tooltip saying why when prerequisites are missing (TODO.md:153 'Improve error messages for user feedback').

**Depends on.** HELP-8

**Verifier note (partially).** The cascade is confirmed in an isolated DB: 80 interviews became 0 after create_students(), via the Student FK cascade at models.py:667. views.py:229-230 re-renders only #population-counts, so the Interviews card count goes stale, and no success message is shown. 'Delete All' students or schools (_population_counts.html:21-27,60-66) cascades the same way and is not mentioned. One claim is wrong: the Compute button's hx-confirm (_interview_counts.html:25) does list what it computes ('1) Students rate schools, 2) Schools rate students, 3) Compute all rankings'). Only the prerequisites are missing. A missed silent failure: with no saved config, (re)Create Students returns 200 with Count 0 and no message. I would rate this medium, not high. The deleted interviews are derived data that are invalid for a regenerated population and can be recomputed in seconds. The harm is the misleading confirm text and the stale UI, not loss of irreplaceable results.

<a id="help-8"></a>

### HELP-8: Create a single-source-of-truth help registry with automatic consistency checks

**Severity:** 🟡 medium (originally high) · **Kind:** recommendation · **Effort:** M · **Plan:** 4.3 · **Verification:** partially

**Evidence.** Help today is scattered across model help_text (nrmps/models.py), form help_text (nrmps/forms.py:60,74), hard-coded labels (simulation_manage.html) and docstrings. Model help_text is serialized into migrations: codespell finds the 'scoreing' typo in nrmps/migrations/0001_initial.py:398,406 and 0005_alter_school_meta_stddev_and_more.py:77,82, and 0005 is a pure AlterField migration re-stating help_text. The scratch prototype review/help/proto_check.py, reading model metadata, flags 7/20 config fields (DEFAULT_OUT_OF_RANGE x2, NO_HELP, TYPO x3, UNUSED_BY_ENGINE x4) plus 11 other model fields with missing or typo help.

**Why it matters.** Without one source, labels, tooltips, the guide's parameter table and validators drift apart, which is how the 0.99 max vs default 2 conflict happened. Keeping copy in model help_text also creates migration churn for every wording change.

**Recommendation.** Create nrmps/help/registry.py with frozen dataclasses FieldHelp(key, label, short, long_md, formula_tex, unit, typical, status, stage, anchor, related), ActionHelp, ColumnHelp, ChartHelp and PageHelp, with dicts keyed like 'SimulationConfig.applicant_score_stddev'. Read default/min/max at render time from Model._meta.get_field(...).validators, so numbers are never duplicated. In SimulationConfigForm.__init__, apply label and help_text from the registry; leave model help_text blank or stable to stop migration churn. Add nrmps/help/checks.py, registered via django.core.checks in NrmpsConfig.ready(), failing when a form field has no entry, a default is outside its validators, a planned field has no stage, or an anchor is missing from the guide. It runs in 'manage.py check' and CI. Wrap strings in gettext_lazy for later i18n (IDEAS.md:150).

**Verifier note (partially).** Help text is scattered as described, and help_text is serialized into migrations (the 'scoreing' typo is at 0001_initial.py:398,406 and 0005:77,82). Running the reviewer's proto_check.py reproduces '7 / 20' plus the 11 other model-field flags. One evidence claim is false: 0005 is not 'a pure AlterField migration re-stating help_text'. Its 16 AlterFields change defaults and validators, e.g. applicant_score_stddev default 25→2, school_interview_limit 10→0.1, and new MaxValueValidator(0.99/99). The help_text only rides along. The churn argument is also weak: help_text AlterFields are no-op SQL. The registry, the system check via checks.register in AppConfig.ready() and the _meta validator introspection are all technically feasible on Django 6.1.1. Still, fixing the model help_text and rendering it (HELP-1) plus one test gets most of the value. That makes this a medium-importance architectural choice, not high.

<a id="help-9"></a>

### HELP-9: Accessible per-field '?' popover built on daisyUI 5 (not hover-only tooltips)

**Severity:** 🟠 high · **Kind:** recommendation · **Effort:** M · **Plan:** 4.3 · **Verification:** confirmed

**Evidence.** The installed daisyUI is 5.1.12 (theme/static_src/node_modules/daisyui/package.json). It provides tooltip with tooltip-content, dropdown with <details> or popover, fieldset/fieldset-legend/label and validator. The templates still use daisyUI 4 classes form-control, label-text, label-text-alt, input-bordered and card-header, which have 0 matches in theme/static/css/dist/styles.css, so they do nothing. Tailwind scans **/*.{html,py,js} (theme/static_src/src/styles.css), so classes used in templates and registry .py files get compiled at deploy time (entrypoint.sh runs 'tailwind build').

**Why it matters.** A daisyUI tooltip's data-tip text is CSS generated content: not reliably announced by screen readers, not reachable on touch, and limited to short text. The help needs rich content (formula, range, default, link) that keyboard and screen-reader users can reach.

**Recommendation.** Add {% help_icon key %} rendering templates/nrmps/help/_help_icon.html: a <details class='dropdown dropdown-end'> whose <summary> is a btn btn-ghost btn-circle btn-xs, at least 24x24 px (WCAG 2.2 2.5.8), with aria-label 'Help: <label>'. The content panel is a dropdown-content card holding short text, long markdown, KaTeX formula, a range/default/typical table, a status badge and a 'Learn more' link to /help/<page>#<anchor>. A small Alpine helper closes it on Escape or click-outside and returns focus to the summary. The short text also stays visible under the input (HELP-1) so assistive tech gets it via aria-describedby. Use the daisyUI tooltip only as a sighted-hover enhancement on compact table headers. Optionally, Django 5.x Field.template_name or Form.bound_field_class can make {{ field.as_field_group }} include the icon automatically. See extra §E for the markup.

**Depends on.** HELP-8

**Verifier note (confirmed).** Confirmed in theme/static_src/node_modules/daisyui (v5.1.12): tooltip-content, fieldset-legend, dropdown with <details> and [popover] support, dropdown-end, modal-end and validator-hint all exist. form-control, label-text and input-bordered don't, and they have 0 matches in the built CSS. styles.css has @source "../../../**/*.{html,py,js}", and entrypoint.sh runs tailwind build. btn-xs gives --size = 0.25rem*6 = 24px, which meets WCAG 2.2 SC 2.5.8 (24x24 CSS px). Django 6.1 has Field.template_name and Form/Field.bound_field_class. Minor corrections: card-header was never a daisyUI 4 class (it comes from Bootstrap). daisyUI 5's .tooltip-content is a real DOM element, not CSS generated content, so only the data-tip variant has the screen-reader problem. Both variants are still hover/focus-only, so the <details> popover choice stands.

<a id="help-10"></a>

### HELP-10: No user guide: nothing explains the NRMP, the stages, the model, CSV formats or terms

**Severity:** 🟠 high · **Kind:** gap · **Effort:** L · **Plan:** 4.4 · **Verification:** confirmed

**Evidence.** The only pages are index, account, contact, privacy, terms, documentation and the simulation pages (nrmps/urls.py:9-47); /help/ returns 404. The index (templates/nrmps/index.html:24-30) has a 4-line Quick Start. TODO.md:125-128 lists 'User documentation: user guide, CSV format, troubleshooting' as not started. markdown-it-py 4.2.0 is already in uv.lock as a dependency of rich 15.0.0 (pulled in by logfire).

**Why it matters.** This is a research and teaching tool with non-obvious statistics. Without a guide users can't configure meaningful experiments, interpret results, or trust the model.

**Recommendation.** Add /help/ (nrmps:help_index) and /help/<slug>/ (nrmps:help_page), rendered from nrmps/help/content/guide/NN-slug.md. Use markdown-it-py plus mdit-py-plugins (front_matter, anchors, dollarmath, deflist, admon, container), cached with functools.lru_cache in nrmps/help/render.py. Shortcodes {{param_table}}, {{glossary}} and {{csv_spec:students}} expand from the registry. Layout: daisyUI menu sidebar TOC, prev/next links, and an 'On this page' anchor list. Vendor KaTeX in static/vendor/katex/ and load it only in help pages' extra_head (latex2mathml is a zero-JS server-side alternative). Add '@source "../../../nrmps/help/content/**/*.md";' if markdown emits daisyUI classes such as admonitions mapped to alert. The full outline is in extra §B.

**Depends on.** HELP-8

**Verifier note (confirmed).** /help/ returns 404, and nrmps/urls.py:9-47 has no guide route. index.html:24-30 has only a 4-item Quick Start, and TODO.md:125-128 is unstarted. uv.lock has markdown-it-py 4.2.0 as a dependency of rich 15.0.0, which comes from logfire 5.1.0 (and cookiecutter). It should be declared as a direct dependency rather than relied on transitively. mdit-py-plugins is not installed and would need adding. It does provide front_matter, anchors, dollarmath, deflist, admon and container. The @source path relative to theme/static_src/src/styles.css is correct. latex2mathml is a real server-side option.

<a id="help-11"></a>

### HELP-11: Model & formulas page with executable worked examples tied to the engine

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 4.4 · **Verification:** confirmed

**Evidence.** The math exists only in docstrings: Beta method of moments at nrmps/models.py:40-50, clamping at :33-35 and :53-54, weights at :156-166, utility at simulation_engine.py:4-10. It is partly wrong (HELP-3), and the planned stages (simulation_engine.py:167-190) have no written specification.

**Why it matters.** Users and reviewers need the exact generative model to interpret results or cite the tool. Once the engine changes, prose formulas will silently go stale unless something tests them.

**Recommendation.** Write guide page 03-model.md with KaTeX blocks for: the Beta parametrisation and feasibility limit σ < √(μ(1−μ)) with the clamping rule; attribute scores a ~ Beta(b, σ_meta); weights w = clip(N(1, σ_w), 0.01, 2)/Σ; utility U_ij = Σ_k w_ik·a_jk; observation Û = U + ε; the ranking rule; and the planned invitation, interview, ROL and applicant-proposing deferred-acceptance steps, each with an Implemented/Planned badge. Add tests/test_help_examples.py: the guide's worked example (e.g. weights {a: 0.5, b: 0.5}, attributes {a: 0.8, b: 0.4} gives U = 0.6) runs through simulation_engine._score and the population generators with a fixed seed, so docs and code can't diverge.

**Depends on.** HELP-10, HELP-3

**Verifier note (confirmed).** The cited math locations are accurate: method of moments at models.py:40-50, clamping at :33-35/:53-54, weights at :156-166, utility at simulation_engine.py:4-10. The formulas are right: the Beta feasibility condition var < mu(1-mu), clip(N(1,σ),0.01,2) normalised, and U = Σ w·a. The worked example checks out (0.5*0.8 + 0.5*0.4 = 0.6), and _score(...) with rating_error=1 reproduces it today. NRMP does use applicant-proposing deferred acceptance (Roth-Peranson).

<a id="help-12"></a>

### HELP-12: Per-page help panel (navbar '?' plus the '?' key) loaded lazily via HTMX

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 4.3 · **Verification:** confirmed

**Evidence.** theme/templates/base.html:17-65 navbar has no help affordance; no page explains its own purpose or next step (screenshots desktop_sim_manage.png, desktop_interviews.png).

**Why it matters.** Field popovers answer 'what is this input?' but not 'what is this page for and what do I do next?'. That page-level question is the main blocker for new users on the manage page.

**Recommendation.** In base.html, add a '?' button (btn btn-ghost btn-circle, aria-label 'Help for this page') and a global Alpine '?' shortcut, ignored inside inputs and shown with <kbd>. Both open <dialog id='help-panel' class='modal modal-end'>: native dialog gives focus trap, Escape and focus return, and daisyUI 5 ships modal-end. Load content on first open with hx-get='{% url "nrmps:help_panel" page_key %}' hx-trigger='click once' into #help-panel-body. Each template sets {% block help_key %}; content lives in nrmps/help/content/pages/<key>.md with sections 'What this page is', 'Do this next', 'Buttons and what they change', 'Columns', 'Learn more'. Include pages simulations_list, simulation_form, simulation_manage, students_list, schools_list, interviews_list, and later results/visualizations.

**Depends on.** HELP-8, HELP-10

**Verifier note (confirmed).** base.html:17-65 has no help affordance. daisyUI 5 ships modal and modal-end, and `hx-trigger='click once'` is valid htmx. Native <dialog>.showModal() makes the rest of the page inert, closes on Escape, and modern browsers restore focus on close. Feasible as described.

<a id="help-13"></a>

### HELP-13: Live parameter previews and a market-summary strip next to the config inputs

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 4.2 · **Verification:** confirmed

**Evidence.** Parameter effects are non-obvious (check_defaults.py). Requesting mean 0.7, sd 2 gives an effective mean of 0.621 and sd 0.431 (U-shaped). Mean 0 with sd 2 gives an effective mean of 0.299. Preference sd 3 clamps 74% of weights. Capacity N(20,10) leaves 2.6% of programs with 0 positions, versus about 0.001% for N(18,4). Lead fact F4: Applicants x Schools interview rows run synchronously (up to 10M).

**Why it matters.** The most useful help for distribution parameters is showing their effect before generating. A preview built on the same Python as the generator can't drift from it. This is the help-side complement to the visualization dimension's sliders.

**Recommendation.** Add GET /simulations/preview/distribution/?kind=beta|normal_capacity|weights&mean=&sd= (nrmps/views_help.py:preview_distribution). It reuses get_beta_parameters and scipy.stats and returns a small server-rendered inline SVG (about 120x36 px, 40-point pdf path) plus the text 'effective mean 0.62 / SD 0.43', with a badge-warning when clamped or bimodal. Wire it with hx-get, hx-trigger='input changed delay:300ms' and hx-include over the paired mean/SD inputs. Add a daisyUI 'stats' strip computed by nrmps/config_checks.py:check_config(cfg) -> list[ConfigHint]: total positions, applicants per position, interview rows (warning above about 250k), and interview slots from programs vs applicants. Each hint links to its FAQ entry.

**Depends on.** HELP-8, HELP-2

**Verifier note (confirmed).** My runs match the numbers: mean 0.7 / sd 2 gives effective mean 0.621 / sd 0.431, mean 0 / sd 2 gives 0.299, and sd 3 clamps 74%. P(capacity rounds to <=0) is 2.56% for N(20,10) and 0.0006% for N(18,4), which is 'about 0.001%' within rounding. get_beta_parameters and scipy.stats can be reused directly, and `input changed delay:300ms` plus hx-include are valid htmx. Feasible.

<a id="help-14"></a>

### HELP-14: First-run guidance is wrong or missing: fix the home Quick Start, add a stage checklist, an example preset and an optional tour

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 0.7, 4.5 · **Verification:** confirmed

**Evidence.** templates/nrmps/index.html:26 'Log in via the Admin to manage data.' is wrong: users sign up, and admin requires staff (demo user is_staff False; /admin/password_change/ redirects to /admin/login/). :28 'Run interviews and simulate the match.' describes features that aren't implemented. :14-17: the primary call to action is 'Go to Account' and Privacy/Terms are hero buttons, with no link to Simulations or help (desktop_home.png). The manage page has no progress indicator; TODO.md:40-43 wants 'progress indicators ... step-by-step wizard ... status dashboard'.

**Why it matters.** New users land on a page that sends them to the wrong place and promises features that don't exist. Nothing tells them the 8-stage order or what is still planned.

**Recommendation.** Rewrite the hero: 'Simulate the residency Match', with CTAs 'Get started' (signup, or simulations when logged in), 'Try an example' and 'Read the guide', a 3-sentence NRMP explainer, and a Quick Start that matches the real flow. Add nrmps/progress.py:simulation_progress(sim) -> list[Step(key, label, status: done|current|blocked|planned, help_anchor, action_url)], rendered as daisyUI <ul class='steps steps-vertical lg:steps-horizontal'> at the top of simulation_manage, each step with a '?' link. Add a 'Create example simulation' action that loads a preset (e.g. 120 applicants x 8 programs, capacity 12±3) used by the tutorial. An optional Driver.js tour (MIT, vendored) can come later, with dismissal stored in User.onboarding_dismissed_at or localStorage.

**Depends on.** HELP-10

**Verifier note (confirmed).** index.html:26 says 'Log in via the Admin'. For the demo user (Is Staff: False), /admin/password_change/ returns 302 to /admin/login/. :28 promises features that aren't implemented. The :14-17 hero buttons are Account/Contact/Privacy/Terms, with no link to Simulations or help. The manage page has no progress indicator (TODO.md:40-43). daisyUI 5 has steps and steps-vertical, and Driver.js is MIT-licensed.

<a id="help-15"></a>

### HELP-15: CSV formats are undocumented in the UI and inconsistent in code; a download-then-upload round trip silently drops preferences

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 1.7 · **Verification:** confirmed

**Evidence.** Formats appear only in docstrings (nrmps/models.py:281-285, 370-374) and unrendered form help (HELP-1). Round trip in an isolated DB: meta_preference before download/upload was {'program_size': 0.375, 'reputation': 0.306, 'location': 0.319}; after, {} (the download at views.py:293 and the upload at models.py:329-361 have no meta_preference column). With empty preferences, _score returns 0 for every pair, so rankings are arbitrary. The schools positional fallback reads score_meta from the 5th column with a legacy meta_stddev in the 4th (models.py:414-421), contradicting the documented 'name,capacity,score[,score_meta]'. Bad numbers are silently coerced to 0.0 (models.py:318-321, 342-344, 406-413), and views.py:251-260 gives no feedback on invalid uploads.

**Why it matters.** Users bringing their own data (a key use case in CLAUDE.md 'CSV upload/download for custom populations') have no spec, no sample and no error report. The exported file can't be re-imported faithfully.

**Recommendation.** Add nrmps/help/csv_specs.py (CSV_SPECS: per file, the column, type, required, range, example, notes). It drives the guide's 'CSV formats' page and the upload validator's messages. Ship static/samples/students_sample.csv and schools_sample.csv, linked beside each upload input and in the guide. Add a meta_preference JSON column to download and upload, or document the loss prominently. Return an upload summary in the partial ('118 rows imported, 2 rows had invalid score and were skipped (lines 14, 37)'). Matches TODO.md:52, 127 and 158.

**Depends on.** HELP-8

**Verifier note (confirmed).** Round trip reproduced in an isolated DB. The download header is 'name,score,score_meta', and after re-upload meta_preference is {}. Every student→school pre score then equals 0.0 (set {0.0}). A bad score is silently coerced ('abc'→0.0). An upload with no file returns the partial with no message. For the positional schools fallback, JSON in the 4th column is ignored (score_meta={}) and read only from the 5th. The finding misses a worse case: uploading the documented minimal format 'name,score' (score_meta optional per models.py:281) and then running Compute Pre-Interview returns HTTP 500. _score raises KeyError, which simulation_engine.py:94 re-raises as a bare Exception. The spec must say score_meta is effectively required, with every School Meta Preference key.

<a id="help-16"></a>

### HELP-16: List-page column headers are ambiguous and unexplained

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** S · **Plan:** 1.5 · **Verification:** confirmed

**Evidence.** templates/nrmps/interviews_list.html:72 'Student Pre Score', :82 'School Pre Score', :92 'Student Rank' and :102 'School Rank' don't say who rates whom, and :62 'Status' always shows 'initialized' (lead fact F5). templates/nrmps/students_list.html:58-60 and schools_list.html:68-70 show 'Score Meta', 'Pref Stddev' and 'Meta Preference' as raw JSON with 16-decimal floats.

**Why it matters.** The Interviews table is the main output so far. Combined with the swapped help_text (HELP-4), users are likely to misread 'Student Rank' as the student's position rather than the student's rank of the program.

**Recommendation.** Rename the headers: 'Applicant's rating of program (pre)', 'Program's rating of applicant (pre)', 'Applicant's rank of program', 'Program's rank of applicant'. Add a COLUMN_HELP '?' or tooltip-bottom on each <th> from the registry, plus a one-line legend above the table ('Rank 1 = most preferred'). Render JSON columns as key: value chips with floatformat:3. Link 'Status' values to the glossary.

**Depends on.** HELP-8, HELP-9

**Verifier note (confirmed).** The headers at interviews_list.html:62,72,82,92,102 and students_list.html:58-60 / schools_list.html:68-70 are as cited. Rendered pages show Python dict repr with 16-decimal floats (e.g. 'board_scores': 0.5349750037692191) and Status 'initialized' on every row.

<a id="help-17"></a>

### HELP-17: Validation and error messages are not user-friendly, not linked to help, and some are missing

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** S · **Plan:** 1.6 · **Verification:** confirmed

**Evidence.** templates/nrmps/simulation_manage.html:69-73 prints raw keys with CSS capitalize ('School_meta_preference_stddev: * Ensure this value is less than or equal to 0.99.'). :231-235 school_capacity_stddev has no inline error block. Simulation.description is required (nrmps/models.py:94, TextField without blank=True): creating a simulation with an empty description returns 'This field is required.' although the form (simulation_form.html:27-32) doesn't mark it required. Uploads with an invalid form fail silently (views.py:251-260). Widgets allow values the validators reject: min=0 on number_of_applicants (forms.py:163) vs MinValueValidator(1), and step='any' on the integer applicant_interview_limit (forms.py:167).

**Why it matters.** Error text is where users most need help, and today it names internal fields and gives no reason or fix.

**Recommendation.** Build the summary from bound fields: {% for f in config_form %}{% if f.errors %}<a href='#{{ f.auto_id }}'>{{ f.label }}</a>: {{ f.errors.0 }}{% endif %}{% endfor %}. Write custom messages that give the range and the reason (e.g. 'SD must be below 0.458 when the mean is 0.7 - see Help > Scores'). Use daisyUI 5 'validator' plus 'validator-hint' for client-side range hints, with min/max/step from the model validators. Make description blank=True (or mark it required with an asterisk). Surface upload errors and HTMX action results through toasts.

**Depends on.** HELP-8, HELP-1

**Verifier note (confirmed).** Confirmed: raw capitalised keys at simulation_manage.html:69-73; no error block for school_capacity_stddev at :231-235. SimulationForm with an empty description is invalid ('This field is required.'), while simulation_form.html:31 renders the textarea without `required`. The widgets are forms.py:163 min=0 against MinValueValidator(1) and :167 step=any on an IntegerField. The finding missed a worse case: the manage page's Edit Simulation card (simulation_manage.html:26-45) renders no field errors at all. POSTing iterations=150 (widget min=1 but no max; validator max 100) returns 200, is not saved, and shows no message; only a dangling aria-describedby='id_iterations_error' remains. daisyUI 5 validator/validator-hint exist.

<a id="help-18"></a>

### HELP-18: Glossary and inline term definitions

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** S · **Plan:** 4.4 · **Verification:** confirmed

**Evidence.** Domain terms appear undefined in labels and copy: 'meta preference', 'meta scores', 'rating error', 'interview limit', 'Pre', 'signal' (nrmps/models.py:676), 'SOAP' and 'couples' (TODO.md:69-72), 'deferred acceptance' (TODO.md:22).

**Why it matters.** The audience mixes medical educators, economists and students; each group lacks the other groups' vocabulary.

**Recommendation.** Add nrmps/help/glossary.py (GLOSSARY: slug -> Term(term, short, long_md, see_also)) and a {% term 'rank-order-list' %} tag that renders a dotted-underline button opening the same popover as HELP-9. Generate the glossary page with <dfn id> anchors. Terms: applicant, program (stored as School), position/quota/capacity, base score, attribute (meta) score, preference weight, utility, true vs observed score, rating error, application, interview invitation, interview limit, preference signal, rank order list, applicant-proposing deferred acceptance (Roth-Peranson), stable matching, blocking pair, unmatched applicant, unfilled position, SOAP, couples match, iteration, random seed.

**Depends on.** HELP-10

**Verifier note (confirmed).** Terms are used undefined: 'signal' at models.py:676, SOAP/couples at TODO.md:70-71, deferred acceptance at TODO.md:22. The term list is accurate NRMP/matching vocabulary.

<a id="help-19"></a>

### HELP-19: Choose one UI vocabulary: Applicant/Program vs Student/School

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** S · **Plan:** 1.6, 2.3 · **Verification:** confirmed

**Evidence.** index.html:11 says 'applicants, programs'; the config labels say 'Applicant Score Mean' and 'School Score Mean' (simulation_manage.html:110,205); the cards and lists say 'Students' and 'Schools' (_population_counts.html:4,43). In the NRMP, applicants match to residency programs, not schools; medical schools are where applicants come from.

**Why it matters.** Mixed terms make help text longer and confusing, and 'School' misleads domain experts, who are the core audience.

**Recommendation.** Show 'Applicant' and 'Program' everywhere via Model Meta verbose_name, registry labels and template copy, keeping the code identifiers. Add a glossary note 'Program (called School in exports/CSV)'. Optionally let CSV headers accept both.

**Depends on.** HELP-8

**Verifier note (confirmed).** The mixed vocabulary is confirmed (index.html:11 'programs'; simulation_manage.html:110 'Applicant' vs :205 'School'; _population_counts.html:4,43 'Students'/'Schools'). The NRMP matches applicants to residency programs, so 'School' is misleading.

<a id="help-20"></a>

### HELP-20: Docstring and comment inaccuracies that feed the generated docs

**Severity:** ⚪ low · **Kind:** defect · **Effort:** S · **Plan:** 1.6 · **Verification:** partially

**Evidence.** nrmps/models.py:83 'links to the others parts'; :85-88 inconsistent indentation and omits delete_students/delete_schools; :109 'applicants_score_mean' (the field is applicant_score_mean); :270,274 annotated '-> int' but return None; :517 'preferacnes', :527/:532 'stdsdev ... computer the', :559 'preferances'; :584 generate_meta_scores(self, ...) is a module-level function with an invalid 'dict[str:float]' annotation, and unused; :728-733 Match docstring 'records the match status between each student and school' (it should hold matched pairs only). nrmps/simulation_engine.py:5 '_score ... for a student' is used in both directions; :4 'meta_preferances' (already TODO.md:147-148); :39 'Students choose which schools they would like to apply to' is wrong (it only computes scores); :167 interview(self) is module-level. nrmps/forms.py:86 mentions dict fields the form doesn't have.

**Why it matters.** These strings are published verbatim on the current docs page and will feed the developer reference, so they mislead both users and contributors.

**Recommendation.** Fix them in one docstring pass with the corrections above, and adopt Google-style Args/Returns sections (CLAUDE.md:177 already requires docstrings). Add codespell to CI with a project dictionary: the default dictionary only caught models.py:559, while a custom dictionary (scoreing->scoring, setp->step, preferacnes->preferences, stdsdev->stddev) caught all 8 plus the migrations. Also ignore-list 'thead'.

**Verifier note (partially).** Every cited inaccuracy exists at the cited line (models.py:83, 85-88, 109, 270/274 '-> int' returning None, 517/527/532/559 typos, 584 invalid 'dict[str:float]', 728-733; simulation_engine.py:4, 5, 39, 167; forms.py:86). Default codespell reproduces with only models.py:559 flagged. The framing 'feed the generated docs' and 'published verbatim' is only partly true. The docs page inspects only nrmps.models docstrings. The typos at 517/527/532/559 are # comments, and the simulation_engine and forms docstrings are not published at all.

<a id="help-21"></a>

### HELP-21: Placeholder contact details and a dead-end 'Change password' link

**Severity:** ⚪ low · **Kind:** defect · **Effort:** S · **Plan:** 0.7 · **Verification:** confirmed

**Evidence.** templates/nrmps/contact.html:9 'support@example.com' and :10 'https://github.com/'; the real repository is github.com/vincentdavis/NRMP_Simulated (git remote). templates/nrmps/account.html:13 links to /admin/password_change/, which redirects the non-staff demo user to /admin/login/?next=... (curl: 302). :6 uses the Bootstrap class 'text-muted'.

**Why it matters.** 'Where do I get help?' leads to fake addresses, and account self-service doesn't work for normal users.

**Recommendation.** Link to https://github.com/vincentdavis/NRMP_Simulated/issues, with issue templates for 'question' and 'bug', and a real contact or a discussion board. Add PasswordChangeView/PasswordChangeDoneView at /account/password/ with templates. Replace text-muted with text-base-content/70.

**Verifier note (confirmed).** contact.html:9-10 has support@example.com and a bare https://github.com/, while the git remote is github.com/vincentdavis/NRMP_Simulated. account.html:13 links to /admin/password_change/, which returns 302 to /admin/login/ for the non-staff demo user. :6 uses Bootstrap's text-muted.

<a id="help-22"></a>

### HELP-22: No README, and developer docs are duplicated and stale

**Severity:** ⚪ low · **Kind:** gap · **Effort:** S · **Plan:** 1.10 · **Verification:** partially

**Evidence.** The repo root has no README* (ls). pyproject.toml has description = 'Add your description here'. Developer docs live in CLAUDE.md, duplicated almost verbatim in .junie/guidelines.md (7275 vs 7181 bytes), with stale line references (CLAUDE.md cites match() at line 188, TODO.md:21 at 189).

**Why it matters.** The GitHub landing page gives no overview, screenshots or links to the hosted guide. Contributors have to reconcile two agent-oriented files.

**Recommendation.** Add README.md (what and why, a screenshot, the hosted URL, a quick start, a link to /help/) and docs/ for developer topics (architecture, data model, simulation engine spec, help-authoring guide: 'to add a parameter, add a FieldHelp entry; manage.py check enforces it'). Make CLAUDE.md and .junie point at docs/ instead of duplicating it, and fix the pyproject description.

**Verifier note (partially).** Confirmed: no README tracked or in the root; pyproject description is 'Add your description here'; .junie/guidelines.md (7181 B) duplicates CLAUDE.md (7275 B), differing only in the header and line wrapping. The 'stale line references' claim is wrong for CLAUDE.md: interview() at 167, students_rank at 175, schools_rank at 183 and match() at 188 are all currently correct. Only TODO.md:21 is off by one (it cites 189, the docstring line).

<a id="help-23"></a>

### HELP-23: 'About this model' page: assumptions, limitations, version, reproducibility and citation

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** S · **Plan:** 4.4 · **Verification:** partially

**Evidence.** There is no version or changelog anywhere in the UI; exports (views.py:286-313, 524-554) don't record the config or code version; Simulation has no seed field; IDEAS.md:128-132 calls for 'Reproducible research features ... publication-ready output'.

**Why it matters.** Research users need to know what is and isn't modelled (no couples, SOAP or signals; full cross-product applications; current noise bug) and to be able to reproduce and cite a run.

**Recommendation.** Add guide page 11-about.md covering assumptions and limitations, a changelog, 'How to cite' (a CITATION.cff in the repo) and privacy. Show the app version from importlib.metadata.version('nrmp-simulated') in the footer and in CSV headers or comments. Add a SimulationConfig.random_seed field (help: 'Leave blank for random; set an integer to reproduce a run exactly'), and have export files include the config JSON.

**Depends on.** HELP-10

**Verifier note (partially).** The gap is real: no seed field, no version in the UI, and the exports (views.py:286-313, 524-554) carry no config. One technical detail is wrong. importlib.metadata.version('nrmp-simulated') raises PackageNotFoundError here: pyproject.toml has no [build-system], so uv treats it as a virtual project and doesn't install it (verified). Use a __version__ constant, tomllib on pyproject.toml, or the deploy's git SHA instead.

<a id="help-24"></a>

### HELP-24: Automated quality gates for help content

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** S · **Plan:** 1.1, 4.7 · **Verification:** partially

**Evidence.** nrmps/tests.py is empty (lead fact F6). Every defect in HELP-1, 2, 4 and 6 is mechanically detectable: the proto_check.py and overflow scripts in the scratch review/help/ directory found them.

**Why it matters.** Help rots silently unless CI enforces coverage, accuracy, links and accessibility.

**Recommendation.** Add tests/test_help_registry.py: every form field, action, column and chart has an entry; defaults are within the validators and pass SimulationConfigForm(...).is_valid(); planned entries have a stage. Add tests/test_help_pages.py: each /help/ page returns 200; all internal anchors and 'Learn more' links resolve; no dangling aria-describedby on manage pages. Add an optional Playwright suite: popover opens with Enter/Space, closes with Escape and returns focus; the help dialog traps focus; scrollWidth <= 390 on mobile; @axe-core/playwright reports no serious violations. Run codespell with the project dictionary in pre-commit or CI.

**Depends on.** HELP-8, HELP-10

**Verifier note (partially).** The recommendation is sound, and nrmps/tests.py is empty. The evidence claim that every defect in HELP-1, 2, 4 and 6 is mechanically detectable and was found by proto_check.py and the overflow scripts is overstated. proto_check's regex catches only typos and missing help. It did not flag HELP-4's swapped student/school wording, 'Pre-interview' on the post field, or '(>= 0)'. Those need human review or targeted assertions.

<a id="help-25"></a>

### HELP-25: Extend the registry to chart help, help search and i18n

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** S · **Plan:** 5.1 · **Verification:** confirmed

**Evidence.** The planned visualizations (TODO.md:45-48; IDEAS.md:94-104) will each need a 'how to read this chart' note. IDEAS.md:150-153 plans multi-language support.

**Why it matters.** Designing the registry once for fields, actions, columns, pages and charts avoids a second help system when the visualization work lands.

**Recommendation.** Add CHART_HELP entries (what it shows, how to read it, what the sliders do, caveats) rendered by the same help_icon in each chart card header. Add a client-side search on /help/ (Alpine filter over a JSON index of the registry, glossary and guide headings, emitted by a json_script tag). Wrap registry strings in gettext_lazy and keep markdown under content/<lang>/ when translation starts.

**Depends on.** HELP-8

**Verifier note (confirmed).** Planned visualizations (TODO.md:45-48, IDEAS.md:94-104) and i18n (IDEAS.md:150-153) exist as cited. Django's json_script and gettext_lazy support the approach; it is feasible.

<a id="opt"></a>

## OPT: Improved simulation options / parameter model

> **Reviewer summary.** The current SimulationConfig is not a usable experiment specification yet. Its defaults fail its own validators, so a new user cannot save the default form. Its standard deviations have no defined units and are silently clamped, which produces 0/1 (Bernoulli-like) populations. The "rating error" scales scores instead of adding noise, and 0 is silently replaced with 1.0. Five of its 20 fields plus Simulation.iterations are never read (the two interview limits, the two post-interview errors, iterations), and school_interview_limit has the wrong unit (a fraction ≤ 0.99 of capacity, i.e. fewer interviews than positions). There is no seed, the config is edited in place with no snapshot, and preference correlation is an accident of meta-score noise rather than a parameter. All of this was shown by running code in an isolated DB (probe_defaults.py and probe_flow.py). I propose replacing the flat 20-field model with a versioned, typed parameter schema organised by stage (market, populations with applicant groups, a common+idiosyncratic utility model with one preference-correlation knob per side, applications/strategy, signals, invitations, interview, rank lists, match, run/replicates). Every run should store a config snapshot and a SeedSequence-based seed, and the schema should drive the form, the '?' help, presets and JSON import/export. A vectorised numpy prototype of the proposed pipeline (applications → signals → invitations → interview cap → rank lists → applicant-proposing deferred acceptance) runs 2,400×300 in about 1.1 s. It shows the new knobs move outcomes a lot: preference correlation 0→0.95 moves the first-choice share from 72% to 28%; top-N vs portfolio applications moves the match rate from 0.77 to 0.92; and 80 applications without backfill cuts the match rate to 0.83. A rough parameter setting already gets close to NRMP 2026 aggregates (≈80% overall, 55–60% IMG match), so a calibrated preset is feasible. Priorities: MUST = fix defaults, noise and seeding, snapshot runs, the typed schema, the core stage parameters and Monte-Carlo; SHOULD = signals, invitation, interview and rank-list behaviour, groups, presets, sweeps and cloning; COULD = specialties, couples/SOAP, geography, application costs.

<a id="opt-1"></a>

### OPT-1: MUST: The default config fails its own validation, and population actions silently do nothing without a saved config

**Severity:** 🟠 high (originally critical) · **Kind:** defect · **Effort:** S · **Plan:** 0.2 · **Verification:** partially

**Evidence.** nrmps/models.py:560-568 (school_meta_preference_stddev default=2 and school_meta_scores_stddev default=2, both with MaxValueValidator(0.99)). probe_flow.py (Django test client, isolated DB): submitting the config form exactly as rendered -> 200, 'configs saved: 0', errors ['school_meta_preference_stddev: Ensure this value is less than or equal to 0.99', 'school_meta_scores_stddev: ...']. SimulationConfig(simulation=s).full_clean() raises the same two errors. POST /simulations/1/create-students/ before any config is saved -> 200, 'students: 0 configs: 0' with no message (nrmps/models.py:118-121 returns 0; views.py:224-230 re-renders the counts). Also, Simulation.description (models.py:94, TextField(default='') without blank=True) is required, so creating a simulation with an empty description fails ('description: This field is required').

**Why it matters.** A first-time user goes New simulation -> (re)Create Students (nothing happens) -> Save Configuration (validation errors on two fields they never touched). The first-run experience is broken, and the error text ('<= 0.99' for a standard deviation) does not tell the user what the field means.

**Recommendation.** (1) Make defaults satisfy validators. With the redesign (OPT-3/OPT-9) the ranges become meaningful, e.g. correlation 0-1 and noise SD 0-3. (2) In views.simulation_create, create a default SimulationConfig (or a preset from OPT-20) in the same transaction, so every simulation has a valid config. (3) In simulation_create_students/_schools, return an HTMX error toast ('Save a configuration first') when no config exists instead of silently rendering 0. (4) Add blank=True to Simulation.description. (5) Add a unit test that SimulationConfigForm(initial defaults).is_valid() is True, so defaults cannot drift from validators again.

**Verifier note (partially).** Reproduced everything in an isolated DB (optverify/v1.py). SimulationConfig(simulation=s).full_clean() and SimulationConfigForm(initial defaults) both fail on exactly school_meta_preference_stddev and school_meta_scores_stddev ('<= 0.99'). The rendered inputs have no max attribute, so the browser posts and the server rejects. POST create-students with no config returns 200 with count 0 and no message. An empty description gives 'This field is required'. The core claim holds. Severity is high rather than critical: the error names the two fields, the user can fix it by editing two values, and nothing is lost.

<a id="opt-2"></a>

### OPT-2: MUST: 'Rating error' is a multiplier, not noise; rating_error=0 is silently turned into 1.0; true scores are never stored

**Severity:** 🟠 high (originally critical) · **Kind:** defect · **Effort:** S · **Plan:** 0.3 · **Verification:** partially

**Evidence.** nrmps/simulation_engine.py:10 returns sum(meta*w) * rating_error. simulation_engine.py:50 and :81 use float(getattr(cfg, '...rating_error', 1.0) or 1.0), and 0.0 is falsy. probe_defaults.py sec.4: observed/true ratio min=0.100000 max=0.100000 ('pure scaling, zero noise'). sec.6: error=0 -> observed=0.9607 == true=0.9607. student_true_score_of_school / school_true_score_of_student (models.py:681, 698) are populated: False. Builds on lead fact F5.

**Why it matters.** The only source of information friction in the model (pre- vs post-interview uncertainty) does nothing, so the interview stage can never add information. The zero case ('perfect information'), which is the natural control scenario, is impossible. With no stored true utility, the gap between observed and true outcomes (the key welfare metric) cannot be computed.

**Recommendation.** Define all utilities on a standardised latent scale (SD 1). Compute true_u = utility(...) and observed = true_u + rng.normal(0, sigma_pre). Store true_u in Interview.student_true_score_of_school / school_true_score_of_student. Replace the four *_rating_error fields with info.applicant_pre_noise_sd, info.program_pre_noise_sd (default 0.5, range 0-3) and info.interview_informativeness kappa in [0,1], with sigma_post = sigma_pre*(1-kappa), plus an optional fit_shock_sd (OPT-17). Read the config through the typed params object (OPT-9) so there are no getattr(..., 1.0) or 1.0 fallbacks. Add an engine test: sigma=0 means observed == true and pre-ranks == true ranks.

**Verifier note (partially).** Confirmed: _score multiplies by rating_error (simulation_engine.py:10), and `or 1.0` turns 0 into 1.0 (:50, :81). My run gives observed/true = 0.100000 for every pair, error=0 gives observed 0.0479 == true 0.0479, and the true_score fields are never written (grep). One claim is backwards: 'the zero (perfect-information) case is impossible'. Because the error is a pure positive multiplier, every setting already gives perfect information (observed ranks = true ranks), and 0 maps to exactly the true score. What is impossible is imperfect information. The 0->1.0 fallback actually prevents an all-zero, all-tie scoring. I rate it high rather than critical: it is a core modelling defect, but no downstream stage exists yet, and F5 already records it.

<a id="opt-3"></a>

### OPT-3: MUST: Beta-based generation with undefined SD units gives 0/1 populations and does not honour the requested mean

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 2.1 · **Verification:** partially

**Evidence.** nrmps/models.py:33-35 silently caps the SD at 0.9*sqrt(m(1-m)); models.py:53-54 floors alpha/beta at 0.1, which shifts the mean. Defaults: applicant_score_stddev=2 (models.py:499-503, max 99), applicant_meta_scores_stddev=10, school_score_mean=0 / stddev=2. probe_defaults.py sec.2: applicant (0.7, 2) -> alpha=0.164, beta=0.100, realised mean 0.617, sd 0.432, 24% < 0.05, 40% > 0.99. School (0, 2) -> realised mean 0.296 (requested 0), 54% < 0.05. Meta scores (any base, sd >= 2) -> alpha=beta=0.117, 36%/36% at the two extremes (Bernoulli-like). sec.3: school scores [0.637, 0.0, 0.034, 0.922, 0.0, 1.0, 1.0, 0.013, 0.918, 0.0]; 91 of 200 students have score > 0.99, violating Student.score MaxValueValidator(0.99) (models.py:601-603), which bulk_create does not enforce (also the source of F3's pending migration). Sanity case (0.5, 0.15) -> sd 0.151, well behaved.

**Why it matters.** Every default population is degenerate: attributes are coin flips with p = base score, so the base score barely drives preferences (see OPT-4: Spearman of student rank vs school base score = 0.14). Users cannot reason about 'stddev 10' on a 0-1 scale, and values they type are silently rewritten.

**Recommendation.** Generate latent quantities on an unbounded z-scale: strength_i ~ N(group_mean, group_sd), quality_j ~ N(0, quality_sd). Generate attributes with an explicit correlation knob instead of an SD: x_im = r_m*strength_i + sqrt(1-r_m^2)*e_im, with r_m in [0,1] set per attribute (replaces *_meta_scores_stddev). Show values in the UI as percentiles or domain scales through a display transform (e.g. board_scores -> 200-300 via scipy.stats.norm.cdf), not as stored raw floats. If bounded scores are kept, validate sd < sqrt(m(1-m)) in form.clean() and reject instead of clamping. Remove the 0.99 validator on Student/School.score (or clip) and apply the pending migration.

**Depends on.** OPT-9

**Verifier note (partially).** Core confirmed. get_beta_parameters(0.7, 2) gives a=0.164, b=0.100, mean 0.621, sd 0.431, P<.05=24%, P>.99=40%. (0, 2) gives a=0.100, b=0.234, mean 0.299, P<.05=54%. My sample had 76/200 students with score > 0.99. The pending migration 0006 is exactly the Student.score MaxValueValidator(0.99) (makemigrations --dry-run). One detail is wrong: meta scores do not get 'alpha=beta=0.117 for any base'. After clamping, temp = 1/0.81-1 = 0.2346, so alpha = 0.2346*m and beta = 0.2346*(1-m), each floored at 0.1. alpha=beta=0.117 only at m=0.5. For m near 0 or 1 the floor pulls the attribute mean to about 0.3 or 0.7. The distribution is Bernoulli-like for every m, so the conclusion stands (my sample: 34% of attributes < 0.05, 37% > 0.95). Also, mapping z to a 200-300 scale is a linear transform; norm.cdf gives percentiles.

<a id="opt-4"></a>

### OPT-4: MUST: No explicit preference-correlation model; heterogeneity is an accident of clamping and meta noise

**Severity:** 🟠 high · **Kind:** gap · **Effort:** M · **Plan:** 2.2 · **Verification:** partially

**Evidence.** simulation_engine.py:4-10: utility = sum_m score_meta[m]*w[m]. The base score, any idiosyncratic term and noise are absent. models.py:156-158: weights w = clamp(gauss(1, sd), 0.01, 2.0), then normalised. With default sd=3, probe_defaults.py shows 37% of raw weights at 0.01 and 37% at 2.0. probe sec.5 (default population): mean pairwise Kendall tau between students' school rankings = 0.613, mean Spearman(student rank, school base score) = 0.138. Prototype proto_model.py (common + idiosyncratic model): applicant_pref_correlation 0.0 / 0.6 / 0.95 -> match rate 0.803 / 0.921 / 0.935, first choice 72.4% / 49.2% / 28.1%, top-3 95.6% / 92.6% / 70.4%. Matches TODO.md 'Preference modeling improvements: preference correlation modeling'.

**Why it matters.** How strongly applicants agree on which programs are best (and programs on which applicants are best) is the most important structural driver of match outcomes: congestion, interview hoarding, first-choice rates. Today there is no parameter for it. It emerges from three unrelated SDs plus clamping, so users cannot run the most basic experiment ('what if everyone agrees on the top programs?').

**Recommendation.** In a new nrmps/engine/utility.py: u_ij = sqrt(rho_a)*C_j + sqrt(1-rho_a)*eps_ij + gamma_geo*home_region_match_ij (+ fit shock revealed at interview), where C_j = standardise(beta*sum_m w_im*y_jm + (1-beta)*quality_j) and eps ~ N(0,1). Symmetric for programs: v_ji = sqrt(rho_p)*S_i + sqrt(1-rho_p)*eta_ji with S_i built from strength_i and attribute scores x_im weighted by program weights. Parameters: prefs.applicant_pref_correlation (default 0.6), prefs.program_pref_correlation (0.7), prefs.attribute_weight_share beta (0.3), prefs.weight_concentration (Dirichlet concentration, default 10), with individual weights w_i ~ Dirichlet(conc * prior_weights). This replaces *_meta_preference_stddev and the clamp. Keep attribute lists so meta-features still matter, but as one term of a normalised utility with known variance shares.

**Depends on.** OPT-3

**Verifier note (partially).** The gap is real. Utility is sum(meta*w) with no base score, idiosyncratic term or noise. With sd=3 the weights are clamped: 37.1% at 0.01 and 37.1% at 2.0 (100k draws, matching the analytic P(|z|>1/3)). The heterogeneity statistics depend on the sample because nothing is seeded: my default run gave mean pairwise Kendall tau 0.475 and Spearman(rank, school base) -0.03, against the reviewer's 0.613 / 0.138. The conclusion 'base barely drives preferences' holds. The prototype effects of rho reproduce exactly (0.803/0.921/0.935; 72.4%/49.2%/28.1%). The proposed formula is inconsistent, though: C_j is indexed only by program but contains the applicant-specific weights w_im. That term is C_ij, so it is partly idiosyncratic, and rho_a would then not equal the inter-applicant utility correlation. Write it as u_ij = sqrt(rho_a)*Q_j + sqrt(1-rho_a)*(standardised mix of w_i·y_j and eps_ij), or accept that rho_a becomes a lower bound.

**Lead note (document check).** The normative utility construction is Appendix A §5. It uses population-mean weights in the common term and taste deviations on attributes residualised on it, so ρ equals the mean inter-applicant correlation.

<a id="opt-5"></a>

### OPT-5: MUST: No application stage: every applicant is rated against every program (full cross-product) and there are no options for how many or which programs to apply to

**Severity:** 🟠 high · **Kind:** gap · **Effort:** L · **Plan:** 3.1 · **Verification:** confirmed

**Evidence.** simulation_engine.py:13-35 creates all Student x School pairs; Interview.student_applied (models.py:673) is never set (probe sec.4: 'student_applied any: False'). The config has no application parameters. Prototype: application_strategy top_n vs portfolio -> match rate 0.769 vs 0.921, mean interviews 5.7 vs 8.6. applications_mean 10 / 30 / 80 -> match rate 0.944 / 0.921 / 0.833, zero-interview share 0.1% / 3.3% / 9.0% (application inflation congests screening). Real reference: ERAS 2025-26 average 81.8 applications per applicant, about 36 per specialty (medschoolcoach.com summary of AAMC ERAS data).

**Why it matters.** Applications are the first real decision in the NRMP pipeline and the main policy lever (application caps, signals, costs). Without them, programs 'pre-rate' applicants who never applied, and the Interview table grows as A×P (F4: up to 10M rows) instead of A×n_apps.

**Recommendation.** Add engine stage applications.py with parameters apps.count_dist {fixed, poisson, negbin}, apps.mean (default 30 at demo scale; per-group override), apps.dispersion, apps.strategy {top_n, portfolio, all, random}, apps.portfolio_shares {reach 0.25, target 0.5, safety 0.25}, apps.target_band (percentile gap 0.15). Portfolio logic: compare the applicant's strength percentile with the program's quality percentile and pick the most-preferred programs in each band (see proto_model.py). Persist only applied pairs (Interview.student_applied=True rows), which makes the Interview table sparse. Set status 'applied'.

**Depends on.** OPT-4, OPT-11

**Verifier note (confirmed).** initialize_interview builds the full cross-product (simulation_engine.py:13-35), and student_applied is never written (grep). Prototype numbers reproduce: top_n 0.769 vs portfolio 0.921; apps 10/30/80 give 0.944/0.921/0.833 and zero-interview 0.1%/3.3%/9.0%. The ERAS 2025-26 figures (81.8 total, about 36 per specialty) are confirmed via the medschoolcoach/AAMC summary. Caveat: the prototype's portfolio strategy assumes applicants know their exact strength percentile and each program's quality percentile, so the 15-point portfolio advantage is an upper bound. Add an apps.self_assessment_noise_sd parameter.

<a id="opt-6"></a>

### OPT-6: MUST: Interview-limit parameters are unused, and school_interview_limit has the wrong unit

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 2.1 · **Verification:** confirmed

**Evidence.** models.py:551-555: school_interview_limit FloatField default=0.1, MaxValueValidator(0.99), help 'Max number of interviews ... In percent of capacity' -> 0.1 × capacity 20 = 2 interviews for 20 positions (probe sec.10), and it can never exceed the number of positions. models.py:504-508: applicant_interview_limit is an IntegerField but forms.py:167 gives it step='any'. grep shows neither field is read anywhere outside forms/templates. The TODO.md 'School invitation logic: add interview invitation limits per school' item needs this unit corrected.

**Why it matters.** The two most important capacity constraints of the interview market (how many applicants a program interviews per position, and how many interviews an applicant can attend) are on the form but have no effect. The school one cannot represent reality even once implemented, because programs interview several times as many applicants as they have positions.

**Recommendation.** Replace with invites.interviews_per_position (float, default 10, range 1-30; slots = ceil(ratio × positions)) and interview.applicant_cap (int, default 12, range 1-50). Add invites.rounds (default 3), so slots declined because of the applicant cap are re-offered (backfill); the prototype shows wasted slots are why the match rate drops with more applications. Label both fields with units in the form ('interviews per position', 'max interviews per applicant').

**Depends on.** OPT-9

**Verifier note (confirmed).** grep shows applicant_interview_limit and school_interview_limit only in the model, form, template and help. school_interview_limit is a Float default 0.1 with Max 0.99, help 'In percent of capacity' (models.py:551-555). Read as a fraction or as a percent, it can never reach the number of positions. forms.py:167 sets step='any' on an IntegerField. One nuance: 'the prototype shows wasted slots are why the match rate drops' was not shown by the prototype, which has no backfill. My backfill test recovers only part of the drop (see OPT-16).

<a id="opt-7"></a>

### OPT-7: MUST: No random seed; generation uses the global `random` module and scipy's global RNG

**Severity:** 🟠 high · **Kind:** gap · **Effort:** S · **Plan:** 2.2 · **Verification:** confirmed

**Evidence.** models.py:116/198 `import random`; models.py:156, 221, 242 random.gauss; models.py:62 beta.rvs(...) with no random_state. probe_flow.py sec.5: same config generated twice -> sum of scores 48.6794 vs 48.9878. There is no seed field on Simulation or SimulationConfig.

**Why it matters.** Results cannot be reproduced, shared, debugged or compared fairly across scenarios. Without common random numbers, a scenario difference (e.g. signals on vs off) mixes the effect with sampling noise.

**Recommendation.** Add run.seed (BigInteger; blank = draw from secrets.randbits(63) and show it) to the run snapshot (OPT-8). Build every draw from ss = np.random.SeedSequence(seed). Replicates: ss.spawn(n). Each replicate spawns one child stream per stage (population, applications, signals, invitations, interview, post_noise, rol), so changing a later-stage parameter leaves earlier draws identical (common random numbers). Pass rng into all generators (rng.normal / rng.beta, or scipy's random_state=rng). Remove the module-level random usage.

**Verifier note (confirmed).** Generation uses module-level random.gauss (models.py:156, 221, 242) and beta.rvs without random_state (models.py:62), and there is no seed field. Generating the same config twice gave score sums 101.7563 vs 100.8568. The proposed APIs are real: np.random.SeedSequence(seed).spawn(n), and scipy accepts random_state=Generator.

<a id="opt-8"></a>

### OPT-8: MUST: The config is edited in place; runs and populations keep no snapshot of the config that produced them

**Severity:** 🟠 high · **Kind:** gap · **Effort:** M · **Plan:** 2.3 · **Verification:** confirmed

**Evidence.** views.py:102 and :117-157: the form is bound to configs.order_by('-id').first() and saved, so the same row is overwritten (probe_flow: 'config rows after two saves: 1 same id: True'). After generating 50 students and then saving 75, 'config now says 75 but population is 50 -> no record of which config produced the population'. The 'latest config' lookup is duplicated at models.py:118, 200 and simulation_engine.py:49, 80. CLAUDE.md claims 'Multiple configs can exist per simulation (latest used)', but no code path creates a second one.

**Why it matters.** Every downstream result (interviews, ranks, eventually matches) can silently disagree with the displayed config. Experiments cannot be audited or compared, and the UI cannot warn that stages are stale.

**Recommendation.** Add a model SimulationRun(simulation FK, params JSONField (validated dump of SimulationParams), schema_version, seed, replicate, sweep FK null, params_hash CharField(64, db_index) = sha256 of canonical JSON, code_version (git SHA or package version), status {queued, running, done, failed}, started_at, finished_at, error, metrics JSONField). Hang Student/School/Interview/Match off the run (FK run, null for legacy rows), or store results as arrays (OPT-11). Keep SimulationConfig as the editable draft (OneToOne 'current config'), frozen into the run at execution time. Store per-stage fingerprints (hash of the params subset each stage reads) so the UI can mark stages 'stale' after an edit and recompute only what changed.

**Depends on.** OPT-9

**Verifier note (confirmed).** Reproduced: a config POST updates the same row (ids [1] -> [1], n_applicants now 75 while the population is unchanged). admin.py registers nothing, and the views create a config only when none exists, so no code path creates a second config. The 'latest config' lookup is duplicated at models.py:118 and 200 and simulation_engine.py:49 and 80, as stated.

<a id="opt-9"></a>

### OPT-9: MUST: Replace the 20 flat model fields with a versioned, typed parameter schema that drives validation, the form, '?' help, docs and JSON import/export

**Severity:** 🟠 high · **Kind:** recommendation · **Effort:** M · **Plan:** 2.1 · **Verification:** confirmed

**Evidence.** models.py:476-578 has a flat list of 20 fields with inconsistent names (applicant_meta_preference is the list of *program* attributes applicants value; school_meta_preference doubles as the list of student score_meta keys). forms.py:91-136 duplicates the clean_* logic for the two list fields. The documentation page (views.py:557-705) auto-renders model help_text, so the wrong help texts in OPT-12 appear there too. pydantic is not installed (.venv has no pydantic*), and numpy is imported directly (models.py:3) but only comes in transitively via scipy.

**Why it matters.** The redesigned option set (~50 parameters in nested groups, lists of groups/tiers/attributes, enums) does not fit well into flat Django columns. A single schema source avoids the current drift between model, form, template and docs, and gives the '?' tooltips (review goal 6) and presets a single source.

**Recommendation.** Add pydantic>=2 and numpy as explicit dependencies. Create nrmps/params.py with SimulationParams(schema_version: Literal[1], run, market, applicants, programs, prefs, info, apps, signals, invites, interview, rol, match), each a BaseModel with Field(default, ge, le, description, json_schema_extra={'stage':..., 'unit':..., 'help_md':..., 'level': 'basic'|'advanced'}). Put cross-field rules in @model_validator. Store the draft in SimulationConfig.params = JSONField plus schema_version. Keep a few typed columns (n_applicants, n_programs) for listing and filtering. Render the form from SimulationParams.model_json_schema(): group cards, a 'basic/advanced' toggle, a '?' popover showing description, unit and range. Add upgrade functions params_v1_to_v2() for schema migrations. Map the old columns in a data migration (see the mapping table in extra).

**Verifier note (confirmed).** The facts hold. pydantic is not in .venv. numpy is imported at models.py:3 but pyproject lists only scipy. The documentation view renders field help_text through _meta.get_fields (views.py around line 662). The naming inversion (applicant_meta_preference = program attribute keys, models.py:129/211) is correct, and forms.py:91-136 duplicates the clean methods. pydantic v2 Field(json_schema_extra=...) and model_json_schema() exist. Effort is likely L rather than M: a generic Django renderer for nested $defs and list-of-object parameters (groups, tiers, signal tiers), plus the data migration and help integration, is more than 1-3 days.

<a id="opt-10"></a>

### OPT-10: MUST: Simulation.iterations is exposed but unused; no Monte-Carlo replicates, aggregated metrics or confidence intervals

**Severity:** 🟠 high · **Kind:** gap · **Effort:** L · **Plan:** 6.1 · **Verification:** partially

**Evidence.** models.py:95 iterations (1-100), forms.py:42 and templates simulation_manage.html:36 / simulations_list.html:31 display it. grep finds no reader in the engine. probe_flow: 'iterations stored: 5 (no code reads it)'. Prototype: seed 1 gives match rate 0.921, but 10 seeds give mean 0.896, 95% CI (0.886, 0.907), so a single run misleads by more than the CI width. Matches IDEAS.md 'Reproducible research features / Statistical significance testing' and TODO.md 'Simulation analysis tools'.

**Why it matters.** With noisy stages, any single outcome is one draw. Users need distributions and CIs to compare options. This is also the data layer the requested sliders and plots need (goal 5).

**Recommendation.** Rename to run.replicates (default 1 for demo, up to 1000 with a size guard) plus run.resample_population (bool: new population per replicate vs. fixed population with only process noise resampled). Compute a fixed metric set per replicate (see extra: match rate overall and by group, fill rate, % first / top-3, mean rank of match, unmatched, unfilled, interviews per applicant, zero-interview share, wasted slots, blocking pairs, welfare = mean true utility of match) into SimulationRun.metrics. Aggregate into mean, SD, t-based 95% CI (scipy.stats.t) and bootstrap percentiles for skewed metrics. Execute in the background with Django 6's django.tasks (the installed backends are only dummy/immediate, so add the django-tasks DatabaseBackend or RQ for production) and show progress over HTMX polling.

**Depends on.** OPT-7, OPT-8, OPT-11

**Verifier note (partially).** Confirmed that iterations is displayed but read by no engine code. Three details need correcting. (1) Since django-tasks 0.12 the DatabaseBackend is in a separate package: django-tasks-db, BACKEND 'django_tasks_db.DatabaseBackend'; RQ is django-tasks-rq. Django 6.1 core ships only dummy/immediate (verified in .venv/django/tasks/backends). (2) The prototype CI uses z=1.96, not t. With t(9)=2.262 the 10-seed CI is about (0.884, 0.908), not (0.886, 0.907). (3) Comparing one draw with the CI of the mean is the wrong yardstick; the relevant figure is the seed-to-seed SD of about 0.017. The need for replicates stands.

<a id="opt-11"></a>

### OPT-11: MUST (enabler): Vectorised array engine with sparse persistence, so the new options, replicates and sweeps are feasible

**Severity:** 🟠 high · **Kind:** recommendation · **Effort:** L · **Plan:** 2.2 · **Verification:** partially

**Evidence.** Lead fact F4: about 0.5 s per pre-interview step for 360 pairs (per-row .save() in simulation_engine.py:55-66, 110-119); the config allows 10,000 × 1,000. Prototype proto_model.py runs the whole proposed pipeline (population, utilities, applications, signals, invitations, interview cap, post-interview update, rank lists, applicant-proposing DA with heaps) for 2,400 × 300 = 720k pairs in 1.12 s, and a full parameter sweep of 12 configs in about 15 s.

**Why it matters.** Monte-Carlo (OPT-10) and sweeps (OPT-21) multiply run counts by 10-1000×. ORM-per-row computation, and storing A×P rows, cannot support this.

**Recommendation.** Create a nrmps/engine/ package of pure functions on numpy arrays: population.py, utility.py, applications.py, signals.py, invitations.py, interview.py, rol.py, match.py (DA with heapq, as in the prototype), metrics.py, each taking (params, rng, state) and returning arrays. The Django layer only loads/saves: bulk_create applied pairs only (A×n_apps), matches, and metrics. For large runs store the arrays as .npz in FileField/object storage instead of rows. Guard size in params validation (e.g. n_applicants × apps.mean ≤ 5M).

**Verifier note (partially).** The timing reproduces: 1.01 s for 2,400x300, and 21 runs in 18 s. But the prototype is not really vectorised. Applications, invitations, acceptance, ROL construction and deferred acceptance are Python loops per agent. It also keeps about 10 dense AxP float arrays (u, v, u_pre, v_pre, gap, screen, u_post, v_post, prog_rank, ...). At the config's own maximum (10,000x1,000) one run took 12.7 s and 763 MB RSS (optverify/big.py). So the proposed guard 'n_applicants x apps.mean <= 5M' does not bound the engine's cost: memory scales with AxP. Guard AxP, or compute utilities in applicant chunks and keep only the top-k or applied pairs, and run replicates off the web process.

<a id="opt-12"></a>

### OPT-12: MUST: Validation ranges are meaningless or missing, there are no cross-field checks, and several help texts are wrong

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 1.6, 2.1 · **Verification:** confirmed

**Evidence.** probe_flow sec.3: form accepts number_of_applicants=10000, number_of_schools=1000, school_capacity_mean=-5, applicant_score_stddev=99, applicant_interview_limit=0 -> 'nonsense config valid? True'. models.py:545 school_capacity_mean has no validators. forms.py:163-164 widgets set min=0 while model validators set min 1. models.py:531 applicant_post_interview_rating_error help says 'Pre-interview rating error stddev'. models.py:560-563 school_meta_preference_stddev has no help_text. models.py:572/577 school pre/post have identical help ('...observed score for each student'). templates/nrmps/simulation_manage.html:194 and :235-ish render value='{{ ...|safe }}' with a Python list repr (['program_size', ...]) inside a single-quoted attribute: the server-rendered value is '[' (it only works because Alpine overwrites it) and it is an injection vector for unnormalised keys (server-side clean does not slugify, forms.py:91-136).

**Why it matters.** Users can submit configs that are impossible (negative capacity), meaningless (SD 99 on a 0-1 scale) or unrunnable (10M rows), and the help text misleads them.

**Recommendation.** In SimulationParams validators: shares sum to 1; n_signals ≤ apps.mean ≤ n_programs; post noise ≤ pre noise (implied by kappa); interviews_per_position × positions ≥ positions; applicant_cap ≥ 1; warn (non-blocking message) when applicants_per_position is outside 0.7-1.6 or expected interviews per applicant (total slots / A) is below applicant_cap / 2; hard cap on A × apps. Slugify attribute keys on the server (django.utils.text.slugify, underscores). Render JSON with json_script / |escapejs instead of |safe. Write help texts with unit + meaning + stage for every field (they feed the '?' popovers).

**Depends on.** OPT-9

**Verifier note (confirmed).** The nonsense config (10000/1000, capacity -5, sd 99, limit 0) validates as True. The help-text errors at models.py:531, 560-563 and 572/577 are as described. The widgets use min=0 while the validator minimum is 1. The rendered hidden input is value='['program_size', ...]', which parses as '['. The second instance is at simulation_manage.html:305, not about 235. Injection demonstrated: saving the key 'a"><img src=x onerror=alert(1)>' through the config POST renders unescaped inside x-data="metaEditor(...)" (lines 172/283). Every view is owner-only, so the XSS is effectively self-XSS today; it becomes stored XSS if public or shared simulations are ever added.

<a id="opt-13"></a>

### OPT-13: SHOULD: Meta-attribute keys are coupled across the two populations; editing one list crashes rating; CSV round-trip drops preferences

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** M · **Plan:** 1.7 · **Verification:** partially

**Evidence.** models.py:129 (student score_meta keys = school_meta_preference) and :211 (school score_meta keys = applicant_meta_preference). probe sec.7: add 'call_schedule' to applicant_meta_preference, regenerate students only -> 'raised: Exception Error computing pre-interview score for Student 1 - School 1' (simulation_engine.py:56-63 swallows the KeyError). probe sec.8: CSV-uploaded students get meta_preference {} (models.py:329-336, 354-361), so all their student->school scores are 0.0 and ranks 1..N are arbitrary ties. views.py:293/309 downloads omit meta_preference, so download -> upload loses preferences.

**Why it matters.** The attribute schema is implicit and spread across two lists named after the *other* side. Any partial regeneration or CSV use gives a crash or a silently meaningless ranking.

**Recommendation.** Define attributes once in params: applicants.attributes = [{key, corr_with_strength, program_weight_prior}] and programs.attributes = [{key, corr_with_quality, applicant_weight_prior}]. Freeze them in the run snapshot. On rating, check that every population member has every key (raise a user-facing validation error listing the missing keys, or impute 0 in z-units if a flag allows). Add meta_preference (JSON) to CSV download/upload and validate uploaded keys against the schema with row-level error feedback. Rename the UI labels to 'Applicant attributes (what programs evaluate)' and 'Program attributes (what applicants evaluate)'.

**Depends on.** OPT-9

**Verifier note (partially).** Reproduced the coupling crash. Adding 'call_schedule' to applicant_meta_preference and regenerating only students raises 'Error computing pre-interview score for Student 1 - School 1'. The engine does not 'swallow' the KeyError: it re-raises a bare Exception `from None`, which hides the real missing key, and the view does not catch it, so the user gets HTTP 500. CSV round-trip confirmed: the download header is name,score,score_meta; after re-upload meta_preference == {} and every student->school score is 0.0.

<a id="opt-14"></a>

### OPT-14: SHOULD: Capacity model makes zero-position programs, and market tightness is an accident of three unrelated inputs

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 2.1 · **Verification:** confirmed

**Evidence.** models.py:221-224: capacity = max(0, round(gauss(20, 10))). probe sec.9 (10k draws): 2.4% of programs have capacity 0, 7.1% ≤ 5. probe sec.3: the default run produced 174 positions for 200 applicants (ratio 1.15) purely by chance. NRMP 2026: 44,344 positions in 6,809 program tracks (about 6.5 per program) and 48,050 active applicants, so applicants per position ≈ 1.08.

**Why it matters.** The ratio of applicants to positions is the first-order determinant of match and fill rates. Users should set it directly and hold it fixed while varying other options, not get it as a random by-product.

**Recommendation.** market.applicants_per_position (default 1.08, range 0.5-3), market.program_size_dist {fixed, shifted_poisson, lognormal, tiers} (default shifted_poisson, min 1), market.program_size_mean (default 6.5). Optional tiers [{name: small, share 0.4, 1-4}, {medium, 0.45, 5-12}, {large, 0.15, 13-40}]. Derive n_programs = round(n_applicants / applicants_per_position / size_mean), or let the user fix n_programs and derive size_mean. Show the derived totals live in the form.

**Depends on.** OPT-9

**Verifier note (confirmed).** From 100k draws of max(0, round(gauss(20, 10))): capacity 0 in 2.6% and <= 5 in 7.3%, matching the reviewer. Real ratios: 44,344/6,809 = 6.5 positions per track and 48,050/44,344 = 1.08 (2026 figures confirmed). The default shifted Poisson (sd about 2.3) is much less dispersed than real program sizes, so lognormal or negative binomial is a better default; the reviewer offers these as options.

<a id="opt-15"></a>

### OPT-15: SHOULD: Program signals: the model has a field but no config and no behaviour

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 3.2 · **Verification:** confirmed

**Evidence.** models.py:676 Interview.student_signal IntegerField is never written. Real reference: for the 2025-26 ERAS season all Internal Medicine applicants get 3 'Gold' and 12 'Silver' signals, and AAIM recommends using them for interview selection but not for ranking (AAIM FY26 recommendations / AAMC program-signaling pages). Prototype: n_signals 0 / 5 / 15 (boost 0.5 SD) -> match rate 0.921 / 0.925 / 0.931, fill 0.963 / 0.967 / 0.974. Matches IDEAS.md 'Information asymmetry: signal quality variations'.

**Why it matters.** Signalling is the biggest recent NRMP/ERAS design change and a natural 'signals on vs off' scenario, but it cannot be modelled today.

**Recommendation.** signals.tiers: list[{name, count, boost}] (default [], preset IM-like [{gold, 3, 0.8}, {silver, 12, 0.4}]). signals.allocation {top_utility, realistic (spend on programs where P(interview) is middling), random}. signals.program_use_share (share of programs that consider signals, default 1.0). signals.use_in_ranking (bool, default False, per AAIM). Store the tier index in Interview.student_signal (0 = none). Apply the boost additively to the program's screening score in invitations. Output metrics: interview rate for signalled vs not, and match rate by signal tier.

**Depends on.** OPT-5

**Verifier note (confirmed).** student_signal is never written. AAIM FY26 confirms 3 Gold + 12 Silver for all IM applicants in 2025-26, and says to use signals for interview offers but not for rank lists. Signals are an ERAS/AAMC feature, not an NRMP one. The prototype deltas reproduce (0.921/0.925/0.931), but they are 0.4-1.0 pp, below the seed-to-seed SD of about 1.7 pp. They are paired, since the signal stage consumes no random numbers, yet they should be quoted with replicates.

<a id="opt-16"></a>

### OPT-16: SHOULD: Program screening and invitation behaviour: thresholds, strategy, yield protection, waves and backfill

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 3.3 · **Verification:** partially

**Evidence.** The config has no invitation parameters. Interview.school_invited (models.py:686) is never set (probe sec.4: 'school_invited any: False'). TODO.md 'School invitation logic' has no design. Prototype: with applications_mean=80 and a single invitation round, the match rate falls to 0.833 and the zero-interview share rises to 9% because top applicants hit their cap and the declined slots are never re-offered.

**Why it matters.** How programs choose whom to interview decides who gets any chance to match. It is also where signals, board-score cut-offs and 'yield protection' (not inviting applicants seen as out of reach) play out.

**Recommendation.** invites.strategy {top_score, threshold_then_top, threshold_then_random, signal_first}; invites.screen_attribute (attribute key or null) and invites.screen_min_percentile (0-1); invites.yield_protection lambda (0-2: subtract lambda × max(0, strength_pct - quality_pct) unless signalled); invites.rounds (default 3) with backfill of declined slots; invites.interviews_per_position (OPT-6). Programs invite in order of quality within each wave (better programs first), which reproduces realistic hoarding. Set Interview.status to 'invited'.

**Depends on.** OPT-5, OPT-6

**Verifier note (partially).** school_invited is never set, and the recommendation is sound. The causal claim is only partly right. I added invitation rounds that re-offer declined slots to the reviewer's prototype (optverify/backfill.py). At apps=80, 1 round gives 0.833, 3 rounds 0.899, 10 rounds 0.901; slot use goes from 72% to 100%. Backfill recovers about 2/3 of the drop. 80 applications is still below 10 (0.944), and the zero-interview share stays at 7.6%. The remaining cause is that programs with correlated screening (rho_p 0.7) all invite the same strong applicants, which the rounds parameter alone does not fix. The DA gives 0 blocking pairs against submitted ROLs, so the prototype matcher is correct.

<a id="opt-17"></a>

### OPT-17: SHOULD: Interview-stage options: acceptance cap and order, scheduling conflicts, information revealed

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 3.3 · **Verification:** confirmed

**Evidence.** simulation_engine.py:167-172 interview() is a stub. Both post_interview_rating_error fields (models.py:528, 574) are unused. Interview.status stays 'initialized' forever (probe sec.4). The TODO.md 'Interview scheduling system: date/time fields, calendar views' item over-builds: dates only matter as a conflict constraint.

**Why it matters.** The interview stage is where uncertainty resolves (pre -> post beliefs) and where the applicant cap binds. Modelling it abstractly gives the key research lever: how informative interviews are.

**Recommendation.** interview.applicant_cap (OPT-6); interview.acceptance_order {best_first, first_come} (first_come uses invitation waves); interview.n_dates (0 = off) and interview.dates_per_program (applicants cannot accept two interviews on the same date, which models conflicts without a calendar UI); info.interview_informativeness kappa (0-1, sigma_post = sigma_pre × (1 - kappa)); info.fit_shock_sd (0-2: a new idiosyncratic 'interview-day fit' term added to both sides' true utility, revealed only after the interview). Status transitions: applied -> invited -> accepted -> interviewed -> declined.

**Depends on.** OPT-2, OPT-16

**Verifier note (confirmed).** interview() is a stub (simulation_engine.py:167-172), both post-interview error fields are unused, and status stays 'initialized'. Minor: the proposed status chain puts 'declined' after 'interviewed'. 'declined' is a branch from 'invited', not a final step.

<a id="opt-18"></a>

### OPT-18: SHOULD: Rank-list and match options: ROL policies, do-not-rank, proposing side, stability check

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 3.5 · **Verification:** confirmed

**Evidence.** students_rank / schools_rank / match are stubs (simulation_engine.py:175-190). The Match model (models.py:727-745) has one row per pair with no ROL length or policy. Real reference: NRMP uses an applicant-proposing algorithm based on Roth-Peranson (NRMP, AMA 'How the Match algorithm favors applicants'). Prototype DA (proto_model.py) with program_dnr_quantile works in a few lines. IDEAS.md lists TTC/RSD as alternative mechanisms.

**Why it matters.** Rank-list length and do-not-rank decisions strongly affect unmatched counts. Comparing applicant- vs program-proposing DA is a classic, cheap teaching and research demo (outcomes usually differ for very few applicants).

**Recommendation.** rol.applicant_policy {all_interviewed, top_k, above_reservation} with rol.applicant_top_k and rol.reservation_utility (z); rol.program_policy {all_interviewed, dnr_quantile, dnr_threshold} with rol.program_dnr_quantile (default 0.1); match.algorithm {applicant_proposing (default), program_proposing}; match.compare_both (bool: report the number of applicants and programs whose outcome differs); always compute a blocking-pair count as a correctness check (should be 0 without couples). Store ROLs as a RankListEntry(run, side, owner_id, target_id, rank) table or as arrays, and Match rows only for matched pairs. Could-level extras: TTC and RSD as match.algorithm options (IDEAS.md).

**Depends on.** OPT-11

**Verifier note (confirmed).** The stubs are at simulation_engine.py:175-190, and the Match model is one row per pair. NRMP applicant-proposing Roth-Peranson is correct, and applicant- vs program-proposing outcomes differ for very few applicants in practice (Roth & Peranson 1999). A blocking-pair count of 0 against submitted ROLs is a valid correctness check (my DA re-implementation: 0). Blocking pairs against true utilities are a separate, useful welfare metric.

<a id="opt-19"></a>

### OPT-19: SHOULD: Applicant groups (US MD / DO / US-IMG / non-US-IMG) and program tiers, with group-level outcomes

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 6.3 · **Verification:** confirmed

**Evidence.** There is only one homogeneous applicant population (models.py:126-181). NRMP 2026 active applicants: 48,050 total, of which US MD seniors 20,934 (43.6%), US DO seniors 8,503 (17.7%), US-citizen IMGs 4,210 (8.8%), non-US-citizen IMGs 11,944 (24.9%), remainder about 5% (other/prior graduates). PGY-1 match rates: MD 93.5%, DO 93.2%, US-IMG 70.0%, non-US-IMG 56.4%, all active 79.8%. Prototype with 4 groups and strength means (0.5, 0.35, -1.0, -1.3): overall 0.818, MD 0.970, DO 0.961, US-IMG 0.604, non-US-IMG 0.555. IDEAS.md already mentions IMG constraints and bias/fairness analysis.

**Why it matters.** Disparities between applicant types are the most-discussed NRMP outcome, and the easiest calibration target. Without groups, fairness or 'who goes unmatched' analyses are impossible.

**Recommendation.** applicants.groups: list[{name, share, strength_mean, strength_sd, applications_mean?, n_signals?, visa_needed?}] with a validator that shares sum to 1. programs.tiers: list[{name, share, quality_mean}]; programs.visa_sponsor_share (programs that will not rank visa-needing applicants). Add Student.group and School.tier CharFields (indexed). Report every metric per group.

**Depends on.** OPT-9, OPT-4

**Verifier note (confirmed).** All 2026 figures verified: MD 20,934 (43.6%), DO 8,503 (17.7%), US-IMG 4,210 (8.8%), non-US-IMG 11,944 (24.9%); PGY-1 rates 93.5/93.2/70.0/56.4; 38,354/48,050 = 79.8%. Calibration nuance: calib.py uses shares 0.12/0.267 for the two IMG groups (not 8.8%/24.9%), and applicants per position 1.13 (not 1.08). Its output misses MD by +3.5 pp and US-IMG by -10 pp, so 'close' is generous.

<a id="opt-20"></a>

### OPT-20: SHOULD: Presets and templates, including one calibrated to NRMP 2026 aggregates, plus a calibration report

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 4.2, 6.4 · **Verification:** partially

**Evidence.** There are no presets; defaults are degenerate (OPT-1, OPT-3). NRMP 2026 aggregates (from NRMP press releases and AMA coverage, March/May 2026): 53,373 registered, 48,050 active, 44,344 positions, 6,809 program tracks, 41,482 filled in the Match (93.5%), 99.3% filled after SOAP, 1,258 couples (93.0% matched), 73.5% of US MD seniors matched to a top-3 choice. 2025: 52,498 registered, 47,208 active, 43,237 positions (40,041 PGY-1), 2,521 positions to SOAP of which 2,318 filled. The rough prototype setting already gives overall 0.80-0.82 and IMG 0.55-0.60.

**Why it matters.** Presets make the tool usable in one click, give meaningful defaults, and make 'what-if' comparisons against a realistic baseline credible.

**Recommendation.** Store nrmps/presets/*.json, each validated by SimulationParams: 'classroom_demo' (60 applicants, 8 programs, size 6, rho 0.5, no signals; < 1 s); 'balanced_market' (applicants_per_position 1.0); 'nrmp_2026_scaled' (1:20 scale, about 2,400 applicants / 340 programs, size mean 6.5, 4 groups with 2026 shares, apps.mean 40, 10 signals, interviews_per_position 10, applicant_cap 12); 'competitive_specialty' (1.5 applicants per position, rho_a 0.85, apps 60); scenario pairs 'signals_off_vs_on' (0 vs 3 gold + 12 silver) and 'application_inflation' (sweep apps.mean 10-80). Add a 'calibration report' card comparing replicate means (with CIs) against a CALIBRATION_TARGETS dict that holds the source URL and date. Later, a could-level auto-calibration using scipy.optimize (Nelder-Mead on group strength means).

**Depends on.** OPT-9, OPT-19

**Verifier note (partially).** The NRMP numbers check out: 53,373 / 48,050 / 44,344 / 41,482 (93.5%) / 99.3% after SOAP / 1,258 couples / 73.5% of MD seniors matched to a top-3 choice; 2025 52,498 / 47,208 / 43,237 / 40,041, SOAP 2,521 -> 2,318. But the claim that the rough prototype setting is already near NRMP aggregates is overstated. The same calib run gives top-3 95.2% vs NRMP 73.5%, MD 97% vs 93.5%, US-IMG 60% vs 70%, and a mean ROL of about 7. The calibration report must include rank-position targets. 2026 SOAP data exist (2,851 offered, 2,632 filled) and should replace the 2025 figures. Nelder-Mead on a stochastic simulator needs fixed seeds or CRN, or a noise-tolerant optimiser.

<a id="opt-21"></a>

### OPT-21: SHOULD: Parameter sweeps (1-D/2-D) and paired scenario comparison with common random numbers

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** L · **Plan:** 6.2 · **Verification:** partially

**Evidence.** No sweep or comparison support exists. TODO.md 'Implement scenario comparison tools' and IDEAS.md 'Parameter sensitivity analysis / A/B testing framework' list it without a design. The prototype sweeps (rho, n_signals, apps.mean, strategy) show large, non-monotone effects (apps 10 -> 80: 0.944 -> 0.833), which a single run cannot reveal.

**Why it matters.** Sweeps are the natural backend for the requested sliders (goal 5): precompute a grid, then a slider scrubs through cells instantly with CI bands.

**Recommendation.** Add models Sweep(simulation, base_params, axes JSON = [{path: 'signals.tiers[0].count', values: [...]} or {path, start, stop, num}], replicates, seed) and SweepCell(sweep, coords JSON, run FK) that reuse SimulationRun. Use the same seed per replicate across cells (CRN) so differences are paired. The comparison view shows metric deltas with paired t CIs. Limit the grid size (cells × replicates × A×apps) by a quota. The UI renders 1-D line + CI band and 2-D heatmap, with sliders bound to the axes.

**Depends on.** OPT-10, OPT-9

**Verifier note (partially).** No sweep support exists, and TODO.md:81 / IDEAS.md:102-104 are cited correctly. The evidence claim 'large, non-monotone effects (apps 10 -> 80: 0.944 -> 0.833)' is false as stated: 10/30/80 gives 0.944/0.921/0.833, which is monotone decreasing. The rho and signal sweeps are monotone too. The recommendation still stands.

<a id="opt-22"></a>

### OPT-22: SHOULD: Clone/duplicate simulation, import/export config JSON, save as preset

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** S · **Plan:** 4.6 · **Verification:** partially

**Evidence.** nrmps/urls.py has no clone, export or import routes. The config is only editable through the 20-field form (views.py:117-157). The CSV export covers populations only (views.py:286-312).

**Why it matters.** Scenario work is 'copy, change one thing, compare'. Today that means re-typing 20 fields, and configs cannot be shared or kept in version control.

**Recommendation.** Add routes simulations/<pk>/clone/ (copy the Simulation and its current params; optionally deep-copy the population with bulk_create), simulations/<pk>/config.json (GET export: SimulationParams JSON with schema_version and the seed), and simulations/<pk>/config/import/ (POST JSON -> validate -> show a diff against current -> save). Add 'Save as my preset' (a UserPreset model or the Simulation.public flag). Show the params_hash and seed on the run page, so a run can be reproduced from the exported JSON.

**Depends on.** OPT-9

**Verifier note (partially).** Correct that there are no clone, config-export or config-import routes (urls.py). Wrong that 'the CSV export covers populations only': simulation_download_interviews exists (urls.py:36, views.py around line 520-550). The 'Simulation.public flag' proposed as a sharing mechanism is currently read by no view (see missed).

<a id="opt-23"></a>

### OPT-23: SHOULD: Use NRMP domain vocabulary: 'School' is really a residency Program; use clearer parameter names

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** S · **Plan:** 1.6, 2.3 · **Verification:** confirmed

**Evidence.** The School model (models.py:623) stands for residency programs. In NRMP terms 'school' means the applicant's medical school, which matters once applicant groups (MD/DO/IMG, i.e. school type) are added. Field names such as applicant_meta_scores_stddev / school_meta_preference_stddev are opaque (OPT-9, OPT-13).

**Why it matters.** Domain-accurate names reduce confusion in the help and docs and avoid a clash with the planned applicant 'school type' attribute.

**Recommendation.** Rename UI labels now ('Program', 'Positions', 'Applicant'). Rename in the params schema (programs.*, applicants.*). Defer the DB rename (RenameModel School -> Program) to the engine rewrite, to avoid churn twice.

**Verifier note (confirmed).** School models residency programs (models.py:623). 'School' for the applicant's medical school clashes with a future MD/DO/IMG school-type attribute. Deferring the DB rename is sensible.

<a id="opt-24"></a>

### OPT-24: COULD: Multiple specialties with different competitiveness, backup specialties and supplemental (prelim/advanced) lists

**Severity:** ⚪ low · **Kind:** gap · **Effort:** L · **Plan:** 8.5 · **Verification:** confirmed

**Evidence.** There is a single market. ERAS 2025-26: applicants apply to just over 2 specialties on average (81.8 applications total, about 36 per specialty; medschoolcoach summary of AAMC data). TODO.md 'specialty-specific matching rules', IDEAS.md 'Specialty-specific features'.

**Why it matters.** Competitiveness differs enormously by specialty, and dual-applying is a major real-world strategy. It is needed for realistic 'competitive specialty' studies.

**Recommendation.** market.specialties: list[{name, position_share, applicants_per_position, rho_a, rho_p, interviews_per_position}]; applicants.primary_specialty_dist; apps.backup_specialty_prob and apps.backup_share. Programs belong to one specialty. The match runs on the joint ROL (specialties interleaved by utility). Supplemental ROLs for advanced positions come later with match.supplemental_lists.

**Depends on.** OPT-11, OPT-19

**Verifier note (confirmed).** ERAS 2025-26: 81.8 total applications and about 36 per specialty, so just over 2 specialties per applicant (medschoolcoach/AAMC). TODO.md:72 and IDEAS.md:53 are cited correctly. ERAS fees reset per specialty, which links this finding to OPT-27.

<a id="opt-25"></a>

### OPT-25: COULD: Couples fraction and SOAP post-match round

**Severity:** ⚪ low · **Kind:** gap · **Effort:** L · **Plan:** 8.3, 8.1 · **Verification:** confirmed

**Evidence.** TODO.md 'Multiple matching rounds: SOAP, couples'. NRMP 2026: 1,258 couples (2,516 applicants ≈ 5.2% of active) with a 93.0% couples match rate. 2025: 1,259 couples, 89.1% both matched. SOAP 2025: 2,521 positions offered, 2,318 filled, over four rounds (NRMP).

**Why it matters.** Couples change the stability properties (a stable match may not exist), which makes a strong research and teaching feature. SOAP explains why the fill rate goes from 93.5% to 99.3%.

**Recommendation.** match.couples_fraction (default 0, NRMP-like 0.05); match.couple_geo_constraint {same_program, same_region, any}. Joint ROL = pairs ranked by the sum of partners' utilities, filtered by the constraint. Implement the Roth-Peranson-style heuristic with a cycle/iteration limit and report instability. match.soap_enabled, match.soap_rounds (4), match.soap_max_applications (NRMP's current SOAP application cap, to be checked when implementing). SOAP re-runs a simplified offer/accept among unmatched applicants and unfilled positions using post-interview beliefs.

**Depends on.** OPT-18

**Verifier note (confirmed).** TODO.md:70-71 and IDEAS.md:66/72 match. 1,258 couples = 2,516 applicants = 5.2% of active applicants. A search summary says NRMP's 93% counts couples where one or both partners matched (nrmp.org is blocked here, so not verified directly). I could not verify the 2025 figure of 89.1% 'both matched'. The 2026 SOAP figures (2,851 offered / 2,632 filled) are available and should be used. Couples can make a stable matching nonexistent (Roth 1984): correct.

<a id="opt-26"></a>

### OPT-26: COULD: Geography and region preference on both sides

**Severity:** ⚪ low · **Kind:** gap · **Effort:** M · **Plan:** 8.6 · **Verification:** confirmed

**Evidence.** 'location' is only an abstract attribute key (models.py:15), with no region structure. TODO.md 'geographic preference constraints' and IDEAS.md 'Geographic constraints / regional clustering' propose it. ERAS offers geographic preference signalling (AAMC supplemental application).

**Why it matters.** Regional preference is a large, well-documented effect and interacts with couples and signals.

**Recommendation.** market.n_regions (1 = off), region shares for applicants and programs, prefs.home_region_bonus_applicant and prefs.local_bonus_program (in SD units, 0-2) added to u and v, and signals.geo_signal (bool) that boosts screening for programs in the signalled region. Metric: share matched in home region.

**Depends on.** OPT-4

**Verifier note (confirmed).** 'location' is only an abstract key (models.py:15). TODO.md:77 and IDEAS.md:47-49 match. ERAS collects geographic preferences in MyERAS (formerly the supplemental application); these are preferences rather than program signals, but a geo boost to screening is a fair model of them.

<a id="opt-27"></a>

### OPT-27: COULD: Application cost, budget and adaptive (strategic) application behaviour

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** L · **Plan:** 8.7 · **Verification:** partially

**Evidence.** The config has no cost concept. IDEAS.md 'Preference revelation strategies' and 'Bounded rationality / satisficing' ideas. Prototype shows application count has a non-monotone market-level effect (OPT-5).

**Why it matters.** Application cost and budget are the policy levers behind application caps, and adaptive stopping rules turn the tool into a genuine market-design lab.

**Recommendation.** apps.fee_schedule: list[{up_to, fee_per_program}] (tiered like ERAS); apps.budget (per group; null = none); apps.stop_rule {fixed_count, marginal_probability} where marginal_probability keeps applying while the estimated P(interview) × value exceeds the fee (estimate P from the previous replicate's interview rates per strength or quality bin). Metrics: total applicant spend, and interviews per 100 applications.

**Depends on.** OPT-5, OPT-10

**Verifier note (partially).** The claim 'the prototype shows application count has a non-monotone market-level effect' is false: the effect is monotone decreasing over 10/30/80, and about 2/3 of the decline is an artefact of the single-round invitation model (see OPT-16). The fee idea itself is well founded: ERAS 2026 fees are two-tier per specialty ($11 per program for the first 30, $30 for each after), so apps.fee_schedule must be per specialty.

<a id="eng"></a>

## ENG: Engineering: security, performance, reliability, testing, deployment, code quality

> **Reviewer summary.** The app gets the basics right: ownership checks return 404 for non-owners (verified), CSRF protection is on (including for HTMX), and passwords are validated. Engineering-wise it is still a prototype. The committed production configuration cannot serve traffic with DEBUG=False: every request crashes with a debug-toolbar RuntimeError, and logfire.configure() raises without a token. The defaults (DEBUG=True, a committed django-insecure SECRET_KEY, no proxy/HTTPS settings) push deployments into insecure modes, and I demonstrated a CSRF 403 on the custom domain behind Railway's TLS proxy. The engine works row by row with a separate autocommitted save per row: 400x25 (10k interviews) takes about 44 s for "Compute pre-interview", which is over gunicorn's 30 s timeout. The config allows 10M-row cross-products (about 13 GB to build, about 44 GB to export), anyone can sign up, and nothing is rate-limited or capped, so one click can take the site down. CSV upload deletes the existing population before parsing, so a bad file gives a 500 and 0 students. The meta-preference editor renders a Python repr with |safe inside HTML attributes, which is XSS I demonstrated. There are no tests or CI, mypy is unconfigured (138 errors, 22 real ones with the django-stubs plugin), and the Docker/entrypoint does installs and builds at every container start and installs the dev group in production. The fixes are mostly small and well understood. The recommended route: a Phase-0 settings/URL hotfix; then CI plus pytest-django/hypothesis tests; then numpy/SQL-vectorised steps and background execution via the built-in django.tasks API on the django-tasks-db backend (which I ran successfully on Django 6.1.1), with a SimulationRun model polled by HTMX.

<a id="eng-1"></a>

### ENG-1: Production mode is broken and insecure by default: debug_toolbar URLs crash every request, logfire crashes at import, DEBUG defaults to True, and a hard-coded SECRET_KEY is used as fallback

**Severity:** 🟠 high (originally critical) · **Kind:** defect · **Effort:** S · **Plan:** 0.1 · **Verification:** confirmed

**Evidence.** NRMP_Simulated/urls.py:3,10 (unconditional debug_toolbar_urls()); NRMP_Simulated/settings.py:23 (fallback 'django-insecure-ed7u8…' committed to git), :26 (DEBUG default "True"), :72-78/93-95 (toolbar only when DEBUG), :191-228 (logfire.configure() when not DEBUG). Ran a GET / with DEBUG=False on the real URLconf: 'RuntimeError Model class debug_toolbar.models.HistoryEntry doesn't declare an explicit app_label…'. `DEBUG=False manage.py check` without a token: LogfireConfigError ('…set the LOGFIRE_TOKEN environment variable'). With DEBUG=False and no SECRET_KEY env var, settings.SECRET_KEY.startswith('django-insecure') == True.

**Why it matters.** Setting DEBUG=False (as CLAUDE.md's docker example does) takes the site down, so production very likely runs DEBUG=True (lead F2). That exposes tracebacks, settings and SQL on error pages and keeps debug_toolbar/browser-reload apps loaded. If SECRET_KEY is ever left unset, the publicly known committed key signs sessions and password-reset tokens, which allows session forgery. The dev group is also installed in the image (ENG-9), so the import succeeds and the crash happens at request time rather than at deploy time. That makes it easy to miss.

**Recommendation.** NRMP_Simulated/urls.py: `urlpatterns = [path('admin/', admin.site.urls), path('', include('nrmps.urls'))]` then `if settings.DEBUG and 'debug_toolbar' in settings.INSTALLED_APPS: from debug_toolbar.toolbar import debug_toolbar_urls; urlpatterns += [*debug_toolbar_urls(), path('__reload__/', include('django_browser_reload.urls'))]` (and add BrowserReloadMiddleware in the DEBUG block, or drop the app). settings.py: `DEBUG = env_bool('DEBUG', default=False)`; `SECRET_KEY = os.environ.get('SECRET_KEY') or (DEV_KEY if DEBUG else raise ImproperlyConfigured)`; `logfire.configure(send_to_logfire='if-token-present', console=False, service_name='nrmp-simulated', environment=os.environ.get('RAILWAY_ENVIRONMENT_NAME','local'))` (verified `'if-token-present'` exists in .venv logfire/_internal/config.py:501). Add a CI job that runs `DEBUG=False SECRET_KEY=… manage.py check --deploy --fail-level WARNING` plus one test-client GET with DEBUG=False so this cannot regress. Rotate the committed key once a real key is set.

**Verifier note (confirmed).** Reproduced in isolation. With DEBUG=False and LOGFIRE_SEND_TO_LOGFIRE=false, GET / raised 'RuntimeError Model class debug_toolbar.models.HistoryEntry doesn't declare an explicit app_label…'. With DEBUG=False and no token, `manage.py check` raised the LogfireConfigError. SECRET_KEY.startswith('django-insecure') is True when the env var is unset. The cited lines are correct: urls.py:3,10; settings.py:23, 26, 72-78, 93-95; logfire.configure() at settings.py:227. logfire._internal/config.py:501 does accept send_to_logfire='if-token-present'. I lowered critical to high because production exposure depends on Railway env vars I cannot see; the deployed host was unreachable (the proxy rejected CONNECT). DEBUG=True leaks tracebacks and source, but Django masks SECRET_KEY/PASSWORD settings on debug pages, and the toolbar only renders for INTERNAL_IPS=127.0.0.1, which never matches behind Railway's proxy. The session-forgery risk holds only if SECRET_KEY is actually unset in production.

<a id="eng-2"></a>

### ENG-2: No HTTPS/proxy security settings; CSRF fails on the custom domain behind Railway's TLS proxy

**Severity:** 🟡 medium (originally high) · **Kind:** defect · **Effort:** S · **Plan:** 0.1 · **Verification:** partially

**Evidence.** `DEBUG=False SECRET_KEY=x LOGFIRE_SEND_TO_LOGFIRE=false DJANGO_SETTINGS_MODULE=smoke_prod_settings manage.py check --deploy` gives security.W004 (HSTS), W008 (SSL redirect), W009 (weak key), W012 (SESSION_COOKIE_SECURE), W016 (CSRF_COOKIE_SECURE). A scratch test (review/ENG/prod/csrf.py) POSTed /login/ with Host/Origin https://nrmp-simulated.heteroskedastic.org and X-Forwarded-Proto: https: 403 with current settings, 200 with SECURE_PROXY_SSL_HEADER set. settings.py:35-42 only trusts RAILWAY_PUBLIC_DOMAIN (git log shows a 'crfs' fix commit 4556013). No SECURE_CSP (see ENG-22).

**Why it matters.** Railway terminates TLS, so without SECURE_PROXY_SSL_HEADER request.is_secure() is False. Django's CSRF origin check then compares against http://… and rejects every form POST on any domain not listed in CSRF_TRUSTED_ORIGINS. The same setting is also required before SECURE_SSL_REDIRECT can be enabled (otherwise it loops). Session and CSRF cookies are currently sent without the Secure flag.

**Recommendation.** In a `if not DEBUG:` block: `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO','https')`, `SECURE_SSL_REDIRECT = True`, `SECURE_REDIRECT_EXEMPT = [r'^healthz/$']`, `SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = True`, `SECURE_HSTS_SECONDS = 3600` (raise to 31536000 after verification; add INCLUDE_SUBDOMAINS/PRELOAD only deliberately), `SECURE_CONTENT_TYPE_NOSNIFF = True` (default). Derive CSRF_TRUSTED_ORIGINS as `[f'https://{h}' for h in ALLOWED_HOSTS if h not in ('localhost','127.0.0.1')]`. Move the production host out of the ALLOWED_HOSTS code default (settings.py:29) into the environment.

**Verifier note (partially).** The mechanism is real. In a local simulation (Host and Origin https://nrmp-simulated.heteroskedastic.org, X-Forwarded-Proto: https) the login POST returned 403 ('Origin checking failed'). It returned 200 with SECURE_PROXY_SSL_HEADER set, and also 200 when CSRF_TRUSTED_ORIGINS contains the domain. The missing secure-cookie and HSTS settings are real. However, the summary's 'demonstrated a CSRF 403 on the custom domain behind Railway's TLS proxy' was a local reproduction, not a test against production. The production outcome depends on env vars nobody can see: settings.py:39-42 reads CSRF_TRUSTED_ORIGINS from the environment, and RAILWAY_PUBLIC_DOMAIN may or may not be the custom domain. The owner added the domain in b6cf5ad and has not touched it since, which suggests login may work there. The recommendation to derive CSRF_TRUSTED_ORIGINS from ALLOWED_HOSTS is unnecessary once SECURE_PROXY_SSL_HEADER is set (same-origin then passes; verified). It also breaks for wildcard hosts such as '.example.com'.

<a id="eng-3"></a>

### ENG-3: Engine steps do one query plus one autocommitted UPDATE per row; 10k interviews exceed gunicorn's 30 s timeout

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 0.4 · **Verification:** confirmed

**Evidence.** nrmps/simulation_engine.py:55-66, 85-96 (per-row .save()), :108-119, 131-142 (one SELECT per student/school, then per-row save). Benchmark review/ENG/perf/perf2.py at 400 students x 25 schools = 10,000 rows (SQLite, isolated DB): initialize 0.83 s/15 queries; students_rate 11.13 s/10,002 queries; schools_rate 11.03 s/10,002; students_rankings 11.09 s/10,401; schools_rankings 10.65 s/10,026. Total for the 'Compute Pre-Interview Scores and Rankings' button: 43.9 s. gunicorn default timeout = 30 (.venv/…/gunicorn/config.py:859). Wrapping one step in transaction.atomic() cut it to 1.91 s. A single SQL `UPDATE … FROM (SELECT id, ROW_NUMBER() OVER (PARTITION BY student_id ORDER BY score DESC) …)` ranked all 10k rows in 0.02 s with 1 query.

**Why it matters.** Real NRMP scale is about 50k applicants and 6k programs. Even small classroom simulations (400x25) already time out and return a 502 through gunicorn, possibly after a partial update, because nothing is transactional. Autocommit per row also means a crash leaves half-scored data. Scoring is embarrassingly vectorisable: it is a weighted dot product per pair.

**Recommendation.** Quick win (S): wrap every engine entry point in `transaction.atomic()` and replace per-row saves with `bulk_update(rows, fields, batch_size=2000)`. Proper fix (M): split `nrmps/engine/` into pure functions over numpy arrays (students x metas matrix, schools x metas matrix, weight matrices; `U = W_s @ M_school.T + rng.normal(0, err, shape)`; ranks via `np.argsort(-U, axis=1)`), independent of the ORM and unit-testable. Persist with `bulk_create`/`bulk_update`. On PostgreSQL, use psycopg3 `cursor.copy()` into a temp table plus `UPDATE … FROM` for million-row writes. Compute rankings in SQL with `Window(RowNumber(), partition_by=[F('student')], order_by=F('student_pre_observed_score_of_school').desc())` or the raw UPDATE shown. Target: under 2 s for 100k rows. Longer term, stop materialising the full cross-product (only applications/interviews need rows; see the simulation-engine reviewer).

**Verifier note (confirmed).** I re-ran perf2.py at 400x25 in an isolated SQLite DB: initialize 0.84 s with 15 queries; students_rate 11.03 s with 10,002 queries; schools_rate 11.18 s; students_rankings 10.85 s with 10,401 queries; schools_rankings 10.31 s. Total 43.4 s. The window-function UPDATE took 0.02 s in 1 query. gunicorn's default timeout of 30 is confirmed (.venv gunicorn/config.py:859). The per-row .save() calls at simulation_engine.py:66/96/119/142 are as cited. Caveats: the timings were measured on SQLite with fsync-per-autocommit, and Postgres on Railway was not measured (likely the same order of magnitude). Django's ORM refuses Window expressions inside .update(), so ranking 'with Window(RowNumber(), …)' needs annotate plus bulk_update, or the raw UPDATE…FROM (SQLite ≥3.33 or Postgres).

<a id="eng-4"></a>

### ENG-4: No background execution or progress reporting; recommend the built-in django.tasks API with the django-tasks-db backend, a SimulationRun model and HTMX polling

**Severity:** 🟡 medium (originally high) · **Kind:** gap · **Effort:** L · **Plan:** 2.5 · **Verification:** confirmed

**Evidence.** All engine work runs inside the request (nrmps/views.py:405-472). Verified in .venv: Django 6.1.1 ships django/tasks/ with only backends/immediate.py and backends/dummy.py (no persistent worker). TaskResult/TaskContext (django/tasks/base.py:203-271) have no progress field. PyPI: django-tasks-db 0.13.0 ('ORM-based backend for Django Tasks', requires django>=5.2, classifiers list 5.2/6.0), django-tasks-rq 0.12.0, celery 5.6.3, huey 3.4.0, django-rq 4.2.0. In a scratch venv (review/ENG/tasksvenv) Django 6.1.1 + django-tasks-db: `@task(takes_context=True)` enqueue went READY, then `manage.py db_worker --batch` gave SUCCESSFUL with return value. htmx 2.0.6 (static/js/htmx.mini.js) honours HTTP 286 to stop polling; django-htmx provides HttpResponseStopPolling (.venv/…/django_htmx/http.py:27).

**Why it matters.** Long steps (ENG-3) and the future match step need to run outside the request. Comparison: django.tasks alone has no worker. django-tasks-db needs no new infrastructure (it uses the Railway Postgres), follows the standard Django API, and ImmediateBackend keeps tests synchronous. Celery or RQ would need Redis plus a broker and more operations work for no benefit at this scale. Huey is simple but has its own non-standard API. SSE would tie up one sync gunicorn worker per open page, so polling fits the current WSGI stack better.

**Recommendation.** Add `django-tasks-db` to deps and 'django_tasks_db' to INSTALLED_APPS. Settings: `TASKS = {'default': {'BACKEND': 'django_tasks_db.DatabaseBackend', 'QUEUES': ['default']}}`, and ImmediateBackend in tests/dev when desired. New model `SimulationRun(simulation FK, step CharField(choices), status [queued/running/succeeded/failed], progress_done/progress_total IntegerFields, task_id, config_snapshot JSONField, seed BigIntegerField, error TextField, started_at/finished_at, created_by)` with `UniqueConstraint(fields=['simulation'], condition=Q(status__in=['queued','running']), name='one_active_run')` to prevent concurrent runs. `nrmps/tasks.py`: `@task def run_step(run_id)` calls the engine and updates progress via `SimulationRun.objects.filter(pk=…).update(progress_done=…)` every N rows. View: POST creates the run, enqueues it, and returns a `_run_status` partial with `hx-get=… hx-trigger='every 1s' hx-swap='outerHTML'`. The status view returns HttpResponseStopPolling plus an `HX-Trigger: runFinished` event when done, which refreshes the counts/plots. Railway: second service from the same image with start command `python manage.py db_worker --queue-name default`, plus a cron job running `prune_db_task_results`.

**Depends on.** ENG-3

**Verifier note (confirmed).** Verified. Django 6.1.1 django/tasks/backends contains only immediate.py and dummy.py. TaskResult is at base.py:203 and TaskContext at :267. django_htmx/http.py:13/27 has HTMX_STOP_POLLING=286 and HttpResponseStopPolling. The vendored htmx is 2.0.6. I re-ran the scratch django-tasks-db 0.13.0 project on Django 6.1.1: the task went READY, then `db_worker --batch` gave SUCCESSFUL. The db_worker (--queue-name, --batch) and prune_db_task_results commands exist, and the backend path 'django_tasks_db.DatabaseBackend' is exported. One nit: the package classifiers stop at Django 6.0, so 6.1 is tested here but not declared. I lowered severity to medium: once ENG-3 vectorisation (under 2 s per 100k rows) and ENG-5 caps are in place, most steps fit comfortably inside a request. Background execution then matters mainly for multi-iteration batches and very large runs.

<a id="eng-5"></a>

### ENG-5: Anyone can sign up and trigger 10M-row operations that exhaust memory; no quotas or rate limiting

**Severity:** 🟡 medium (originally high) · **Kind:** defect · **Effort:** M · **Plan:** 0.4, 2.5 · **Verification:** partially

**Evidence.** nrmps/views.py:52-66 (open signup, no throttle, no email verification); LoginView (nrmps/urls.py:9) has no lockout. nrmps/models.py:483-492 allows 10000 applicants x 1000 schools. Measured initialize_interview peak 1,291 B/row (tracemalloc, perf.py), so about 12.9 GB for 10M rows built in one Python list (simulation_engine.py:20-35). download-interviews peaked at 4,441 B/row with a fully buffered HttpResponse (views.py:528-554), so about 44 GB for 10M rows (2.39 s per 10k rows). `?page_size=100000000` is accepted (views.py:337-342, 499-504). A worker process is about 148 MB RSS after app load, with 4 workers hard-coded.

**Why it matters.** A single anonymous visitor can create an account, set 10000x1000, click Initialize, and OOM-kill the container. The same applies to CSV export. Brute-forcing logins is also unthrottled. TODO.md's 'Add rate limiting for API endpoints' is the right idea but aims at the wrong target: there is no API, and the exposed surfaces are signup, login and the heavy actions.

**Recommendation.** (1) Quotas in SimulationConfig.clean(): cap applicants x schools (for example 2M cells, configurable per user via a staff flag or group) and cap simulations per user. (2) Stream exports: `StreamingHttpResponse(csv_rows(qs.values_list(...).iterator(chunk_size=5000)))` with a pseudo-buffer writer, or generate the export in a background task to a gzip file. (3) Clamp page_size to the offered list [25, 50, 100, 200, 500]. (4) Add django-axes 8.x for login lockout and django-ratelimit 4.1 (`@ratelimit(key='ip', rate='5/h', method='POST')`) on signup and on heavy POST actions. Use a shared cache (DatabaseCache via `createcachetable`) because LocMem is per-worker. (5) Optionally require email verification or admin approval (User.status already exists, see ENG-19).

**Verifier note (partially).** Holds: signup is open with no throttle (views.py:52-66), LoginView has no lockout, the config caps are 10000x1000 (models.py:483-492), and page_size is unbounded (views.py:337-342, 499-504). The OOM figures are overstated because they ignore gunicorn's 30 s worker timeout. I measured Interview instance construction without tracemalloc at about 51k instances/s and about 630 B/row RSS (tracemalloc slows construction about 3x and reports different per-row figures). A single Initialize request is therefore killed after roughly 1.5M instances (about 1 GB), not 12.9 GB. The same bound applies to the export: at about 2.4 s per 10k rows, a worker dies after about 125k rows. A 10M-row simulation also cannot be created through the UI within the timeout. bulk_create wraps its batches in one atomic block, but the preceding delete() at simulation_engine.py:19 is committed separately, so a killed request leaves 0 interviews. The real impact is worker exhaustion: 4 sync workers means 4 concurrent heavy clicks stall the site for 30 s each, repeatably, with roughly 1 GB spikes per worker that can still OOM a small plan. Caps, clamping and rate limiting remain the right fixes.

<a id="eng-6"></a>

### ENG-6: CSV upload deletes the population before parsing, silently coerces bad values, loses data on round-trip, and stores user files forever on shared ephemeral disk

**Severity:** 🟠 high · **Kind:** defect · **Effort:** M · **Plan:** 0.6 · **Verification:** confirmed

**Evidence.** views.py:246-279 writes the upload to BASE_DIR/data/simulation_{id}_students.csv, then models.py:278-365/367-473 re-reads it. models.py:298/387 delete existing rows before parsing, with no transaction. Scratch test review/ENG/upload/upload.py: (a) downloading students CSV and re-uploading it gives meta_preference {'program_size':0.015,…} before and {} after, and all student pre-scores become [0.0], because the download (views.py:293) omits meta_preference. (b) 'Alice,abc / Bob,57 / Carol,-3' is accepted as scores 0.0, 57.0, -3.0 (validators bypassed by bulk_create; Student.score max is 0.99). (c) a binary file raises UnicodeDecodeError, returns 500, and leaves 'students now 0' (population destroyed). (d) the positional school fallback reads column 3 as a legacy meta_stddev (models.py:414-417, F841), so the documented 4th column score_meta is dropped ({}). (e) the file remains in data/ after the request, data/ is not in .gitignore, and deleting a simulation does not remove it. templates/nrmps/privacy.html:10 claims 'uploaded datasets are kept in your environment'.

**Why it matters.** This path loses user data and has no validation. On Railway the disk is per-container and ephemeral, gunicorn runs 4 workers, and concurrent uploads for the same simulation race on the same filename. HTMX swallows the 500 (ENG-16), so the user just sees the counts drop to 0. It also makes the documented CSV round-trip workflow unusable for experiments.

**Recommendation.** Parse in memory inside the form: `PopulationCSVForm.clean_file()` checks size (5 MB) and extension, wraps it with `io.TextIOWrapper(f.file, encoding='utf-8-sig', newline='')`, uses `csv.DictReader`, and caps rows at 50k. Validate each row with a small row Form or dataclass (name required, 0<=score<=1, capacity>=0 int, score_meta/meta_preference JSON objects of str to float) and collect `[(line_no, column, message)]`. If there are any errors, return the population partial with an error table (first 20) and change nothing. Otherwise run `transaction.atomic(): delete(); bulk_create()`. Never write to disk. Make the format symmetric: download and upload both carry name, score, score_meta, meta_preference (plus capacity for schools); remove the positional/legacy branches; add a 'download template' link and a dry-run/preview option. Move this code to `nrmps/io/population_csv.py` and delete the data/ directory convention. Correct the privacy page.

**Verifier note (confirmed).** Reproduced with the test client in an isolated DB. (a) Download then re-upload: the download header is 'name,score,score_meta', and meta_preference went from {'program_size':0.49,…} to {}. (b) 'name,score / Alice,abc / Bob,57 / Carol,-3' was stored as 0.0, 57.0, -3.0. (c) A binary upload returned 500 (UnicodeDecodeError) and left 0 students, because the delete at models.py:298 runs before decoding and nothing is atomic. (e) The file persists in data/, and `git check-ignore data/x.csv` returns nothing. Claim (d) holds from code reading: the positional school fallback treats row[3] as meta_stddev and row[4] as score_meta (models.py:414-422). privacy.html:10 says 'uploaded datasets are kept in your environment'. Nit: without a header row the first data row is swallowed as the header, which is a further data-loss path.

<a id="eng-7"></a>

### ENG-7: XSS and broken markup: meta-preference lists rendered as Python repr with |safe inside HTML attributes

**Severity:** 🟡 medium (originally high) · **Kind:** defect · **Effort:** S · **Plan:** 0.5 · **Verification:** partially

**Evidence.** templates/nrmps/simulation_manage.html:172,283 (`x-data="metaEditor($el, '…', {{ …meta_preference|default:'[]'|safe }})"`) and :194,305 (`value='{{ …|safe }}'`). The demo server renders `value='['program_size', 'reputation', 'location']'` (manage1.html:205), which is broken HTML: the browser sees value='['. forms.py:91-112 accepts any JSON (a dict {'not':'a list'} is valid). Scratch test review/ENG/upload/xss.py: POSTing applicant_meta_preference=["x\" x-init=\"alert(document.domain)"] gave 302, and the page then renders `x-data="metaEditor($el, 'id_applicant_meta_preference', ['x" x-init="alert(document.domain)'])"`, an injected Alpine directive that executes.

**Why it matters.** Today this is self-XSS because only the owner sees the page. It becomes stored XSS as soon as the `public` flag or sharing is implemented (ENG-19), or if staff view configs. The client-side normaliser in the page's inline script is the only guard, and a direct POST bypasses it. Without JS the hidden input submits '[' and the config cannot be saved.

**Recommendation.** Render initial data with `{{ config_form.instance.applicant_meta_preference|json_script:'applicant-meta-initial' }}` and use `x-data="metaEditor($el, 'id_applicant_meta_preference', JSON.parse(document.getElementById('applicant-meta-initial').textContent))"`. Render the hidden input's static value escaped (`value="{{ form.applicant_meta_preference.value }}"`, where Django escapes the JSON string). Validate server-side in one shared `clean_meta_list()` helper: must be a list of up to 20 unique strings matching `^[a-z0-9_-]{1,64}$`, otherwise raise ValidationError. Never silently return []. Ban `|safe` in templates by grep in CI.

**Verifier note (partially).** The vulnerability is real, but the reviewer's proof of concept does not actually execute. I rendered the page and loaded it in Playwright Chromium. With the exact payload ['x" x-init="alert(document.domain)'], the x-init value becomes "alert(document.domain)'])", which Alpine rejects ('Invalid or unexpected token'). No dialog fired. A corrected payload ['x" x-init="alert(document.domain)" y="'] fired 2 alert dialogs, one for each |safe site (lines 172/194 of the rendered template). The broken markup is confirmed: value='['program_size', …]' at simulation_manage.html:194/305. Severity is lower than claimed today. The manage page is owner-only (404 for others) and POSTs are CSRF-protected, so this is currently self-XSS. It becomes stored XSS only if sharing or `public` is implemented. The json_script plus server-side validation fix is correct.

<a id="eng-8"></a>

### ENG-8: No tests, CI or pre-commit; a prototype suite immediately catches 2 real bugs

**Severity:** 🟠 high · **Kind:** gap · **Effort:** L · **Plan:** 1.1 · **Verification:** confirmed

**Evidence.** nrmps/tests.py:1 is a comment only; no .github/ and no .pre-commit-config.yaml. Prototype (scratch review/ENG/tests_proto/test_proto.py, pytest-django + hypothesis in a scratch venv): 8 tests, '2 failed, 6 passed in 6.12s'. Passing: non-owner gets 404 on 4 routes; the HTMX create-students POST returns only the #population-counts fragment; a hypothesis property test (300 random markets) of a reference deferred-acceptance algorithm (capacity, individual rationality, no blocking pairs). Failing, both real bugs: default SimulationConfig().full_clean() raises (ENG-18), and observed pre-interview scores max out at 0.100 because the rating error multiplies (lead F5).

**Why it matters.** The upcoming work (invitations, interviews, final ranking, match) is algorithmic and easy to get subtly wrong. Stability and optimality properties are exactly what property-based tests check well. There is also nothing to catch F2/F3-style regressions or the dependency bumps.

**Recommendation.** Dev deps: pytest-django 4.14, hypothesis 6.x, factory-boy 3.3 (or model-bakery), pytest-cov, pytest-playwright 0.9 (optional job). pyproject `[tool.pytest.ini_options] DJANGO_SETTINGS_MODULE='NRMP_Simulated.settings' python_files=['test_*.py'] addopts='--strict-markers -ra'`. Layout: nrmps/tests/{factories.py, test_engine_math.py (score, noise, ranking ties, seeds), test_match_properties.py (hypothesis: stable, capacity respected, applicant-optimal compared against brute-force enumeration for n<=6, strategy-proof for applicants), test_views_permissions.py (parametrised over every URL name: anon redirects to login, non-owner 404, GET-only/POST-only enforced), test_htmx_partials.py (HX-Request gives a fragment with no <html>), test_csv_io.py (round-trip and error reporting), test_settings_prod.py (DEBUG=False GET / returns 200)}. Playwright smoke: log in, create simulation, generate, run steps, screenshot. GitHub Actions (see extra): ruff check, ruff format --check, mypy (django-stubs), `manage.py makemigrations --check --dry-run`, `check --deploy` with prod env, and pytest against a postgres:17 service plus sqlite. pre-commit with ruff and ruff-format hooks, check-added-large-files, and a no-|safe grep.

**Depends on.** ENG-12, ENG-13

**Verifier note (confirmed).** nrmps/tests.py contains only a comment. There is no .github/ and no .pre-commit-config.yaml. I copied and re-ran the prototype suite with the scratch venv (pytest-django 4.14.0, hypothesis 6.168.1): '2 failed, 6 passed in 6.07s'. The failures are test_default_config_is_valid (ValidationError) and test_pre_interview_rating_adds_noise_not_scales, matching ENG-18 and F5. The hypothesis test exercises a reference deferred-acceptance implementation, not app code, which the finding states correctly. Side note: a .hypothesis/ directory (created 16:41) appeared in the repo root, apparently from running hypothesis with cwd=repo. It is git-ignored, so harmless.

<a id="eng-9"></a>

### ENG-9: Dependency groups are wrong: a fresh `uv sync` dev env cannot start, and the Docker image installs the dev group in production

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 0.1 · **Verification:** confirmed

**Evidence.** pyproject.toml:15-20 puts whitenoise and dj-database-url in the 'prod' group, but settings.py:82 always loads whitenoise middleware. Fresh env: `UV_PROJECT_ENVIRONMENT=<scratch> uv sync --frozen` then loading the WSGI app gives 'ModuleNotFoundError: No module named whitenoise' (manage.py check passes, which hides it). `uv export --frozen --group prod` includes cookiecutter, django-debug-toolbar, django-stubs, mypy, pytest, ruff, ty, because uv's default-groups is ['dev'] and there is no [tool.uv] override. `--no-dev --group prod` gives only gunicorn, honcho, whitenoise. honcho (a dev process runner for Procfile.tailwind) is a runtime dependency (pyproject.toml:11).

**Why it matters.** CLAUDE.md's setup instructions ('uv sync' then runserver) fail on a clean clone. The production image carries about 100 MB of dev tooling, including debug_toolbar, which makes the ENG-1 crash appear at runtime instead of at import.

**Recommendation.** Move whitenoise and dj-database-url to [project].dependencies (both tiny and imported by settings). Keep gunicorn and psycopg[binary] in 'prod'. Move honcho to 'dev' and drop cookiecutter unless tailwind init is needed. Docker: `uv sync --locked --no-dev --group prod`. Alternatively set `[tool.uv] default-groups = ['dev']` explicitly and document `uv sync --group prod` for a local prod-like run. Use `--locked` in CI so a stale lock fails.

**Verifier note (confirmed).** `uv export --frozen` with the default groups does not include whitenoise, yet settings.py:82 always loads WhiteNoiseMiddleware, so runserver or WSGI loading fails on a plain `uv sync`. `uv export --frozen --group prod` includes cookiecutter, django-debug-toolbar, django-stubs, mypy, pytest, ruff and ty, because dev is a default group, so the Dockerfile:13 image ships dev tooling. One detail is wrong: `--no-dev --group prod` yields dj-database-url, gunicorn, honcho, psycopg/psycopg-binary and whitenoise (plus the main dependencies), not 'only gunicorn, honcho, whitenoise'. honcho is indeed a runtime dependency (pyproject.toml:11).

<a id="eng-10"></a>

### ENG-10: Dockerfile/entrypoint installs, builds and migrates at every container start; Node in the runtime image; no .dockerignore; root user; fixed gunicorn settings

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** M · **Plan:** 1.2 · **Verification:** confirmed

**Evidence.** Dockerfile:4 (nodejs/npm in the runtime image), :10 `COPY . .` before dependency install (no layer caching) with no .dockerignore (copies .git, .venv, db.sqlite3, data/, node_modules), :13 `uv sync --frozen --group prod` (includes dev, ENG-9), and no USER. entrypoint.sh:8 `uv sync --group prod` (not frozen, needs network at boot), :12 `tailwind install` (npm install at boot), :15 build, :19 migrate (run by every replica concurrently), :23 collectstatic, :27 `uv run gunicorn … --workers 4` (uv run re-syncs; ignores WEB_CONCURRENCY; default sync worker with 30 s timeout; no --preload or access log). Each worker is about 148 MB RSS after app load. No railway.json, health endpoint or Procfile for production. dj_database_url.parse (settings.py:128) has no conn_max_age/conn_health_checks.

**Why it matters.** Cold starts are slow and depend on npm and PyPI being reachable. A registry outage or a lock drift fails the deploy at runtime instead of at build time, and concurrent migrations can race. Four sync workers at about 150 MB each is roughly 600 MB baseline and invites OOM on small Railway plans.

**Recommendation.** Multi-stage Dockerfile (see extra): stage 1 `node:22-alpine` runs `npm ci && npm run build` in theme/static_src (the @source glob needs the repo copied); stage 2 `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` does `uv sync --locked --no-dev --group prod --no-install-project` (cached layer), then COPY, copies the CSS from stage 1, runs `collectstatic` at build time, creates a non-root user, sets `ENV UV_NO_SYNC=1 PYTHONUNBUFFERED=1`, and uses `CMD .venv/bin/gunicorn NRMP_Simulated.wsgi --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-2} --timeout 60 --preload --access-logfile -`. Add .dockerignore. railway.json: builder DOCKERFILE, `deploy.preDeployCommand` running `python manage.py migrate --noinput`, `healthcheckPath: /healthz` (a trivial view that does a DB `SELECT 1`). `dj_database_url.parse(url, conn_max_age=600, conn_health_checks=True)`. Document every env var in an `.env.example` and in README/CLAUDE.md.

**Depends on.** ENG-9

**Verifier note (confirmed).** Checked the Dockerfile: nodejs/npm (:4), `COPY . .` before dependency sync (:10), `uv sync --frozen --group prod` (:13), no USER, and no .dockerignore in the repo. entrypoint.sh runs a non-frozen uv sync (:8), tailwind install (:12), build (:15), migrate (:19), collectstatic (:23), and `uv run gunicorn … --workers 4` (:27). The explicit --workers overrides WEB_CONCURRENCY, and `uv run` re-syncs by default. There is no railway.json and no health endpoint. dj_database_url.parse at settings.py:128 passes no conn_max_age. The recommendations are standard and feasible.

<a id="eng-11"></a>

### ENG-11: Static assets: whitenoise without compression or manifest; vendored htmx and Alpine outside dependency management

**Severity:** ⚪ low (originally medium) · **Kind:** gap · **Effort:** S · **Plan:** 1.2 · **Verification:** confirmed

**Evidence.** settings.STORAGES is the default StaticFilesStorage (printed in the f2.py run), so there are no hashed filenames and no gzip/brotli. whitenoise then cannot set far-future cache headers, and CSS/JS changes need hard refreshes. static/js/htmx.mini.js is version 2.0.6 (npm latest 2.0.11); static/js/alpine_mini.js is 3.14.9 (latest 3.17.4). uv-bump does not see these, and theme/static_src/package-lock.json pins daisyui 5.1.12 / tailwindcss 4.1.13 (latest 5.7.44 / 4.3.3).

**Why it matters.** The upgrade review covered Python only. The front-end libraries that drive every HTMX interaction are three to five minor versions behind and have no update path.

**Recommendation.** `STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'}}` when not DEBUG. Add htmx.org and alpinejs (or @alpinejs/csp, see ENG-22) to theme/static_src/package.json and copy them into static/js during `npm run build`, or document the vendoring with a version comment. Add Dependabot or Renovate for the uv, npm and github-actions ecosystems.

**Verifier note (confirmed).** STORAGES is the default (no whitenoise manifest or compression). static/js/htmx.mini.js reports version 2.0.6 and alpine_mini.js 3.14.9. package-lock pins daisyui 5.1.12 and tailwindcss 4.1.13. npm view gives htmx.org 2.0.11, alpinejs 3.17.4, daisyui 5.7.44, tailwindcss 4.3.3. Wording nit: htmx is 5 patch releases behind, not 3-5 minor versions. I lowered severity because nothing is broken or known-vulnerable; this is maintenance hygiene.

<a id="eng-12"></a>

### ENG-12: mypy runs without the django-stubs plugin (138 mostly bogus errors); with the plugin, 22 real errors remain

**Severity:** ⚪ low (originally medium) · **Kind:** defect · **Effort:** S · **Plan:** 1.1 · **Verification:** confirmed

**Evidence.** `mypy .` gives 'Found 138 errors in 4 files' (65 var-annotated, 58 attr-defined such as 'Simulation has no attribute owner_id'). With scratch review/ENG/mypy.ini (plugins = mypy_django_plugin.main, django_settings_module, exclude migrations, scipy ignore_missing_imports) the count drops to 22 errors in 2 files. Real ones: models.py:270,274 (delete_students/delete_schools annotated -> int but return None); models.py:338-345, 436-450 (`row` reused as list[str] and dict in two branches); models.py:584 (`dict[str:float]` invalid annotation; module-level function with `self`); settings.py:128 (str | None passed to parse); settings.py:220-225 (untyped LOGGING dict). ty 0.0.84: 87 diagnostics, mostly Django-unaware unresolved-attribute (54).

**Why it matters.** With 138 unconfigured errors the type checker cannot act as a quality gate. Configured, it becomes a short, actionable list.

**Recommendation.** Add `[tool.mypy] plugins=['mypy_django_plugin.main'] python_version='3.13' exclude=['migrations/'] warn_unused_ignores=true` and `[tool.django-stubs] django_settings_module='NRMP_Simulated.settings'` plus `[[tool.mypy.overrides]] module=['scipy.*','logfire.*'] ignore_missing_imports=true`. Fix the 22 errors, then turn on `disallow_untyped_defs` for nrmps/engine/. Keep ty as an informational, non-blocking CI step until it supports Django.

**Verifier note (confirmed).** `mypy .` gives 'Found 138 errors in 4 files'. With the reviewer's mypy.ini (django-stubs plugin, migrations excluded, scipy ignored): 'Found 22 errors in 2 files'. The listed ones are present: models.py:270/274 missing return, :338-345 and :436-450 row type reuse, :584 dict[str:float] and the misplaced self, settings.py:128, and :220-225. Most of the 22 are typing hygiene rather than runtime bugs, so low severity is more apt than medium.

<a id="eng-13"></a>

### ENG-13: Ruff configuration is miswired; after a config fix plus format/--fix, 138 findings drop to 54, of which 7 are real

**Severity:** ⚪ low (originally medium) · **Kind:** recommendation · **Effort:** S · **Plan:** 1.1 · **Verification:** confirmed

**Evidence.** ruff.toml:2 target-version py312 vs pyproject requires-python >=3.13; :17 'DOC' has no effect without preview; :53 'TRIO' remapped to ASYNC1; D203/D211 and D212/D213 conflict warnings (no pydocstyle convention); :27 'FAST' (FastAPI) is irrelevant; :61 per-file-ignores 'tests/*' matches nothing (tests live in nrmps/tests.py). Current: 138 findings (54 E501, 41 in migrations). On a scratch copy (git archive), with target py313, migrations excluded, convention=google, then `ruff format` and `ruff check --fix`: 54 remain. 41 are D1xx missing docstrings. The real ones are F841 models.py:417, S110 views.py:675, SIM103 views.py:602, RUF046 models.py:222, DJ001 models.py:70, PERF401 simulation_engine.py:25, RUF005 NRMP_Simulated/urls.py:7 (gone with the ENG-1 fix). `ruff format --check`: 12 files would be reformatted (single quotes in views.py documentation(), theme/apps.py).

**Why it matters.** Worth fixing: F841/S110/SIM103/RUF046/DJ001 (real smells), and E501 via the formatter. Worth ignoring for Django: RUF012 on Meta/widgets, D105/D106 (magic methods, Meta classes), and D100 on module files. CLAUDE.md says docstrings are required for public functions, so either keep D103 and write the 15 view docstrings, or relax the rule.

**Recommendation.** ruff.toml: `target-version='py313'` (or delete it and let ruff read requires-python), `extend-exclude=['**/migrations/**']`, `[lint.pydocstyle] convention='google'`, drop DOC/TRIO/FAST, add 'DTZ', 'ERA', 'PT', 'PL' (selected), `ignore=['D100','D104','D105','D106','D107','RUF012']`, per-file-ignores `'**/tests/**'=['S101','D','PLR2004']`. Run `ruff format` once in a dedicated commit (and add it to .git-blame-ignore-revs).

**Verifier note (confirmed).** `ruff check .` gives 138 errors (54 E501, 15 D103, 14 RUF012, 14 D100 …) and prints the claimed warnings: TRIO remapped to ASYNC1, DOC has no effect without preview, and the D203/D211 and D212/D213 conflicts. `ruff format --check` reports 12 files would be reformatted. The per-file-ignore 'tests/*' matches nothing, and ruff.toml target-version py312 conflicts with requires-python >=3.13. I did not re-derive the post-fix count of 54. This is a config and hygiene recommendation, so low severity.

<a id="eng-14"></a>

### ENG-14: Ownership check and step views are copy-pasted 20 times; centralise them in a queryset/helper and a step dispatcher

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** S · **Plan:** 1.8 · **Verification:** confirmed

**Evidence.** `get_object_or_404(Simulation, pk=pk); if sim.owner_id != request.user.id: raise Http404()` appears 20 times in nrmps/views.py (grep -c). Six near-identical engine views (views.py:403-472) each do an inline import and call one function. Every view repeats @login_required. django-htmx middleware is installed but `request.htmx` is never used.

**Why it matters.** Any new view (invitations, interviews, match, plots, share links) must remember the check; one missed copy is an IDOR. Adding 'public' read-only sharing later would mean editing all 20 sites.

**Recommendation.** `class SimulationQuerySet(models.QuerySet): def owned_by(self, user): return self.filter(owner=user); def visible_to(self, user): return self.filter(Q(owner=user) | Q(public=True))`, and `objects = SimulationQuerySet.as_manager()`. Helper `get_owned_simulation(request, pk) = get_object_or_404(Simulation.objects.owned_by(request.user), pk=pk)`, or a `@simulation_view(owner_only=True)` decorator that injects `sim`. Add `django.contrib.auth.middleware.LoginRequiredMiddleware` (present in .venv contrib/auth/middleware.py:43) and mark public pages with `@login_not_required` (decorators.py:89). Replace the six step views with `STEPS = {'initialize': engine.initialize_interview, …}` and one `simulation_run_step(request, pk, step)` routed as `simulations/<int:pk>/steps/<slug:step>/`, which later enqueues a task (ENG-4). Add a permissions test parametrised over all URL names (ENG-8).

**Verifier note (confirmed).** `grep -c 'sim.owner_id != request.user.id' nrmps/views.py` gives 20, and there are 22 @login_required decorators. The six step views each use a function-level import of one engine function. request.htmx is never used. LoginRequiredMiddleware (contrib/auth/middleware.py:43) and login_not_required (decorators.py:89) exist in Django 6.1.1. The proposed QuerySet, helper and dispatcher are straightforward.

<a id="eng-15"></a>

### ENG-15: N+1 queries on the simulations list, missing composite indexes, redundant index, unbounded page_size

**Severity:** ⚪ low (originally medium) · **Kind:** defect · **Effort:** S · **Plan:** 1.8, 2.3 · **Verification:** partially

**Evidence.** templates/nrmps/simulations_list.html:39-40 call `sim.students.count`/`sim.schools.count` per row. Measured (perf/nplus1.py): 5 simulations = 13 queries, 25 = 53 (3 + 2N). EXPLAIN (perf3.py) on the per-student ranking query: 'SEARCH nrmps_interview USING INDEX student_id … USE TEMP B-TREE FOR ORDER BY'. Interview list sorted by student or score: 'SEARCH … simulation_id … USE TEMP B-TREE FOR ORDER BY' (a full-simulation sort for every page). Indexes present: unique(student_id, school_id), school_id, simulation_id, and student_id (redundant with the unique index prefix). models.py:720-722/741-742 use legacy unique_together. views.py:337-342 accepts any page_size.

**Why it matters.** At 1M+ rows every interview-list page sorts the whole simulation and COUNT(*)s it. The list page and the ranking steps are the hot paths. TODO.md 'Add database indexes for common queries' matches; these are the specific ones.

**Recommendation.** `Simulation.objects.owned_by(user).annotate(n_students=Count('students', distinct=True), n_schools=Count('schools', distinct=True))` (or Subquery counts), and paginate the list. Interview.Meta: `constraints=[UniqueConstraint(fields=['student','school'], name='uniq_interview_pair')]`, `indexes=[Index(fields=['simulation','student','-student_pre_observed_score_of_school']), Index(fields=['simulation','school','-school_pre_observed_score_of_student']), Index(fields=['simulation','status'])]`, and do the same for Match. Once the engine is vectorised, drop db_index on the student FK. Clamp page_size to the offered values and add `?q=` filtering. For big tables, consider keyset pagination or an estimated count.

**Depends on.** ENG-3

**Verifier note (partially).** The N+1 is real (simulations_list.html:39-40 calls .count twice per row, and views.py:73 has no annotate), but it only matters at the number of simulations a user owns. The redundant student_id index next to the unique_together (student, school) index is correct. The recommended composite indexes (simulation, student, -score) target the per-student ranking loop, where each sort covers only as many rows as there are schools (1000 or fewer, trivial), and ENG-3 removes that loop anyway. The indexes also do not help the interviews-list sorts, which order by student__name or school__name (joins) or by a score across the whole simulation; those would need (simulation, <sort column>) indexes or keyset pagination. The unbounded page_size duplicates ENG-5.

<a id="eng-16"></a>

### ENG-16: Silent failures: errors hidden by broad excepts, swallowed HTMX 4xx/5xx, no user feedback, double-submit possible

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 0.4, 1.5 · **Verification:** confirmed

**Evidence.** simulation_engine.py:62-63, 93-94 `except Exception: raise Exception(f'Error computing …') from None` (a KeyError on a missing meta key becomes a generic Exception with its cause suppressed); views.py:675 `except Exception: pass`; forms.py:105-107 JSON errors become []. No `hx-indicator`, `hx-disabled-elt` or `htmx:responseError` handler, and no messages framework use in templates (grep). The binary upload 500 in ENG-6 leaves the UI unchanged except counts at 0. create_students() returns 0 when no config exists (models.py:118-121) and views ignore the return (views.py:229), so a new simulation's 'Create Students' silently does nothing.

**Why it matters.** Users cannot tell success from failure, and developers lose root causes. Long synchronous POSTs without disabled buttons invite double clicks, which run the same destructive step twice concurrently.

**Recommendation.** Define domain exceptions (`SimulationError`, `MissingConfig`, `PopulationMismatch(meta_key)`) raised with `from exc`. In views, catch them and return the partial with an error alert (django-htmx `retarget(response, '#alerts')` and `trigger_client_event(response, 'toast', {...})`). Add a global `htmx:responseError`/`htmx:sendError` listener in base.html that shows a daisyUI toast. Add `hx-disabled-elt='this'` and `hx-indicator` spinners on every action button. Show 'no configuration yet' guidance instead of a 0 count. Add Django messages rendering to base.html for full-page flows.

**Verifier note (confirmed).** simulation_engine.py:62-63/93-94 raise a generic Exception 'from None'. views.py:674-675 has `except Exception: pass`. The forms.py clean_* methods silently return [] on a JSON error. grep finds no hx-indicator, hx-disabled-elt, responseError or messages rendering in the templates. create_students() returns 0 without a config (models.py:118-121) and the view ignores the return value (views.py:229). _population_counts.html:15 shows the Create button unconditionally.

<a id="eng-17"></a>

### ENG-17: Runs are not reproducible: unseeded global RNGs and in-place config edits leave no record of what produced a population

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 2.2 · **Verification:** confirmed

**Evidence.** models.py:62 `beta.rvs` (numpy global state), :156/:242 `random.gauss`, :221 capacity `random.gauss`; no seed field anywhere. views.py:119-121 edits the latest SimulationConfig in place, so the 'multiple configs per simulation' described in CLAUDE.md never happens and earlier parameters are overwritten. Generation calls scipy once per value (4 x N calls).

**Why it matters.** A research simulator must reproduce a result from (config, seed, code version). This is also needed for deterministic tests and for comparing scenarios with the same draws (common random numbers), which the visualisation and sliders goals rely on.

**Recommendation.** Add `seed = BigIntegerField(null=True)` on SimulationConfig (random if blank, stored), and thread `rng = np.random.default_rng(seed)` through all generation and engine functions (vectorised: `rng.beta(a, b, size=n)`, `rng.normal(1, sd, size=(n, k))`). Snapshot `config_snapshot` (model_to_dict), seed, `git_sha` (from a RAILWAY_GIT_COMMIT_SHA env var) and timings on SimulationRun (ENG-4). Either stop mutating configs (create a new version on save) or drop the FK multiplicity and make it a OneToOne. The simulation-engine reviewer covers the modelling side; this finding covers the plumbing.

**Depends on.** ENG-4

**Verifier note (confirmed).** beta.rvs uses global numpy state (models.py:62). random.gauss is used at :156/:221/:242. No seed field exists anywhere. views.py:119-121 binds the POST to the latest config instance, so configs are edited in place. Additional source of non-reproducibility: ranking ties are broken by DB order, because order_by uses only the score (simulation_engine.py:114/137). That is common after the CSV round-trip in ENG-6, which yields all-zero scores.

<a id="eng-18"></a>

### ENG-18: Model defaults violate the model's own validators, so saving the untouched default config fails; widget and validator mismatches

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 0.2 · **Verification:** partially

**Evidence.** models.py:560-563 school_meta_preference_stddev default=2 with MaxValueValidator(0.99); :564-568 school_meta_scores_stddev default=2 with max 0.99. Scratch forms_check.py: SimulationConfigForm(data=model defaults).is_valid() gives False with {'school_meta_preference_stddev': 'Ensure this value is less than or equal to 0.99.', 'school_meta_scores_stddev': …}, reproduced as a failing test in ENG-8. forms.py:163-164 widgets min=0 while the model min is 1; :167 step='any' on the IntegerField applicant_interview_limit; models.py:531 post-interview help_text says 'Pre-interview'; :572/577 school errors say 'score of each student'. Student.score max 0.99 but generation is not clipped and uploads bypass validation (ENG-6).

**Why it matters.** A new user's first 'Save Configuration' click fails. Engine code also defensively reads config values with getattr(..., default), which masks such problems.

**Recommendation.** Fix the defaults or ranges, then add `SimulationConfig.clean()` for cross-field rules (such as the beta-feasible stddev below sqrt(mean(1-mean)) instead of silent clamping in models.py:34-35, and school_score_mean > 0). Generate widget min/max/step from the model validators with a small `ModelFormWithValidatorAttrs` mixin so HTML and model limits never diverge. Add the test `SimulationConfig().full_clean(exclude=['simulation'])`. Correct the help_text copy errors (the Help/UI reviewers will reuse them for '?' tooltips).

**Verifier note (partially).** Core confirmed. SimulationConfigForm(data=model defaults).is_valid() is False, with errors on school_meta_preference_stddev and school_meta_scores_stddev ('≤ 0.99'). SimulationConfig().full_clean(exclude=['simulation']) raises the same errors. The unbound form's initial values are 2 and 2, so the first save of a new config fails. The widget min=0 versus model MinValueValidator(1), and step='any' on the integer applicant_interview_limit, are confirmed. models.py:531 has help_text 'Pre-interview' on the post-interview field, as claimed. One detail is wrong: the school_*_interview_rating_error help_text ('observed score for each student', models.py:572/577) is accurate, since that is the error with which schools observe students. It is not a copy error.

<a id="eng-19"></a>

### ENG-19: Admin is empty and several model fields are dead (public, iterations, Simulation.status, User.status/disabled)

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** S · **Plan:** 1.8 · **Verification:** confirmed

**Evidence.** nrmps/admin.py:1 is a comment only, so the custom User and all models are unmanageable in /admin/. models.py:93 `public` (default True, shown as 'Public: Yes' in simulations_list.html:33 but never read by any view), :95 iterations (never read), :97 status (never set), :71-72 User.disabled/status (never read; `disabled` duplicates is_active), :70 full_name CharField null=True (DJ001).

**Why it matters.** Users are told their simulation is 'Public' when nothing is shared, and the fields suggest features that don't exist. Admin is the cheapest ops tool for moderating signups (ENG-5) and inspecting runs.

**Recommendation.** admin.py: `@admin.register(User) class UserAdmin(auth_admin.UserAdmin)` adding full_name/status to fieldsets. Register Simulation (list_display owner/name/created_at/n_students, list_filter public, search), SimulationConfig inline, and read-only Student/School/Interview/Match with `list_select_related` and `show_full_result_count=False`. Either implement `public` as read-only sharing through `visible_to()` (ENG-14) or remove it and default new simulations to private. Wire `iterations` into multi-run batches (ENG-4) or remove it. Replace Simulation.status with SimulationRun status. Drop User.disabled in favour of is_active, and use User.status for approval gating if needed.

**Verifier note (confirmed).** nrmps/admin.py contains only a comment. grep shows `public` and `iterations` are used only in SimulationForm (forms.py:42) and simulations_list.html; no view or engine code reads them. Simulation.status and User.status/disabled are never read or set (models.py:70-72, 93-97). public defaults to True, and the list shows it as 'Yes'.

<a id="eng-20"></a>

### ENG-20: Account page 'Change password' goes to the admin (non-staff are bounced to admin login); no password reset

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 0.8 · **Verification:** confirmed

**Evidence.** templates/nrmps/account.html:13 href '/admin/password_change/'. On the demo server as non-staff 'demo' ('Is Staff: False'): GET gives 302 to /admin/login/?next=/admin/password_change/. /password_reset/ gives 404. No EMAIL_BACKEND configured.

**Why it matters.** Regular users cannot change or recover passwords. Signup collects an optional email that is never used.

**Recommendation.** Include `path('accounts/', include('django.contrib.auth.urls'))` (PasswordChangeView, PasswordResetView and friends) with DaisyUI-styled templates under templates/registration/. Configure an email backend via env (console backend in DEBUG, SMTP or an API provider in prod). Add account deletion (privacy requirement) and optional email verification tied to ENG-5.

**Verifier note (confirmed).** account.html:13 links to /admin/password_change/. For a non-staff user the test client got 302 to /admin/login/?next=/admin/password_change/. /password_reset/ and /accounts/password_reset/ both return 404. EMAIL_BACKEND is the default SMTP backend with no configuration.

<a id="eng-21"></a>

### ENG-21: Logging is noisy and duplicated in production

**Severity:** ⚪ low (originally medium) · **Kind:** recommendation · **Effort:** S · **Plan:** 1.2 · **Verification:** partially

**Evidence.** With DEBUG=False every record printed twice in the upload.py/xss.py runs ('16:38:02.950 simulation_manage POST' from the logfire console exporter plus 'simulation_manage POST' from the StreamHandler), because settings.py:219-225 adds both handlers and logfire.configure() keeps its console exporter on. views.py:112-116, 129-139, 145-155, 162-173 log INFO on every form POST, including the full POST key list and sizes. forms.py:93-135 emits debug logs in clean methods with 200-character value previews.

**Why it matters.** This doubles log volume and cost on Railway and Logfire and buries real errors. Logging form previews at INFO or DEBUG can leak user-entered data into a third-party service.

**Recommendation.** Use `logfire.configure(console=False, send_to_logfire='if-token-present', …)` and keep a single StreamHandler with a structured (JSON) formatter in prod. Drop the per-POST INFO logs and log only failures (form errors at WARNING without values). Instrument engine steps and tasks with `logfire.span('engine.step', simulation_id=…, rows=…)` for timing, which also gives performance data for ENG-3. Optionally add `logfire.instrument_psycopg()`.

**Verifier note (partially).** Duplication confirmed. With DEBUG=False, one logger.info produced two lines: '17:17:29.369 hello-dup-check' from the logfire console exporter and 'hello-dup-check' from the StreamHandler. The per-POST INFO logs at views.py:112-173 exist. The data-leak concern is weaker than stated. The INFO logs carry POST keys, lengths and error JSON, not field values, and the 200-character value previews in forms.py are logger.debug calls, which the 'nrmps' logger (level INFO) never emits. This is noise and cost, so low severity.

<a id="eng-22"></a>

### ENG-22: Adopt Django 6.x features verified in the installed source: template partials, {% querystring %}, built-in CSP, LoginRequiredMiddleware, django.tasks

**Severity:** 🟡 medium · **Kind:** recommendation · **Effort:** M · **Plan:** 1.8, 5.1, 5.5 · **Verification:** partially

**Evidence.** .venv django/template/defaulttags.py:1204 `{% partialdef name [inline] %}`; django/template/engine.py:179 supports loading 'template.html#partial'; defaulttags.py:1286 `{% querystring %}`; django/middleware/csp.py (ContentSecurityPolicyMiddleware, SECURE_CSP / SECURE_CSP_REPORT_ONLY in conf/global_settings.py:681-682, nonce via the context processor `csp` in template/context_processors.py:94); contrib/auth/middleware.py:43 LoginRequiredMiddleware; django/tasks (ENG-4). Current code: separate partial files included into simulation_manage.html:320-322 and rendered alone from views; sort/pagination links hand-build query strings in 3 list templates (for example interviews_list.html:31-134, 16 links); one inline <script> (simulation_manage.html:330-360); Alpine standard build (uses Function evaluation, so a strict CSP would need 'unsafe-eval').

**Why it matters.** Partials let each HTMX endpoint render a named fragment of the full page template, so markup lives in one place and the upcoming run-status, plots and invitations fragments stay consistent. querystring removes a class of bugs where links drop filters. CSP is the standard defence in depth against issues like ENG-7.

**Recommendation.** Convert _population_counts.html/_interview_counts.html into `{% partialdef population-counts inline %}` blocks in simulation_manage.html, and have views `render(request, 'nrmps/simulation_manage.html#population-counts', ctx)`. Use `{% querystring sort='student' order=next_order page=None %}` in list headers and pagination. Enable `ContentSecurityPolicyMiddleware` with `SECURE_CSP_REPORT_ONLY = {'default-src':[CSP.SELF], 'script-src':[CSP.SELF, CSP.NONCE], 'style-src':[CSP.SELF, CSP.UNSAFE_INLINE], 'img-src':[CSP.SELF,'data:'], 'frame-ancestors':[CSP.NONE]}`. Move the inline metaEditor script to static/js with a nonce, switch to the @alpinejs/csp build (register metaEditor via Alpine.data), set htmx.config.includeIndicatorStyles=false, then enforce SECURE_CSP. Charting libraries chosen by the visualisation reviewer must be served from static (no CDN) to fit the policy.

**Depends on.** ENG-7, ENG-14

**Verifier note (partially).** All cited Django features are verified in .venv: partialdef at defaulttags.py:1204, template 'name#partial' loading at engine.py:179, querystring at defaulttags.py:1286, middleware/csp.py, SECURE_CSP and SECURE_CSP_REPORT_ONLY at global_settings.py:681-682, the csp context processor at context_processors.py:94, and the CSP.SELF/NONE/NONCE/UNSAFE_INLINE constants in utils/csp.py. The CSP migration inventory is incomplete. Besides the inline <script> at simulation_manage.html:331, three inline event handlers (onchange="this.form.submit()" in interviews_list.html:18, schools_list.html:15, students_list.html:15) would be blocked by a nonce-based script-src, because nonces do not apply to event-handler attributes. With the @alpinejs/csp build, the x-data expressions that pass arguments (metaEditor($el, 'id', [...])) must also be restructured.

<a id="eng-23"></a>

### ENG-23: Code organisation: fat models, duplicated student/school code, dead code, inline imports, and a 150-line introspection view

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** M · **Plan:** 2.2 · **Verification:** confirmed

**Evidence.** models.py:102-473 (population generation plus CSV parsing inside Simulation, duplicated for students and schools); dead or odd code: models.py:141-144, 152-155, 227-230, 238-241 (`try: k = str(key) except: k = str(key)`), :414-417 unused meta_stddev (F841), :584-590 module-level `generate_meta_scores(self, …)` never called, simulation_engine.py:167 `def interview(self)` at module level, :52/83/105/128 re-importing Interview (already imported at :1), models.py:270-276 `-> int` returning None, many `getattr(config, 'field', default)` on real model fields (models.py:128-133, 210-215; engine :50, :81). 22 function-level imports (views 6, models 10, engine 4, forms 2). views.py:557-705 documentation() rebuilds config dicts and nested helpers on every request, uses `hasattr(inspect,'signature')` (always true), and documents only models.py, not the engine. forms.py:91-136 two identical clean methods.

**Why it matters.** This will get worse as the invitation, interview, ranking and match steps land. Pure engine functions are also what make ENG-3, ENG-8 and ENG-17 possible.

**Recommendation.** Target layout: `nrmps/engine/{population.py, preferences.py, interview.py, ranking.py, match.py}` (pure numpy plus dataclasses, no ORM); `nrmps/services/{runner.py (load arrays, call engine, persist), population_csv.py}`; views thin; `nrmps/tasks.py`. Generate students and schools through one parametrised function (`generate_side(n, score_mean, score_sd, meta_keys, pref_keys, pref_sd, rng)`). Delete the dead code listed and fix the typo `meta_preferances` (matches TODO.md). Move documentation introspection to a module-level `@functools.cache` builder, or replace it with curated help content (Help reviewer).

**Depends on.** ENG-8

**Verifier note (confirmed).** Confirmed: the no-op try/except around str(key) at models.py:141-144/152-155; the unused module-level generate_meta_scores(self, …) at :584; `def interview(self)` at module level (simulation_engine.py:167); re-imports of Interview at engine :52/83/105/128; function-level import counts of views 6, models 10, engine 4, forms 2; `hasattr(inspect, 'signature')` at views.py:633/698; and two identical clean methods at forms.py:91-136.

<a id="eng-24"></a>

### ENG-24: Repository hygiene: generic .NET .gitignore missing data/, tracked stray files, unwired dev apps, undocumented env vars

**Severity:** ⚪ low · **Kind:** defect · **Effort:** S · **Plan:** 1.2 · **Verification:** partially

**Evidence.** .gitignore is a 574-line Visual Studio template; `git check-ignore data/x.csv` returns nothing, so uploaded user CSVs can be committed. Tracked strays: identifier.sqlite (0 bytes, JetBrains artifact), templates/base.html.bak (old Bootstrap base: 'd-flex flex-column min-vh-100' at :36), .junie/guidelines.md (partial duplicate of CLAUDE.md). An untracked 0-byte db.sqlite3 sits in the repo root. django_browser_reload is in INSTALLED_APPS (settings.py:77) but has no middleware or URLs (grep), so it is non-functional. django-reset-migrations and cookiecutter are dev deps with no documented use. pyproject description is 'Add your description here'. No README or .env.example; env vars used: SECRET_KEY, DEBUG, ALLOWED_HOSTS, RAILWAY_PUBLIC_DOMAIN, CSRF_TRUSTED_ORIGINS, DATABASE_URL, LOGFIRE_TOKEN, PORT.

**Why it matters.** Small, but these files confuse contributors and AI agents: CLAUDE.md, .junie and base.html.bak each describe different states of the project.

**Recommendation.** Replace .gitignore with a focused Python/Django/Node one (.venv, __pycache__, *.sqlite3, staticfiles/, theme/static/css/dist/, node_modules/, data/, .env, .mypy_cache, .ruff_cache, .pytest_cache, .hypothesis, coverage). `git rm identifier.sqlite templates/base.html.bak`; either delete .junie or make it a pointer to CLAUDE.md. Wire or remove django_browser_reload. Add a README.md (setup, env var table, deploy), .env.example, and a project description.

**Verifier note (partially).** It is not a 'generic .NET .gitignore'. It concatenates the VisualStudio (line 1), JupyterNotebooks (399) and Python (413) templates, and already ignores .venv, .env, db.sqlite3 (line 472), .hypothesis, staticfiles/, node_modules/ and dist/. Replacing it is cosmetic. The real gap is data/: `git check-ignore data/x.csv` returns nothing. Confirmed: identifier.sqlite, templates/base.html.bak (Bootstrap 'd-flex flex-column min-vh-100') and .junie/guidelines.md are tracked. django_browser_reload is in INSTALLED_APPS (settings.py:77) with no middleware and no URLs. There is no README or .env.example. The 0-byte db.sqlite3 is untracked and ignored.

<a id="eng-25"></a>

### ENG-25: Migration drift: model validators changed without a migration (0006 pending)

**Severity:** ⚪ low · **Kind:** defect · **Effort:** S · **Plan:** 0.2 · **Verification:** confirmed

**Evidence.** `manage.py makemigrations nrmps --dry-run -v 3` generates 0006_alter_student_score.py: AlterField Student.score with validators Min(0)/Max(0.99) (state-only, no SQL). Five earlier migrations are mostly alter-churn on defaults and validators.

**Why it matters.** Harmless for the schema, but it shows no gate exists. The next real model change (SimulationRun, indexes) would bundle unrelated drift.

**Recommendation.** Commit 0006, and add `python manage.py makemigrations --check --dry-run` to CI and pre-commit. If production holds no data worth keeping, consider squashing 0001-0006 before adding the ENG-4 and ENG-15 models; otherwise keep the history.

**Verifier note (confirmed).** `makemigrations nrmps --check --dry-run` in an isolated DB reports 'nrmps/migrations/0006_alter_student_score.py ~ Alter field score on student'.

<a id="eng-26"></a>

### ENG-26: CLAUDE.md and TODO.md contain inaccurate or stale statements

**Severity:** ⚪ low · **Kind:** defect · **Effort:** S · **Plan:** 1.10 · **Verification:** confirmed

**Evidence.** CLAUDE.md: 'Programmatic generation using Gaussian distributions for scores', but scores and meta-scores use beta (models.py:59-62, 138, 146, 220, 232); Gaussian is used only for capacity (:221) and preference weights (:156, :242). 'Django 5.2+' (now 6.1.1). The setup 'uv sync' fails (ENG-9). The 'docker run … -e DEBUG=False' example crashes (ENG-1). 'Pre-interview rating ✓' despite the rating_error bug (F5). 'Multiple configs can exist per simulation', but the view edits the latest in place (ENG-17). 'Docstrings required', yet 41 are missing (ENG-13). The TODO line refs in CLAUDE.md (167/175/183/188) are correct today but brittle. TODO.md: match() cited as simulation_engine.py:189 (actually :188). 'Implement proper CSRF protection' is already done (CsrfViewMiddleware plus hx-headers in theme/templates/base.html:15). 'Set up Redis for caching/sessions' is unnecessary with the ENG-4/ENG-5 choices (DB cache plus django-tasks-db). 'Add rate limiting for API endpoints': there is no API; the target should be signup, login and heavy actions (ENG-5). IDEAS.md 'Blockchain integration' conflicts with the vectorisation-first priority.

**Why it matters.** Agents and contributors follow CLAUDE.md literally, so wrong setup or deploy instructions directly cause broken environments.

**Recommendation.** After Phase 0/1, update CLAUDE.md: commands (`uv sync`, `uv run pytest`, `uv run mypy .`, the worker command), the env var table, the architecture (engine/services/tasks), and function names instead of line numbers. Update TODO.md: mark CSRF done, retarget rate limiting, replace Redis with 'DB cache + django-tasks-db', and link each item to this review's phase. Keep .junie in sync or remove it.

**Depends on.** ENG-1, ENG-9

**Verifier note (confirmed).** Confirmed. CLAUDE.md:107 says 'Gaussian distributions for scores', but the code uses beta. CLAUDE.md:130 says 'Django 5.2+'. The :71 DEBUG=False docker example crashes (ENG-1). The :88 claim of multiple configs contradicts the in-place edit. TODO.md:21 cites simulation_engine.py:189 while match() is at :188. TODO.md:157 lists CSRF as a todo although it is done (theme/templates/base.html:15 hx-headers plus CsrfViewMiddleware). TODO.md:133 lists Redis and :156 lists 'rate limiting for API endpoints'. IDEAS.md:199 contains 'Blockchain integration'.

<a id="crit"></a>

## CRIT: Completeness critic (cross-cutting)

<a id="crit-1"></a>

### CRIT-1: Running the same step concurrently corrupts data: two (re)Create Students calls double the population, and two Initialize Interviews calls give an IntegrityError 500

**Severity:** 🟠 high · **Kind:** defect · **Effort:** S · **Plan:** 0.4, 2.5 · **Verification:** critic (self-verified)

**Evidence.** scratch/review/CRIT/c2_double_create.py uses two threads and a Barrier to call Simulation.create_students() at the same moment on an isolated SQLite DB with number_of_applicants=3000. 3/3 runs printed "[('B', 3000), ('A', 3000)] students in DB: 6000 configured: 3000 distinct names: 3000". scratch/review/CRIT/c1_concurrency.py runs two initialize_interview() calls on 400x25; 3/3 runs gave one success and one "IntegrityError: UNIQUE constraint failed: nrmps_interview.student_id, nrmps_interview.school_id". Causes: delete-then-insert with no transaction or lock (nrmps/models.py:118-124 and :204, nrmps/simulation_engine.py:19-35); no uniqueness on Student(simulation, name); production runs gunicorn --workers 4 (entrypoint.sh:27); no hx-sync, hx-disabled-elt or hx-indicator anywhere in templates/ (grep: 0 hits). htmx 2 only queues repeat clicks on the same element, so two tabs, two different buttons (Create + Upload, or Create Students + Initialize Interviews) or a retry after an apparent hang (UX-2: no spinner) all run in parallel.

**Why it matters.** SIM-20, ENG-16 and UX-2 mention non-atomic steps and double-submit, but nobody showed that concurrent steps corrupt data silently. The duplicated population has twice the configured applicants, every name appears twice, and every later step and chart is wrong with no error shown. This gets worse once background jobs exist (ENG-4): without a per-simulation lock, a queued job and a user click will interleave in the same way.

**Recommendation.** Phase 0: wrap every destructive step in transaction.atomic(). Start each step with Simulation.objects.select_for_update().get(pk=pk) (a row lock on Postgres; SQLite serialises writes). Add hx-sync="#sim-workspace:queue" (or :abort) and hx-disabled-elt="this" on all step buttons. Phase 2: when SimulationRun/Job lands (ENG-4), enforce one active job per simulation with UniqueConstraint(fields=['simulation'], condition=Q(status__in=['queued','running']), name='one_active_job_per_sim'), and have views return 409 plus an HTMX toast of 'a step is already running' instead of starting a second one. Add a regression test that repeats the two-thread Barrier scripts above (pytest-django transactional_db).

**Depends on.** ENG-4, SIM-20

<a id="crit-2"></a>

### CRIT-2: Write a single versioned model specification before the engine rewrite; the reviewers' prototypes use three different utility models

**Severity:** 🟠 high · **Kind:** recommendation · **Effort:** M · **Plan:** 2.0 · **Verification:** critic (self-verified)

**Evidence.** The repo model is U = sum(meta_score x weight) x rating_error, on Beta-generated attributes, and ignores the base score (nrmps/simulation_engine.py:4-10, nrmps/models.py:33-60, SIM verifier #1). The STG and VIZ prototypes use a rho/Gaussian common+idiosyncratic model (VIZ verifier #4). OPT-4 proposes a common+idiosyncratic model with one correlation knob per side. SIM-13 proposes adding a horizontal component. VIZ-6, VIZ-8 and VIZ-20 need a JS port with a portable RNG, and HELP-11 needs executable formulas. Every quoted outcome number (OPT: first-choice 72%->28%; STG: 25.8% first choice; VIZ: blocking-pair shares) comes from a different model.

**Why it matters.** Without one spec, the Python engine, the browser 'Match Explorer' and slider previews, the help formulas, the presets calibrated to NRMP 2026 and the golden tests would each implement a slightly different simulator, and a user would see numbers in the preview that the real run does not reproduce. This decision unblocks most of Phases 2 to 6, and no reviewer made it an explicit deliverable.

**Recommendation.** Create docs/model_spec.md (versioned, e.g. model_version='2.0'). Define: latent quality q_j and a_i; attribute vectors; utility U_ij = w_c*q_j + w_f*<x_i, beta_j> + w_e*eps_ij with the correlation knob mapped to w_e; observation O_pre = U + N(0, sigma_pre) and O_post = U + N(0, sigma_post); tie-break rule; stage order; RNG stream layout (numpy SeedSequence.spawn per stage, per replicate) so that common random numbers work. Implement it once in a pure numpy module (nrmps/engine/model.py). If a JS port is needed, generate it from the same spec with a shared RNG (PCG64 is hard in JS; consider a counter-based Philox or xoshiro128** implemented in both languages) and parity tests (VIZ-20). Store model_version on every Run. HELP-11 formulas and the OPT-9 schema reference this spec.

<a id="crit-3"></a>

### CRIT-3: No sharing, visibility or collaboration model; the dead 'public' flag defaults to True on every existing simulation, so a future gallery would leak them

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** L · **Plan:** 0.2, 7.1 · **Verification:** critic (self-verified)

**Evidence.** nrmps/models.py:93 has `public = models.BooleanField(default=True)`, exposed in SimulationForm (nrmps/forms.py:42) with no explanation. On the :8800 demo, /simulations/ shows the 'Public: Yes' badge for all 3 simulations (templates/nrmps/simulations_list.html:33). No view reads `public`: all 20 views use the copy-pasted `sim.owner_id != request.user.id` check (grep count 20 in nrmps/views.py). TODO.md:86-87 asks for user roles and sharing permissions, and IDEAS.md:122 for multi-researcher workspaces. CSV exports write user-supplied names raw (nrmps/views.py:296, :312). In c3_privacy.py an uploaded name `=HYPERLINK("http://evil.example","click")` came back in the download as a cell starting with '=', which is spreadsheet formula injection (CWE-1236).

**Why it matters.** Research and teaching users will want to share a result read-only, publish to a gallery, fork someone's setup and co-edit with a collaborator. ENG-19 and the OPT verifier only note that `public` is unused. The hidden trap is that every existing row is already public=True without meaningful consent, so a gallery built on this field would publish them. Once other people's data can be downloaded, the formula-injection issue becomes a real attack vector.

**Recommendation.** Phase 0: add a data migration setting public=False on existing rows, change the default to False, and relabel the field. Phase 7: replace `public` with visibility = private|unlisted|public, add SimulationShare(token, role=viewer, expires_at) for signed read-only links, SimulationCollaborator(user, role=viewer|editor), a /gallery/ of public simulations, 'Fork to my account' (reuses OPT-22 clone), and a central permission helper (Simulation.objects.viewable_by(user)/editable_by(user), per ENG-14) used by all views. Sanitise CSV exports by prefixing a single quote to cells that start with = + - @ \t \r. Unlisted pages get <meta name=robots content=noindex>; public result pages get Open Graph tags with a chart PNG from VIZ-18.

**Depends on.** ENG-14, SIM-21, ENG-5, CRIT-6

<a id="crit-4"></a>

### CRIT-4: Privacy and terms pages are inaccurate: uploads outlive deletion, participant names reach logs and Logfire, Logfire is undisclosed, and users cannot delete their account or export their data

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** M · **Plan:** 0.7, 1.9 · **Verification:** critic (self-verified)

**Evidence.** templates/nrmps/privacy.html:10 says 'Data: uploaded datasets are kept in your environment.' In fact uploads are written to server disk at BASE_DIR/data/simulation_<id>_students.csv (nrmps/views.py:252-257) and to the DB. scratch/review/CRIT/c3_privacy.py showed: 'after simulation delete, upload file still on disk: True' and 'after user delete, upload file still on disk: True' (simulation_delete at nrmps/views.py:191-198 never removes files). A step failure logs the participant's name: the 500 record was 'Internal Server Error ... exc=Error computing pre-interview score for Jane Doe (real applicant) - Mercy' (nrmps/simulation_engine.py:63, :94 plus Interview.__str__ at nrmps/models.py:723-724). In production, root logging and every request span are sent to Pydantic Logfire (NRMP_Simulated/settings.py:220-228: LogfireLoggingHandler, logfire.configure(), logfire.instrument_django()), and privacy.html never mentions it. nrmps/urls.py has no account-delete or data-export route. terms.html:8-10 has three lines with no MIT license reference, no acceptable-use rules and no disclaimer about real applicant data. NRMP states that R3 system data is proprietary and may not be shared without permission.

**Why it matters.** The privacy statement is factually wrong about where data lives and omits a third-party processor. For a tool whose privacy page invites research data that may contain PII ('Do not upload sensitive PII unless necessary', privacy.html:7), that matters. ENG-6 notes the files are kept forever but not the policy or deletion consequences. HELP-21 and UX-24 only cover placeholder contact details.

**Recommendation.** Phase 0 (S): correct privacy.html. Describe server-side storage, retention, Logfire as a processor and region, cookies, and the contact for deletion. Stop putting names in exception messages (use ids) and configure logfire.configure(scrubbing=...) plus instrument_django(excluded_urls=...). Phase 1 (M): add /account/delete/ (password confirm; cascades simulations and deletes data/ files through a post_delete signal or by storing uploads in FileField/default_storage and deleting them), a 'Download all my data' ZIP (configs JSON + populations CSV + results), a retention job that purges raw uploads after N days, an upload checkbox 'contains no real personal data', and Terms covering MIT license, acceptable use (no real applicant, ERAS or R3 data), 'results are not predictions', and the quota policy (ENG-5).

**Depends on.** ENG-6

<a id="crit-5"></a>

### CRIT-5: No NRMP trademark or non-affiliation disclaimer, and no statement that results are not predictions

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** S · **Plan:** 0.7 · **Verification:** critic (self-verified)

**Evidence.** The site brands itself 'NRMP Simulations' (theme/templates/base.html:8, :36, :77; templates/nrmps/index.html:2, :9) on the domain nrmp-simulated.heteroskedastic.org. `grep -rni 'affiliat|trademark|endorse|disclaim'` over templates/, nrmps/, IDEAS.md, TODO.md and CLAUDE.md returns nothing. The National Resident Matching Program uses ® on 'National Resident Matching Program®', 'NRMP®' and 'The Match®' (nrmp.org; AAMC and ECFMG pages write 'National Resident Matching Program® (NRMP®)'), and USPTO reg. 4782823 covers 'NATIONAL RESIDENT MATCHING PROGRAM NRMP INTERNATIONAL'. The logo (static/NRMP_Simulations_logo.png) is original artwork, not NRMP's.

**Why it matters.** Medical students are an obvious audience. Without a disclaimer the site can be read as official or endorsed, and simulated match rates can be taken as personal predictions. That is a reputational risk and possibly a trademark one, and none of the seven reviewers raised it.

**Recommendation.** Phase 0 (S): add a footer and About/Help line: 'Independent educational and research simulator. Not affiliated with, sponsored or endorsed by the National Resident Matching Program® (NRMP®). NRMP®, National Resident Matching Program® and The Match® are registered marks of their owner.' Add a 'Simulated outcomes are not predictions of any real applicant's match' notice on results pages and in the Terms. Before a wider public launch, the owner should get legal advice on the product name (e.g. 'Residency Match Simulator') and the domain.

<a id="crit-6"></a>

### CRIT-6: No protection against login brute force or bot signups

**Severity:** 🟡 medium · **Kind:** defect · **Effort:** S · **Plan:** 0.8, 2.5 · **Verification:** critic (self-verified)

**Evidence.** On :8800, 30 consecutive POSTs to /login/ with wrong passwords for user 'demo' all returned 200 with no lockout or delay, and the next correct password logged in (302). /admin/login/ uses the same backend at the default path. The signup view (nrmps/views.py:52-66) needs only a username and password: email is optional (nrmps/forms.py:20), there is no verification (privacy.html:9 admits 'without email verification'), and there is no CAPTCHA or honeypot. INSTALLED_APPS (NRMP_Simulated/settings.py:57-70) has no throttling app.

**Why it matters.** ENG-5 covers quotas on heavy operations. It does not cover the account layer: scripted signups can multiply any per-user quota, and passwords can be guessed without limit, including the staff/admin account that ENG-19 wants to make more powerful.

**Recommendation.** Add django-axes (lockout after 5 failures per username+IP, AXES_COOLOFF_TIME=15 min, behind the proxy with the correct IP header per ENG-2), and django-ratelimit (or a cache-based decorator) on /signup/, /login/ and heavy POST steps. Add a honeypot field on signup, require and verify email for new accounts (CRIT-7) or use instructor invite codes for classroom mode, apply per-account quotas that count unverified accounts as zero, and use django-otp TOTP for staff. Move the admin to a non-default path via an env var.

**Depends on.** CRIT-7, ENG-2

<a id="crit-7"></a>

### CRIT-7: Email is not configured and is optional at signup, which blocks password reset, verification and job-finished notifications

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** S · **Plan:** 1.9, 2.5 · **Verification:** critic (self-verified)

**Evidence.** There are no EMAIL_* or DEFAULT_FROM_EMAIL settings (grep over NRMP_Simulated/ and nrmps/ returns nothing), so Django falls back to SMTP on localhost:25 and webmaster@localhost. SignupForm.email is required=False (nrmps/forms.py:20). There is no password-reset route (curl :8800/accounts/password_reset/ and /password-reset/ both 404). The account page links to the admin password change (templates/nrmps/account.html:12).

**Why it matters.** ENG-20 and UX-15 recommend adding password reset. Wiring Django's PasswordResetView as things stand would try SMTP to localhost and 500 in production, and users who signed up without an email could never recover their account. Background jobs (ENG-4) that take minutes also need a 'your run finished' channel.

**Recommendation.** Phase 1: EMAIL_BACKEND from env (django-anymail with Postmark, SES or Resend in prod; console.EmailBackend in dev), DEFAULT_FROM_EMAIL and SERVER_EMAIL. Make email required and unique for new accounts, and prompt existing email-less users on the account page. Then add Django's PasswordReset*/PasswordChange* views with styled templates (ENG-20), email verification (CRIT-6), and an opt-in 'notify me when a run finishes' on SimulationRun.

<a id="crit-8"></a>

### CRIT-8: There is no headless or programmatic interface (CLI, Python API, notebooks) and no experiment bundle export/import

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** L · **Plan:** 2.2, 6.5 · **Verification:** critic (self-verified)

**Evidence.** There is no nrmps/management/ directory, so no management commands. The engine is tied to the ORM (nrmps/simulation_engine.py:1 imports Interview and Simulation; every function takes a Simulation and saves rows). There is no /api/ (404 on :8800). The only exports are per-table CSVs (nrmps/views.py:286-555), and the interviews export would be about 44 GB at the maximum config (ENG-5). IDEAS.md:113 ('Research collaboration data sharing APIs') and IDEAS.md:128 ('Reproducible research features') ask for this. SIM-24 and OPT-11 propose a vectorised core but not a public interface to it.

**Why it matters.** Researchers will want to run 1,000-replicate sweeps overnight, from a notebook or on a cluster, without a browser and without the web quota. They also need to publish one artefact that reproduces a figure. Without a headless path, every experiment competes with web traffic and the only way to reproduce a result is to click through the UI.

**Recommendation.** When the engine is rewritten (Phase 2), put it in a Django-free package (nrmps/engine/: params.py = the OPT-9 schema, model.py = the CRIT-2 spec, stages.py, da.py, metrics.py) with `run(params, seed) -> Results` (numpy arrays). Add `manage.py nrmp_run --params cfg.json --seed 42 --replicates 200 --out results.parquet`, `manage.py seed_demo` (fixes UX-17/HELP-14 onboarding), and `manage.py export_bundle/import_bundle <sim>`. A bundle is a ZIP holding params.json, seed, model_version, engine_version, git SHA, uv.lock hash, populations.csv, rank lists and matches as Parquet, and metrics.json. Add docs/notebooks/quickstart.ipynb. Later, add a read-only token-authenticated JSON API reusing the VIZ-13 endpoints. Consider publishing the engine to PyPI.

**Depends on.** SIM-24, OPT-9, CRIT-2

<a id="crit-9"></a>

### CRIT-9: The project is not citable or versioned: no README, CITATION.cff or CHANGELOG, and the version is never shown or recorded with results

**Severity:** ⚪ low · **Kind:** gap · **Effort:** M · **Plan:** 2.0, 6.5, 3.7 · **Verification:** critic (self-verified)

**Evidence.** `ls CITATION* CHANGELOG* README*` finds nothing. pyproject.toml:3-4 has version = "0.1.0" and description = "Add your description here". No template displays a version (grep over templates/ and theme/templates/). The LICENSE is MIT, (c) 2025 Vincent. HELP-23 and VIZ-18 mention citation and version only as part of a page and a chart export.

**Why it matters.** Research use needs a stable way to cite 'simulator vX, model vY' and to tell whether a result predates a bug fix such as SIM-1, which changes every past result. Without version stamping, results from before the noise fix cannot be told apart from later ones.

**Recommendation.** Add CITATION.cff and README.md (HELP-22), use semantic versions plus CHANGELOG.md (Keep a Changelog), and make GitHub releases with a Zenodo DOI. Stamp app_version, model_version (CRIT-2) and git SHA (from an env var set at Docker build) on every Run and in every export and chart footer, and show them in the About page and footer. Add a 'validation report' page, generated by tests, that checks theory properties on random markets: stability (0 blocking pairs), applicant-optimality against the 'matching' oracle (STG-19), the rural-hospitals theorem (same unmatched set and same filled counts under applicant- vs program-proposing DA), and no profitable single-applicant misreport under applicant-proposing DA on small markets.

**Depends on.** CRIT-2, SIM-21

<a id="crit-10"></a>

### CRIT-10: No teaching or classroom mode, 'explain my match' view, or demo that works without signing up, although the site advertises educational use

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** L · **Plan:** 7.3 · **Verification:** critic (self-verified)

**Evidence.** templates/nrmps/terms.html:9 says 'Use the application for research and educational purposes'. IDEAS.md:136-148 lists 'Gamification for Education' and 'Role-playing simulations (switch perspectives student <-> program director)'. Every simulation view requires login (/simulations/ -> 302 /login/), and the only inputs are generated or CSV populations: there is no per-participant editing or manual rank list. None of the 7 dimensions has a teaching finding. The VIZ Web Worker prototype (scratch/review/VIZ/proto) already runs DA in the browser in 1-13 ms.

**Why it matters.** Letting people play the market is one of the best ways to learn how deferred acceptance behaves. Students can submit strategic and truthful lists, watch proposals and rejections step by step, and see why an applicant went unmatched. This is also the cheapest route to real users, via medical-education and market-design courses.

**Recommendation.** Phase 7. (a) A public /explore/ page, the VIZ prototype built on the CRIT-2 spec, needing no account and no DB writes. (b) A DA step-through for small markets (at most 8x5): an ECharts or sigma animation of each proposal and rejection with a 'next step' slider, plus a per-applicant 'explain my match' trace (programs that rejected them, and each program's cutoff rank) produced by da.py with record_trace=True. (c) Classroom mode: models Cohort(owner, join_code), Membership(user, role=applicant|program, participant FK) and ManualRankList. Participants see only their own profile and order a rank list by drag and drop (SortableJS 1.15 via cdn/vendored, with an Alpine fallback of up/down buttons). The instructor locks lists, runs the match and reveals results and the class dashboard. Permissions reuse CRIT-3 and abuse limits reuse CRIT-6.

**Depends on.** STG-1, STG-19, CRIT-2, CRIT-3, VIZ-4

<a id="crit-11"></a>

### CRIT-11: Ops is not ready for the planned architecture: no health check, no worker service, a silent SQLite fallback in production, no backups and no engine telemetry

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 0.1, 1.2, 2.5 · **Verification:** critic (self-verified)

**Evidence.** curl on :8800 returns 404 for /healthz and /health/. entrypoint.sh:27 starts only gunicorn, and Procfile.tailwind is for dev only. honcho is a production dependency (pyproject.toml:10) but nothing uses it in production, so the django-tasks-db `db_worker` that ENG-4, UX-3 and SIM-24 recommend has no process definition on Railway. NRMP_Simulated/settings.py:124-137: if DATABASE_URL is unset, production silently uses BASE_DIR/db.sqlite3 inside the container (Dockerfile `COPY . .` also ships the empty db.sqlite3 from the repo), so every redeploy on ephemeral disk would wipe all accounts. There is no backup or restore documentation, and TODO.md:144 ('Add health check endpoints') is still open. Logfire is configured, but no engine stage emits spans with size or duration.

**Why it matters.** ENG-1 and ENG-10 fix settings and the image, and ENG-4 designs jobs. Nobody specified how the worker is deployed and supervised, how the platform checks the app is alive, or how silent data loss is prevented if the database variable is missing. Without these, the background-job phase cannot ship.

**Recommendation.** Add /healthz (SELECT 1 on the DB, plus worker heartbeat age from a TaskHeartbeat row) and set Railway healthcheckPath. Fail fast when DEBUG=False and DATABASE_URL is unset (raise ImproperlyConfigured). Run a second Railway service from the same image with `python manage.py db_worker` (or one container under honcho with a Procfile of web and worker), and document how to scale it. Enable Railway Postgres backups and document a pg_dump restore drill. Add a periodic cleanup task (stale runs, expired uploads per CRIT-4, quota counters). Wrap each engine stage in logfire.span('stage', sim_id=..., n_applicants=..., n_programs=...), and add a staff-only ops page (runs per day, failures, p95 duration, largest simulations, per-user quota use) in the admin (ENG-19). Add a feedback link (GitHub issues or form) to replace the placeholder contact page (HELP-21).

**Depends on.** ENG-1, ENG-4, ENG-10

<a id="crit-12"></a>

### CRIT-12: Front-end dependencies were not part of the upgrade, and nothing automates dependency updates

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** S · **Plan:** 1.3 · **Verification:** critic (self-verified)

**Evidence.** `npm outdated` in theme/static_src (read-only): @tailwindcss/postcss 4.1.13 -> 4.3.3, daisyui 5.1.12 -> 5.7.44, postcss 8.5.6 -> 8.5.28, cross-env 7.0.3 -> 10.1.0, postcss-cli 11.0.1 -> 12.0.0, postcss-nested 7.0.2 -> 8.0.1. The vendored static/js/htmx.mini.js is version 2.0.6 (npm latest 2.0.11), and static/js/alpine_mini.js is 3.14.9 (latest 3.17.4). There is no .github/ directory, so no Dependabot, Renovate or CI. uv-bump (commit 01b1eb5) only raises the pyproject.toml floors.

**Why it matters.** The user's goal 1 was a dependency upgrade review, but only the Python half was done. daisyUI has moved six minor versions while templates still use daisyUI 4 class names (UX-8), so bumping it blind would change layouts in ways that are hard to attribute. Vendored files outside a package manager will keep going stale (ENG-11, VIZ-5), and ECharts and sigma will add more.

**Recommendation.** In Phase 1, after the UX-8 class migration, run `npm update` or `npx npm-check-updates -u` in theme/static_src, rebuild, and diff Playwright screenshots against the F7 set. Replace the hand-vendored htmx with django-htmx's {% htmx_script %} (UX verifier #5) or npm-managed copies from a `vendor` script, and do the same for Alpine, ECharts and sigma. Add .github/dependabot.yml (or renovate.json) covering the uv (pyproject/uv.lock), npm (theme/static_src) and GitHub Actions ecosystems, grouped weekly, and gated by the CI of ENG-8.

**Depends on.** UX-8, ENG-8

<a id="crit-13"></a>

### CRIT-13: No plan for migrating existing deployed data through the proposed schema rework

**Severity:** 🟡 medium · **Kind:** gap · **Effort:** M · **Plan:** 2.0, 2.3 · **Verification:** critic (self-verified)

**Evidence.** The app is deployed (ALLOWED_HOSTS includes nrmp-simulated.heteroskedastic.org, NRMP_Simulated/settings.py:28) with 5 migrations (nrmps/migrations/0001-0005) and a pending 0006 (F3/ENG-25). The proposals change the schema heavily: Run/RankList/MatchResult (SIM-21, STG-16, VIZ-2), a sparse interview table (SIM-8), a versioned param schema replacing 20 flat fields (OPT-9), an Applicant/Program rename (HELP-19, OPT-23), visibility (CRIT-3), and config snapshots (SIM-18). No finding says what happens to existing users' simulations, or that old results were produced by the buggy noise model (SIM-1).

**Why it matters.** If there is no decision, the lead will either write expensive data migrations for data that is scientifically invalid anyway, or silently break or delete users' simulations. Renaming Student and School in place also touches every template, view and CSV header, and it is cheapest to do while the new models are being introduced.

**Recommendation.** Decide explicitly in Phase 2. Recommended: build the new models (Applicant, Program, ParamSet, Run, ...) as new tables alongside the current ones. Mark legacy simulations 'v1 (legacy model)' as read-only with a banner that their results used the pre-fix rating model. Offer 'Export' (CRIT-4/CRIT-8 bundle) and 'Re-create as v2' (copy populations, map config fields to ParamSet), then drop the v1 tables in a later release. Before that, squash 0001-0006, add django-test-migrations tests for forward and backward runs, and announce the change on a changelog or news banner (CRIT-9).

**Depends on.** SIM-21, OPT-9, HELP-19, ENG-25

<a id="crit-14"></a>

### CRIT-14: Add mechanism comparison (RSD, immediate acceptance/Boston, TTC, program-proposing DA, decentralised scramble) on the same market

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** M · **Plan:** 8.2 · **Verification:** critic (self-verified)

**Evidence.** IDEAS.md:7-11 ('Alternative matching mechanisms: TTC, Random Serial Dictatorship ... compare outcomes') and IDEAS.md:13-17 (strategic vs truthful reporting). OPT-18 and STG-19 cover only applicant- vs program-proposing DA. None of the findings covers other mechanisms.

**Why it matters.** Once rank lists exist (STG-14), each extra mechanism is about 50-150 lines of numpy. Running them side by side on the same seeded market, with stability, welfare (rank distributions), unmatched counts and incentive to misreport, answers the most common teaching and research question ('why does the NRMP use DA?'), and it reuses the VIZ comparison charts.

**Recommendation.** Phase 8. Add nrmps/engine/mechanisms.py with da(proposer='applicant'|'program'), serial_dictatorship(order='random'|'score'), immediate_acceptance(), ttc() (school-priority TTC) and decentralised_offers(rounds=k) (a pre-Match 'scramble' baseline). Add Run.mechanism (enum), a 'Compare mechanisms' experiment type using common random numbers (OPT-21), and a VIZ small-multiples card. Oracle-test DA and TTC against the 'matching' package where it applies.

**Depends on.** STG-14, STG-19, OPT-21

<a id="crit-15"></a>

### CRIT-15: Triage TODO.md and IDEAS.md explicitly in the plan so obsolete or conflicting items don't resurface

**Severity:** ⚪ low · **Kind:** recommendation · **Effort:** S · **Plan:** 1.10 · **Verification:** critic (self-verified)

**Evidence.** TODO.md:157 'Implement proper CSRF protection' is already done (ENG summary: CSRF on, including HTMX). TODO.md:133 'Set up Redis' is unnecessary if DB-backed django-tasks-db and the DB cache are adopted (ENG-4). TODO.md:33-36 'interview date/time fields ... calendar views' is superseded by the capacity/wave interview model (OPT-16/17). TODO.md:1-25 plans the stubs on the current per-row engine, which SIM-24 says to rewrite first. IDEAS.md:199 (blockchain) adds nothing to a simulator. IDEAS.md:110-112 (ERAS/USMLE data import) conflicts with privacy, terms and NRMP data rules (CRIT-4). ENG-26 notes stale statements but gives no item-by-item disposition.

**Why it matters.** The review document will be the new plan. If TODO.md stays a parallel, contradictory backlog (for example 'implement interview() now' before the rewrite), contributors or future agent sessions will act on it.

**Recommendation.** Add an appendix to docs/PROJECT_REVIEW.md mapping every TODO.md and IDEAS.md item to done, superseded-by-<finding>, in plan phase N, or dropped with a reason. Then replace TODO.md with a short pointer to the phased plan (or GitHub issues/milestones), and update CLAUDE.md's 'Current Implementation Status' (ENG-26) so the assistant tooling does not keep planning the per-row stubs.

