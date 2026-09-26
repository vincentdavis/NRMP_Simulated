"""The pre-interview run: population, true utilities, observations, ranks and diagnostics (model_spec.md §3-6, §8).

Pair-level values are never held for the whole market: each side is walked in blocks of about `block_pairs` pairs
(all targets of a few agents at a time), and only per-agent results and running sums are kept. Every pair-level
value is recomputable later for any agent (`agent_view`), which is how the drill-down pages show them.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from nrmps.params import SimulationParams

from . import metrics
from .population import Population, generate_population, validate_population
from .rank import rank_rows
from .rng import Stream, check_seed, pair_uniforms
from .utility import MarketModel, Observation, SideModel, build_market

F64 = NDArray[np.float64]
I32 = NDArray[np.int32]
Indices = NDArray[np.int64]

DEFAULT_BLOCK_PAIRS = 1_000_000
Progress = Callable[[int, int], None]


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
) -> tuple[SideResult, metrics.SideAccumulator]:
    accumulator = metrics.SideAccumulator(side.n_agents, side.n_targets)
    for agents in blocks(side.n_agents, block_pairs // max(1, side.n_targets)):
        true, observed, true_ranks, observed_ranks = side_block(side, view, agents, replicate)
        accumulator.add(agents, true, observed, true_ranks, observed_ranks)
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
) -> PreInterviewResult:
    """Run the population and pre-interview stages for (params, seed, replicate).

    `population` replaces the generated one (for uploads or reuse); it must fit the parameters. `progress(done,
    total)` is called after every block, in pairs (each side counts once).
    """
    seed = check_seed(seed)
    if population is None:
        population = generate_population(params, seed, replicate)
    else:
        validate_population(population, params)
    model = build_market(params, population, seed, replicate)
    pairs = population.n_applicants * population.n_programs
    total = 2 * pairs
    done = 0

    def advance(count: int) -> None:
        nonlocal done
        done += count
        if progress is not None:
            progress(done, total)

    applicants, applicant_acc = _run_side(model.applicants, model.applicant_view, replicate, block_pairs, advance)
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
