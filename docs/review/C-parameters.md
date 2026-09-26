# Appendix C: Simulation parameters

This appendix has four parts:
1. the **interim default fix** for today's `SimulationConfig` (Phase 0.2);
2. how today's fields map onto the proposed typed schema;
3. the proposed schema itself (Phase 2.1, [OPT-9](FINDINGS.md#opt-9));
4. the calibration targets for an NRMP-2026-like preset.

The model the parameters feed is specified in [Appendix A](A-model-spec.md).

## 1. Interim default fix (Phase 0.2, keeps today's fields)

Today, saving the untouched default config fails validation. Every default stddev is also infeasible on the 0–1 Beta scale and gets silently clamped into U-shaped populations (SIM-2, SIM-3, HELP-2). These interim values are feasible, pass the validators, and give a balanced demo market: 200 applicants and 10 programs × 20 positions is 1.0 positions per applicant. Put them in one migration that also absorbs the pending `0006`.

| Field | Current default | Interim default | Validator change | Note |
|---|---|---|---|---|
| `applicant_score_mean` | 0.7 | 0.7 | exclusive (0, 1) | |
| `applicant_score_stddev` | 2 ✗ | **0.1** | max 0.45, plus `clean()`: σ < √(μ(1−μ)) with the limit in the message | 2 was being cut to 0.41 with a U-shape |
| `applicant_meta_scores_stddev` | 10 ✗ | **0.1** | max 0.45 | |
| `applicant_meta_preference_stddev` | 3 ✗ | **0.3** | max 1.0 | at 3, 74% of weights land on a clamp bound |
| `applicant_pre_interview_rating_error` | 0.1 | 0.1 | 0 allowed and meaningful | now **additive** on the 0–1 utility scale (Phase 0.3) |
| `applicant_post_interview_rating_error` | 0.02 | 0.02 | | unused until Phase 3; show "Not used yet" |
| `applicant_interview_limit` | 5 | 5 | add a max (e.g. 50); widget `step=1` | unused until Phase 3 |
| `school_score_mean` | 0 ✗ | **0.5** | exclusive (0, 1) | 0 was coming out as a mean of about 0.30 |
| `school_score_stddev` | 2 ✗ | **0.1** | max 0.45, plus the same `clean()` rule | |
| `school_capacity_mean` | 20 | 20 | **min 1** (none today) | a negative mean is currently accepted |
| `school_capacity_stddev` | 10 | **4** | ≤ mean/2 recommended | P(capacity = 0) goes from 2.6% to ≈ 0 |
| `school_interview_limit` | 0.1 | unchanged | | unused; show "Planned: redefined as *interviews per position* (≥ 1) in Phase 2". Its current unit (a fraction ≤ 0.99 of capacity) can never reach one interview per position |
| `school_meta_preference_stddev` | 2 ✗ **fails its own max 0.99** | **0.3** | max 1.0 | |
| `school_meta_scores_stddev` | 2 ✗ **fails its own max 0.99** | **0.1** | max 0.45 | |
| `school_pre/post_interview_rating_error` | 0.1 / 0.02 | unchanged | | as for applicants |
| `Student.score` / `School.score` | max 0.99 | | **max 1.0** | generated scores reach 1.0 |
| `Simulation.description` | required | | `blank=True` | |
| `Simulation.public` | True | **False**, plus a data migration setting existing rows to False | | nothing reads this flag yet |

Add a unit test that builds `SimulationConfigForm` from the model defaults and asserts `is_valid()`, so defaults and validators can't drift apart again.

## 2. Old field → new parameter
| Current field (nrmps/models.py) | Problem | Replacement |
|---|---|---|
| number_of_applicants | ok, but the upper bound is unsafe | market.n_applicants (+ size guard) |
| number_of_schools | tightness is an accident | market.n_programs or derived from market.applicants_per_position |
| applicant_score_mean / _stddev | Beta clamp, SD 2 on a 0-1 scale | applicants.groups[].strength_mean / strength_sd (z-scale) |
| applicant_meta_scores_stddev | Bernoulli-like attributes | applicants.attributes[].corr_with_strength |
| applicant_meta_preference (list) | named after the wrong side | programs.attributes[].key (what applicants evaluate) |
| applicant_meta_preference_stddev | 74% of weights clamped to 0.01 or 2 | prefs.weight_concentration (Dirichlet) |
| applicant_pre/post_interview_rating_error | multiplier; post not used; 0 becomes 1 | info.applicant_pre_noise_sd + info.interview_informativeness |
| applicant_interview_limit | unused | interview.applicant_cap |
| school_score_mean / _stddev | default mean 0 comes out as 0.296 | programs.quality_sd (+ programs.tiers) |
| school_capacity_mean / _stddev | Gaussian gives 0-position programs | market.program_size_dist / program_size_mean |
| school_interview_limit | wrong unit (fraction ≤ 0.99) | invites.interviews_per_position |
| school_meta_preference (list) | doubles as student keys | applicants.attributes[].key (what programs evaluate) |
| school_meta_preference_stddev / _scores_stddev | defaults break their validators | prefs.weight_concentration / programs.attributes[].corr_with_quality |
| school_pre/post_interview_rating_error | same as applicant | info.program_pre_noise_sd + kappa |
| Simulation.iterations | unused | run.replicates (+ run.resample_population) |
| (none) | no reproducibility | run.seed |

## 3. Proposed parameter schema (v1 of the new schema)

In schema v1, `attribute_weight_share`, `taste_share`, `weight_concentration` and `interview_informativeness` are shared by both sides (Appendix A §11).
| Group | Name | Type | Default | Range | Meaning | Stage |
|---|---|---|---|---|---|---|
| run | seed | int or null | null (auto, shown) | 0 – 2^63-1 | Root seed; SeedSequence spawns one stream per replicate and per stage | all |
| run | replicates | int | 1 | 1 – 1000 | Monte-Carlo replicates | all |
| run | resample_population | bool | false | – | false: population and true utilities fixed, only process noise resampled; true: new population each replicate (Appendix A §3) | population |
| run | ci_level | float | 0.95 | 0.5 – 0.99 | Confidence level for aggregated metrics | analysis |
| market | n_applicants | int | 1000 | 10 – 60,000 (guard on **applicants × programs**, not only applicants × apps, because dense stages cost memory in A×P; see D4) | Active applicants | population |
| market | applicants_per_position | float | 1.08 | 0.5 – 3.0 | Market tightness (NRMP 2026: 48,050 / 44,344) | population |
| market | n_programs | int or derived | derived | 1 – 7,000 | Programs; derived from the two rows above unless set | population |
| market | program_size_dist | enum {fixed, lognormal, shifted_multinomial, tiers} | lognormal | – | Distribution of positions per program (min 1), rescaled so the total matches applicants per position (Appendix A §4.3) | population |
| market | program_size_mean | float | 6.5 | 1 – 60 | Mean positions per program (44,344 / 6,809) | population |
| market | specialties (COULD) | list[{name, position_share, applicants_per_position, rho_a, rho_p}] | [] | shares sum to 1 | Specialty sub-markets | population/apps |
| market | n_regions (COULD) | int | 1 | 1 – 10 | Geography; 1 = off | population |
| applicants | groups | list[{name, share, strength_mean, strength_sd, applications_mean?, n_signals?}] | MD 0.44 / 0.5; DO 0.18 / 0.35; US-IMG 0.09 / -1.0; non-US-IMG 0.25 / -1.3; other 0.04 / -0.5 (sd 1) | shares sum to 1; mean -3 to 3 | Applicant types | population |
| applicants | attributes | list[{key, corr_with_strength, program_weight_prior}] | board_scores 0.8 / 0.5; research 0.5 / 0.3; honors 0.6 / 0.2 | corr 0 – 1 | What programs evaluate | population, program rating |
| programs | quality_sd | float | 1.0 | > 0 – 3 | Within-tier spread of latent quality relative to tier means; no effect without tiers (Appendix A §4.1) | population |
| programs | tiers | list[{name, share, quality_mean}] | [] | – | Optional quality tiers | population |
| programs | attributes | list[{key, corr_with_quality, applicant_weight_prior}] | reputation 0.9 / 0.5; program_size 0.0 / 0.2; location 0.0 / 0.3 | corr 0 – 1 | What applicants evaluate | population, applicant rating |
| prefs | applicant_pref_correlation (rho_a) | float | 0.6 | 0 – 1 | Share of applicant-utility variance that is common (1 = all applicants agree) | rating |
| prefs | program_pref_correlation (rho_p) | float | 0.7 | 0 – 1 | Same for programs rating applicants | rating |
| prefs | attribute_weight_share (beta) | float | 0.3 | 0 – 1 | Part of the common component driven by the attribute-weighted index rather than latent quality/strength | rating |
| prefs | weight_concentration | float | 10 | 0.1 – 1000 | Dirichlet concentration: the *shape* of individual tastes (low = sparse, one dominant attribute; high = smooth). It does not set how much applicants agree; ρ does (Appendix A §4.4) | population |
| prefs | taste_share (τ) | float | 0.5 | 0 – 1 | Part of the personal (non-common) utility that comes from attribute tastes rather than pure fit (Appendix A §5) | rating |
| prefs | home_region_bonus (COULD) | float | 0 | 0 – 2 (SD units) | Applicant bonus for programs in the home region | rating |
| prefs | local_bonus_program (COULD) | float | 0 | 0 – 2 | Program bonus for local applicants | rating |
| info | applicant_pre_noise_sd | float | 0.5 | 0 – 3 (SD units) | Applicant's observation error before interviews | apps / interview acceptance |
| info | program_pre_noise_sd | float | 0.5 | 0 – 3 | Program's screening error | invitations |
| info | interview_informativeness (kappa) | float | 0.6 | 0 – 1 | The interview shrinks the existing pre-interview error by (1 − κ): sigma_post = sigma_pre × (1 − κ); κ = 1 reveals the truth (Appendix A §7) | post-interview |
| info | fit_shock_sd | float | 0.3 | 0 – 2 | New idiosyncratic 'fit' revealed only at interview | post-interview |
| info | visibility_heteroskedasticity (γ_h) | float | 0 | 0 – 2 | Extra pre-interview noise for less-known programs/applicants (Appendix A §6) | rating |
| info | halo_share (ψ) | float | 0 | 0 – 1 | Share of pre-interview error that is common to everyone judging the same program | rating |
| apps | count_dist | enum {fixed, poisson, negbin} | negbin | – | Distribution of applications per applicant | applications |
| apps | mean | float | 30 (demo) | 1 – n_programs | Mean applications (ERAS 2025-26 real average about 82); per-group override | applications |
| apps | dispersion | float | 0.5 | 0.01 – 10 | Negative-binomial dispersion | applications |
| apps | strategy | enum {top_n, portfolio, all, random} | portfolio | – | How applicants choose programs | applications |
| apps | portfolio_shares | {reach, target, safety} | 0.25 / 0.5 / 0.25 | sums to 1 | Portfolio mix | applications |
| apps | target_band | float | 0.15 | 0 – 0.5 | Percentile gap between applicant and program that counts as 'target' | applications |
| apps | self_assessment_noise_sd | float | 0.5 | 0 – 2 (SD units) | Error in an applicant's estimate of their own competitiveness, used by the portfolio strategy (0 = perfect self-knowledge, an upper bound; OPT-5 verifier) | applications |
| apps | fee_schedule (COULD) | list[{up_to, fee}] | [] | – | Tiered cost per application | applications |
| apps | budget (COULD) | float or null | null | ≥ 0 | Spending limit per applicant | applications |
| signals | tiers | list[{name, count, boost}] | [] (IM preset: gold 3 / 0.8, silver 12 / 0.4) | count ≤ apps | Program signals and screening boost (SD units) | signals / invitations |
| signals | allocation | enum {top_utility, realistic, random} | realistic | – | Where applicants spend signals | signals |
| signals | program_use_share | float | 1.0 | 0 – 1 | Share of programs that use signals | invitations |
| signals | use_in_ranking | bool | false | – | Whether a signal also affects ROLs (AAIM says no) | rank lists |
| invites | interviews_per_position | float | 10 | 1 – 30 | Interview slots = ceil(ratio × positions) | invitations |
| invites | strategy | enum {top_score, threshold_then_top, threshold_then_random, signal_first} | top_score | – | Program selection rule | invitations |
| invites | screen_attribute / screen_min_percentile | str or null / float | null / 0 | 0 – 1 | Hard screen (e.g. board_scores ≥ 40th percentile) | invitations |
| invites | yield_protection | float | 0 | 0 – 2 | Penalty for 'overqualified' applicants unless they signalled | invitations |
| invites | rounds | int | 3 | 1 – 10 | Invitation waves; declined slots are backfilled | invitations |
| interview | applicant_cap | int | 12 | 1 – 50 | Max interviews an applicant attends | interview |
| interview | acceptance_order | enum {best_first, first_come} | first_come | – | How applicants accept invitations | interview |
| interview | n_dates / dates_per_program | int / int | 0 (off) / 3 | 0 – 60 / 1 – 10 | Scheduling conflicts (one interview per date) | interview |
| rol | applicant_policy | enum {all_interviewed, top_k, above_reservation, truncate_k, likelihood_weighted} | all_interviewed | – | Applicant rank-list construction, including strategic variants | rank lists |
| rol | applicant_top_k / reservation_utility | int / float | 20 / -1.0 | – | Parameters for the applicant policy | rank lists |
| rol | program_policy | enum {all_interviewed, dnr_quantile, dnr_threshold} | dnr_quantile | – | Program rank lists and do-not-rank | rank lists |
| rol | program_dnr_quantile | float | 0.1 | 0 – 0.9 | Bottom share of interviewees not ranked | rank lists |
| match | algorithm | enum {applicant_proposing, program_proposing, (COULD) ttc, rsd} | applicant_proposing | – | Mechanism (NRMP uses applicant-proposing, Roth-Peranson) | match |
| match | compare_both | bool | false | – | Also run the other proposing side and report differences | match |
| match | couples_fraction (COULD) | float | 0 | 0 – 0.3 | Share of applicants in couples (NRMP 2026 about 0.05) | match |
| match | couple_geo_constraint (COULD) | enum {same_program, same_region, any} | same_region | – | Constraint for joint ROLs | match |
| match | soap_enabled / soap_rounds / soap_max_applications (COULD) | bool / int / int | false / 4 / NRMP cap (check when implementing) | – | Post-match SOAP | post-match |

Cross-field rules (model_validator):
- group shares sum to 1;
- max signal count ≤ apps.mean ≤ n_programs;
- interviews_per_position ≥ 1;
- guard on n_applicants × n_programs (dense stages, per the D4 budget) and on n_applicants × apps.mean (sparse rows);
- warning (not an error) if applicants_per_position is outside 0.7 – 1.6;
- warning if (slots / applicants) < applicant_cap / 2.

## 4. Utility model

The utility, noise and interview formulas these parameters feed are specified once in [Appendix A §5–7](A-model-spec.md), which supersedes the version in the options review.

## 5. Calibration targets (for the `nrmp_2026_scaled` preset)
The WebFetch tool was blocked, so these numbers come from search-result summaries of the linked pages.

| Metric | 2026 | 2025 | Source |
|---|---|---|---|
| Registered applicants | 53,373 | 52,498 | NRMP press releases, Mar 2026 / May 2025 |
| Active applicants (certified ROL) | 48,050 | 47,208 | NRMP |
| Positions offered | 44,344 | 43,237 (40,041 PGY-1) | NRMP |
| Program tracks | 6,809 | 6,626 (derived: 6,809 - 183) | NRMP |
| Filled in the Match | 41,482 (93.5%) | – | NRMP |
| Filled after Match + SOAP | 99.3% (2026 SOAP: 2,851 positions offered, 2,632 filled) | 99.4% (2,521 positions to SOAP, 2,318 filled) | NRMP |
| PGY-1 match rate, all active applicants | 79.8% | about 80% | NRMP |
| PGY-1 match rate, US MD seniors | 93.5% (20,934 active) | 93.5% | NRMP / AMA |
| PGY-1 match rate, US DO seniors | 93.2% (8,503 active) | 92.6% | NRMP |
| PGY-1 match rate, US-citizen IMG | 70.0% (4,210 active) | 67.8% | NRMP |
| PGY-1 match rate, non-US-citizen IMG | 56.4% (11,944 active) | 58.0% | NRMP |
| Couples | 1,258, 93.0% matched | 1,259, 93.2% (89.1% both) | NRMP |
| US MD seniors matched to a top-3 choice | 73.5% | – | NRMP |
| Applications per applicant (ERAS 2025-26) | 81.8 (about 36 per specialty) | – | medschoolcoach.com summary of AAMC ERAS data |
| IM signals (2025-26) | 3 gold + 12 silver | – | AAIM FY26 recommendations |

Sources:
- https://www.nrmp.org/about/news/2026/03/nrmp-releases-results-of-the-2026-main-residency-match-for-more-than-38000-future-residents/
- https://www.nrmp.org/match-data/2026/05/results-and-data-2026-main-residency-match/
- https://www.nrmp.org/about/news/2025/05/nrmp-releases-2025-main-residency-match-results-and-data-report-providing-in-depth-insight-into-the-largest-residency-match-in-history/
- https://www.ama-assn.org/medical-students/preparing-residency/largest-match-day-record-dive-2026-numbers
- https://www.medschoolcoach.com/resource/average-number-of-residency-eras-applications
- https://students-residents.aamc.org/applying-residencies-eras/program-signaling-2026-myeras-application-season

Mean contiguous ranks (Charting Outcomes 2024) is a good further target; read it from the NRMP PDF tables when implementing.

With strength means (0.5, 0.35, -1.0, -1.3), a rough prototype setting gives overall 0.818, MD 0.970, DO 0.961, US-IMG 0.604, non-US-IMG 0.555, fill 0.923. That prototype used IMG shares of 0.12 / 0.267 and 1.13 applicants per position, not the 2026 figures. **It is not yet close on rank positions** (top-3 is 95% vs. NRMP's 73.5%; mean ROL is about 7), so the calibration report must include rank-position targets and not only match rates. If the calibration is automated (for example with Nelder–Mead), fix the seeds (use common random numbers) or use a noise-tolerant optimiser. Still to tune:
- MD and DO rates are too high;
- the top-3 share (95%) is too high, which needs higher rho_a and longer ROLs.

## 6. Storage design
```python
# nrmps/params.py  (add pydantic>=2 and numpy to [project].dependencies)
class Prefs(BaseModel):
    applicant_pref_correlation: float = Field(0.6, ge=0, le=1,
        description="Share of applicant-utility variance common to all applicants",
        json_schema_extra={"stage": "rating", "unit": "share", "level": "basic"})
    ...
class SimulationParams(BaseModel):
    schema_version: Literal[1] = 1
    run: RunParams = RunParams(); market: Market = Market(); applicants: Applicants = Applicants()
    programs: Programs = Programs(); prefs: Prefs = Prefs(); info: Info = Info(); apps: Apps = Apps()
    signals: Signals = Signals(); invites: Invites = Invites(); interview: InterviewP = InterviewP()
    rol: Rol = Rol(); match: MatchP = MatchP()
    @model_validator(mode="after")
    def _cross_field(self): ...
```
- **SimulationConfig** (the editable draft): `params` JSONField, `schema_version`, and typed `n_applicants` / `n_programs` columns for listings.
- **SimulationRun** (immutable once running):
  - identity and inputs: simulation FK, params (snapshot), schema_version, seed, replicate, sweep FK, params_hash (sha256 of canonical JSON), code_version;
  - execution: status, started_at, finished_at, error;
  - results: metrics JSON, stage_fingerprints JSON.
- **Sweep and SweepCell**: axes, replicates and seed, with one cell per SimulationRun.
- **Import/export:** `GET /simulations/<pk>/config.json` and `POST /simulations/<pk>/config/import/` (validate → show a diff → save).
- **Clone:** `POST /simulations/<pk>/clone/`.
- **Presets:** stored as `nrmps/presets/*.json`, validated by the same schema. Pydantic's `model_json_schema()` drives the form, the '?' popovers and the documentation table.

## 7. Metrics to compute for every replicate (feeds Monte-Carlo and the plots)
- Match rate (overall and by group) and position fill rate.
- Share matched to their first choice and to a top-3 choice, and the mean rank of the match (applicants and programs).
- Unmatched applicants and unfilled positions.
- Applications, interviews and ROL length per applicant (mean and distribution), and the zero-interview share.
- Interview slots offered, accepted and wasted.
- Signalled vs unsignalled interview rate.
- Blocking pairs (should be 0).
- Welfare: mean true utility of the match for each side, and the gap between observed and true utility.
- Proposing-side difference count.
- (COULD) Share matched in home region, couples match rate, SOAP fills.

## 8. Prototype sensitivity (illustrative only)

These numbers come from the reviewer's prototype (2,400 applicants × 300 programs, seed 1). It is uncalibrated and uses a simpler model than Appendix A. They show how much each knob matters, not real-world levels:

| Variation | Match rate | First choice | Top-3 |
|---|---|---|---|
| ρ_A = 0 | 0.803 | 0.724 | 0.956 |
| ρ_A = 0.6 | 0.921 | 0.492 | 0.926 |
| ρ_A = 0.95 | 0.935 | 0.281 | 0.704 |
| signals 0 / 5 / 15 per applicant | 0.921 / 0.925 / 0.931 | – | – |
| applications 10 / 30 / 80 | 0.944 / 0.921 / 0.833 | – | – |
| top-N vs. portfolio strategy | 0.769 vs. 0.921 | – | – |

Verifier caveats:
- The seed-to-seed SD of match rate is about 1.7 pp over 10 seeds, which is **larger than the signal effects shown**. Compare scenarios with replicates, common random numbers and t-based intervals; the 10-seed interval quoted in the review used z instead of t.
- The applications effect is monotone decreasing, not non-monotone. About two thirds of the drop at 80 applications comes from the prototype's single invitation round. With 3 backfill rounds the match rate is 0.899, and 10 rounds give 0.901.
- The remaining drop comes from correlated screening: every program invites the same strong applicants.
