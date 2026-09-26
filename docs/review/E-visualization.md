# Appendix E: Visualization suite

*Chart catalog, slider architecture, library choice, data API, prototype and phased plan.* These are the visualization reviewer's deliverables, with the verifiers' corrections applied. The master plan schedules this work in Phases 1.2–1.3, 2.1, 2.3, 3.7–3.8 (diagnostic charts), 4.2, 5, 6.1–6.2 and 7.2. Monte-Carlo bands and sweep charts (EXP-1/2, MAT-1 intervals, ROL-1 bands) need Phase 6 even where marked P0.

All measurements come from runs in the review session. The prototype is committed as [`viz-prototype/`](viz-prototype/); the benchmark scripts are not.

> **Model caveat (verifier).** Every prototype number here comes from the prototype's own simple utility model (ρ/Gaussian common + idiosyncratic), not this repo's current model or the Appendix A spec. The numbers show magnitudes and that the approach is feasible. A browser Explorer must implement the *same* model as the Python engine ([Appendix A](A-model-spec.md), decision D7).

---

## 0. Prototype (built and measured, outside the repo)

`viz-prototype/index.html` + `sim.js` + `worker.js`. It loads echarts 6.1.0, sigma 3.0.3, graphology 0.26.0 and graphology-library 0.8.0 as UMD `<script>` tags with no bundler: from pinned jsDelivr URLs in the committed copy, and from vendored files, byte-identical to the npm tarballs, in the review. Serve it with `python3 -m http.server` from that folder; the Web Worker does not load over `file://`.

- **What `sim.js` does.** It runs the whole planned pipeline: population → true utilities `U = √ρ·prestige + √(1-ρ)·ε` and `V = √ρ·score + √(1-ρ)·η` → pre-interview observed (added noise) → top-A applications plus signals → program invitations (slots per position × capacity, signal boost) → applicant interview limit → post-interview observed → rank lists → applicant-proposing deferred acceptance (DA) → metrics.
  - The metrics are funnel, rank achieved, match by decile, program fill, decile heatmap, true-preference blocking pairs, a true-vs-observed sample and network edges.
  - The RNG is counter-based (a hash of seed, stream, i, j), so each slider position reuses the same noise draws (common random numbers, CRN).
  - DA correctness: 0 blocking pairs with respect to submitted rank lists over 200 random instances.
- **UI.** 8 sliders with `?` help badges, a market-size select, 5 stat tiles and 7 ECharts charts: Sankey funnel, rank achieved, decile match rate, program fill with dataZoom, decile heatmap with visualMap, true-vs-observed scatter with Spearman, and a Monte-Carlo sweep band. There is also a sigma bipartite network with two-column/ForceAtlas2 layouts, a stage filter and a click-for-ego-network view. It supports light and dark themes via CSS tokens, and mobile at 390 px has 0 px overflow.
- **Timings (Chromium, worker round trip):**

  | Market | Worker | ECharts render | DA |
  |---|---|---|---|
  | 1000×100 | 34–81 ms | 45–67 ms | — |
  | 5000×500 | 467–593 ms | — | — |
  | 10000×1000 | 1.79–1.91 s | — | 6.8 ms |

  - A sweep of 80 runs at 1000×100 takes 2.8 s.
  - Node: DA takes 2.4–13 ms at every size. The O(n·m) true-preference blocking scan takes 0.5 s at 10k×1k.
  - numpy dense: 4.5 s total at 10k×1k (DA 20 ms), with 38 MB per float32 n×m matrix.
- **Screenshot:** [`img/viz-prototype.jpg`](img/viz-prototype.jpg). In the review the ForceAtlas2 layout gave an unreadable hairball on a random market, which is why FA2 isn't the default layout.

---

## 1. Chart catalog

Priorities: **P0** is the first dashboard, **P1** is the next wave, **P2** is research extras.

Field names are current model fields. **new** marks data proposed in VIZ-1/2/17: `SimulationRun`, `RunMetric`, `RunArtifact`, `Interview.stage`, per-run arrays.

Scale column: what to do at 10,000 applicants × 1,000 programs (10M pairs, about 300k applications at A=30, about 120k interviews, 10k matches).

### 1A. Population (buildable today)

| ID | Question | Chart (ECharts) | Data | Interactivity | Pri | Scale at 10k×1k |
|---|---|---|---|---|---|---|
| POP-1 | Did the generator produce the distribution I asked for? | Histogram (bar) + KDE line, small multiples: applicant vs program score, shared x 0–1. Overlay requested mean/sd, effective sd after the beta clamp, and realized mean/sd. | `Student.score`, `School.score`; `SimulationConfig.*_score_mean/stddev`; `get_beta_parameters()` | Hover bin → count; brush a range → filters the student table and other cards | P0 | `np.histogram` 40 bins + `scipy.stats.gaussian_kde` on a 5k sample; payload about 2 KB |
| POP-2 | How do meta-scores relate to base score and each other? | Scatter-matrix (SPLOM): k×k grid of scatter series with a histogram diagonal; color = score decile (sequential) | `Student.score_meta{key}` (keys = `school_meta_preference`), `Student.score`; same for `School.score_meta` | `brush` + `brushLink:'all'` across cells; hover shows the student | P1 | Stratified sample of 3–5k per side; above that, a density mode (`histogram2d` 50×50 per cell as a heatmap) |
| POP-3 | How diverse are preference weights? | Ternary scatter (barycentric → x,y projection, triangle via `graphic`) for 3 keys; for k>3, parallel coordinates (`parallel` series) or a 100% stacked weight strip sorted by dominant key | `Student.meta_preference`, `School.meta_preference` (sum to 1) | Brush region → highlight those applicants elsewhere; clamp-floor band marked | P1 | 5k sample; above that, a hexbin of the simplex (triangular bins, precomputed) |
| POP-4 | Is the market tight or slack? | Stat tile "positions per applicant" + capacity histogram with capacity-0 programs flagged | `School.capacity`, count `Student` | Hover | P0 | Server bins; trivial |
| POP-5 | Do better programs have more positions? | Scatter of prestige vs capacity | `School.score`, `School.capacity` | Hover, brush | P2 | 1k points: fine |
| POP-6 | What will these config values produce? (live preview) | Beta pdf area line, capacity pmf, weight distribution, positions/applicant tile, next to the config form | Config form values only (browser port of `get_beta_parameters`, clamps) | Updates on `@input.debounce.100ms` | P0 | Pure browser; O(1) |

### 1B. Ratings and pre-interview rankings (stages 2–4)

| ID | Question | Chart | Data | Interactivity | Pri | Scale |
|---|---|---|---|---|---|---|
| RAT-1 | How noisy are pre- and post-interview perceptions? | Scatter of true (x) vs observed (y) with the identity line; two series (pre, post); applicant-side and program-side tabs | `Interview.student_true_score_of_school` vs `student_pre_observed_score_of_school` / `student_post_observed_score_of_school`; program side analogous (**true fields must be populated**) | Hover shows student/program; toggle side; click → ego network | P0 | 5k stratified sample or `histogram2d` 80×80 density heatmap of all pairs, computed in SQL/numpy |
| RAT-2 | How well do observed rankings preserve true rankings, and how does that depend on rating error? | (a) box/violin of per-applicant Spearman ρ and Kendall τ (pre vs post); (b) sweep curve of mean ρ vs `*_rating_error` with a p10–p90 band | Per-student `scipy.stats.spearmanr/kendalltau` over grouped arrays; sweep uses `RunMetric` keys `spearman_pre_mean`, `kendall_pre_mean` | Slider on rating error (tier b/c); hover | P0 (a), P1 (b) | Per-student ρ is O(m log m) each, about 1 s for 10k×1k, run as a job; the chart shows 10k values as a box/violin |
| RAT-3 | Is demand concentrated on a few programs? | Bar: applicants ranking each program #1 (and in their top 5) vs its capacity (reference ticks), sorted by demand; Lorenz curve + Gini tile | `Interview.students_pre_rank_of_school == 1` grouped by school; `School.capacity` | Hover; dataZoom when more than 60 programs | P0 | GROUP BY in SQL; 1k bars with `large:true` or tier-aggregated |
| RAT-4 | Do programs agree on who is best? | m×m heatmap of Kendall τ between program rankings (seriated), or a histogram of pairwise τ when m > 60 | `schools_pre_rank_of_student` | Hover a cell → the program pair | P2 | Sample 60 programs; τ via scipy |
| RAT-5 | What does the whole preference landscape look like? | Student × program heatmap, rows sorted by score, columns by prestige; value = true / pre / post / rank / stage | `Interview.*_score*`, `*_rank*`, `stage` | Value toggle, sort toggle (score or seriation), visualMap range slider | P1 | Full resolution only when n·m ≤ 250k; otherwise bin-mean to 200×200 = 40k cells (about 300 KB) with a `progressive` heatmap |

### 1C. Applications and signals (new stage)

| ID | Question | Chart | Data | Interactivity | Pri | Scale |
|---|---|---|---|---|---|---|
| APP-1 | How many applications per applicant and per program? | Two histograms: applications per applicant, applications per position per program | `Interview.stage >= APPLIED` counts by student and by school | Brush a decile | P1 | SQL counts |
| APP-2 | Do signals get interviews? | Grouped bar of interview-offer rate for signaled vs non-signaled applications by program tier, with CIs; plus signals received per position | `student_signal`, `school_invited`, `School.score` tier | Signals slider (tier b/c) | P1 | Aggregates |
| APP-3 | Do applicants reach, target or safety? | Strip/jitter scatter of applicant score (x) vs prestige percentile of applied programs (y) with reach/target/safety bands | Applications CSR + scores | Hover an applicant → ego | P2 | Sample 1k applicants |

### 1D. Invitations and interviews

| ID | Question | Chart | Data | Interactivity | Pri | Scale |
|---|---|---|---|---|---|---|
| INT-1 | Where do pairs drop out? | **Sankey** applied → invited → interviewed → ranked → matched, with drop-off nodes (not invited, declined/over limit, ranked not matched); per-decile small multiples | `Interview.stage` counts (GROUP BY), `Match` | Hover a link → count and %; decile selector; on mobile, `orient:'vertical'` or a funnel bar list | P0 | Counts only; O(1) payload |
| INT-2 | Who gets the interviews? | Histogram of interviews per applicant + box per score decile; Lorenz curve / Gini of interviews | `stage >= INTERVIEWED` count by student | Brush decile | P0 | SQL counts |
| INT-3 | Are program interview slots used? | Stacked bar per program: slots, invited, interviewed | `interview_slots_per_position × capacity` (VIZ-9), counts | dataZoom | P1 | 1k bars `large:true` or tiers |
| INT-4 | How do interviews reorder preferences? | Slope/bump chart of pre-rank vs post-rank for one applicant or program | `students_pre_rank_of_school` vs `students_post_rank_of_school` | Pick an entity (combobox) | P2 | One entity at a time |

### 1E. Rank lists

| ID | Question | Chart | Data | Interactivity | Pri | Scale |
|---|---|---|---|---|---|---|
| ROL-1 | How does P(match) grow with rank-list length? (NRMP "Charting Outcomes" style) | Line of P(match) vs number of ranks, by score tercile, with a Monte-Carlo band | Per-applicant ROL length + matched flag across runs | Hover (crosshair, all series) | P0 | Binned per run → `RunArtifact` |
| ROL-2 | How long are rank lists on each side? | Two histograms | ROL CSR lengths | — | P1 | Server bins |

### 1F. Match outcome

| ID | Question | Chart | Data | Interactivity | Pri | Scale |
|---|---|---|---|---|---|---|
| MAT-1 | Headline results | Stat tiles: match rate, fill rate, unfilled positions, unmatched applicants, % first choice, mean rank achieved, % in a true-preference blocking pair; each "72.5% (68–76%)" across iterations | `RunMetric` | Click a tile → the related chart | P0 | O(1) |
| MAT-2 | What share got their 1st, 2nd, … choice? | Bar of the rank-achieved distribution + "unmatched" bar in neutral gray; cumulative line toggle; per-decile small multiples | Match rank in the applicant's ROL (**new** per-run match result) | Hover; normalize toggle | P0 | Bins; O(L) |
| MAT-3 | Who is left out? | 100% stacked bar per applicant score decile: 1st / 2–3 / 4+ / unmatched | Match result + `Student.score` decile | Hover; click decile → table | P0 | 10 rows |
| MAT-4 | Which programs don't fill? | Stacked bar per program sorted by prestige: filled + unfilled; list of unfilled programs | Match counts by school, `School.capacity` | dataZoom; hover; click → program ego | P0 | 1k bars `large:true`; tier-aggregate toggle (deciles) |
| MAT-5 | How assortative is the match? | 10×10 (or 20×20) heatmap of applicant decile × program prestige decile (counts or row-normalized); also feeds the tier graph | Match + scores | visualMap slider; hover | P0 | O(100) cells |
| MAT-6 | Is the outcome stable and efficient? | Correctness badge (blocking pairs w.r.t. rank lists = 0); tiles: true-preference blocking pairs, % applicants involved; histogram of regret (true rank of match among all programs); oracle comparison bars (actual vs full-information DA); dumbbell of applicant- vs program-proposing results per decile | `RunMetric`: `blocking_pairs_true`, `share_in_bp_true`, `oracle_gap_*`, `proposing_diff`; `RunArtifact`: `regret_hist` | Hover | P1 | O(n·m) once per run (0.5 s JS at 10k×1k), stored |
| MAT-7 | Show me the market as a network | **sigma.js** bipartite graph: two-column sorted layout (default); ego network of one applicant or program with edges colored by stage; tier graph (decile super-nodes); ForceAtlas2 only when a cluster attribute exists | `/api/runs/<id>/network` (nodes, edges with stage) | Click → ego; stage filter; decile filter; search combobox; hover labels | P1 (ego), P2 (full) | Ego ≤ 1k edges; filtered subgraph ≤ 20k edges (WebGL); tier graph for the full market |
| MAT-8 | Why were applicants unmatched? | Horizontal bar of the reason taxonomy (no invites / no interviews / interviewed but unranked / ranked but outcompeted) + table | Derived per applicant from stage + ROL + match | Click reason → filtered table | P1 | Counts |

### 1G. Experiments (many runs)

| ID | Question | Chart | Data | Interactivity | Pri | Scale |
|---|---|---|---|---|---|---|
| EXP-1 | How uncertain is each metric? | Strip + box per metric across iterations; bands on every curve chart | `RunMetric` grouped by scenario | Hover a run → open it | P0 (once runs exist) | 100 iterations × 20 metrics = 2k rows |
| EXP-2 | How does outcome X respond to parameter P? | Median line + p10–p90 band vs P (applications per applicant, interview slots per position, signals, rating error, preference correlation, positions/applicant); one metric per small multiple | `ParameterSweep` + `RunMetric` | Scrub slider over precomputed values (tier a) highlights the point and updates the other cards from that run's artifacts | P0 | Precomputed; O(values × reps) |
| EXP-3 | Does design B beat A? | Small multiples of MAT-1/2/3/4 with shared axes; delta tiles with paired CI (CRN); diverging bar of per-decile difference | Two scenarios' `RunMetric`/`RunArtifact` | Scenario pickers | P1 | Aggregates |
| EXP-4 | Two-parameter interaction | Heatmap/contour of metric over a P1×P2 grid | 2-D sweep | Hover a cell → open that run | P2 | Grid ≤ 20×20 |
| EXP-5 | Have I run enough iterations? | Running mean ± 95% CI vs iteration count | `RunMetric` ordered by iteration | — | P2 | O(iterations) |
| EXP-6 | How does the interview season unfold? (if invitation waves are added) | ECharts `timeline` animation of the funnel and network per wave | Per-wave stage snapshots | Play/pause slider | P2 | Aggregates per wave |

---

## 2. What-if slider design

### 2.1 Sliders (parameter → stage it invalidates → architecture)

| Parameter | Field today / proposed | Range | Recompute from | Tier |
|---|---|---|---|---|
| Market size | `number_of_applicants`, `number_of_schools` | Log select (120 … 10k / 8 … 1k) | Population | (b) async / (c) Explorer ≤5k |
| Score mean / sd | `applicant_score_mean/stddev`, `school_*` | 0–0.99 / 0–0.5 (effective sd shown) | Population | Preview in the browser (POP-6); regenerate = (b) |
| Positions per applicant | derived from `school_capacity_mean` | 0.6–1.4 | Population | (b)/(c) |
| Preference correlation (common vs idiosyncratic) | **new** `prefs.applicant_pref_correlation`, `prefs.program_pref_correlation` | 0–1 | Utilities | (b)/(c) |
| Pre-interview rating error | `applicant_/school_pre_interview_rating_error` (fixed to additive) | 0–2 (sd in utility units) | Pre-observed → everything after | (b)/(c) |
| Applications per applicant | **new** `applications_per_applicant` | 1–80 | Applications | (b)/(c) |
| Signals per applicant, signal boost | **new** `signals_per_applicant`, `signal_boost` | 0–10, 0–1 | Applications/invitations | (b)/(c) |
| Interview slots per position | replaces `school_interview_limit` (VIZ-9) | 1–30 | Invitations | (b)/(c) |
| Max interviews per applicant | `applicant_interview_limit` | 1–50 | Interviews | (b)/(c) |
| Post-interview rating error | `*_post_interview_rating_error` | 0–1 | Post-observed → rank lists → DA (cheap) | (b) sync at any size / (c) drag |
| Rank-list length cap, acceptability threshold | **new** | 1–30 | Rank lists → DA (cheap) | (b) sync / (c) drag |
| Proposing side | **new** mechanism enum | applicant/program | DA only (≤20 ms) | (b) sync / (c) |
| Seed, iterations | **new** `seed`; `Simulation.iterations` | 1–100 | All | (b) async |
| Filters: decile range, program search, stage ≥, bins, normalization, ego focus | display only | — | Nothing | (a) |

**Stage-aware cache (DAG).** Stages: population → utilities → pre-observed → applications/signals → invitations → interviews → post-observed → rank lists → DA → metrics.

- Each stage's output is cached under `hash(upstream params, seed, engine_version)`. A slider recomputes only from the earliest stage it affects.
- Measured, so post-interview and mechanism sliders are fast even at 10k×1k:
  - DA: 2–13 ms (JS), 20 ms (numpy + Python).
  - Rank-list build: 106 ms (numpy).
  - Application/invitation stages: 1.1 s (JS) and 4.4 s (numpy dense). Sparse storage would cut this.
- CRN: noise is a deterministic function of (seed, stream, i, j), so moving a slider changes only that parameter's effect. The prototype does this, and the numpy reimplementation matches JS to 5.6e-17.

### 2.2 Three architectures

| | (a) Client-side filtering of precomputed data | (b) Server recompute (HTMX/JSON, debounced, cached) | (c) In-browser engine (JS port in a Web Worker / Pyodide) |
|---|---|---|---|
| How | Payload holds everything; ECharts `dataZoom`/`visualMap`/`brush`/`timeline` or JS filters | `hx-post="/api/simulations/<pk>/whatif" hx-trigger="input changed delay:400ms"` (small) or `change` (large), `hx-sync="this:replace"`, `hx-indicator`; cache hit → instant; miss and n·m > 400k → enqueue a django-tasks job, poll `every 1s` | `worker.postMessage(params)`; coalesce so only the latest params run (prototype: busy/pending flags); stage cache in the worker |
| Latency | ≤ 16–50 ms | 35 ms numpy at 1000×100 sync; 4.5 s at 10k×1k (job) | 35–80 ms at 1000×100 (drag OK); about 0.5 s at 5000×500 (on release); about 1.8 s at 10k×1k |
| Pros | Instant, no server load | One authoritative engine; works on the user's real population | Offline, no server cost, smooth drag, great for teaching |
| Cons | Only what was precomputed | Server CPU/RAM; must go async at scale | Second implementation to maintain (needs parity tests); Pyodide: 314.0.7 JS package 13.9 MB + numpy/scipy wheels, multi-second cold start |
| Use for | Filters, brushing, ego focus, scrubbing precomputed sweeps and Monte-Carlo runs | "Rerun my simulation with X", sweeps and Monte-Carlo (as jobs), anything saved or shared | Standalone "Match Explorer" on synthetic markets ≤ 5k×500; config preview |

**Latency budgets:**

| Interaction | Budget | How |
|---|---|---|
| Hover/brush | ≤ 50 ms | (a) |
| Slider drag | ≤ 100 ms | (a), or (c) at ≤ 1k×100, or downstream-only stages at any size |
| Slider release | ≤ 1 s | (c) ≤ 5k×500, (b) sync ≤ about 2k×200 (assumes the vectorised Phase 2 engine; today's per-row engine takes about 0.5 s per step for 360 rows) |
| Full rerun at 10k×1k | 2–5 s | (b) job with a progress bar |
| Sweeps / Monte-Carlo (e.g. 10k×1k × 100 iterations, several minutes) | background | (b) background job + notification; result → `RunMetric` → (a) scrubbing |

**Recommendation.**
1. Build (a) and (b) on the Python engine first. They serve saved simulations and are authoritative.
2. Add (c) as a separate "Match Explorer" page later, reusing the prototype's `sim.js` design.
3. Guard (c) with golden parity tests against the Python engine, using the shared counter-based RNG.
4. Don't use Pyodide unless offline use of the exact engine becomes a requirement.

---

## 3. Library selection

Versions are from the npm registry on 2026-09-24. Sizes are `gzip -9` of the published minified dist files.

| Library | Version / license | Min+gz | Sankey | Heatmap | Ternary | Network | WebGL / large data | Sliders / animation | Linked brushing | No-bundler UMD |
|---|---|---|---|---|---|---|---|---|---|---|
| **Apache ECharts** | 6.1.0, Apache-2.0 | **368 KB** full (common 240 KB lacks sankey/heatmap/graph) | ✓ | ✓ (+visualMap) | via projection | graph series (≤ 2k nodes) | canvas `large`/`progressive`; echarts-gl 2.1.0 (+175 KB) for scatterGL/graphGL | dataZoom, visualMap, timeline | brush + brushLink | ✓ (verified in prototype) |
| Plotly.js | 4.1.1, MIT | 1,468 KB full; cartesian 496 KB (no sankey/splom/scattergl); basic 395 KB | ✓ (full only) | ✓ | ✓ native | ✗ | scattergl/splom (full) | layout.sliders + frames | selection events (manual linking) | ✓ |
| Vega-Lite + Vega + embed | 6.4.3 / 6.4.0 / 7.3.0, BSD-3 | 280 KB | ✗ | ✓ | ✗ | ✗ (Vega force is limited) | ✗ (≤ about 50k marks) | `bind: range` params | best in class | ✓ (Altair 6.3 on the Python side) |
| Observable Plot (+d3) | 0.6.17 ISC / d3 7.9.0 ISC | 69 + 92 KB | ✗ | ✓ | ✗ | ✗ | ✗ | DIY | ✗ | ✓ |
| Chart.js | 4.5.1, MIT | 70 KB | plugin | plugin (chartjs-chart-matrix 3.1.0) | ✗ | ✗ | ✗ | DIY | ✗ | ✓ |

| Network library | Version / license | Min+gz | Renderer | Comfortable size | Notes |
|---|---|---|---|---|---|
| **sigma.js + graphology (+library)** | 3.0.3 / 0.26.0 / 0.8.0, MIT | 47 + 14 + 48 KB | WebGL | 10^4–10^5 edges | Reducers for ego/filters; FA2 in a worker (FA2Layout), louvain, noverlap; UMD globals verified |
| Cytoscape.js (+fcose) | 3.34.3 / 2.2.0, MIT | 136 KB | canvas (+experimental WebGL opts in 3.34) | ≤ about 5k nodes / 10k edges | Rich analysis API and layouts; great for small graphs |
| vis-network | 10.1.2, Apache-2.0/MIT | 63–154 KB | canvas physics | ≤ a few thousand | Easy, but slows quickly |
| d3-force | d3 7.9.0, ISC | 92 KB (full d3) | SVG/canvas DIY | depends | Most custom work |

**Decision.** Use ECharts 6.1.0 for all charts and sigma.js 3.0.3 + graphology 0.26.0 for networks. Vendor them under `static/vendor/<lib>/<version>/` with licenses, which matches the vendored htmx/Alpine and avoids CDN dependence (jsDelivr was unreachable from this environment).

Prerequisites (VIZ-5):
- `STORAGES` = `CompressedManifestStaticFilesStorage`.
- `@source not "../../../static/vendor";`.
- Load libraries per page via `{% block extra_js %}`.
- Refresh htmx to 2.0.11 and Alpine to 3.17.4.

---

## 4. Backend data API and precomputation

### 4.1 Models (see VIZ-2 and VIZ-17)
- `SimulationRun(simulation, scenario, sweep?, iteration, seed, config_snapshot JSON, engine_version, status, started_at, finished_at, duration_ms, arrays File/Binary)`.
  - `arrays` = `np.savez_compressed` of: applications CSR (indptr, indices, signal), invited/interviewed CSR, rank lists CSR (both sides), `match_student→program` (int32, -1 = unmatched), true/observed utilities for applied pairs only.
- `RunMetric(run, key, value)`: tidy scalars for bands and sweeps.
- `RunArtifact(run, kind, data JSON)`: precomputed chart payloads (`funnel`, `rank_achieved`, `decile_match`, `program_fill`, `heat_decile`, `regret_hist`, `rol_pmatch`, `true_vs_obs_sample`, `spearman_dist`).
- `ParameterSweep(simulation, parameter, values JSON, reps, status)`.
- `Interview.stage` IntegerChoices + indexes `(simulation, stage)`, `(simulation, student)`, `(simulation, school)`.
- `Simulation.population_version` (incremented on regenerate or upload) for cache invalidation.

### 4.2 Code layout
- `nrmps/engine/`: pure numpy engine over arrays, returning `RunResult` dataclasses. The ORM is touched only at persistence (bulk_create / npz). This replaces the per-row `.save()` loops.
- `nrmps/analytics/loaders.py`: ORM values_list or npz → numpy.
- `nrmps/analytics/metrics.py`: pure functions (histograms, KDE, deciles, Spearman/Kendall, rank achieved, fill, blocking pairs, regret, oracle DA).
- `nrmps/analytics/payloads.py`: columnar JSON builders with rounding and sampling rules.
- `nrmps/tasks.py`: `@task run_simulation(run_id)`, `@task run_sweep(sweep_id)` via the built-in `django.tasks` API. Settings: `INSTALLED_APPS += ["django_tasks_db"]` and `TASKS = {"default": {"BACKEND": "django_tasks_db.DatabaseBackend"}}`, with `ImmediateBackend` in tests, and a worker running `manage.py db_worker`. (Verifier correction: since django-tasks 0.12 the database backend is the separate `django-tasks-db` package.)
- `nrmps/api/views.py`: thin JsonResponse views + `@gzip_page` + `@condition(etag_func)` + cache. Ownership checks match existing views (plus public read-only if `Simulation.public`).

### 4.3 Endpoints
```
GET  /simulations/<pk>/dashboard/?tab=population|ratings|interviews|match|experiments   (HTML)
GET  /api/simulations/<pk>/population/summary?bins=40            -> histograms+KDE, capacity pmf, tightness
GET  /api/simulations/<pk>/population/points?side=student&fields=score,score_meta.research&sample=3000
GET  /api/simulations/<pk>/runs/?scenario=&sweep=                -> [{id, iteration, seed, status, headline metrics}]
POST /api/simulations/<pk>/runs/        {scenario, iterations, overrides{...}}  -> {job_ids}
GET  /api/runs/<id>/charts/<kind>?decile=3                       -> RunArtifact (computed and cached on miss)
GET  /api/runs/<id>/heatmap?value=pre|post|true|rank|stage&rows=student_pct&cols=program_pct&bins=100
GET  /api/runs/<id>/network?focus=student:123&min_stage=interviewed&deciles=1-10&limit=20000
GET  /api/simulations/<pk>/metrics?keys=match_rate,fill_rate&group_by=scenario|sweep_value&stats=median,p10,p90,n
POST /api/simulations/<pk>/whatif       {overrides, seed}         -> result (small) or {job_id} (large)
GET  /api/jobs/<id>                                               -> {status, progress, run_id}
```

### 4.4 Payload shape (columnar, 4-decimal floats)
```json
{"meta": {"simulation": 1, "run": 42, "seed": 7, "engine_version": "0.3.0", "config_hash": "9f2c…", "kind": "program_fill", "generated_at": "…"},
 "columns": {"program_id": [..], "name": [..], "prestige": [..], "capacity": [..], "filled": [..]},
 "summary": {"unfilled": 170, "fill_rate": 0.81}}
```
- Network: `{"nodes": {"id":[], "kind":[], "label":[], "x":[], "y":[], "size":[]}, "edges": {"s":[], "t":[], "stage":[]}}`.
- Heatmap: `{"x_edges":[], "y_edges":[], "values":[[...]], "value":"post", "agg":"mean"}`.

### 4.5 Caching
- Finished runs are immutable: `Cache-Control: private, max-age=31536000` + ETag `run:kind:params_hash:engine_version`.
- `CACHES` = `DatabaseCache` (no new infrastructure) or Redis (TODO.md item). Key `viz:{run}:{kind}:{params_hash}:{engine}`.
- What-if key: `sha256(population_version, overrides, seed, engine)`.
- Gzip API JSON with `@gzip_page`. (Verifier note: BREACH is not the risk it once was, because Django masks CSRF tokens per response and its GZipMiddleware adds random padding. Compressing only JSON is still a sensible default.)

---

## 5. Front-end integration pattern
- `static/js/nrmp-charts.js`:
  - `NRMPCharts.register(kind, (payload, tokens) => echartsOption)`.
  - Initializes on `DOMContentLoaded` and `htmx:afterSettle` for `[data-chart]`; disposes on `htmx:beforeCleanupElement`.
  - ResizeObserver; theme tokens read from CSS variables and re-applied on theme toggle.
  - Tooltips built with `echarts.format.encodeHTML` / textContent (VIZ-12).
  - Keeps the previous render at 55% opacity while refetching.
- Cards: `<section class="card" data-chart="rank_achieved" data-src="/api/runs/42/charts/rank_achieved/">`, lazily fetched by `nrmp-charts.js` with `fetch()` in an `IntersectionObserver`; or an HTML partial that embeds `{{ payload|json_script:"p-rank" }}`. (Verifier correction: an `hx-get` against a JSON endpoint would swap raw JSON into the card, because htmx expects HTML.)
- Every card has a title that states the question, a `?` popover from `nrmps/viz_catalog.py` (VIZ-19), a table-view toggle, PNG/SVG/CSV export and a footer "Run #42 · seed 7 · engine 0.3.0".
- Filters go in one row above the cards and scope the whole tab; slider state goes in the URL via `hx-push-url`.

---

## 6. Phased plan (VIZ track)

| Phase | Scope | Findings | Effort |
|---|---|---|---|
| 0: Foundations | STORAGES/compression, `static/vendor/` + Tailwind `@source not`, vendor ECharts 6.1.0 + sigma/graphology, refresh htmx/Alpine; `nrmp-charts.js` registry with safe tooltips; chart tokens + dark mode toggle; `viz_catalog.py` | VIZ-4, 5, 12, 16, 19 | S–M |
| 1: Population (works on today's data) | Config preview (POP-6), POP-1, POP-4 tiles, POP-3 ternary, POP-2 SPLOM; `/api/.../population/summary`; mini-charts on manage-page cards; warning banners for clamped sd / degenerate populations | VIZ-7, 8, 15 | M |
| 2: Data contract (with SIM engine completion) | `Interview.stage` + indexes, true scores populated, additive rating error, applications/signals/invitations/interviews/rank lists/DA; `SimulationRun`/`RunMetric`/`RunArtifact`, numpy engine, npz arrays; RAT-1/2a/3, INT-1/2, ROL-1, MAT-1..5 | VIZ-1, 2, 3, 9, 17, 21 | L |
| 3: Experiments and what-if (server) | Iterations/Monte-Carlo, sweeps, A/B via django-tasks; EXP-1/2/3, RAT-2b; what-if tier (b) with stage cache + CRN; API caching/ETag/gzip | VIZ-6, 10, 13, 14 | L |
| 4: Networks and Explorer | sigma ego network + tier graph + filtered subgraph endpoint (MAT-7), MAT-6/8 stability/regret/oracle; JS "Match Explorer" (tier c) from the prototype, with Python↔JS parity tests | VIZ-10, 11, 20 | L |
| 5: Polish | Exports, permalinks, run citation, Playwright render/overflow smoke in CI, EXP-4/5/6, RAT-4/5 | VIZ-18, 20 | M |

**Relation to existing docs:**
- TODO.md "Data visualization" (population charts, match outcome visualizations, ranking distribution graphs) is expanded by this catalog.
- TODO.md "Simulation workflow UI / status dashboard" is covered by Phase 1 and VIZ-15.
- TODO.md "Implement query result caching" and "Set up Redis for caching/sessions" are covered by VIZ-13.
- TODO.md "Interview scheduling system / calendar views": deprioritize calendars. Invitation waves with timeline animation (EXP-6) give more insight.
- IDEAS.md "Network analysis tools / Match stability analysis / Blocking pair identification" is covered by VIZ-10, VIZ-11 and MAT-6/7.
- IDEAS.md "Real-time simulation dashboards / Parameter sensitivity analysis / Scenario comparison tools / A/B testing framework" is covered by VIZ-6 and VIZ-14.
- IDEAS.md "Compare outcomes across different matching algorithms" is covered by the proposing-side and oracle comparison in MAT-6.
- IDEAS.md "Blockchain integration" has no visualization value; suggest dropping it.


### Notes from verification
- **True-preference blocking pairs** (MAT-6, VIZ-10) include pairs that interviewed and ranked each other but whose noisy post-interview rankings put them in the wrong order, not only pairs that never interviewed. Stability with respect to *submitted* rank lists must always be 0.
- `Interview.stage` as a single linear enum loses information, because ranking is two-sided and declined/signalled are branches. Keep per-side flags (or a bitmask) and derive a "furthest stage" for funnels (VIZ-17).
- `school_interview_limit`'s replacement needs a reset to the new default rather than `old × 100`: 0.1 of capacity is 0.1 interviews per position, not 10 (VIZ-9).
- Label signal charts as ERAS/AAMC program signals, not NRMP data (VIZ-21).

