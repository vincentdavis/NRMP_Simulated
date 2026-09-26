"""Applications (model_spec.md §7.1): how many programs each applicant applies to, and which.

Applicants choose from their strict pre-interview ranks of every program, so the choice is made while the
pre-interview pass walks the applicants in blocks (`ApplicationChooser.choose`); only the chosen pairs are kept.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import NDArray

from nrmps.params import SimulationParams

from .numeric import quantiles
from .population import Population
from .rng import Stream, pair_uniforms, replicate_for, stream_generator
from .utility import MarketModel

F64 = NDArray[np.float64]
I32 = NDArray[np.int32]
Indices = NDArray[np.int64]

TARGET, REACH, SAFETY = 0, 1, 2


@dataclass(frozen=True, eq=False)
class Applications:
    """The applied pairs, sorted by applicant then program, with what the applicant saw when choosing."""

    i: I32  # applicant index of each pair
    j: I32  # program index of each pair
    pre_rank: I32  # the applicant's pre-interview rank of the program
    observed: F64  # the applicant's pre-interview view of the program (u_hat)
    category: NDArray[np.int8]  # TARGET, REACH or SAFETY relative to the applicant's self-assessment
    count: I32  # per applicant: the number of applications k_i
    competitiveness: F64  # per applicant: self-assessed standing c_i
    standing: F64  # per applicant: quantile of the programs' common view S_i (without self-assessment error)
    prestige: F64  # per program: quantile of the applicants' common view C_j

    @property
    def size(self) -> int:
        """Return the number of applications."""
        return int(self.i.shape[0])


def application_counts(params: SimulationParams, population: Population, seed: int, replicate: int) -> tuple[I32, F64]:
    """Return k_i and the self-assessment normals xi, drawn from stream APPS (§12.2)."""
    apps = params.apps
    n, m = population.n_applicants, population.n_programs
    means = {group.name: group.applications_mean for group in params.applicants.groups}
    group_names = population.applicants.group_names
    per_group = np.array([means.get(name) or apps.mean for name in group_names], dtype=np.float64)
    mu = per_group[population.applicants.group]
    rng = stream_generator(seed, Stream.APPS, replicate_for(Stream.APPS, replicate, params.run.resample_population))
    if apps.count_dist == "poisson":
        counts = rng.poisson(mu).astype(np.float64)
    elif apps.count_dist == "negbin":
        size = 1.0 / apps.dispersion
        counts = rng.negative_binomial(size, size / (size + mu)).astype(np.float64)
    else:
        counts = np.round(mu)
    xi = rng.standard_normal(n)
    k = np.clip(counts, 1, m).astype(np.int32)
    if apps.strategy == "all":
        k = np.full(n, m, dtype=np.int32)
    return k, xi


@dataclass
class ApplicationChooser:
    """Collects each applicant's applications from blocks of pre-interview ranks."""

    params: SimulationParams
    model: MarketModel
    population: Population
    seed: int
    replicate: int = 0
    count: I32 = field(init=False)
    competitiveness: F64 = field(init=False)
    standing: F64 = field(init=False)
    prestige: F64 = field(init=False)
    _parts: list[tuple[I32, I32, I32, F64, NDArray[np.int8]]] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        self.count, xi = application_counts(self.params, self.population, self.seed, self.replicate)
        common_of_applicants = self.model.programs.common  # S: the programs' common view of each applicant
        sigma = self.params.apps.self_assessment_noise_sd
        self.competitiveness = quantiles(common_of_applicants + sigma * xi)
        self.standing = quantiles(common_of_applicants)
        self.prestige = quantiles(self.model.applicants.common)  # C: the applicants' common view of each program

    def categories(self, agents: Indices) -> NDArray[np.int8]:
        """Return REACH, SAFETY or TARGET for every program, for a block of applicants."""
        band = self.params.apps.target_band
        standing = self.competitiveness[agents][:, None]
        prestige = self.prestige[None, :]
        result: NDArray[np.int8] = np.where(
            prestige > standing + band, REACH, np.where(prestige < standing - band, SAFETY, TARGET)
        ).astype(np.int8)
        return result

    def choose(self, agents: Indices, observed: F64, observed_ranks: I32) -> None:
        """Choose the applications of a block of applicants (rows of their pre-interview views and ranks)."""
        strategy = self.params.apps.strategy
        k = self.count[agents][:, None]
        m = observed_ranks.shape[1]
        category = np.zeros(observed_ranks.shape, dtype=np.int8)
        if strategy in ("top_n", "all"):
            mask = observed_ranks <= k
        elif strategy == "random":
            keys = pair_uniforms(self.seed, Stream.APPS, self.replicate, agents[:, None], np.arange(m)[None, :])
            order = np.argsort(keys, axis=1, kind="stable")
            key_rank = np.empty_like(order)
            np.put_along_axis(key_rank, order, np.arange(1, m + 1)[None, :], axis=1)
            mask = key_rank <= k
        else:
            category = self.categories(agents)
            mask = self._portfolio(category, observed_ranks, k)
        rows, columns = np.nonzero(mask)
        self._parts.append(
            (
                agents[rows].astype(np.int32),
                columns.astype(np.int32),
                observed_ranks[rows, columns].astype(np.int32),
                observed[rows, columns],
                category[rows, columns],
            )
        )

    def _portfolio(self, category: NDArray[np.int8], ranks: I32, k: NDArray[np.int32]) -> NDArray[np.bool_]:
        """Best reach, best safety, then best target programs, filled up with the best remaining (§7.1)."""
        shares = self.params.apps.portfolio_shares
        n_reach = np.minimum(np.round(k * shares.reach), k)
        n_safety = np.minimum(np.round(k * shares.safety), k - n_reach)
        order = np.argsort(ranks, axis=1, kind="stable")  # programs in pre-interview order
        ordered = np.take_along_axis(category, order, axis=1)

        def best(kind: int, limit: NDArray[np.floating[Any]] | NDArray[np.integer[Any]]) -> NDArray[np.bool_]:
            is_kind = ordered == kind
            picked: NDArray[np.bool_] = is_kind & (np.cumsum(is_kind, axis=1) <= limit)
            return picked

        picked = best(REACH, n_reach) | best(SAFETY, n_safety)
        remaining = k - picked.sum(axis=1, keepdims=True)
        picked |= best(TARGET, remaining)
        remaining = k - picked.sum(axis=1, keepdims=True)
        open_ = ~picked
        picked |= open_ & (np.cumsum(open_, axis=1) <= remaining)
        mask = np.empty_like(picked)
        np.put_along_axis(mask, order, picked, axis=1)
        return mask

    def result(self) -> Applications:
        """Return all applications, sorted by applicant then program."""
        if self._parts:
            i, j, rank, observed, category = (np.concatenate(values) for values in zip(*self._parts, strict=True))
        else:
            i = j = rank = np.zeros(0, dtype=np.int32)
            observed = np.zeros(0)
            category = np.zeros(0, dtype=np.int8)
        order = np.lexsort((j, i))
        return Applications(
            i=i[order],
            j=j[order],
            pre_rank=rank[order],
            observed=observed[order],
            category=category[order],
            count=self.count,
            competitiveness=self.competitiveness,
            standing=self.standing,
            prestige=self.prestige,
        )
