# NRMP Simulated: model specification 2.1

**Status: normative for `model_version = "2.1"`** (engine `2.1.x`, parameter schema v1 in `nrmps/params.py`).
Model 2.0 was adopted by owner decision D1 on 2026-09-25; 2.1 adds the stages from applications to the match (§7–8)
and leaves §3–6 unchanged. The Python engine (`nrmps/engine/`), the help formulas, presets and any
browser port implement this document. Every run stores the `model_version` it used (§12.11); any change to a
formula, a stream ID or a draw recipe needs a new model version, because results are then no longer reproducible
from (parameters, seed). The defects of the legacy v1 generator that motivated this model are described in
[Appendix A §1](review/A-model-spec.md) of the project review; by decision D3 the v1 generator and its results are
removed rather than kept read-only.

Implementation status: everything in §3–10 is implemented for single applicants. Replicates, SOAP, couples, dates
and the optional Bayesian interview update are specified as planned; their parameters exist in the schema with
`implemented = false` (§12.10).

---

## 1. Notation

| Symbol | Meaning |
|---|---|
| $i=1..N$ | applicants; $g(i)$ is the applicant's group (US MD, DO, US-IMG, non-US-IMG, …) |
| $j=1..M$ | programs; $t(j)$ is the program tier; $c_j\ge1$ positions; $P=\sum_j c_j$ |
| $k\in\mathcal K_A$ | **applicant attributes**, which programs evaluate (e.g. `board_scores`, `research`, `honors`) |
| $l\in\mathcal K_P$ | **program attributes**, which applicants evaluate (e.g. `reputation`, `program_size`, `location`) |
| $\operatorname{std}(\cdot)$ | standardise to mean 0, SD 1 over the indicated index set (population SD, §12.5) |
| $\Phi$ | standard normal CDF |

Indices are 0-based in the implementation (§12).

## 2. Scale conventions

- Latent strength $a_i$ and quality $q_j$ live on an unbounded z-scale, so no (μ, σ) pair is infeasible and nothing
  is clamped. They enter the model only after standardisation or as quantiles.
- Utilities have SD ≈ 1 per agent, and every noise SD is in those units.
- Display: users see transforms such as the percentile $100\,\Phi(\operatorname{std}(a_i))$, or a linear map of an
  attribute to a familiar scale. CSV uploads may supply raw z-values or percentiles, declared in the header.

---

## 3. Randomness and reproducibility

- A run has a root `seed`, an integer in $[0, 2^{63}-1]$. A blank `run.seed` is replaced by `secrets.randbits(63)`
  and the value used is stored with the run.
- Replicate $r$ is the $r$-th child of `SeedSequence(seed)`, and each stage draws from its **own stream** with a
  fixed ID (§12.1). Draws depend only on *(seed, replicate, stream)* and, for pair-level draws, the pair — never on
  how many draws another stage made or on array shapes.
- **Common random numbers (CRN).** Changing a parameter of one stage leaves the draws of every other stage unchanged.
  A slider move or an A/B comparison shows the parameter's effect, not new noise.
- **Replicate modes** (`run.resample_population`):
  - `false` (default): the population streams `POP_A`, `POP_P`, `CAP`, `WEIGHTS_A`, `WEIGHTS_P`, `IDIO_A` and
    `IDIO_P` use replicate 0, so the population and the true utilities $u, v$ are fixed and only process noise varies.
    This answers "how much of an individual's outcome is luck?".
  - `true`: every stream is re-drawn per replicate, for the distribution of market-level outcomes.
- **Population-level draws** use numpy `Generator(PCG64(SeedSequence(seed, spawn_key=(replicate, stream))))`.
- **Pair-level draws** use the counter-based generator Philox4x32-10 keyed by the seed with counter
  (i, j, stream, replicate), mapped to uniforms and Box–Muller normals by an exact recipe (§12.3–12.4). This makes
  pair draws independent of block boundaries, lets sparse stages draw only the pairs they need, and lets a
  JavaScript port reproduce them (decision D7).

---

## 4. Population

### 4.1 Groups, strength and quality

Group sizes are the largest-remainder rounding (§12.5) of `share × N`; the labels are shuffled over applicant
indices. Tiers (optional; one implicit tier `all` with mean 0 otherwise) are assigned to programs the same way.

$$a_i=\mu_{g(i)}+\sigma_{g(i)}\,z_i,\qquad q_j=\mu_{t(j)}+\sigma_q\,z'_j,\qquad z,z'\sim N(0,1)$$

Only differences between group (tier) means relative to $\sigma_g$ ($\sigma_q$) matter; without tiers $\sigma_q$ has no
effect, but it must be > 0.

### 4.2 Attributes with an explicit correlation

$$x_{ik}=\rho_k\,\operatorname{std}(a)_i+\sqrt{1-\rho_k^2}\;e_{ik},\qquad y_{jl}=\rho'_l\,\operatorname{std}(q)_j+\sqrt{1-\rho'^2_l}\;e'_{jl},\qquad e,e'\sim N(0,1)$$

$\rho_k$ answers "how closely does `board_scores` track overall strength?". Defaults: `board_scores` 0.8, `research`
0.5, `honors` 0.6; `reputation` 0.9, `location` 0.0.

**`program_size`.** A program attribute whose key is exactly `program_size` is not drawn: its value is
$y_{j,\texttt{program\_size}}=\operatorname{std}(\log c)_j$, so it reflects the program's real size, and its
`corr_with_quality` is ignored (its noise draw is still consumed, so other attributes do not move).

### 4.3 Positions and capacities

**Tightness is an input.** $P=\max(1,\operatorname{round}(N/\texttt{applicants\_per\_position}))$ (NRMP 2026:
48,050 / 44,344 ≈ 1.08). $M$ is `market.n_programs` if set, else $\max(1,\operatorname{round}(P/\texttt{program\_size\_mean}))$
(NRMP 2026: 44,344 / 6,809 ≈ 6.5). `round` halves to even. $M\le P$ is required.

Every program gets one position; the remaining $P-M$ are spread so that $c_j\ge1$ and $\sum_j c_j=P$ exactly:

| `program_size_dist` | Extra positions per program |
|---|---|
| `fixed` | even split by largest remainder (sizes differ by at most 1) |
| `lognormal` (default) | proportional to $s_j\sim\text{LogNormal}(0,\sigma_{size})$, by largest remainder; $\sigma_{size}$ = `program_size_dispersion` (0.8); real sizes are right-skewed |
| `shifted_multinomial` | $\text{Multinomial}(P-M,\,1/M)$, marginally close to a shifted Poisson |

### 4.4 Preference weights

$$w_i\sim\text{Dirichlet}(\lambda\,m_A)\ \text{over }\mathcal K_P,\qquad v_j\sim\text{Dirichlet}(\lambda\,m_P)\ \text{over }\mathcal K_A$$

- $m_A$ (`programs.attributes[].applicant_weight_prior`) and $m_P$ (`applicants.attributes[].program_weight_prior`)
  are the mean importances, renormalised to sum to 1. Defaults: reputation 0.5, location 0.3, program_size 0.2;
  board_scores 0.5, research 0.3, honors 0.2.
- $E[w_{il}]=m_l$ and $\operatorname{Var}(w_{il})=m_l(1-m_l)/(\lambda+1)$; no clipping, rows always sum to 1.
- **λ (`prefs.weight_concentration`) sets the shape of individual tastes, not their amount.** The taste term is
  standardised (§5), so its share of utility variance is $(1-\rho)\tau$ for any λ. Low λ gives sparse tastes (each
  agent cares mainly about one attribute); high λ gives weights close to $m$.

---

## 5. True utilities

The applicant's true utility for program $j$ has three standardised parts that are uncorrelated within every
applicant:

$$C_j=\operatorname{std}_j\!\Big((1-\beta)\,\operatorname{std}(q)_j+\beta\sum_l m_{A,l}\,y_{jl}\Big)\quad\text{(common: the same for every applicant)}$$

$$\tilde y_{jl}=y_{jl}-b_l\,C_j,\quad b_l=\operatorname{Cov}_j(y_{\cdot l},C)\qquad T_{ij}=\operatorname{std}_j\!\Big(\sum_l (w_{il}-m_{A,l})\,\tilde y_{jl}\Big)\ \text{within each applicant }i$$

$$\varepsilon_{ij}\sim N(0,1)\ \text{(idiosyncratic fit, stream IDIO\_A)}$$

$$\boxed{u_{ij}=\sqrt{\rho_A}\,C_j+\sqrt{1-\rho_A}\,\Big(\sqrt{\tau}\,T_{ij}+\sqrt{1-\tau}\,\varepsilon_{ij}\Big)}$$

The program's true utility for applicant $i$ is symmetric, with the applicant attributes residualised on $S$
($\tilde x_{ik}=x_{ik}-b'_kS_i$, $b'_k=\operatorname{Cov}_i(x_{\cdot k},S)$) and $T'$ standardised within each program:

$$S_i=\operatorname{std}_i\!\Big((1-\beta)\operatorname{std}(a)_i+\beta\sum_k m_{P,k}\,x_{ik}\Big),\quad T'_{ji}=\operatorname{std}_i\!\Big(\sum_k (v_{jk}-m_{P,k})\,\tilde x_{ik}\Big),\quad \eta_{ji}\sim N(0,1)\ \text{(IDIO\_P)}$$

$$\boxed{v_{ji}=\sqrt{\rho_P}\,S_i+\sqrt{1-\rho_P}\,\Big(\sqrt{\tau}\,T'_{ji}+\sqrt{1-\tau}\,\eta_{ji}\Big)}$$

**Why this form.** The common term uses the population-mean weights $m$, so it is truly common; the personal part
uses taste deviations $w_i-m_A$, which are centred; residualising the attributes on $C$ makes
$\operatorname{Corr}_j(C,T_{i\cdot})=0$ for *every* applicant, not only on average. Consequences:

- $\operatorname{Var}_j(u_{ij})\approx1$ for every applicant (per-applicant SD about 0.07 at the defaults).
- **Averaged over pairs of applicants**, $\operatorname{Corr}_j(u_{ij},u_{i'j})\approx\rho_A$ (0.602 at $\rho_A=0.6$).
  $\rho_A$ is the "applicant preference correlation": 1 means everyone agrees, 0 means purely personal tastes.
  Individual pairs vary around it (SD 0.147 at the defaults). Very sparse tastes raise the mean slightly, because each
  agent's taste term is scaled by its own SD: at λ = 0.3 by +0.02 at $\rho_A=0$ and +0.007 at $\rho_A=0.6$ (λ = 10:
  within ±0.002).
- $\tau$ (`prefs.taste_share`) is the share of the personal part that is attribute taste rather than pure fit.
- $\beta$ (`prefs.attribute_weight_share`) is the *mixing weight* of the attribute index in $C$, not a variance share:
  attributes correlate with quality, so the variance they add beyond $q$ is small (about 2% at β = 0.3 with the
  default attributes; reported as `attribute_share_of_common`).
- **Degenerate case:** with $|\mathcal K_P|<2$, or for an applicant whose taste term has SD below $10^{-12}$ (weights
  equal to $m_A$), $T\equiv0$ and τ is treated as 0 for that applicant (all personal weight on ε); the schema warns
  when a side has fewer than 2 attributes. $T'$ is handled the same way.

**Defaults:** $\rho_A=0.6$, $\rho_P=0.7$, $\beta=0.3$, $\tau=0.5$, $\lambda=10$. In schema v1 β, τ and λ are shared by
both sides. Planned geography terms ($\gamma_A\,\mathbb 1\{\text{region}_i=\text{region}_j\}$, $\gamma_P$) are not
part of model 2.1.

---

## 6. Observation before interviews

$$\hat u_{ij}=u_{ij}+\sigma_{A,pre}\,h_j\,\delta_{ij},\qquad \hat v_{ji}=v_{ji}+\sigma_{P,pre}\,h'_i\,\zeta_{ji}$$

- **Units.** σ is in utility SD units. The reliability is $r=1/(1+\sigma^2)$ and $\operatorname{Corr}(u,\hat u)=\sqrt r$
  when $\gamma_h=0$; σ = 0.5 gives r = 0.8. In general
  $\operatorname{Corr}(u,\hat u)\approx1/\sqrt{1+\sigma^2E[h^2]}$ (`expected_correlation`).
- **Exactness.** σ = 0 gives $\hat u=u$ bit for bit.
- **Visibility heteroskedasticity** $\gamma_h$: $h_j=1+\gamma_h(1-P_j)$ with $P_j$ program $j$'s quality quantile
  (§12.5), so less-known programs are judged more noisily; $h'_i=1+\gamma_h(1-Q_i)$ with $Q_i$ applicant $i$'s
  strength quantile.
- **Halo (correlated error)** ψ: $\delta_{ij}=\sqrt{1-\psi}\,\delta^0_{ij}+\sqrt\psi\,\nu_j$, so everyone misjudges
  program $j$ in the same direction (herding); symmetrically $\zeta_{ji}=\sqrt{1-\psi}\,\zeta^0_{ji}+\sqrt\psi\,\nu'_i$.
  $\delta^0$ (`PRE_A`), $\zeta^0$ (`PRE_P`), $\nu$ (`HALO_A`) and $\nu'$ (`HALO_P`) are standard normals.
- **Signals** enter the program's screening score, not its utility (§7.3); by default they do not affect rank lists.

---

## 7. From applications to interviews

Model 2.1 adds these stages; §3–6 are unchanged, so everything up to the pre-interview ranks is reproduced exactly.
Every stage works on the sparse set of pairs that reached it. Two public percentiles recur:

- the program's **prestige** $p_j$, the quantile (§12.5) of the applicants' common view $C_j$;
- the applicant's **self-assessed competitiveness** $c_i$, the quantile of $S_i+\sigma_{self}\,\xi_i$, where $S_i$ is
  the programs' common view of the applicant (§5), $\xi_i\sim N(0,1)$ and $\sigma_{self}$ =
  `apps.self_assessment_noise_sd` (0 = perfect self-knowledge).

### 7.1 Applications (stream `APPS`)

- **Count.** $\mu_i$ is the applicant's group `applications_mean`, or `apps.mean` when blank. `fixed`:
  $k_i=\operatorname{round}(\mu_i)$; `poisson`: $k_i\sim\text{Poisson}(\mu_i)$; `negbin`: negative binomial with mean
  $\mu_i$ and variance $\mu_i+d\,\mu_i^2$ ($d$ = `apps.dispersion`). Then $k_i=\min(\max(k_i,1),M)$.
- **Strategy** (`apps.strategy`); every strategy uses the applicant's strict pre-interview ranks (§8) of all programs:
  - `top_n`: the $k_i$ programs the applicant ranks best before interviews;
  - `all`: every program ($k_i=M$);
  - `random`: the $k_i$ programs with the smallest `APPS` pair uniforms $a_{ij}$;
  - `portfolio`: reach $R_i=\{j:p_j>c_i+b\}$, safety $S_i=\{j:p_j<c_i-b\}$ and target $T_i$ the rest, with
    $b$ = `apps.target_band`. With $n_R=\min(\operatorname{round}(k_i\,s_R),k_i)$ and
    $n_S=\min(\operatorname{round}(k_i\,s_S),k_i-n_R)$ from `apps.portfolio_shares`, the applicant takes the best
    $n_R$ of $R_i$, the best $n_S$ of $S_i$, fills up to $k_i$ with the best of $T_i$, and finally with the best
    remaining programs of any category ("best" always means the best pre-interview rank).

### 7.2 Signals (stream `SIGNALS`)

- Tiers (`signals.tiers`, for example gold 3 and silver 12) are filled in order. If the applicant's group sets
  `n_signals`, the applicant sends at most that many in total, filling tiers in order.
- Signals go only to programs the applicant applied to, in the order given by `signals.allocation`: `top_utility`,
  the best pre-interview rank first; `realistic`, first the non-reach applications ($p_j\le c_i+b$) by pre-interview
  rank, then the reach ones; `random`, the smallest `SIGNALS` pair uniforms first.
- Program $j$ uses signals when its `SIGNALS` population uniform is below `signals.program_use_share`.

### 7.3 Screening, invitations and acceptance (streams `INVITES`, `ACCEPT`)

- **Screening score** of applied pair $(i,j)$:
  $\text{screen}_{ji}=\hat v_{ji}+\beta_t$ when the applicant signalled $j$ and $j$ uses signals, else
  $\hat v_{ji}-y\,\max(0,Q^S_i-p_j)$, where $\beta_t$ is the boost of the signal's tier, $y$ =
  `invites.yield_protection` and $Q^S_i$ the quantile of $S_i$ (a program sees an applicant as overqualified when the
  applicant stands higher than the program, unless a signal it reads says otherwise).
- **Hard screen** (strategies `threshold_then_top` and `threshold_then_random`, when `invites.screen_attribute` is
  set): applicants whose attribute quantile is below `screen_min_percentile` are never invited.
- **Slots:** $s_j=\lceil \texttt{interviews\_per\_position}\cdot c_j-10^{-9}\rceil$ (the tolerance keeps exact
  products such as 1.1 × 10 from rounding up).
- **Waves** $w=1..W$ ($W$ = `invites.rounds`). In each wave every program with open slots
  $o_j=s_j-\text{accepted}_j>0$ invites up to $\lceil 1.2\,o_j\rceil$, computed exactly as $(12\,o_j+9)$ div 10
  ($o_j$ in the last wave), of the
  eligible applicants it has not invited yet: `top_score` and `threshold_then_top` by screening score (ties by the
  `TIE_P` keys); `signal_first` signalled applicants first (tier order, then score), then the others by score;
  `threshold_then_random` by the smallest `INVITES` pair uniforms.
- **Responses.** After all programs have invited, applicants respond in the order of a random permutation (one per
  wave, from the `ACCEPT` generator). Each goes through their new invitations, `best_first` by pre-interview view
  $\hat u_{ij}$ or `first_come` by the smallest `ACCEPT` pair uniforms, and accepts while they have fewer than
  `interview.applicant_cap` accepted interviews and the program has an open slot; otherwise they decline.

### 7.4 Interviews and the post-interview view (streams `FIT`, `FIT_P`)

For each accepted interview:
- **Fit shock:** $u^*_{ij}=u_{ij}+\sigma_{fit}\,f_{ij}$ and $v^*_{ji}=v_{ji}+\sigma_{fit}\,g_{ji}$ with standard
  normals $f$ (`FIT`) and $g$ (`FIT_P`); welfare metrics use $u^*$ and $v^*$.
- **Post-interview view:** $\tilde u_{ij}=u^*_{ij}+(1-\kappa)\,e_{ij}$, where $e_{ij}$ is the *same* pre-interview
  error term ($\hat u=u+e$, §6), so the interview shrinks the existing misperception: κ = 0 leaves it unchanged,
  κ = 1 reveals $u^*$ exactly. Programs are symmetric: $\tilde v_{ji}=v^*_{ji}+(1-\kappa)\,e'_{ji}$. An optional
  Bayesian variant (Appendix A §7) is not part of model 2.1.
- Pairs that did not interview get no post-interview view and cannot be ranked.

## 8. Ranking, tie-breaking and the match

- **Strict orders everywhere.** $\text{rank}_i(j)$ comes from `np.lexsort((t_ij, -score_ij))` with tie keys
  $t_{ij}$ from `TIE_A` (applicants ranking programs) or `TIE_P` (programs ranking applicants); rank 1 is best and
  ranks are a permutation of $1..|D_i|$. The domain $D_i$ is explicit: all programs before applications, and the
  interviewed pairs for rank order lists.
- **Rank order lists.** Applicants rank the programs they interviewed at by $\tilde u_{ij}$, keeping, by
  `rol.applicant_policy`: `all_interviewed` all of them; `top_k` and `truncate_k` the first `applicant_top_k`;
  `above_reservation` those with $\tilde u_{ij}\ge$ `reservation_utility`; `likelihood_weighted` all of them, ordered
  by $\tilde u_{ij}+\ln\Phi((c_i-p_j)/b)$ instead (applicants move programs they are less likely to match with down
  the list). Programs rank the applicants they interviewed by $\tilde v_{ji}$, plus the signal boost when
  `signals.use_in_ranking` is on and the program uses signals, keeping, by `rol.program_policy`: `all_interviewed`
  all; `dnr_quantile` the best $\max(1,\lceil n(1-q)-10^{-9}\rceil)$ of $n$ ($q$ = `program_dnr_quantile`); `dnr_threshold`
  those with $\tilde v_{ji}\ge$ `reservation_utility`. Applicant lists are at most 300 long (the NRMP's limit);
  program lists have no limit. Applicants with a non-empty list are *certified* and take part in the match.
- **Mechanism.** Deferred acceptance with capacities (Gale–Shapley; Roth–Peranson without couples): proposers go down
  their lists; a program (or an applicant, when programs propose) holds the best offers it ranked, up to its
  capacity (1 for an applicant), and rejects the rest; proposals to someone who did not rank the proposer are
  rejected. `match.algorithm` chooses the proposing side (applicants by default, as the NRMP). The result is the
  unique proposer-optimal stable matching, whatever the processing order.
- **Validation on every run** (`nrmps/engine/validate.py`, stored as `outcomes.checks`): no blocking pair against
  the submitted lists; capacities respected; each matched pair on both lists; list entries only for interviews, ranks
  exactly $1..k$ per list, applicant lists within 300. With `match.compare_both` the other side's algorithm also
  runs; the matched applicants and the number matched to each program must then be equal (rural hospitals theorem),
  and every applicant weakly prefers the applicant-proposing result. `manage.py nrmp_validate` repeats these checks
  on random markets, adds agreement with an independent solver (the `matching` package) and checks that no applicant
  gains by submitting another list under applicant-proposing deferred acceptance (strategy-proofness for the
  proposing side); docs/VALIDATION.md is its report.

---

## 9. Acceptance tests

`nrmps/tests/engine/` (pytest, no database):

| # | Test | Status |
|---|---|---|
| 1 | Determinism: same (params, seed, replicate) ⇒ byte-identical population npz, identical utilities and metrics JSON | implemented |
| 2 | CRN: changing only σ_pre keeps population, weights, u and v; changing only ρ keeps the population; κ keeps applications, signals and invitations | implemented |
| 3 | Exactness: σ = 0 ⇒ $\hat u=u$ and pre-ranks = true ranks; σ > 0, γ_h = 0, large N ⇒ pooled Corr(u, û) within ±0.01 of $\sqrt{1/(1+\sigma^2)}$; κ = 1 ⇒ $\tilde u=u^*$ | implemented |
| 4 | Correlation knob: $\rho_A=1,\sigma=0$ ⇒ identical rankings; for ρ ∈ {0, …, 0.8}, N ≥ 500, M ≥ 100, the mean pairwise correlation is within ±0.02 of ρ (±0.01 at 0); $\operatorname{Corr}_j(C,T_{i\cdot})=0$ for every applicant | implemented (both sides) |
| 5 | Moments: Var(u) ≈ 1; Dirichlet mean and variance; Σc = P, all c ≥ 1; realised applicants per position | implemented |
| 6 | Ranks are permutations; tie-breaking differs by seed and repeats for the same seed | implemented |
| 7 | Match: stability, capacity, rural-hospitals theorem, agreement with an oracle, no profitable misreport for applicants (the validation report); stage invariants (applications ≤ M, signals ⊆ applications, accepted ⊆ invited ⊆ applied, caps and slots respected, lists ⊆ interviews) | implemented |
| 8 | Validation: bad shares, duplicate keys, M > P, the pair guard, bad seeds and mismatched attribute keys raise before any computation | implemented |
| 9 | JS parity on 200 × 20 markets | planned (the recipe of §12.3–12.4 is fixed now) |

## 10. Diagnostics

Computed on every run (`nrmps/engine/metrics.py` and `nrmps/engine/outcomes.py` document the JSON):

| Diagnostic | Definition |
|---|---|
| Market | N, M, P, realised and requested applicants per position, capacity summary |
| Generation | realised vs requested moments: group shares, strength means and SDs; attribute correlations; mean weights; tier shares and quality means |
| Consensus | mean pairwise Pearson correlation of true utilities and mean pairwise Spearman of true rankings, both sides (O(N·M) identity: with rows $z_i$ standardised over $D$ columns, the mean over pairs is $(\lVert\sum_i z_i\rVert^2-nD)/(Dn(n-1))$) |
| Fidelity | noise SD, reliability, expected and pooled Corr(u, û), per-agent Spearman(u_i·, û_i·) mean and deciles, observed consensus |
| First choices | distinct pre-interview first choices, share of the most popular program and of the 10 most popular |
| Histograms | strength, quality, capacity, per-agent fidelity (20 bins) |
| Funnel | applications, signals, invitations, interviews and list entries per applicant and per position; applicants with no interview |
| Match | match rate (of certified applicants), fill rate, unfilled positions and programs, share matched to their 1st and a top-3 choice, the matched-rank distribution, list length of matched and unmatched applicants, blocking pairs (always 0), and the proposing-side comparison when requested |
| Signals | signal-to-interview and signal-to-match rates |
| Welfare | the true-utility rank ($u^*$) of the match among the applicant's interviews; regret against the best interviewed program; post-interview fidelity |
| By group | match rate and mean matched rank per applicant group and per strength decile |
| Checks | the validation of §8: blocking pairs, programs over capacity, matches not on both lists, list entries without an interview, lists that are not strict, applicant list entries beyond 300 (all 0), the rural hospitals and applicant-optimality flags, and `passed` |
| Planned | replicates and intervals, true-preference blocking pairs |

## 11. Parameter symbols ↔ schema names

| Symbol | Schema path | Default |
|---|---|---|
| seed, R | `run.seed`, `run.replicates`, `run.resample_population` | blank (drawn and stored), 1, false |
| $N$, app/pos, $\bar c$, $M$ | `market.n_applicants`, `market.applicants_per_position`, `market.program_size_mean`, `market.n_programs` | 1000, 1.08, 6.5, derived (142) |
| size distribution, $\sigma_{size}$ | `market.program_size_dist`, `market.program_size_dispersion` | lognormal, 0.8 |
| $\mu_g,\sigma_g$, shares | `applicants.groups[]` | us_md 0.44 / 0.5, us_do 0.18 / 0.35, us_img 0.09 / −1.0, non_us_img 0.25 / −1.3, other 0.04 / −0.5; SD 1 |
| $\rho_k$, $m_P$ | `applicants.attributes[].corr_with_strength`, `.program_weight_prior` | §4.2, §4.4 |
| $\sigma_q$, tiers, $\rho'_l$, $m_A$ | `programs.quality_sd`, `programs.tiers[]`, `programs.attributes[].corr_with_quality`, `.applicant_weight_prior` | 1.0, [], §4.2, §4.4 |
| $\rho_A,\rho_P$ | `prefs.applicant_pref_correlation`, `prefs.program_pref_correlation` | 0.6, 0.7 |
| β, τ, λ | `prefs.attribute_weight_share`, `prefs.taste_share`, `prefs.weight_concentration` | 0.3, 0.5, 10 |
| $\sigma_{A,pre},\sigma_{P,pre}$ | `info.applicant_pre_noise_sd`, `info.program_pre_noise_sd` | 0.5, 0.5 |
| κ, $\sigma_{fit}$ | `info.interview_informativeness`, `info.fit_shock_sd` | 0.6, 0.3 |
| $\gamma_h$, ψ | `info.visibility_heteroskedasticity`, `info.halo_share` | 0, 0 |
| $\mu_i$, count distribution, $d$ | `apps.mean` (or `applicants.groups[].applications_mean`), `apps.count_dist`, `apps.dispersion` | 30, negbin, 0.5 |
| strategy, $s_R,s_T,s_S$, $b$, $\sigma_{self}$ | `apps.strategy`, `apps.portfolio_shares`, `apps.target_band`, `apps.self_assessment_noise_sd` | portfolio, 0.25 / 0.5 / 0.25, 0.15, 0.5 |
| tiers, $\beta_t$ | `signals.tiers[]` (name, count, boost), `signals.allocation`, `signals.program_use_share`, `signals.use_in_ranking` | [], realistic, 1.0, off |
| $s_j$, $W$, $y$ | `invites.interviews_per_position`, `invites.rounds`, `invites.yield_protection`, `invites.strategy`, `invites.screen_attribute`, `invites.screen_min_percentile` | 10, 3, 0, top_score, blank, 0 |
| interview cap | `interview.applicant_cap`, `interview.acceptance_order` | 12, first_come |
| list policies | `rol.applicant_policy`, `rol.applicant_top_k`, `rol.reservation_utility`, `rol.program_policy`, `rol.program_dnr_quantile` | all_interviewed, 20, −1.0, dnr_quantile, 0.1 |
| mechanism | `match.algorithm`, `match.compare_both` | applicant_proposing, off |

---

## 12. Implementation contract

These definitions make results reproducible and portable. Changing any of them changes `model_version`.

### 12.1 Stream IDs

| ID | Stream | Kind | Used for |
|---|---|---|---|
| 1 | `POP_A` | population | group labels, strength, applicant attributes |
| 2 | `POP_P` | population | tier labels, quality, program attributes |
| 3 | `CAP` | population | capacities |
| 4 | `WEIGHTS_A` | population | applicants' weights $w$ |
| 5 | `WEIGHTS_P` | population | programs' weights $v$ |
| 6 | `IDIO_A` | pair | $\varepsilon_{ij}$ |
| 7 | `IDIO_P` | pair | $\eta_{ji}$ |
| 8 | `PRE_A` | pair | $\delta^0_{ij}$ |
| 9 | `PRE_P` | pair | $\zeta^0_{ji}$ |
| 10 | `APPS` | population, pair | application counts $k_i$ and self-assessment $\xi_i$; `random` strategy keys $a_{ij}$ |
| 11 | `SIGNALS` | population, pair | which programs use signals; `random` allocation keys |
| 12 | `INVITES` | pair | `threshold_then_random` invitation keys |
| 13 | `ACCEPT` | population, pair | applicants' response order per wave; `first_come` keys |
| 14 | `FIT` | pair | applicants' fit shocks $f_{ij}$ |
| 15, 16 | `POST_A`, `POST_P` | planned | the Bayesian interview update |
| 17 | `TIE_A` | pair | applicants' tie keys |
| 18 | `TIE_P` | pair | programs' tie keys |
| 19 | `SOAP` | planned | post-match SOAP |
| 20 | `HALO_A` | pair | $\nu_j$ at pair (0, j) |
| 21 | `HALO_P` | pair | $\nu'_i$ at pair (i, 0) |
| 22 | `FIT_P` | pair | programs' fit shocks $g_{ji}$ |

IDs are never renumbered or reused. `IDIO_*` count as population streams for the replicate modes (§3). A stream of
both kinds draws its population values from its `Generator` and its pair values from Philox with its ID.

### 12.2 Population-level draws

`stream_generator(seed, stream, replicate) = Generator(PCG64(SeedSequence(seed, spawn_key=(replicate, stream))))`,
i.e. child `stream` of child `replicate` of `SeedSequence(seed)`. Draw order per stream:

- `POP_A`: permutation of the group labels; N standard normals $z$; $N\times|\mathcal K_A|$ standard normals $e$
  (row-major).
- `POP_P`: permutation of the tier labels; M standard normals $z'$; $M\times|\mathcal K_P|$ standard normals $e'$.
- `CAP`: `fixed`: M uniforms (tie keys); `lognormal`: M lognormal(0, σ_size) scores, then M uniforms (tie keys);
  `shifted_multinomial`: one multinomial draw.
- `WEIGHTS_A` / `WEIGHTS_P`: Dirichlet rows in log space, robust to tiny concentrations (λ m ≈ 0.002): an $n\times K$
  block of Gamma(α + 1) variates $G$, then an $n\times K$ block of uniforms $U\in(0,1]$ (`1 - random()`);
  $\log g=\log G+\log(U)/\alpha$ (Marsaglia–Tsang boost), then $w=\exp(\log g-\max)/\sum\exp(\log g-\max)$ per row.
  With one attribute $w\equiv1$ and nothing is drawn.
- `APPS`: N counts (`poisson`: `poisson(μ)`; `negbin`: `negative_binomial(1/d, (1/d)/(1/d + μ))`; `fixed`: none),
  then N standard normals $\xi$.
- `SIGNALS`: M uniforms (program use).
- `ACCEPT`: one permutation of the N applicant indices per invitation wave, in wave order.

These rely on numpy's `Generator` algorithms, which numpy may change between versions; store the numpy version with
a run, and store populations (npz) when they must survive upgrades.

### 12.3 Pair-level draws: Philox4x32-10

Philox4x32 with 10 rounds (Salmon et al. 2011; Random123), multipliers `0xD2511F53`, `0xCD9E8D57`, Weyl constants
`0x9E3779B9`, `0xBB67AE85`. One round on counter $(c_0,c_1,c_2,c_3)$ with key $(k_0,k_1)$:

```
(hi0, lo0) = mulhilo(0xD2511F53, c0)        # 32 x 32 -> 64-bit product, high and low words
(hi1, lo1) = mulhilo(0xCD9E8D57, c2)
c = (hi1 ^ c1 ^ k0, lo1, hi0 ^ c3 ^ k1, lo0)
```

Round 1 uses the key as given; before each later round, $k_0 \mathrel{+}= \texttt{0x9E3779B9}$ and
$k_1 \mathrel{+}= \texttt{0xBB67AE85}$ (mod $2^{32}$). For every pair draw, on both sides:

```
counter = (i, j, stream, replicate)     # i = applicant index, j = program index, as 32-bit words
key     = (seed & 0xffffffff, seed >> 32)
```

Known answers (Random123 `kat_vectors`, verified in `nrmps/tests/engine/test_rng.py`, and against the independent
`randomgen` 2.3.0 implementation on 200 random counters):

| counter | key | output |
|---|---|---|
| 0, 0, 0, 0 | 0, 0 | `6627e8d5 e169c58d bc57ac4c 9b00dbd8` |
| ffffffff ×4 | ffffffff, ffffffff | `408f276d 41c83b0e a20bc7c6 6d5451fd` |
| 243f6a88 85a308d3 13198a2e 03707344 | a4093822 299f31d0 | `d16cfe09 94fdcceb 5001e420 24126ea1` |

### 12.4 Uniform and normal mapping

With output words $(w_0,w_1,w_2,w_3)$:

```
uniform(a, b) = ((a >> 5) * 67108864 + (b >> 6) + 0.5) / 9007199254740992      # 53 random bits
pair_uniform  = uniform(w0, w1)
pair_normal   = sqrt(-2 * log(uniform(w0, w1))) * cos(6.283185307179586 * uniform(w2, w3))
```

- The integer part is exact; `+ 0.5` and the division are IEEE double operations. The smallest value is $2^{-54}$.
  Adding 0.5 to a 53-bit integer $k\ge2^{52}$ rounds half to even, so the single value $k=2^{53}-1$ maps to exactly
  1.0: the image is contained in $(0,1]$. Use $\log u$, never $\log(1-u)$. $|z|\le\sqrt{108\ln2}\approx8.65$.
- `log`, `cos` and `sqrt` are evaluated in exactly this order. `sqrt` is correctly rounded everywhere; `log` and
  `cos` come from the platform's math library (numpy may use SIMD kernels), which can differ in the last bit between
  platforms and from JavaScript's `Math`. Results are bit-identical on one platform; parity tests across platforms
  must tolerate near-ties.
- JavaScript port notes: parse seeds above $2^{53}$ with `BigInt`; use `>>> 0` for unsigned words; `Math.imul` gives
  only the low word of a product, so compute `mulhilo` with `BigInt` or 16-bit limbs.

### 12.5 Numeric definitions

- **Standardisation** $\operatorname{std}(x)=(x-\bar x)/s$ with the population SD $s$ (ddof = 0). A vector with
  $s\le10^{-12}\max(1,\max|x|)$ counts as constant and maps to zeros.
- **Largest remainder** (Hamilton): entry $k$ gets $\lfloor T\,w_k/\sum w\rfloor$; the leftover units go to the largest
  fractional parts, ties broken by index (groups, tiers: the lower index first) or by the `CAP` uniforms
  (capacities: the smaller uniform first).
- **Quantiles** $P_j$, $Q_i$: the 0-based ascending rank (ties by index) divided by $n-1$; the lowest value gets 0, the
  highest 1, and a single agent gets 1.
- **Residualisation coefficient** $b_l=\operatorname{Cov}_j(y_l,C)/\operatorname{Var}_j(C)$ with population moments
  (equal to $\operatorname{Cov}_j(y_l,C)$ since $C$ is standardised; $b=0$ if $C$ is constant).
- **Taste moments** are analytic: with $d_i=w_i-m_A$, $\text{mean}_i=d_i\cdot\operatorname{mean}_j(\tilde y)$ and
  $\text{sd}_i^2=d_i^\top\operatorname{Cov}_j(\tilde y)\,d_i$ (population covariance), so
  $T_{ij}=(d_i\cdot\tilde y_j-\text{mean}_i)/\text{sd}_i$ needs no full row.
- $P$ and $M$ use Python's `round` (halves to even).

### 12.6 Degenerate cases

- A side with fewer than 2 attributes, `taste_share` = 0, or an agent with $\text{sd}_i<10^{-12}$: that agent's T is 0
  and its τ is 0 (it gets $\sqrt{1-\rho}\,\varepsilon$ as personal part). When no agent on a side has a taste term,
  the inner term is exactly ε.
- σ_pre = 0: $\hat u=u$ (no `PRE` draws). ψ = 0: $\delta=\delta^0$ (no `HALO` draws).
- M = 1 (or N = 1 on the program side): correlations and Spearman statistics are undefined and reported as `null`.

### 12.7 Evaluation order and blocks

Per pair, every step is an elementwise IEEE operation, in this order:

```
R     = d[i,0]*ỹ[j,0] + d[i,1]*ỹ[j,1] + …     (accumulated left to right over the K attributes)
T     = (R - mean_i) / sd_i
inner = sqrt(tau_i)*T + sqrt(1 - tau_i)*eps_ij
u     = sqrt(rho)*C[j] + sqrt(1 - rho)*inner
e     = scale[j]*delta_ij,   scale[j] = sigma_pre*(1 + gamma_h*(1 - P_j))
delta = sqrt(1 - psi)*delta0_ij + sqrt(psi)*nu_j
u_hat = u + e
u_star = u + sigma_fit*f_ij                     (interviewed pairs; programs: v + sigma_fit*g_ji)
u_post = u_star + (1 - kappa)*e
screen = v_hat + boost                           (signalled, program uses signals)
screen = v_hat - y*max(0, QS_i - p_j)            (not signalled)
```

The attribute contraction is an explicit fixed-order sum rather than a BLAS matrix product, so any block of rows,
columns or pairs is bit-identical to the same entries of the full matrix. The engine walks blocks of about
`block_pairs` (default 10⁶) pairs; peak memory is about 100 bytes per block pair on top of the population.

### 12.8 Ranks

`rank_rows` sorts each row by score, detects exact ties among neighbours, and re-sorts only the tied rows with
`lexsort((t, -score))` using tie keys drawn for those rows; the result equals the full lexsort. Ties in the keys
themselves fall back to index order (lexsort is stable). The rank of one entry within a row (drill-down views) is
$1+\#\{\text{higher score}\}+\#\{\text{equal score, smaller key}\}+\#\{\text{equal score and key, smaller index}\}$.

### 12.9 Populations as data

Uploaded populations enter as the same arrays (`Population`) and must pass `validate_population`: N, M ≥ 1; names
and keys unique and matching `^[a-z][a-z0-9_]{0,39}$`; shapes and dtypes; no NaN or ±∞; labels in range; capacities
≥ 1; weight rows non-negative summing to 1 ± 10⁻⁶. The attribute keys of the parameters must equal the population's.
`population_digest` hashes canonical metadata and little-endian float64 / int16 / int32 array bytes.

### 12.10 Parameters implemented in model 2.1

| Group | Implemented | Planned (in the schema, `implemented = false`) |
|---|---|---|
| run | `seed` | `replicates`, `resample_population` (the engine already maps population streams to replicate 0 unless it is set), `ci_level` |
| market, applicants, programs, prefs, info, apps, signals, invites, rol, match | all fields | – |
| interview | `applicant_cap`, `acceptance_order` | `n_dates`, `dates_per_program` |

Cross-field rules are validation errors when they would make a stage impossible (group and tier shares sum to 1
within 10⁻⁶, unique names and keys, M ≤ P, $N\cdot M\le5\times10^7$); rules that only make a setting unusual are
warnings (`SimulationParams.warnings()`), for example portfolio shares that do not add up to 1 or fewer interview
slots per applicant than half the interview cap.

### 12.11 Version stamps

Every run stores, next to its parameters and seed:

| Stamp | Source | Changes when |
|---|---|---|
| `model_version` | `nrmps.engine.MODEL_VERSION` (`"2.1"`) | a formula, stream ID, draw recipe or numeric definition in this document changes |
| `engine_version` | `nrmps.engine.ENGINE_VERSION` (`"2.1.x"`) | the engine code changes without changing results (the patch number), or with a new model version |
| `schema_version` | `nrmps.params.SCHEMA_VERSION` (1) | the parameter schema changes incompatibly; older versions are upgraded on load |
| `app_version` | `version` in `pyproject.toml` | a release |
| `git_sha` | `GIT_SHA` or Railway's `RAILWAY_GIT_COMMIT_SHA` | every deploy (empty when unknown) |
| `numpy_version`, `python_version` | the running interpreter | an upgrade; population draws use numpy's algorithms (§12.2) |

Exports carry the same stamps, so a result can be traced to the code and model that produced it.

### 12.12 Model history

| Version | Changes |
|---|---|
| 2.0 | Population, true utilities, the pre-interview view and strict ranks (§3–6, §8 ranks). |
| 2.1 | Applications, signals, screening and invitations, interviews, rank order lists and the match (§7–8); streams 10–14 and 22 defined. Results of §3–6 are unchanged. |
