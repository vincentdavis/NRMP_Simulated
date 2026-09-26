"""The stage state machine (plan step 2.4): what each stage of a simulation shows and why.

Each stage's state comes from the draft parameters and the runs:

- done: the latest successful run computed this stage from exactly what the draft would use now;
- stale: something the stage depends on changed since (the reason names it), so running again changes the results;
- finished, running or waiting: a run is in progress and has finished this stage, is computing it, or has not
  reached it yet (a queued run has its population: it is built when the run starts);
- failed: the latest run failed at this stage (the error is shown);
- ready: nothing has run yet; blocked: the parameters are not valid;
- planned: the stage is not implemented yet.

"Done" is decided by comparing stage fingerprints (`runs.fingerprints`), so a stage whose inputs did not change stays
done after an unrelated edit: changing a noise parameter leaves the population done and makes the pre-interview stage
and every later stage stale. A stale stage names what changed among its own inputs, and the stage before it when that
one is stale too.
"""

from dataclasses import dataclass

from pydantic import ValidationError

from .engine import MODEL_VERSION
from .models import IMPLEMENTED_STAGES, Simulation, SimulationRun, Stage
from .params import STAGE_INPUTS, SimulationParams, stage_inputs
from .runs import fingerprints, upload_sources

STATE_LABELS = {
    "done": "Done",
    "stale": "Out of date",
    "finished": "Finished",
    "running": "Running",
    "waiting": "Waiting",
    "failed": "Failed",
    "ready": "Ready",
    "blocked": "Blocked",
    "planned": "Planned",
}

# Readable names of the parameters in STAGE_INPUTS.
INPUT_TITLES = {
    "market": "market",
    "applicants.groups[name,share,strength_mean,strength_sd]": "applicant groups",
    "applicants.attributes": "applicant attributes",
    "programs": "program quality, tiers or attributes",
    "prefs.weight_concentration": "weight concentration",
    "prefs": "preferences",
    "info.applicant_pre_noise_sd": "information (noise)",
    "info.program_pre_noise_sd": "information (noise)",
    "info.visibility_heteroskedasticity": "information (noise)",
    "info.halo_share": "information (noise)",
    "apps": "applications",
    "applicants.groups[name,applications_mean]": "group application means",
    "signals": "signals",
    "applicants.groups[name,n_signals]": "group signal limits",
    "invites": "invitations",
    "interview.applicant_cap": "the interview cap",
    "interview.acceptance_order": "the acceptance order",
    "info.interview_informativeness": "interview informativeness",
    "info.fit_shock_sd": "the fit shock",
    "rol": "rank order lists",
    "signals.use_in_ranking": "signals in ranking",
    "match": "the match settings",
}

# The run page tab that shows each stage's results (a URL name in nrmps/urls.py).
RESULT_TABS = {
    Stage.POPULATION: "nrmps:run_population",
    Stage.PRE_INTERVIEW: "nrmps:run_pre_interview",
    Stage.APPLICATIONS: "nrmps:run_applications",
    Stage.SIGNALS: "nrmps:run_applications",
    Stage.INVITATIONS: "nrmps:run_applications",
    Stage.INTERVIEWS: "nrmps:run_applications",
    Stage.RANK_LISTS: "nrmps:run_match",
    Stage.MATCH: "nrmps:run_match",
}

# How a stale stage names a change in the stage before it.
UPSTREAM_TITLES = {
    Stage.POPULATION: "the population",
    Stage.PRE_INTERVIEW: "the pre-interview views",
    Stage.APPLICATIONS: "the applications",
    Stage.SIGNALS: "the signals",
    Stage.INVITATIONS: "the invitations",
    Stage.INTERVIEWS: "the interviews",
    Stage.RANK_LISTS: "the rank order lists",
}


@dataclass(frozen=True)
class StageState:
    """What the stepper shows for one stage."""

    key: str
    label: str
    state: str
    reason: str = ""

    @property
    def state_label(self) -> str:
        """Return the state as text."""
        return STATE_LABELS[self.state]

    @property
    def implemented(self) -> bool:
        """Return True if the engine implements this stage."""
        return self.state != "planned"

    @property
    def results_url_name(self) -> str:
        """Return the URL name of the run page tab with this stage's results."""
        return RESULT_TABS[Stage(self.key)]

    @property
    def has_results(self) -> bool:
        """Return True if the latest successful run has results for this stage (up to date or not)."""
        return self.state in {"done", "stale"}


def _changes(draft: SimulationParams, run: SimulationRun, stage: str) -> list[str]:
    """Return what changed since `run` among the things `stage` depends on, in words."""
    changes = []
    if run.model_version != MODEL_VERSION:
        changes.append("the model version")
    if draft.run.seed is not None and draft.run.seed != run.seed:
        changes.append("the seed")
    now, then = stage_inputs(draft, stage), stage_inputs(run.get_params(), stage)
    for path in STAGE_INPUTS[stage]:
        title = INPUT_TITLES.get(path, path)
        if now[path] != then[path] and title not in changes:
            changes.append(title)
    return changes


def get_pipeline(simulation: Simulation) -> list[StageState]:
    """Return the state of every stage, implemented or planned, in order."""
    try:
        draft: SimulationParams | None = simulation.get_params()
    except ValidationError:
        draft = None
    active = simulation.active_run()
    latest = simulation.latest_run()
    reference = simulation.latest_run(succeeded=True)
    failed = latest if latest is not None and latest.status == SimulationRun.Status.FAILED else None
    failed_stage = None
    if failed is not None:
        failed_stage = failed.stages.filter(status=SimulationRun.Status.FAILED).values_list("stage", flat=True).first()
    active_stages: set[str] = set()
    in_progress = False
    if active is not None:
        active_stages = set(active.stages.values_list("stage", flat=True))
        in_progress = active.status == SimulationRun.Status.RUNNING
    now_prints: dict[str, str] = {}
    if draft is not None and reference is not None:
        seed = draft.run.seed if draft.run.seed is not None else reference.seed
        now_prints = fingerprints(draft.with_seed(seed), seed, upload_sources(simulation.uploads_by_side()))

    states: list[StageState] = []
    for stage in Stage:
        upstream_stale = bool(states) and states[-1].state == "stale"
        label = str(stage.label)
        if stage not in IMPLEMENTED_STAGES:
            states.append(StageState(stage.value, label, "planned", "Not implemented yet."))
        elif active is not None:
            if stage.value in active_stages:
                states.append(StageState(stage.value, label, "finished", f"Finished in run {active.number}."))
            elif in_progress:
                states.append(StageState(stage.value, label, "running", f"Run {active.number} is computing it."))
                in_progress = False
            else:
                status = active.get_status_display().lower()
                states.append(StageState(stage.value, label, "waiting", f"Run {active.number} is {status}."))
        elif failed is not None and failed_stage == stage.value:
            states.append(StageState(stage.value, label, "failed", f"Run {failed.number} failed: {failed.error}"))
        elif draft is None:
            states.append(StageState(stage.value, label, "blocked", "The saved parameters are not valid."))
        elif reference is None:
            states.append(StageState(stage.value, label, "ready", "Not run yet."))
        elif reference.fingerprints.get(stage.value) == now_prints.get(stage.value):
            states.append(StageState(stage.value, label, "done", f"Up to date (run {reference.number})."))
        else:
            changes = _changes(draft, reference, stage.value)
            if stage == Stage.POPULATION and not changes:
                changes.append("the uploaded populations")
            if upstream_stale:
                changes.append(UPSTREAM_TITLES[Stage(states[-1].key)])
            reason = f"Changed since run {reference.number}: {', '.join(changes)}." if changes else "Changed."
            states.append(StageState(stage.value, label, "stale", reason))
    return states


def needs_run(states: list[StageState]) -> bool:
    """Return True if running now would change or produce results."""
    return any(state.state in {"stale", "ready", "failed"} for state in states)


def pipeline_summary(states: list[StageState]) -> tuple[str, str]:
    """Return one word for a simulation's state, with a badge colour: for lists of simulations."""
    found = {state.state for state in states}
    if found & {"finished", "running", "waiting"}:
        return "Running", "badge-info"
    if "failed" in found:
        return "Failed", "badge-error"
    if "blocked" in found:
        return "Invalid parameters", "badge-error"
    if found <= {"done", "planned"}:
        return "Up to date", "badge-success"
    if found <= {"ready", "planned"}:
        return "Not run yet", "badge-ghost"
    return "Out of date", "badge-warning"
