# Appendix F: Help system and in-context "?" help

These are the help reviewer's deliverables, with the verifiers' corrections applied. The master plan schedules them in Phases 1.4, 1.6 and 4.3–4.7. The default values in §C match the interim fix in [Appendix C §1](C-parameters.md). After decision D1, the model section of the guide (§B.3) must document the [Appendix A](A-model-spec.md) formulas, not the v1 formulas listed here. **The text in §C–D describes the app after Phase 0**: additive noise, validated SDs, true scores written. Step 1.6 applies it, so it must not describe the pre-Phase-0 bugs as current behaviour.

## A. Help architecture and file layout

**Principles.** There is one source of truth: prose lives in the registry and markdown files, and numbers come from model metadata. Help appears at three levels: field (a popover), page (a dialog panel) and guide (/help/). User docs are separate from developer docs. Everything must work by keyboard, with screen readers, on touch and at 390px.

```
nrmps/help/
  __init__.py
  registry.py        # FieldHelp / ActionHelp / ColumnHelp / ChartHelp / PageHelp dataclasses + dicts
  glossary.py        # GLOSSARY: slug -> Term(term, short, long_md, see_also)
  csv_specs.py       # CSV_SPECS: students / schools / interviews columns (drives docs and upload errors)
  render.py          # markdown-it-py + mdit_py_plugins (front_matter, anchors, dollarmath, deflist, admon, container)
                     # shortcodes {{param_table}} {{glossary}} {{csv_spec:students}}; functools.lru_cache
  checks.py          # django.core.checks: H001 missing entry, H002 default outside validators,
                     # H003 planned w/o stage, H004 unknown anchor, H005 label drift
  content/guide/00-index.md ... 13-developer.md     # front matter: title, slug, order, audience, status
  content/pages/{simulations_list,simulation_form,simulation_manage,students_list,schools_list,interviews_list}.md
nrmps/templatetags/help_tags.py   # help_icon, field_row, term, help_url, page_help_button
nrmps/views_help.py               # help_index, help_page, help_panel (HTMX), developer_reference (staff),
                                  # preview_distribution (HTMX SVG)
nrmps/progress.py                 # simulation_progress(sim) -> list[Step]
nrmps/config_checks.py            # check_config(cfg) -> list[ConfigHint]
templates/nrmps/help/{base_help,index,page,developer,_panel,_help_icon,_param_table,_glossary,_csv_spec}.html
templates/nrmps/components/{_field,_progress_steps,_dist_preview}.html
static/samples/{students_sample.csv,schools_sample.csv}
static/vendor/katex/{katex.min.css,katex.min.js,fonts/}
tests/{test_help_registry,test_help_pages,test_help_examples}.py
```

URLs: `/help/`, `/help/<slug>/`, `/help/panel/<page_key>/` (HTMX), `/help/developer/` (staff only), `/documentation/` (301 to `/help/`), `/simulations/preview/distribution/` (HTMX SVG).

**Registry entry.**
```python
@dataclass(frozen=True)
class FieldHelp:
    key: str                 # "SimulationConfig.applicant_score_stddev"
    label: str               # "Applicant score SD"
    short: str               # <=120 chars; shown under the input (aria-describedby target)
    long_md: str = ""        # popover body and parameter reference
    formula_tex: str = ""    # KaTeX
    unit: str = ""
    typical: tuple[float, float] | None = None
    status: Literal["active", "planned", "deprecated", "known-issue"] = "active"
    stage: int | None = None # 1..8
    anchor: str = ""         # "model#base-scores"
    related: tuple[str, ...] = ()
# default/min/max are read at render time from Model._meta.get_field(name) (never duplicated)
```

## B. User guide outline (/help/)

0. **Help home.** What the simulator is, in 3 sentences. Three cards: Quick start, Try the example, Understand the model. A stage map (1 to 8) with Implemented/Planned badges. A search box.
1. **Getting started.** 1.1 Create an account and a simulation. 1.2 A 5-minute quick start using the example preset. 1.3 The workflow at a glance (the same checklist shown on the manage page).
2. **How the real NRMP works.** 2.1 Participants: applicants, programs, positions. 2.2 Timeline: applications, signals, interview invitations, interviews, rank order lists, the matching algorithm, Match Day, SOAP. 2.3 Applicant-proposing deferred acceptance (Roth-Peranson), stability, why truthful ranking is safe for applicants. 2.4 What this simulator does and doesn't model.
3. **The simulation model**, with formulas. Each subsection has a plain-language summary, the formula, the parameters involved (auto-linked to the registry) and a "try this" note.
   3.1 Scores on a 0-1 scale: Beta(μ, σ) via α = μk, β = (1−μ)k, k = μ(1−μ)/σ² − 1; the feasibility limit σ < √(μ(1−μ)), enforced by the form; the live preview.
   3.2 Attribute (meta) scores: a ~ Beta(base, σ_meta); which keys each side gets.
   3.3 Preference weights: w = clip(N(1, σ_w), 0.01, 2) / Σ.
   3.4 True utility: U_ij = Σ_k w_ik · a_jk, and V_ji for programs.
   3.5 Observed scores and rating error: Û = U + ε, ε ~ N(0, σ_pre).
   3.6 Pre-interview rankings: rank 1 is best; how ties are handled.
   3.7 Applications (planned). 3.8 Interview invitations and acceptance (planned): ⌈m × capacity⌉ invitations per program; applicants accept up to their limit. 3.9 Interviews and re-rating with σ_post (planned). 3.10 Rank order lists: who is ranked and list length (planned). 3.11 Matching: deferred-acceptance pseudo-code (planned). 3.12 Iterations and seeds (planned).
4. **Using the app**, task-oriented. 4.1 Simulations list. 4.2 Manage a simulation: config sections, save, generate, and what each button changes or deletes. 4.3 Populations: generate vs upload; reading the applicant and program tables. 4.4 Interviews table, column by column. 4.5 Results and visualizations: how to read each chart (from CHART_HELP). 4.6 Exporting.
5. **Parameter reference**, generated from the registry: name, meaning, unit, range, default, typical, status, stage.
6. **CSV formats**, generated from CSV_SPECS: students, schools, interviews export; sample downloads; validation rules; common errors; round-trip notes.
7. **Worked example / tutorial.** "Does pre-interview noise hurt strong applicants?" Start from the preset, compute one applicant's utility by hand, change σ_pre, compare. The numbers are verified by tests/test_help_examples.py.
8. **Experiment recipes.** Tight vs loose market; homogeneous vs heterogeneous preferences; information noise; interview caps; links to IDEAS.md themes.
9. **FAQ and troubleshooting.** Why did my interviews disappear? Why does the form reject 2? Why isn't my SD the SD I get? Why do some programs have 0 positions? How big can a run be? Are my simulations public? How do I reproduce a run? Why is my uploaded CSV ranking everything equally?
10. **Glossary**, generated.
11. **About.** Assumptions and limitations, version and changelog, how to cite (CITATION.cff), contact and issues, privacy.
12. **Developer reference** (staff only, separate nav). Architecture, filtered auto-generated reference for models, the engine and the registry, endpoints, running locally, help-authoring guide.

Per-page panels (content/pages): simulations_list, simulation_form, simulation_manage, students_list, schools_list, interviews_list, and later results and visualizations. Each panel has the sections "What this page is", "Do this next", "Buttons and what they change", "Columns" and "Learn more".

## C. Corrected help text for every SimulationConfig field

Legend for the last column: *recommended* (current). ✗ means the current default fails its validator or is degenerate.

| Field | Label | Short help (under input) | Long help (popover / reference) | Unit / range | Default |
|---|---|---|---|---|---|
| number_of_applicants | Applicants | How many applicants (medical students) to generate. | Each applicant gets a base score, one attribute score per *School Meta Preference* and one preference weight per *Applicant Meta Preference*. Interview rows = Applicants × Programs (200×10 = 2,000; 10,000×1,000 = 10 M), so cost grows with the product. | count; 1-10,000; Applicants × Programs is capped at the interim limit (D4) | *200* (200) |
| number_of_schools | Programs | How many residency programs to generate. | Each program gets a base score, a capacity (positions) and one attribute score per *Applicant Meta Preference*. Market tightness = Applicants ÷ (Programs × capacity mean). | count; 1-1,000 | *10* (10) |
| applicant_score_mean | Applicant score mean | Average applicant base (overall strength) score on a 0-1 scale. | Base scores ~ Beta(μ, σ), with α = μk, β = (1−μ)k, k = μ(1−μ)/σ² − 1. The base score is the applicant's true overall strength and the centre of their attribute scores. Values at or beyond 0 or 1 are clamped to 0.001/0.999. | 0-1 score; 0.01-0.99 | *0.7* (0.7) |
| applicant_score_stddev | Applicant score SD | How spread out applicant base scores are (SD on the 0-1 scale). | Must be below √(μ(1−μ)) (0.458 at μ = 0.7), and the form rejects larger values. Before Phase 0 they were silently cut to 90% of that limit, giving a U-shaped distribution and a shifted mean. 0 gives every applicant exactly the mean. | SD; 0 ≤ σ < √(μ(1−μ)); typical 0.05-0.2 | *0.1* (2 ✗) |
| applicant_interview_limit | Max interviews per applicant | The most interviews an applicant can accept and attend. | **Planned (Stage 5-6).** Applicants accept invitations in order of their pre-interview ranking until they reach this limit; programs not interviewed with can't be ranked. Not used by the current engine. Should be ≤ number of programs. Real applicants often attend about 10-15. | interviews (integer); 0 to Programs | *5* (5); set step=1 |
| applicant_meta_preference | Program attributes applicants value | Program attributes applicants care about, e.g. program_size, reputation, location. | Each name creates (a) an attribute score for every program (School.score_meta) and (b) a preference weight for every applicant (Student.meta_preference). Applicant utility = Σ weight × program attribute. Names are normalised to lower_snake_case. After changing them, regenerate both populations. | list of identifiers; 1-10 items | *["program_size","reputation","location"]* (same) |
| applicant_meta_preference_stddev | Applicant preference diversity | How much applicants disagree about which program attributes matter. | Raw weight ~ N(1, σ), clamped to [0.01, 2.0], then normalised to sum to 1. σ = 0 gives identical preferences (everyone ranks programs the same way). Above ~0.6 most draws hit the clamps (σ = 3 leaves 74% of weights at exactly 0.01 or 2.0). | SD of raw weight; useful 0-0.6; max 1 | *0.3* (3 ✗) |
| applicant_meta_scores_stddev | Applicant attribute spread | How much an applicant's attribute scores vary around their base score. | For every *School Meta Preference* (e.g. board_scores, research), the applicant's attribute score ~ Beta(mean = base score, SD = σ). 0 makes all attributes equal the base score, so programs rank applicants purely by base score. The same Beta limit applies. | SD; typical 0.05-0.2; max 0.45 | *0.1* (10 ✗) |
| applicant_pre_interview_rating_error | Applicant pre-interview noise | How noisy applicants' view of programs is before interviewing. | observed = true utility + ε, ε ~ N(0, σ); σ = 0 means perfect information. Higher σ means pre-interview rankings (and, from Phase 3, applications) drift from true preferences. | SD on the utility scale (0-1); typical 0-0.2 | *0.1* (0.1) |
| applicant_post_interview_rating_error | Applicant post-interview noise | How noisy applicants' view of programs is after interviewing (usually smaller). | **Planned (Stage 6).** observed_post = U + ε, ε ~ N(0, σ_post), with σ_post ≤ σ_pre because interviews reveal information. Drives the applicant's final rank order list. Not used yet. | SD; 0 ≤ σ_post ≤ σ_pre | *0.02* (0.02) |
| school_score_mean | Program score mean | Average program base (overall quality/prestige) score on a 0-1 scale. | Program base scores ~ Beta(μ, σ), as for applicants, and are the centre of each program's attribute scores. The mean must be strictly between 0 and 1; the old default of 0 produced a realised mean of about 0.30. | 0-1; 0.01-0.99 | *0.5* (0 ✗) |
| school_score_stddev | Program score SD | How spread out program base scores are. | Same Beta feasibility limit, √(μ(1−μ)), as the applicant score SD; the form rejects larger values. | SD; typical 0.05-0.2; max 0.45 | *0.1* (2 ✗) |
| school_capacity_mean | Positions per program (mean) | Average number of residency positions per program. | Capacity ~ N(mean, SD), rounded and floored at 0. Total positions ≈ Programs × mean. With 200 applicants and 10 programs, 20 gives a balanced market (1.0 position per applicant) and 18 gives ~1.1 applicants per position. | positions; ≥ 1 (add MinValueValidator(1)) | *20* (20) |
| school_capacity_stddev | Positions per program (SD) | How much program sizes vary. | A large SD relative to the mean creates zero-capacity programs that can never match. N(20, 10) gives ≈ 2.6% of programs 0 positions; N(18, 4) gives effectively none. | positions; 0 ≤ SD ≤ mean/2 recommended | *4* (10) |
| school_interview_limit | Program interview limit (fraction of capacity; not used yet) | Not used yet: Phase 2 replaces it with *interviews per position*. | **Planned.** Until Phase 2.1 this field is a 0–0.99 fraction of capacity, which could never allow as many interviews as positions (0.1 × 20 = 2 interviews for 20 positions). Phase 2.1 replaces it with *interviews per position* (≥ 1, default about 10): each program invites up to ⌈ratio × capacity⌉ of the applicants who applied. Use the "Interviews per position" label only in the Phase 2.1 schema. | × capacity; recommended 1-20 (currently 0-0.99) | unchanged until it is redefined in Phase 2 (0.1 ✗) |
| school_meta_preference | Applicant attributes programs value | Applicant attributes programs care about, e.g. board_scores, research, honors. | Each name creates (a) an attribute score for every applicant (Student.score_meta) and (b) a preference weight for every program (School.meta_preference). Program utility = Σ weight × applicant attribute. Normalised to lower_snake_case. | list; 1-10 items | *["board_scores","research","honors"]* (same) |
| school_meta_preference_stddev | Program preference diversity | How much programs disagree about which applicant attributes matter. | Raw weight ~ N(1, σ), clamped to [0.01, 2.0], normalised to sum to 1. σ = 0 means every program ranks applicants by the same formula. | SD of raw weight; useful 0-0.6; max 1 | *0.3* (2 ✗, fails its own max 0.99) |
| school_meta_scores_stddev | Program attribute spread | How much a program's attribute scores vary around its base score. | For every *Applicant Meta Preference* (program_size, reputation, location), the program's attribute score ~ Beta(mean = base score, SD = σ). The same Beta limit applies. | SD; typical 0.05-0.2; max 0.45 | *0.1* (2 ✗, fails max 0.99) |
| school_pre_interview_rating_error | Program pre-interview noise | How noisy programs' view of applicants is from the application alone. | observed = V + ε, ε ~ N(0, σ); σ = 0 means perfect information. From Phase 3 it drives interview invitations. | SD on the utility scale; typical 0-0.2 | *0.1* (0.1) |
| school_post_interview_rating_error | Program post-interview noise | How noisy programs' view of applicants is after interviewing. | **Planned (Stage 6).** σ_post ≤ σ_pre; drives the program's final rank order list. Not used yet. | SD; ≤ σ_pre | *0.02* (0.02) |

Simulation fields:
- **name**: "A short name for this experiment."
- **description**: "Notes on what you are testing (optional)." Make it blank=True.
- **iterations**: "Planned: number of independent repeats with different random seeds; results will be aggregated. Not used yet." Range 1-100, default 1.
- **public**: "Planned: let others view this simulation read-only. Currently has no effect; only you can see it." Recommended default False.
- **status**: internal; hide it.
- **Proposed random_seed**: "Leave blank for random; set an integer to reproduce a run exactly."

## D. Corrected help text for other model fields

- **Student.score**: "Applicant's base (true overall) strength, 0-1; centre of their attribute scores."
- **Student.meta_stddev**: deprecated. It is never written and always 0; remove it.
- **Student.score_meta**: 'Applicant attribute scores (0-1) keyed by School Meta Preference names, e.g. {"board_scores": 0.72, "research": 0.55, "honors": 0.61}.'
- **Student.meta_stddev_preference**: "SD used when this applicant's preference weights were drawn (copied from config)."
- **Student.meta_preference**: 'Applicant preference weights (sum to 1) keyed by Applicant Meta Preference names, e.g. {"program_size": 0.31, "reputation": 0.45, "location": 0.24}.'
- **School.name**: "Program name."
- **School.capacity**: "Number of positions the program can fill (≥ 0)."
- **School.score**: "Program's base (true overall) quality, 0-1; centre of its attribute scores."
- **School.meta_stddev**: deprecated. It is unused, with default 1.0; remove it.
- **School.score_meta**: 'Program attribute scores (0-1) keyed by Applicant Meta Preference names, e.g. {"program_size": 0.4, "reputation": 0.8, "location": 0.6}.'
- **School.meta_stddev_preference**: "SD used when this program's weights were drawn."
- **School.meta_preference**: 'Program preference weights (sum to 1) keyed by School Meta Preference names, e.g. {"board_scores": 0.5, "research": 0.3, "honors": 0.2}.'
- **Interview.status**: "Stage reached for this pair: initialized → applied → invited → interviewed → ranked (currently always initialized)." Use TextChoices.
- **Interview.student_applied**: "True if the applicant applied to this program."
- **Interview.student_signal**: "Preference signal the applicant sent this program (0 = none). Not used yet."
- **Interview.student_accepted**: "True if the applicant accepted this program's interview invitation."
- **Interview.school_invited**: "True if the program invited this applicant to interview (requires an application)."
- **Interview.student_true_score_of_school**: "Applicant's noise-free utility for this program (Σ weight × program attribute). Written by the pre-interview step (from Phase 0.3)."
- **Interview.school_true_score_of_student**: "Program's noise-free utility for this applicant. Written by the pre-interview step (from Phase 0.3)."
- **Interview.student_pre_observed_score_of_school**: "Applicant's pre-interview (noisy) rating of this program."
- **Interview.school_pre_observed_score_of_student**: "Program's pre-interview (noisy) rating of this applicant, from the application."
- **Interview.students_pre_rank_of_school**: "Where this program falls in the applicant's pre-interview ordering (1 = favourite)."
- **Interview.schools_pre_rank_of_student**: "Where this applicant falls in the program's pre-interview ordering (1 = top applicant)."
- **Interview.student_post_observed_score_of_school**: "Applicant's post-interview rating of this program."
- **Interview.school_post_observed_score_of_student**: "Program's post-interview rating of this applicant."
- **Interview.students_post_rank_of_school**: "Program's position on the applicant's rank order list (1 = first choice)."
- **Interview.schools_post_rank_of_student**: "Applicant's position on the program's rank order list."
- **Match**: the docstring should read "One row per matched applicant-program pair produced by the matching algorithm." The rank fields: "Rank the applicant gave the matched program" and "Rank the program gave the matched applicant."

## E. Component markup

Field component:
```html
<fieldset class="fieldset">
  <legend class="fieldset-legend">{{ field.label }}{% if field.field.required %} <span aria-hidden="true">*</span>{% endif %} {% help_icon field.name %}</legend>
  {{ field }}  {# Django emits aria-describedby="{{ field.auto_id }}_helptext" and aria-invalid #}
  <p class="label whitespace-normal" id="{{ field.auto_id }}_helptext">{{ field.help_text }}{% if h.status == 'planned' %} <span class="badge badge-warning badge-xs">Not used yet · Stage {{ h.stage }}</span>{% endif %}</p>
  {% if field.errors %}<div id="{{ field.auto_id }}_error">{% for e in field.errors %}<p class="label whitespace-normal text-error">{{ e }}</p>{% endfor %}</div>{% endif %}
</fieldset>
```

Help popover:
```html
<details class="dropdown dropdown-end" x-data @keydown.escape.prevent="$el.open=false; $refs.s.focus()" @click.outside="$el.open=false">
  <summary x-ref="s" class="btn btn-ghost btn-circle btn-xs min-h-6 min-w-6" aria-label="Help: {{ h.label }}">?</summary>
  <div class="dropdown-content card card-sm bg-base-100 shadow-lg w-80 max-w-[90vw] z-30" role="note">
    <div class="card-body text-sm">{{ h.short }} {{ h.long_html }}
      {% if h.formula_tex %}<div class="math block">{{ h.formula_tex }}</div>{% endif %}
      <table class="table table-xs"><tr><th>Range</th><td>{{ min }}-{{ max }}</td></tr><tr><th>Default</th><td>{{ default }}</td></tr><tr><th>Typical</th><td>{{ h.typical }}</td></tr></table>
      <a class="link link-primary" href="{{ h.learn_more_url }}">Learn more →</a></div></div>
</details>
```

Page panel: a `<dialog id="help-panel" class="modal modal-end">` whose `modal-box` loads through HTMX with `hx-get` and `hx-trigger="click once"`.

## F. Suggested rollout (help dimension)

- **H0: quick fixes (≤1 day).** HELP-2 defaults and validators; HELP-5 restrict or rename the docs page; HELP-6 overflow and CSS; HELP-21 contact/account; home Quick Start copy (HELP-14); HELP-20 docstrings plus a codespell dictionary.
- **H1: field help (2-3 days).** HELP-8 registry and checks; HELP-1/HELP-9 field_row and popover (fixes the dangling ARIA); HELP-3 planned badges; HELP-4 corrected copy; HELP-17 error summary; HELP-7 action help and confirm text.
- **H2: guide (1-2 weeks).** HELP-10 /help/ with markdown and KaTeX; HELP-11 model page and executable examples; HELP-15 CSV reference and samples; HELP-18 glossary; HELP-12 page panels; HELP-16 column help; HELP-19 vocabulary; FAQ.
- **H3: guided experience (~1 week).** HELP-14 checklist, example preset and optional tour; HELP-13 distribution previews and market summary.
- **H4: ongoing.** HELP-24 CI gates (coverage, anchors, a11y, mobile width); HELP-22 README/docs; HELP-23 about, cite and seed; HELP-25 chart help, search, i18n.

### Corrections from verification
- Django 6.1 adds `<auto_id>_error` to `aria-describedby` whenever a field has errors (`django/forms/boundfield.py`), so the field component must render an element with that id. The markup above does.
- daisyUI 5's `.label` is `white-space: nowrap`, which is the root cause of the error text spilling into the neighbouring column. Add `whitespace-normal` to hint and error text.
- For the About page version, `importlib.metadata.version('nrmp-simulated')` raises `PackageNotFoundError`, because the project is a uv *virtual* project with no `[build-system]`. Use a `__version__` constant, read `pyproject.toml` with `tomllib`, or use the deploy's git SHA.
- Automated checks catch typos and missing entries, but not swapped wording (e.g. "score of student" on a `*_of_school` field). Those need targeted assertions or human review.
- A codespell project dictionary (scoreing→scoring, setp→step, preferacnes→preferences, stdsdev→stddev) catches all current typos, including the ones serialised into migrations `0001` and `0005`.
