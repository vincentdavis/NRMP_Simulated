"""Preference signals (model_spec.md §7.2): which applications carry a signal, of which tier."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from nrmps.params import SimulationParams

from .applications import Applications
from .population import Population
from .rng import Stream, pair_uniforms, replicate_for, stream_generator

NO_SIGNAL = -1


@dataclass(frozen=True, eq=False)
class Signals:
    """The signal tier of every application (NO_SIGNAL = none) and which programs use signals."""

    tier: NDArray[np.int8]  # aligned with the applications; 0 = the first tier
    program_uses: NDArray[np.bool_]  # per program
    boost: NDArray[np.float64]  # per tier

    def boost_of(self, pairs: NDArray[np.int64], programs: NDArray[np.int32]) -> NDArray[np.float64]:
        """Return the screening boost of the given applications (0 without a signal or a program that ignores it)."""
        tier = self.tier[pairs]
        signalled = (tier != NO_SIGNAL) & self.program_uses[programs]
        if self.boost.size == 0:
            return np.zeros(pairs.shape[0])
        result: NDArray[np.float64] = np.where(signalled, self.boost[np.maximum(tier, 0)], 0.0)
        return result


def group_starts(sorted_keys: NDArray[np.int32]) -> NDArray[np.int64]:
    """Return, for each position of a sorted key array, the position where its key's run starts."""
    n = sorted_keys.shape[0]
    if n == 0:
        return np.zeros(0, dtype=np.int64)
    new = np.empty(n, dtype=np.bool_)
    new[0] = True
    new[1:] = sorted_keys[1:] != sorted_keys[:-1]
    starts = np.flatnonzero(new)
    result: NDArray[np.int64] = starts[np.cumsum(new) - 1]
    return result


def allocate_signals(
    params: SimulationParams, population: Population, applications: Applications, seed: int, replicate: int = 0
) -> Signals:
    """Give each applicant's signals to their applications in the order of `signals.allocation` (§7.2)."""
    config = params.signals
    m = population.n_programs
    rng = stream_generator(
        seed, Stream.SIGNALS, replicate_for(Stream.SIGNALS, replicate, params.run.resample_population)
    )
    program_uses = rng.random(m) < config.program_use_share
    counts = np.array([tier.count for tier in config.tiers], dtype=np.int64)
    boost = np.array([tier.boost for tier in config.tiers], dtype=np.float64)
    tier = np.full(applications.size, NO_SIGNAL, dtype=np.int8)
    if counts.size == 0 or applications.size == 0:
        return Signals(tier, program_uses, boost)
    i, j = applications.i, applications.j
    if config.allocation == "random":
        key = pair_uniforms(seed, Stream.SIGNALS, replicate, i, j)
        order = np.lexsort((key, i))
    elif config.allocation == "realistic":
        band = params.apps.target_band
        reach = applications.prestige[j] > applications.competitiveness[i] + band
        order = np.lexsort((applications.pre_rank, reach, i))
    else:
        order = np.lexsort((applications.pre_rank, i))
    sorted_i = i[order]
    position = np.arange(order.shape[0]) - group_starts(sorted_i)
    limits = {group.name: group.n_signals for group in params.applicants.groups}
    group_limit = np.array(
        [
            limits.get(name) if limits.get(name) is not None else counts.sum()
            for name in population.applicants.group_names
        ],
        dtype=np.int64,
    )
    total = np.minimum(counts.sum(), group_limit[population.applicants.group[sorted_i]])
    bounds = np.cumsum(counts)
    sorted_tier = np.searchsorted(bounds, position, side="right").astype(np.int8)
    sorted_tier[position >= total] = NO_SIGNAL
    tier[order] = sorted_tier
    return Signals(tier, program_uses, boost)
