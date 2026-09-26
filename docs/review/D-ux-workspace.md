# Appendix D: UX, information architecture and workspace

These are the UI/UX reviewer's deliverables, with the verifiers' corrections applied. The phasing in §E is the reviewer's; the master plan in [PROJECT_REVIEW.md §9](../PROJECT_REVIEW.md#9-phased-implementation-plan) schedules the same work across Phases 0, 1, 2 (2.4, 2.5), 4 and 5 (5.3). Screenshots of the current UI are in `img/`.

## A. Proposed page list (new IA)

| URL | Page | Notes |
|---|---|---|
| `/` | Landing | Value proposition, 7-step overview (`steps`), **Try a demo** (preset + run all), recent simulations when logged in |
| `/simulations/` | My simulations | Stage badge, market size, headline KPI, ⋯ menu (Open/Duplicate/Compare/Delete), empty state with preset cards |
| `/simulations/new/` | New simulation | Name + preset cards + optional Advanced. Creates Simulation **and** SimulationConfig, then goes to Setup |
| `/simulations/<pk>/` | Workspace (redirects to current step) | Shared `workspace_base.html` |
| `…/setup/` | 1 Setup | Fieldsets, sliders+numbers, presets, live market summary, "?" help |
| `…/population/` | 2 Population | Tabs Students / Schools: stats, histograms, generate/upload (validated preview modal), table |
| `…/applications/` | 3 Applications | Pre-interview ratings and ranks, applications/signals, true-vs-observed scatter |
| `…/interviews/` | 4 Interviews | Invitations, interviews held, per-school load, post-interview update |
| `…/rank-lists/` | 5 Rank lists | ROL length distribution, per-entity lists |
| `…/match/` | 6 Match | Run deferred acceptance (job), unmatched lists |
| `…/results/` | 7 Results | KPI stats, chart grid, network, what-if sliders |
| `…/runs/` | Runs & compare | Job history, iterations, overlay 2–4 runs |
| `…/students/<id>/`, `…/schools/<id>/` | Detail drill-down | Attributes, ranked lists pre/post, interviews, match |
| `/help/` (+ `#step-*`, `#param-*`) | Help centre | Guide, concepts, glossary from `help_content.py`, CSV templates, FAQ |
| `/help/reference/` | Developer model reference | Current auto-docs, staff-only or without User |
| `/account/`, `/account/password/`, `/password-reset/…` | Account | Profile form, password change/reset, theme, delete account |
| `/contact/`, `/privacy/`, `/terms/`, 404/500 | Static | Real content |

## B. Workspace wireframe (desktop ≥1024px)

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│ [logo] NRMP Simulations        Simulations   Help                 (☾)  demo ▾        │  navbar (menu-active on current)
├──────────────────────────────────────────────────────────────────────────────────────┤
│ Simulations › Demo Match 2026                                                         │  breadcrumbs
│ Demo Match 2026  [badge: Interviews ▸ in progress]   120 applicants × 8 programs      │
│                         [▶ Next: Rank lists]  [⏩ Run all remaining]  [Duplicate] [⋯] │  ⋯ = Edit details / Export / Danger zone
│ ┌──────────────────────────────────────────────────────────────────────────────────┐ │
│ │ (✓)Setup ─ (✓)Population ─ (✓)Applications ─ (●)Interviews ─ ( )Rank lists ─     │ │  steps steps-horizontal (clickable,
│ │ ( )Match ─ ( )Results                        ⚠ Setup changed after Population    │ │   step-primary / step-warning = stale)
│ └──────────────────────────────────────────────────────────────────────────────────┘ │
│ ┌ job bar (only while running) ────────────────────────────────────────────────────┐ │
│ │ Computing pre-interview scores…  [██████████░░░░░░░ 62%]  step 2/3   [Cancel]    │ │  progress + hx-trigger="every 1s"
│ └──────────────────────────────────────────────────────────────────────────────────┘ │
│ ▸ What happens in this step? (?)                                                     │  collapse → /help/#step-interviews
│ ┌stats──────────┬───────────────┬────────────────┬─────────────────┐                  │
│ │ Invited 412   │ Interviewed   │ Avg / applicant│ Avg / position  │                  │  daisyUI stats
│ │  of 960 pairs │    388        │    3.2 (?)     │    4.0 (?)      │                  │
│ └───────────────┴───────────────┴────────────────┴─────────────────┘                  │
│ ┌ chart card ─────────────────────┐ ┌ chart card ─────────────────────┐               │
│ │ Interviews per applicant  (?) ⤓ │ │ True vs observed score  (?)  ⤓ │               │
│ │   ▁▃▇█▅▂                         │ │   · ·· ···  r=0.81             │               │
│ └─────────────────────────────────┘ └─────────────────────────────────┘               │
│ Filters: [Student ▾] [School ▾] [Status ▾] [Rank 1 ━━●━━ 20]  Showing 1–100 of 960    │  hx-get, hx-push-url, delay:300ms
│ ┌table table-pin-rows table-zebra───────────────────────────────────────────────────┐ │
│ │ Student ▲ │ School │ Status  │ True │ Obs. │ Δ    │ Stu rank │ Sch rank │         │ │  names link to detail pages
│ │ Student 1 │ Sch 3  │[invited]│0.612 │0.598 │-0.014│    1     │    7     │         │ │  3-dp numbers, badges
│ └───────────────────────────────────────────────────────────────────────────────────┘ │
│                      « 1 2 3 … 10 »                                                   │
└──────────────────────────────────────────────────────────────────────────────────────┘
  toast toast-top toast-end  → "✓ Created 300 students" / "✕ Upload failed: row 4 score 'abc'"
  <dialog class="modal">     → confirm destructive actions with counts; CSV preview/validation
```

Mobile (390px): the stepper becomes a horizontally scrollable `steps` row with the current step scrolled into view. The primary action is a sticky bottom bar (`dock`-style: Next / Run all). Stats show as 2×2, charts stack, tables show key columns only (`hidden md:table-cell`), and the ⋯ menu holds secondary actions.

## C. Setup tab wireframe

```
Preset: [ Balanced market ▾ ] [Reset]     ● Unsaved changes      [Save setup]
┌ fieldset: Market size ─────────────────┐ ┌ Market summary (live) ───────────┐
│ Applicants (?)   [ 300 ] ━━━━●━━━━━━    │ │ Positions 450  · 1.50 / applicant│
│ Programs (?)     [  30 ] ━━●━━━━━━━━    │ │ Max interviews / position  12    │
└────────────────────────────────────────┘ │ Applicant score  ▁▂▅█▅▂▁ (beta)  │
┌ fieldset: Applicant pool ──────────────┐ └──────────────────────────────────┘
│ Score mean (?) [0.60] ━━━━━━●━━  0–0.99│
│ Score spread (?) [0.10] ━●━━━━━  hint  │   (?) = popover button: short text,
└────────────────────────────────────────┘        range, typical value, "Learn more →"
▸ Programs & capacity   ▸ Preferences & attributes   ▸ Information noise
▸ Interview limits      ▸ Advanced: randomness (seed, iterations)
```

## D. daisyUI 5 component mapping (replace the dead v4 classes)

| Need | Component / class |
|---|---|
| Field wrapper | `fieldset` + `fieldset-legend` + `label` (hint) + `validator`/`validator-hint`, `input-error` |
| Stage | `steps`, `step step-primary`, `step-warning` (stale), `data-content="✓"` |
| Workspace tabs | `tabs tabs-border` / `tab tab-active` (links, not JS tabs) |
| KPIs | `stats`, `stat`, `stat-title`, `stat-value`, `stat-desc` |
| Help | native `popover` + `card`, `tooltip` + `tooltip-content` (desktop only), `collapse collapse-arrow` |
| Feedback | `toast toast-top toast-end` + `alert alert-success/error`, `loading loading-spinner`, `progress` |
| Confirm / preview | `modal` via `<dialog>`, `modal-box`, `modal-action` |
| Sliders | `range range-xs range-primary` paired with a number `input` (Alpine x-model) |
| Status | `badge badge-soft badge-info/success/warning` |
| Tables | `table table-zebra table-sm table-pin-rows table-pin-cols`, `row-hover` (not `hover`) |
| Navigation | `breadcrumbs`, `menu-active`, `drawer` (help TOC / mobile nav), `dropdown` (⋯ menu) |
| Theme | `theme-controller` + `swap` |

## E. Suggested UX phasing (for the lead's plan)

- **Phase 0 — stop the bleeding (S, ~2–3 days):** UX-1 defaults and config-on-create; UX-10 XSS; UX-4 atomic, validated upload; UX-9 overflow fixes; UX-15 login error and password-change route; UX-8 class migration via `_field.html`; UX-13 number formatting; UX-16 URL tags and nav state.
- **Phase 1 — feedback and flow (M, ~1 week):** UX-2 toasts, indicators, error handler; UX-20 confirm modal; UX-5 HX-Trigger refresh and stale badges; UX-6 pipeline service, stepper, gated buttons; UX-11 field help from `help_content.py`; UX-19 accessibility pass (with axe in Playwright).
- **Phase 2 — workspace (L, ~2 weeks):** UX-7 tabbed workspace and detail pages; UX-3 SimulationRun/job + `django.tasks` with the `django-tasks-db` worker (since django-tasks 0.12 the database backend lives in the separate `django-tasks-db` package) + progress + Run all; UX-14 filters and pagination; UX-21 presets and sliders; UX-18 form cleanup; UX-26 list and duplicate.
- **Phase 3 — insight (L–XL):** UX-22 results dashboard, network, what-if sliders and compare; UX-12 help centre; UX-17 landing and demo; UX-23 dark mode; UX-24/25 polish.

## F. Snippets that matter

HTMX feedback pattern (base.html):
```html
<div id="toasts" class="toast toast-top toast-end z-50" aria-live="polite">
  {% for m in messages %}<div class="alert alert-{{ m.tags }}">{{ m }}</div>{% endfor %}
</div>
<script>
  document.body.addEventListener('toast', e => showToast(e.detail.level, e.detail.text));
  document.body.addEventListener('htmx:responseError', e => showToast('error', `Server error ${e.detail.xhr.status} — nothing was changed`));
</script>
```
Button pattern: `<button hx-post="…" hx-disabled-elt="this" hx-indicator="find .loading" class="btn btn-primary">Generate<span class="loading loading-spinner loading-xs htmx-indicator"></span></button>`. The view returns `trigger_client_event(resp, "simulation-changed")` plus a `toast` event, and panels listen with `hx-trigger="simulation-changed from:body"`.

Also from the verifiers:
- The dead daisyUI 4 classes predate the dependency bump. daisyUI 5.1.12 has been locked since commit `6623367`.
- django-htmx 1.29's `{% htmx_script %}` can replace the hand-vendored htmx and adds the DEBUG error display.
- The review's evidence scripts (dead-class scanner, overflow probes, contrast and XSS checks) are not committed. Port the dead-class scanner and the 390 px overflow check into CI (Phase 1.4).
