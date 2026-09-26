# Appendix A: Model specification (draft v2)

**Status: draft for owner decision D1.** Once accepted:
- move this file to `docs/model_spec.md`;
- set `model_version = "2.0"`;
- treat it as normative for the Python engine, the help formulas, presets, and any browser port.

Every run stores the `model_version` it used (CRIT-2, CRIT-9).

Why a spec comes first:
- The current engine (v1) has defects that make its outputs meaningless (§1).
- The reviewers' own prototypes used three different utility models (VIZ verifier, CRIT-2). If nobody writes down one model, the engine, the slider previews, the help formulas and the calibrated presets will each simulate something slightly different.

---

## 1. The current model (v1) and what is wrong with it

| Quantity | Code | v1 formula | Problem |
|---|---|---|---|
| Base score | `models.py:18-62` | $q\sim\text{Beta}(\alpha,\beta)$ from (μ, σ). If $\sigma>\sqrt{\mu(1-\mu)}$, σ is cut to 90% of that limit; α, β are floored at 0.1 | Every default Beta σ (2 for both scores; 10 and 2 for the meta-scores) triggers the cut, which gives U-shaped populations and moves the mean (0.7 → 0.62; 0 → 0.30). SIM-3 |
| Attributes | `models.py:140-147, 226-233` | $x_{ik}\sim\text{Beta}(\text{mean}=q_i,\ \sigma_{meta})$ with the same clamps | A single knob mixes spread and correlation; attribute values come out Bernoulli-like. SIM-14 |
| Weights | `models.py:151-166, 237-252` | $\text{clip}(N(1,\sigma_w),0.01,2)$, then normalised | At σ = 3, 74% of draws land on a clamp bound, so weights act like on/off switches. SIM-12 |
| Capacity | `models.py:221-224` | $\max(0,\text{round}(N(\mu_c,\sigma_c)))$ | Programs with 0 positions; tightness is never controlled. SIM-15 |
| Utility | `simulation_engine.py:10` | $U_{ij}=\sum_k w_{ik}y_{jk}$ (implicit, never stored) | No idiosyncratic term, so preferences are nearly vertical. The base score is unused. SIM-13 |
| "Observed" | `simulation_engine.py:10, 50, 81` | $\hat U = \sigma_{pre}\cdot U$, and σ = 0 is treated as 1 | A monotone rescaling, so observed ranks equal true ranks. SIM-1 |
| Ranks | `simulation_engine.py:99-142` | position in `ORDER BY score DESC` | Ties follow DB row order; the whole cross-product is ranked. SIM-10 |
| RNG | global `random` + scipy global state | | Not reproducible. SIM-19 |

Naming trap in v1: `applicant_meta_preference` lists the *program* attributes applicants value, and it is also the key set of `School.score_meta`. `school_meta_preference` lists the *applicant* attributes programs value, and it is the key set of `Student.score_meta`. v2 defines each attribute once, on the side that owns it.

**Interim fix (Phase 0.3, still v1).** Keep the 0–1 scale but use $\hat U_{ij}=U_{ij}+\sigma_{pre}\,\delta_{ij}$ with $\delta\sim N(0,1)$, σ = 0 meaning exact, no `or 1.0` fallback. Store $U$ in the true-score fields. Break ties by (score desc, id).

---

## 2. Notation

| Symbol | Meaning |
|---|---|
| $i=1..N$ | applicants; $g(i)$ is the applicant's group (US MD, DO, US-IMG, non-US-IMG, …) |
| $j=1..M$ | programs; $t(j)$ is the optional program tier; $c_j\ge1$ positions |
| $k\in\mathcal K_A$ | **applicant attributes**, which programs evaluate (e.g. `board_scores`, `research`, `honors`) |
| $l\in\mathcal K_P$ | **program attributes**, which applicants evaluate (e.g. `reputation`, `program_size`, `location`) |
| $\operatorname{std}(\cdot)$ | standardise to mean 0, SD 1 over the indicated index set |
| $\Phi$ | standard normal CDF |

---

## 3. Randomness and reproducibility

- A run has a root `seed` (63-bit, shown in the UI; drawn with `secrets.randbits(63)` if blank). Replicates use `SeedSequence(seed).spawn(R)`.
- Inside a replicate, each stage draws from its **own child stream** with a fixed stage ID. Draws therefore depend only on *(seed, replicate, stage)*, never on how many draws an earlier stage made:

  | Stream | Stream | Stream |
  |---|---|---|
  | `POP_A` | `POP_P` | `CAP` |
  | `WEIGHTS_A` | `WEIGHTS_P` | `IDIO_A` |
  | `IDIO_P` | `PRE_A` | `PRE_P` |
  | `APPS` | `SIGNALS` | `INVITES` |
  | `ACCEPT` | `FIT` | `POST_A` |
  | `POST_P` | `TIE` | `SOAP` |

- **Common random numbers (CRN).** Changing a parameter of stage *s* leaves every draw of stages ≠ *s* unchanged. So a slider move or an A/B comparison shows the parameter's effect, not new noise.
- **Replicate modes** (`run.resample_population`):
  - `false` (**default**): the `POP_*`, `CAP`, `WEIGHTS_*` and `IDIO_*` streams are taken from replicate 0. True utilities $u, v$ are therefore fixed, and only process noise varies (`PRE_*`, `APPS`, `SIGNALS`, `INVITES`, `ACCEPT`, `FIT`, `POST_*`, `TIE`, `SOAP`). This answers "how much of an individual's outcome is luck?" and suits a user's own generated or uploaded market.
  - `true`: every stream is re-drawn. This answers "what is the distribution of market-level outcomes?"
- **Pair-level draws and browser parity (decision D7).** For per-pair noise ($\varepsilon_{ij}$, $\delta_{ij}$, …) the engine should support a **counter-based generator**: a hash of (seed, stream, i, j) mapped to a uniform, then Box–Muller. That makes pair-level draws independent of array shape, lets sparse stages draw only the pairs they need, and can be reproduced in JavaScript to within the last ulp. The prototype in `viz-prototype/sim.js` does this, and its numpy re-implementation matched to a max |diff| of 5.55e-17. `Math.log`/`cos` may differ from numpy in the last bit, so parity tests must tolerate near-ties. Population-level draws can use numpy `Generator` streams.

---

## 4. Population

### 4.1 Latent strength and quality (z-scale)
$$a_i\sim N(\mu_{g(i)},\,\sigma_{g(i)}),\qquad q_j\sim N(\mu_{t(j)},\,\sigma_q)$$

- All modelling happens on this unbounded scale, so there are no infeasible (μ, σ) pairs and no clamping.
- $a$ and $q$ enter the model only after standardisation (§4.2, §5) or as quantiles (§6). So $\sigma_q$ matters only relative to differences between tier means, and $\sigma_g$ only relative to differences between group means. With no tiers, $\sigma_q$ has no effect; it must be > 0.
- **Display.** Users see a transform: percentile $100\,\Phi(\operatorname{std}(a_i))$, or an optional familiar scale per attribute (e.g. a linear map to 200–300 for a board-score-like attribute). CSV uploads may supply either raw z-values or percentiles, declared in the header.
- **Legacy look (optional).** If the owner wants to keep 0–1 Beta-distributed scores in the UI, map with $F^{-1}_{\text{Beta}(\mu,\sigma)}(\Phi(z))$. The form must *validate* $\sigma<\sqrt{\mu(1-\mu)}$, never clamp it, and show the implied α, β with a histogram preview.

### 4.2 Attributes with an explicit correlation to strength or quality
$$x_{ik}=\rho_k\,\operatorname{std}(a)_i+\sqrt{1-\rho_k^2}\;e_{ik},\qquad y_{jl}=\rho'_l\,\operatorname{std}(q)_j+\sqrt{1-\rho'^2_l}\;e'_{jl},\qquad e,e'\sim N(0,1)$$

$\rho_k$ answers "how closely does board_scores track overall strength?". Suggested defaults:

| Side | Attribute | Correlation |
|---|---|---|
| Applicant | `board_scores` | 0.8 |
| Applicant | `research` | 0.5 |
| Applicant | `honors` | 0.6 |
| Program | `reputation` | 0.9 |
| Program | `program_size` | 0.0 |
| Program | `location` | 0.0 |

### 4.3 Capacities
**Tightness is an input.** `applicants_per_position` (NRMP 2026: 48,050 / 44,344 ≈ 1.08) fixes the total number of positions, $P=\operatorname{round}(N/\text{app\_per\_pos})$. Unless the user sets $M$, it is $\operatorname{round}(P/\text{program\_size\_mean})$, with `program_size_mean` ≈ 6.5 (NRMP 2026: 44,344 / 6,809).

Sizes, all $c_j\ge1$ with $\sum_j c_j=P$ exactly:
- **Default: lognormal.** Draw lognormal sizes with the configured dispersion, then rescale them to sum to $P$ using largest-remainder rounding. Real program sizes are right-skewed; a shifted Poisson (SD ≈ 2.3) is too narrow (OPT-14 verifier).
- **Option: shifted multinomial.** $c_j = 1+\text{Multinomial}(P-M,\,1/M)$, which is marginally close to a shifted Poisson.
- **Option: tiers.**

### 4.4 Preference weights
$$w_i\sim\text{Dirichlet}(\lambda_A\,m_A)\ \text{over }\mathcal K_P,\qquad v_j\sim\text{Dirichlet}(\lambda_P\,m_P)\ \text{over }\mathcal K_A$$

- $m$ is the mean importance of each attribute. It is editable per attribute tag, must sum to 1 (renormalised on save), and defaults to the Appendix C §3 priors (e.g. reputation 0.5, location 0.3, program_size 0.2).
- $E[w_{il}]=m_l$ and $\operatorname{Var}(w_{il})=m_l(1-m_l)/(\lambda+1)$. No clipping is needed, and the weights always sum to 1.
- **$\lambda$ sets the *shape* of individual tastes, not their amount.**
  - Because the taste term is standardised (§5), its share of utility variance is $(1-\rho_A)\tau_A$ for any λ.
  - Low λ gives sparse tastes: each applicant cares mainly about one attribute, so applicants cluster into about $|\mathcal K_P|$ taste types.
  - High λ gives smooth, Gaussian-like tastes.
  - Consensus is set by $\rho_A$ (and $\tau_A$), never by λ. The document check confirmed this: from λ = 0.3 to λ = 10⁵, the mean pairwise utility correlation stayed at 0.59–0.61.

---

## 5. True utilities

The applicant's true utility for program $j$ is built from three standardised parts, which are uncorrelated with each other within every applicant:

$$C_j=\operatorname{std}_j\!\Big((1-\beta_A)\,\operatorname{std}(q)_j+\beta_A\sum_l m_{A,l}\,y_{jl}\Big)\quad\text{(common: the same for every applicant)}$$
$$\tilde y_{jl}=y_{jl}-b_l\,C_j,\quad b_l=\operatorname{Cov}_j(y_{\cdot l},C)\qquad T_{ij}=\operatorname{std}_j\!\Big(\sum_l (w_{il}-m_{A,l})\,\tilde y_{jl}\Big)\ \text{within each applicant }i$$
$$\text{(personal taste: the applicant's deviation from average weights, on attributes residualised on }C\text{)}$$
$$\varepsilon_{ij}\sim N(0,1)\quad\text{(idiosyncratic fit, stream IDIO\_A)}$$
$$\boxed{u_{ij}=\sqrt{\rho_A}\,C_j+\sqrt{1-\rho_A}\,\Big(\sqrt{\tau_A}\,T_{ij}+\sqrt{1-\tau_A}\,\varepsilon_{ij}\Big)\;[+\,\gamma_A\,\mathbb 1\{\text{region}_i=\text{region}_j\}]}$$

The program's true utility for applicant $i$ is symmetric. The applicant attributes are residualised on $S$ ($\tilde x_{ik}=x_{ik}-b'_k S_i$), and $T'$ is standardised within each program $j$:
$$S_i=\operatorname{std}_i\!\Big((1-\beta_P)\operatorname{std}(a)_i+\beta_P\sum_k m_{P,k}\,x_{ik}\Big),\quad T'_{ji}=\operatorname{std}_i\!\Big(\sum_k (v_{jk}-m_{P,k})\,\tilde x_{ik}\Big),\quad \eta_{ji}\sim N(0,1)$$
$$\boxed{v_{ji}=\sqrt{\rho_P}\,S_i+\sqrt{1-\rho_P}\,\Big(\sqrt{\tau_P}\,T'_{ji}+\sqrt{1-\tau_P}\,\eta_{ji}\Big)\;[+\,\gamma_P\,\mathbb 1\{\text{local}\}]}$$

**Why this form.** A reviewer's first proposal put each applicant's *own* weights inside the "common" term, which made it partly personal, so $\rho_A$ stopped meaning what its label says (verifier on OPT-4). Here:
- The common term uses the population-mean weights $m_A$.
- The personal part is centred ($E[w_i-m_A]=0$, independent across applicants).
- Residualising the attributes on $C$ makes $\operatorname{Corr}_j(C,T_{i\cdot})=0$ for *every* applicant, not only on average. The first draft omitted this step: individual applicants then had $\operatorname{Var}_j(u_{ij})$ anywhere from 0.4 to 3, because attributes such as reputation correlate 0.9 with $q$.

As a result:
- $\operatorname{Var}_j(u_{ij})\approx1$ for every applicant, before the optional geography term. The document check measured a per-applicant SD of 0.07 with residualisation, against 0.42 without.
- **Averaged over pairs of applicants**, $\operatorname{Corr}_j(u_{ij},u_{i'j})\approx\rho_A$ (measured 0.603 at $\rho_A=0.6$). So $\rho_A$ is the "applicant preference correlation" the slider shows: 1 means everyone agrees, 0 means purely personal tastes.
- *Individual* pairs vary around $\rho_A$ (SD ≈ 0.15 at defaults), because tastes live in a $(|\mathcal K_P|-1)$-dimensional space. That spread doesn't shrink as $M$ grows.
- $\tau$ is the share of the personal part that is attribute taste rather than pure fit.
- $\beta$ is the *mixing weight* of the attribute index in $C$. It is not a variance share: because attributes correlate with $q$, the variance attributable to attributes beyond $q$ is much smaller (≈ 2% at β = 0.3 with the default attributes). The form should show the realised share.
- **Degenerate case:** if $|\mathcal K_P|<2$, the taste term has zero variance. Set $T\equiv0$ and give its weight to $\varepsilon$ (treat $\tau_A$ as 0); the validator warns. $T'$ is handled the same way when $|\mathcal K_A|<2$.

The prototype measured how strongly $\rho_A$ matters (OPT-4; 2,400 × 300): first-choice share 72% at $\rho_A=0$, 49% at 0.6, 28% at 0.95. That prototype used a different construction, so re-measure with the v2 engine before quoting these numbers.

**Defaults:** $\rho_A=0.6$, $\rho_P=0.7$, $\beta_A=\beta_P=0.3$, $\tau_A=\tau_P=0.5$, $\gamma=0$.

**Stored:**
- $u$ and $v$ for every *applied* pair (the true-score fields in v1 naming);
- dense float32 arrays per run only while $N\cdot M\le$ the D4 budget.

---

## 6. Observation before interviews (information friction)

$$\hat u_{ij}=u_{ij}+\sigma_{A,pre}\,h_{ij}\,\delta_{ij},\qquad \hat v_{ji}=v_{ji}+\sigma_{P,pre}\,h'_{ji}\,\zeta_{ji},\qquad \delta,\zeta\sim N(0,1)$$

- **Units.** σ is in utility SD units, and utilities have SD 1. The *reliability* is $r=1/(1+\sigma^2)$ and $\operatorname{Corr}(u,\hat u)=\sqrt r$; σ = 0.5 gives r = 0.8. The UI may offer the reliability slider and map it back to $\sigma=\sqrt{(1-r)/r}$.
- **Exactness.** σ = 0 gives $\hat u=u$ exactly. This is an acceptance test.
- **Options:**
  - *Visibility heteroskedasticity:* $h_{ij}=1+\gamma_h(1-P_j)$, where $P_j\in[0,1]$ is program $j$'s quality quantile, so less-known programs are judged more noisily. The applicant side is symmetric.
  - *Halo, or correlated error:* $\delta_{ij}=\sqrt{1-\psi}\,\delta^0_{ij}+\sqrt\psi\,\nu_j$, meaning everyone misjudges program $j$ in the same direction (herding; IDEAS.md).
- **Signals** enter the program's **screening score**, not its utility: $\text{screen}_{ji}=\hat v_{ji}+b_{\text{tier}(ij)}$, where $b$ is in SD units (e.g. gold 0.8, silver 0.4). By default signals do not affect rank lists (AAIM guidance).

---

## 7. Interviews and post-interview update

For each pair that actually interviewed:
- **Fit shock:** $f_{ij}\sim N(0,\sigma_{fit})$ (stream `FIT`) is revealed. The realised true utility becomes $u^*_{ij}=u_{ij}+f_{ij}$, and welfare metrics use $u^*$. Programs are symmetric with $g_{ji}$.
- **Post-interview observation (default):** $\tilde u_{ij}=u^*_{ij}+(1-\kappa_A)\,\sigma_{A,pre}\,h_{ij}\,\delta_{ij}$. This reuses the *same* $\delta_{ij}$ as the pre-interview view, so the interview shrinks the applicant's existing misperception rather than drawing a new one. $\kappa\in[0,1]$ is **interview informativeness** (default 0.6):
  - κ = 0: the error is unchanged; only the fit shock is revealed;
  - κ = 1: the interview reveals the truth.
  
  The post-interview SD is $\sigma_{A,post}=(1-\kappa_A)\sigma_{A,pre}$.
- **Optional Bayesian variant.** Treat the interview as a fresh signal $s=u^*+\sigma_{int}\delta'$ with $\sigma_{int}=\sigma_{A,post}$ and use $\tilde u=E[u^*\mid\hat u,s]$.
  - With a flat prior this is $\dfrac{\hat u/(\sigma^2_{pre}+\sigma^2_{fit})+s/\sigma^2_{int}}{1/(\sigma^2_{pre}+\sigma^2_{fit})+1/\sigma^2_{int}}$, because $\hat u$ measures $u$, not $u^*$.
  - With the model prior $u\sim N(0,1)$, it is the linear regression of $u^*$ on $(\hat u,s)$ with $\operatorname{Var}(\hat u)=1+\sigma^2_{pre}$, $\operatorname{Var}(s)=1+\sigma^2_{fit}+\sigma^2_{int}$, $\operatorname{Cov}(\hat u,s)=1$, $\operatorname{Cov}(u^*,\hat u)=1$ and $\operatorname{Cov}(u^*,s)=1+\sigma^2_{fit}$.
  - Use $\sigma_{pre}h_{ij}$ when visibility heteroskedasticity is on.
- Pairs that did not interview get no post-interview score and **cannot be ranked**. In practice, NRMP rank lists contain only interviewed programs.
- Optional: virtual-interview noise multiplier; no-show probability.

---

## 8. Ranking, tie-breaking and the match

- **Strict orders everywhere.** $\text{rank}_i(j)$ comes from `np.lexsort((t_ij, -score_ij))`, with the tie key $t$ drawn from the `TIE` stream. Rank 1 is best, and ranks are a permutation of $1..|D_i|$. The domain $D_i$ is stated explicitly: all programs before applications, the applied set afterwards, and interviewed pairs (after the ROL policy) for rank order lists.
- **ROLs:** length ≤ 300 (the NRMP limit). Applicant policies are all-interviewed, top-k or above-reservation. Program policies are all-interviewed or do-not-rank below a quantile.
- **Mechanism:** applicant-proposing deferred acceptance with capacities ([Appendix B §3.1](B-stage-spec.md)), optionally program-proposing for comparison. Stability is checked against submitted ROLs, so every run must have 0 blocking pairs (singles only).

---

## 9. Acceptance tests (pytest; must pass before `model_version` 2.0 ships)

1. **Determinism:** the same (params, seed, replicate) gives byte-identical arrays and results.
2. **CRN:** changing only $\sigma_{pre}$ leaves population, weights, $u$ and $v$ unchanged, and changing only κ leaves everything before stage 7 unchanged.
3. **Exactness:** σ = 0 gives $\hat u=u$, and pre-ranks equal true ranks. With σ > 0, $\gamma_h=0$, $\gamma_A=0$ and a large N, the pooled $\operatorname{Corr}(u,\hat u)$ is within ±0.01 of $\sqrt{1/(1+\sigma^2)}$. κ = 1 gives $\tilde u=u^*$ exactly.
4. **Correlation knob:** $\rho_A=1,\ \sigma=0$ means every applicant has the same ranking of programs. For $\rho_A\in\{0,0.2,0.4,0.6,0.8\}$ with N ≥ 500 and M ≥ 100, the **mean over all applicant pairs** of $\operatorname{Corr}_j(u_{ij},u_{i'j})$ is within ±0.02 of $\rho_A$ (±0.01 at $\rho_A=0$; its seed-to-seed SD is about 0.0006 at N = 1000, M = 142). Don't test individual pairs: their spread is about 0.15 and doesn't shrink with M. Also check that $\operatorname{Corr}_j(C,T_{i\cdot})=0$ for every applicant.
5. **Moments:** $\operatorname{Var}(u)\approx1$. Dirichlet weights have the stated mean and variance. The realised capacity mean and applicants-per-position match their targets.
6. **Ranks:** every ranking is a permutation. A different seed breaks ties differently; the same seed breaks them the same way.
7. **Match:** 0 blocking pairs against submitted ROLs; capacity respected; matched pairs appear on both lists; the same matched set and per-program fill under applicant- and program-proposing DA (rural-hospitals theorem); agreement with the `matching` package oracle on small instances.
8. **Validation:** a missing attribute key or infeasible parameters raise a domain error before any write.
9. **Parity (if D7):** the JS port gives identical matches for fixed seeds on 200 × 20 markets. Pair-level draws agree to within 1e-15; seeds whose markets contain near-ties at that tolerance are excluded or tie-broken on the counter key.

---

## 10. Diagnostics stored on every run

| Diagnostic | Definition |
|---|---|
| Fidelity | mean and quantiles of $\text{Spearman}(u_{i\cdot},\hat u_{i\cdot})$ per applicant; the same for programs; pre vs. post |
| Consensus | mean pairwise Spearman of true rankings, both sides |
| Market | positions per applicant, interviews per position |
| Generation | realised vs. requested moments for every generated quantity |
| Outcomes | match metrics from [Appendix B §5](B-stage-spec.md), including welfare ($u^*$ of the match), regret, and true-preference blocking pairs |

---

## 11. Parameter symbols ↔ schema names

| Symbol | Schema path ([Appendix C](C-parameters.md)) | Default |
|---|---|---|
| seed, R | `run.seed`, `run.replicates`, `run.resample_population` | auto, 1, **false** (fixed population) |
| $N$, app/pos, $\bar c$, $M$ | `market.n_applicants`, `market.applicants_per_position`, `market.program_size_mean`, `market.n_programs` | 1000, 1.08, 6.5, derived |
| $\mu_g,\sigma_g$, shares | `applicants.groups[]` | see C |
| $\rho_k$, $m_P$ | `applicants.attributes[].corr_with_strength`, `.program_weight_prior` | see C |
| $\sigma_q$, tiers, $\rho'_l$, $m_A$ | `programs.quality_sd`, `programs.tiers[]`, `programs.attributes[]` | 1.0, [], see C |
| $\rho_A,\rho_P$ | `prefs.applicant_pref_correlation`, `prefs.program_pref_correlation` | 0.6, 0.7 |
| $\beta$, $\tau$, $\lambda$ | `prefs.attribute_weight_share`, `prefs.taste_share`, `prefs.weight_concentration` | 0.3, 0.5, 10 |
| $\sigma_{pre}$, κ, $\sigma_{fit}$ ($\sigma_{int}\equiv\sigma_{post}$) | `info.applicant_pre_noise_sd`, `info.program_pre_noise_sd`, `info.interview_informativeness`, `info.fit_shock_sd` | 0.5, 0.5, 0.6, 0.3 |
| $\gamma_h,\psi$ | `info.visibility_heteroskedasticity`, `info.halo_share` | 0, 0 |
| $b$ | `signals.tiers[].boost` | [] |
| $\gamma_A,\gamma_P$ | `prefs.home_region_bonus`, `prefs.local_bonus_program` | 0, 0 |

`prefs.taste_share` (τ), `info.visibility_heteroskedasticity`, `info.halo_share` and `apps.self_assessment_noise_sd` are additions to the OPT schema made by this spec or its verification.

In schema v1, β, τ, λ and κ are **one value shared by both sides** ($\beta_A=\beta_P$, $\tau_A=\tau_P$, $\lambda_A=\lambda_P$, $\kappa_A=\kappa_P$). The side-specific symbols above allow per-side fields later without changing the model.
