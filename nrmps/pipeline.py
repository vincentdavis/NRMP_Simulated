"""The stage state machine (plan step 2.4): what each stage of a simulation shows and why.

Each stage's state comes from the draft parameters and the runs:

- done: the latest successful run computed this stage from exactly what the draft would use now;
- stale: something the stage depends on changed since (the reason names it), so running again changes the results;
- queued or running: a run is in progress;
- failed: the latest run failed at this stage (the error is shown);
- ready: nothing has run yet; blocked: the parameters are not valid;
- planned: the stage is not implemented yet.

"Done" is decided by comparing stage fingerprints (`runs.fingerprints`), so a stage whose inputs did not change stays
done after an unrelated edit: changing a noise parameter leaves the population done and makes only the
pre-interview stage stale.
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
    "queued": "Queued",
    "running": "Running",
    "failed": "Failed",
    "ready": "Ready",
    "blocked": "Blocked",
    "planned": "Planned",
}

# Readable names of the parameter groups in STAGE_INPUTS.
INPUT_TITLES = {
    "market": "market",
    "applicants": "applicant groups or attributes",
    "programs": "program quality, tiers or attributes",
    "prefs.weight_concentration": "weight concentration",
    "prefs": "preferences",
    "info": "information (noise)",
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


def _changes(draft: SimulationParams, run: SimulationRun, stage: str) -> list[str]:
    """Return what changed since `run` among the things `stage` depends on, in words."""
    changes = []
    if run.model_version != MODEL_VERSION:
        changes.append("the model version")
    if draft.run.seed is not None and draft.run.seed != run.seed:
        changes.append("the seed")
    now, then = stage_inputs(draft, stage), stage_inputs(run.get_params(), stage)
    changes.extend(INPUT_TITLES.get(path, path) for path in STAGE_INPUTS[stage] if now[path] != then[path])
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
    now_prints: dict[str, str] = {}
    if draft is not None and reference is not None:
        seed = draft.run.seed if draft.run.seed is not None else reference.seed
        now_prints = fingerprints(draft.with_seed(seed), seed, upload_sources(simulation.uploads_by_side()))

    states = []
    population_changed = False
    for stage in Stage:
        label = str(stage.label)
        if stage not in IMPLEMENTED_STAGES:
            states.append(StageState(stage.value, label, "planned", "Not implemented yet."))
        elif active is not None:
            states.append(
                StageState(stage.value, label, str(active.status), f"Run {active.number} is {active.status}.")
            )
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
            if stage == Stage.PRE_INTERVIEW and population_changed:
                changes.append("the population")
            population_changed = population_changed or stage == Stage.POPULATION
            reason = f"Changed since run {reference.number}: {', '.join(changes)}." if changes else "Changed."
            states.append(StageState(stage.value, label, "stale", reason))
    return states


def needs_run(states: list[StageState]) -> bool:
    """Return True if running now would change or produce results."""
    return any(state.state in {"stale", "ready", "failed"} for state in states)
