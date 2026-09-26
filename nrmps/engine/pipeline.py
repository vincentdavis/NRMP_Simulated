"""A run of the model: every stage from the population to the match, with the diagnostics (model_spec.md §3-10).

The population, true utilities, observations and ranks (§3-6, §8) come first, then applications, signals,
invitations, interviews, rank order lists and the match (§7-8).

Pair-level values are never held for the whole market: each side is walked in blocks of about `block_pairs` pairs
(all targets of a few agents at a time), and only per-agent results, running sums and the applications (a sparse set
of pairs) are kept. Every pair-level value is recomputable later for any agent (`agent_view`), which is how the
drill-down pages show them.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from nrmps.params import SimulationParams

from . import metrics
from .applications import ApplicationChooser, Applications
from .interviews import Interviews, interview
from .invitations import Invitations, invite
from .match import MatchResult, build_lists, run_match
from .outcomes import outcome_metrics
from .population import Population, generate_population, validate_population
from .rank import rank_rows
from .rng import Stream, check_seed, pair_uniforms
from .rol import RankLists, rank_lists
from .signals import Signals, allocate_signals
from .utility import MarketModel, Observation, SideModel, build_market

F64 = NDArray[np.float64]
I32 = NDArray[np.int32]
Indices = NDArray[np.int64]

DEFAULT_BLOCK_PAIRS = 1_000_000
Progress = Callable[[int, int], None]
# Receives each block of one side: (agents, true, observed, true ranks, observed ranks).
BlockHook = Callable[[Indices, F64, F64, I32, I32], None]
# Receives each finished stage: (stage name, seconds, counts).
StageReport = Callable[[str, float, dict[str, int]], None]


@dataclass(frozen=True, eq=False)
class SideResult:
    """Per-agent results of one side before interviews."""

    first_choice: NDArray[np.int64]  # target index each agent ranks first on observed scores
    fidelity: F64  # Spearman correlation of each agent's true and observed rankings (NaN if undefined)
    popularity: NDArray[np.int64]  # per target: how many agents rank it first


@dataclass(frozen=True, eq=False)
class PreInterviewResult:
    """What a pre-interview run produces: the population, per-agent results and the diagnostics."""

    population: Population
    applicants: SideResult  # applicants ranking programs
    programs: SideResult  # programs ranking applicants
    metrics: dict[str, Any]


@dataclass(frozen=True, eq=False)
class AgentView:
    """One agent's row: true utilities, observed scores and both rankings over every target."""

    true: F64
    observed: F64
    true_rank: I32
    observed_rank: I32


def blocks(n: int, size: int) -> list[Indices]:
    """Split range(n) into consecutive index blocks of at most `size`."""
    size = max(1, size)
    return [np.arange(start, min(start + size, n), dtype=np.int64) for start in range(0, n, size)]


def _tie_keys(side: SideModel, agents: Indices, targets: Indices, replicate: int) -> Callable[[Indices], F64]:
    stream = Stream.TIE_A if side.agents_are_applicants else Stream.TIE_P

    def keys(rows: Indices) -> F64:
        i, j = side.pair_counters(agents[rows], targets)
        return pair_uniforms(side.seed, stream, replicate, i, j)

    return keys


def side_block(side: SideModel, view: Observation, agents: Indices, replicate: int) -> tuple[F64, F64, I32, I32]:
    """Return (true, observed, true ranks, observed ranks) for a block of agents over all targets."""
    targets = np.arange(side.n_targets, dtype=np.int64)
    true = side.utilities(agents, targets)
    observed = view.observe(true, agents, targets)
    keys = _tie_keys(side, agents, targets, replicate)
    return true, observed, rank_rows(true, keys), rank_rows(observed, keys)


def _run_side(
    side: SideModel,
    view: Observation,
    replicate: int,
    block_pairs: int,
    progress: Callable[[int], None],
    hook: BlockHook | None = None,
) -> tuple[SideResult, metrics.SideAccumulator]:
    accumulator = metrics.SideAccumulator(side.n_agents, side.n_targets)
    for agents in blocks(side.n_agents, block_pairs // max(1, side.n_targets)):
        true, observed, true_ranks, observed_ranks = side_block(side, view, agents, replicate)
        accumulator.add(agents, true, observed, true_ranks, observed_ranks)
        if hook is not None:
            hook(agents, true, observed, true_ranks, observed_ranks)
        progress(agents.size * side.n_targets)
    result = SideResult(
        first_choice=accumulator.first_choice.copy(),
        fidelity=accumulator.fidelity.copy(),
        popularity=np.bincount(accumulator.first_choice, minlength=side.n_targets).astype(np.int64),
    )
    return result, accumulator


def run_pre_interview(
    params: SimulationParams,
    seed: int,
    *,
    replicate: int = 0,
    population: Population | None = None,
    block_pairs: int = DEFAULT_BLOCK_PAIRS,
    progress: Progress | None = None,
    model: MarketModel | None = None,
    applicant_hook: BlockHook | None = None,
) -> PreInterviewResult:
    """Run the population and pre-interview stages for (params, seed, replicate).

    `population` replaces the generated one (for uploads or reuse); it must fit the parameters. `progress(done,
    total)` is called after every block, in pairs (each side counts once). `applicant_hook` sees every block of the
    applicants' rows (the applications stage chooses from them).
    """
    seed = check_seed(seed)
    if population is None:
        population = generate_population(params, seed, replicate)
    else:
        validate_population(population, params)
    if model is None:
        model = build_market(params, population, seed, replicate)
    pairs = population.n_applicants * population.n_programs
    total = 2 * pairs
    done = 0

    def advance(count: int) -> None:
        nonlocal done
        done += count
        if progress is not None:
            progress(done, total)

    applicants, applicant_acc = _run_side(
        model.applicants, model.applicant_view, replicate, block_pairs, advance, applicant_hook
    )
    programs, program_acc = _run_side(model.programs, model.program_view, replicate, block_pairs, advance)
    result_metrics = {
        "market": metrics.market_metrics(params, population),
        "generation": metrics.generation_metrics(params, population, model),
        "applicants": applicant_acc.result(model.applicant_view) | metrics.side_summary(model.applicants),
        "programs": program_acc.result(model.program_view) | metrics.side_summary(model.programs),
        "histograms": metrics.histograms(population, applicants.fidelity, programs.fidelity),
    }
    return PreInterviewResult(population, applicants, programs, result_metrics)


def agent_view(model: MarketModel, agent: int, *, applicant: bool, replicate: int = 0) -> AgentView:
    """Recompute one agent's row (an applicant over all programs, or a program over all applicants)."""
    side, view = (model.applicants, model.applicant_view) if applicant else (model.programs, model.program_view)
    agents = np.array([agent], dtype=np.int64)
    true, observed, true_ranks, observed_ranks = side_block(side, view, agents, replicate)
    return AgentView(true[0], observed[0], true_ranks[0], observed_ranks[0])


@dataclass(frozen=True, eq=False)
class PipelineResult:
    """Everything a run produces, from the population to the match, with the diagnostics."""

    pre: PreInterviewResult
    applications: Applications
    signals: Signals
    invitations: Invitations
    interviews: Interviews
    lists: RankLists
    match: MatchResult
    metrics: dict[str, Any]

    @property
    def population(self) -> Population:
        """Return the population."""
        return self.pre.population


def run_pipeline(
    params: SimulationParams,
    seed: int,
    *,
    replicate: int = 0,
    population: Population | None = None,
    block_pairs: int = DEFAULT_BLOCK_PAIRS,
    progress: Progress | None = None,
    on_stage: StageReport | None = None,
) -> PipelineResult:
    """Run every stage for (params, seed, replicate): the pre-interview pass, then applications to the match.

    `on_stage(name, seconds, counts)` is called as each stage finishes.
    """
    seed = check_seed(seed)
    if population is None:
        population = generate_population(params, seed, replicate)
    else:
        validate_population(population, params)
    model = build_market(params, population, seed, replicate)
    chooser = ApplicationChooser(params, model, population, seed, replicate)
    clock = time.perf_counter()

    def report(stage: str, counts: dict[str, int]) -> None:
        nonlocal clock
        now = time.perf_counter()
        if on_stage is not None:
            on_stage(stage, now - clock, counts)
        clock = now

    pre = run_pre_interview(
        params,
        seed,
        replicate=replicate,
        population=population,
        block_pairs=block_pairs,
        progress=progress,
        model=model,
        applicant_hook=lambda agents, _true, observed, _true_ranks, observed_ranks: chooser.choose(
            agents, observed, observed_ranks
        ),
    )
    report("pre_interview", {"pairs": population.n_applicants * population.n_programs})
    applications = chooser.result()
    report("applications", {"applications": applications.size})
    signals = allocate_signals(params, population, applications, seed, replicate)
    report("signals", {"signals": int((signals.tier >= 0).sum())})
    invitations = invite(params, population, model, applications, signals, seed, replicate)
    report(
        "invitations",
        {"invitations": int((invitations.wave > 0).sum()), "interviews": int(invitations.accepted.sum())},
    )
    interviews = interview(params, model, applications, invitations, seed, replicate)
    report("interviews", {"interviews": int(invitations.accepted.sum())})
    lists = rank_lists(params, applications, signals, interviews, seed, replicate)
    report(
        "rank_lists",
        {
            "applicant_entries": int((lists.applicant_rank > 0).sum()),
            "program_entries": int((lists.program_rank > 0).sum()),
        },
    )
    match_lists = build_lists(applications, lists, population.programs.capacity)
    match = run_match(params.match.algorithm, match_lists, params.match.compare_both)
    outcomes = outcome_metrics(population, applications, signals, invitations, interviews, lists, match_lists, match)
    report("match", {"matched": int((match.program >= 0).sum()), "blocking_pairs": match.blocking_pairs})
    result_metrics = pre.metrics | {"outcomes": outcomes}
    return PipelineResult(pre, applications, signals, invitations, interviews, lists, match, result_metrics)
