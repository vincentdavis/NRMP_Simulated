"""Diagnostics of a pre-interview run (model_spec.md §10).

The JSON returned by `pipeline.run_pre_interview(...).metrics` has these parts:

- `market`: N, M, P, requested and realised applicants per position, and a capacity summary.
- `generation`: realised against requested moments of the population: group shares and strength moments, attribute
  correlations with strength or quality, mean weights, tier shares and quality means, and how much of the common
  view the attributes add beyond latent quality or strength (`attribute_share_of_common`).
- `applicants` and `programs`, one per side (agents evaluating targets):
  - `consensus`: mean pairwise Pearson correlation of true utilities, mean pairwise Spearman correlation of true
    rankings, and the Pearson consensus of the observed scores. With each row z_i standardised over the D targets,
    the mean over pairs of agents is (||sum z_i||^2 - sum ||z_i||^2) / (D n (n - 1)), so no pair is compared
    explicitly.
  - `fidelity`: noise SD, reliability 1 / (1 + sigma^2), the expected and the pooled correlation of true and observed
    utilities, and the mean and deciles of each agent's Spearman correlation between true and observed rankings.
  - `first_choices`: how many distinct first choices there are before interviews, and the share of agents whose first
    choice is the most popular target or one of the ten most popular.
- `histograms`: 20-bin histograms of strength, quality, capacity and per-agent fidelity.

Statistics that are undefined (one target, or constant values) are null.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

from nrmps.params import SimulationParams

from .numeric import correlation, standardise_rows
from .population import PROGRAM_SIZE, Population
from .utility import MarketModel, Observation, SideModel

F64 = NDArray[np.float64]
I32 = NDArray[np.int32]
Indices = NDArray[np.int64]

BINS = 20


def _float(value: float | np.floating[Any] | None) -> float | None:
    """Return a JSON-safe float (None for None or a non-finite value)."""
    if value is None:
        return None
    number = float(value)
    return number if np.isfinite(number) else None


def _round(values: ArrayLike, digits: int = 6) -> list[float]:
    return [round(float(v), digits) for v in np.asarray(values, dtype=np.float64)]


def histogram(values: ArrayLike, bins: int = BINS) -> dict[str, list[float] | list[int]] | None:
    """Return {"edges": [...], "counts": [...]} for the finite values, or None if there are none."""
    data = np.asarray(values, dtype=np.float64)
    data = data[np.isfinite(data)]
    if data.size == 0:
        return None
    counts, edges = np.histogram(data, bins=bins)
    return {"edges": _round(edges), "counts": [int(c) for c in counts]}


def _pair_mean(total: F64, squares: float, n: int, width: int) -> float | None:
    """Mean over pairs of rows of (1/D) z_i . z_i' from the sum of the rows and the sum of their squared norms."""
    if n < 2 or width < 1:
        return None
    return _float((float(total @ total) - squares) / (width * n * (n - 1)))


@dataclass
class SideAccumulator:
    """Accumulates one side's diagnostics over blocks of agents (each block: agents x all targets)."""

    n_agents: int
    n_targets: int
    utility_sum: F64 = field(init=False)
    rank_sum: F64 = field(init=False)
    observed_sum: F64 = field(init=False)
    utility_squares: float = 0.0
    rank_squares: float = 0.0
    observed_squares: float = 0.0
    pooled: F64 = field(default_factory=lambda: np.zeros(5))  # sum u, sum u_hat, sum u^2, sum u_hat^2, sum u u_hat
    pooled_count: int = 0
    fidelity: F64 = field(init=False)
    first_choice: NDArray[np.int64] = field(init=False)

    def __post_init__(self) -> None:
        self.utility_sum = np.zeros(self.n_targets)
        self.rank_sum = np.zeros(self.n_targets)
        self.observed_sum = np.zeros(self.n_targets)
        self.fidelity = np.full(self.n_agents, np.nan)
        self.first_choice = np.full(self.n_agents, -1, dtype=np.int64)

    def add(self, agents: Indices, true: F64, observed: F64, true_ranks: I32, observed_ranks: I32) -> None:
        """Add one block of agents' rows."""
        width = self.n_targets
        z = standardise_rows(true)
        self.utility_sum += z.sum(axis=0)
        self.utility_squares += float(np.sum(z * z))
        zo = standardise_rows(observed)
        self.observed_sum += zo.sum(axis=0)
        self.observed_squares += float(np.sum(zo * zo))
        if width > 1:
            # Ranks 1..D have mean (D + 1) / 2 and population SD sqrt((D^2 - 1) / 12).
            zr = (true_ranks - (width + 1) / 2.0) / np.sqrt((width * width - 1) / 12.0)
            self.rank_sum += zr.sum(axis=0)
            self.rank_squares += float(np.sum(zr * zr))
            difference = (true_ranks - observed_ranks).astype(np.float64)
            self.fidelity[agents] = 1.0 - 6.0 * np.sum(difference * difference, axis=1) / (width * (width * width - 1))
        self.pooled += (
            true.sum(),
            observed.sum(),
            np.sum(true * true),
            np.sum(observed * observed),
            np.sum(true * observed),
        )
        self.pooled_count += true.size
        self.first_choice[agents] = np.argmin(observed_ranks, axis=1)

    def pooled_correlation(self) -> float | None:
        """Return the correlation of true and observed utilities over all pairs."""
        n = self.pooled_count
        su, so, suu, soo, suo = self.pooled
        cov = suo / n - (su / n) * (so / n)
        var_u = suu / n - (su / n) ** 2
        var_o = soo / n - (so / n) ** 2
        if var_u <= 0 or var_o <= 0:
            return None
        return _float(cov / np.sqrt(var_u * var_o))

    def result(self, view: Observation) -> dict[str, Any]:
        """Return the side's consensus, fidelity and first-choice diagnostics."""
        n, width = self.n_agents, self.n_targets
        sigma = view.sigma
        mean_h2 = float(np.mean((view.scale / sigma) ** 2)) if sigma > 0 else 1.0
        fidelity = self.fidelity[np.isfinite(self.fidelity)]
        demand = np.bincount(self.first_choice, minlength=width)
        top = np.sort(demand)[::-1]
        return {
            "consensus": {
                "true_utility_correlation": _pair_mean(self.utility_sum, self.utility_squares, n, width),
                "true_rank_correlation": (
                    _pair_mean(self.rank_sum, self.rank_squares, n, width) if width > 1 else None
                ),
                "observed_utility_correlation": _pair_mean(self.observed_sum, self.observed_squares, n, width),
            },
            "fidelity": {
                "noise_sd": sigma,
                "reliability": 1.0 / (1.0 + sigma * sigma),
                "expected_correlation": 1.0 / np.sqrt(1.0 + sigma * sigma * mean_h2),
                "pooled_correlation": self.pooled_correlation(),
                "spearman_mean": _float(fidelity.mean()) if fidelity.size else None,
                "spearman_deciles": _round(np.quantile(fidelity, np.linspace(0.1, 0.9, 9))) if fidelity.size else None,
            },
            "first_choices": {
                "distinct": int(np.count_nonzero(demand)),
                "most_popular_share": _float(top[0] / n),
                "top_10_share": _float(top[:10].sum() / n),
            },
        }


def _shares(labels: NDArray[np.int16], names: Sequence[str]) -> dict[str, float]:
    counts = np.bincount(labels, minlength=len(names))
    return {name: float(count / labels.size) for name, count in zip(names, counts, strict=True)}


def generation_metrics(params: SimulationParams, population: Population, model: MarketModel) -> dict[str, Any]:
    """Compare the realised population with the requested moments."""
    a, p = population.applicants, population.programs
    requested_groups = {g.name: g for g in params.applicants.groups}
    groups: dict[str, Any] = {}
    for index, name in enumerate(a.group_names):
        members = a.strength[a.group == index]
        group = requested_groups.get(name)
        groups[name] = {
            "share": float(members.size / a.size),
            "requested_share": group.share if group else None,
            "strength_mean": _float(members.mean()) if members.size else None,
            "requested_strength_mean": group.strength_mean if group else None,
            "strength_sd": _float(members.std()) if members.size > 1 else None,
            "requested_strength_sd": group.strength_sd if group else None,
        }
    requested_tiers = {t.name: t for t in params.programs.tiers}
    tiers: dict[str, Any] = {}
    for index, name in enumerate(p.tier_names):
        members = p.quality[p.tier == index]
        tier = requested_tiers.get(name)
        tiers[name] = {
            "share": float(members.size / p.size),
            "requested_share": tier.share if tier else (1.0 if not requested_tiers else None),
            "quality_mean": _float(members.mean()) if members.size else None,
            "requested_quality_mean": tier.quality_mean if tier else (0.0 if not requested_tiers else None),
        }
    applicant_attributes = {
        key: {
            "correlation_with_strength": correlation(a.attributes[:, k], a.strength),
            "requested_correlation": next(
                (x.corr_with_strength for x in params.applicants.attributes if x.key == key), None
            ),
            "mean_weight": float(p.weights[:, k].mean()),
            "requested_mean_weight": _requested_weight(params, key, "program"),
        }
        for k, key in enumerate(a.keys)
    }
    program_attributes = {
        key: {
            "correlation_with_quality": correlation(p.attributes[:, k], p.quality),
            "requested_correlation": (
                None
                if key == PROGRAM_SIZE
                else next((x.corr_with_quality for x in params.programs.attributes if x.key == key), None)
            ),
            "mean_weight": float(a.weights[:, k].mean()),
            "requested_mean_weight": _requested_weight(params, key, "applicant"),
        }
        for k, key in enumerate(p.keys)
    }
    common_quality = correlation(model.applicants.common, p.quality)
    common_strength = correlation(model.programs.common, a.strength)
    return {
        "groups": groups,
        "tiers": tiers,
        "applicant_attributes": applicant_attributes,
        "program_attributes": program_attributes,
        "attribute_share_of_common": {
            "applicants": _float(1.0 - common_quality**2) if common_quality is not None else None,
            "programs": _float(1.0 - common_strength**2) if common_strength is not None else None,
        },
    }


def _requested_weight(params: SimulationParams, key: str, judge: str) -> float | None:
    """Return the renormalised mean weight the parameters request for `key` (judged by applicants or programs)."""
    if judge == "applicant":
        priors = {x.key: x.applicant_weight_prior for x in params.programs.attributes}
    else:
        priors = {x.key: x.program_weight_prior for x in params.applicants.attributes}
    if key not in priors:
        return None
    return float(priors[key] / sum(priors.values()))


def market_metrics(params: SimulationParams, population: Population) -> dict[str, Any]:
    """Return the market size, tightness and a capacity summary."""
    capacity = population.programs.capacity
    return {
        "n_applicants": population.n_applicants,
        "n_programs": population.n_programs,
        "n_positions": population.n_positions,
        "n_pairs": population.n_applicants * population.n_programs,
        "applicants_per_position": population.n_applicants / population.n_positions,
        "requested_applicants_per_position": params.market.applicants_per_position,
        "capacity": {
            "min": int(capacity.min()),
            "max": int(capacity.max()),
            "mean": float(capacity.mean()),
            "median": float(np.median(capacity)),
        },
    }


def histograms(population: Population, applicant_fidelity: F64, program_fidelity: F64) -> dict[str, Any]:
    """Return the 20-bin histograms of the population and of per-agent fidelity."""
    return {
        "strength": histogram(population.applicants.strength),
        "quality": histogram(population.programs.quality),
        "capacity": histogram(population.programs.capacity),
        "applicant_fidelity": histogram(applicant_fidelity),
        "program_fidelity": histogram(program_fidelity),
    }


def side_summary(model: SideModel) -> dict[str, Any]:
    """Return how many agents on a side have a taste term (the rest have pure fit as their personal part)."""
    return {"agents_with_taste": int(np.count_nonzero(model.has_taste))}
