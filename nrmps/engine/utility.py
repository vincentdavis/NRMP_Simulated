"""True utilities and pre-interview observations (model_spec.md §5, §6 and §12.5-12.7).

`SideModel` holds everything one side needs to evaluate the other: the common term, the residualised attributes and
each agent's taste moments. `utilities(agents, targets)` then computes any block of true utilities with elementwise
operations in the fixed order of §12.7, so a block is bit-identical to the same entries of the full matrix.
`observe` adds the pre-interview error.

Pair-level draws always use the counter (applicant index, program index), whichever side is evaluating.
"""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from nrmps.params import SimulationParams

from .numeric import quantiles, standardise
from .population import Population
from .rng import Stream, pair_normals, replicate_for

F64 = NDArray[np.float64]
Indices = NDArray[np.int64]

TASTE_SD_MIN = 1e-12


@dataclass(frozen=True, eq=False)
class SideModel:
    """One side's true-utility model: agents (who evaluate) and targets (who are evaluated)."""

    agents_are_applicants: bool
    common: F64  # C (or S), one value per target
    residual: F64  # target attributes residualised on the common term, (targets, K)
    deviation: F64  # agents' weights minus the mean weights, (agents, K)
    taste_mean: F64  # mean over targets of each agent's taste index
    taste_sd: F64  # SD over targets of each agent's taste index (1 where the agent has no taste term)
    has_taste: NDArray[np.bool_]
    sqrt_tau: F64  # per agent: sqrt(tau), or 0 without a taste term
    sqrt_one_minus_tau: F64
    sqrt_rho: float
    sqrt_one_minus_rho: float
    idio_stream: Stream
    idio_replicate: int
    seed: int

    @property
    def n_agents(self) -> int:
        """Return the number of agents on this side."""
        return int(self.deviation.shape[0])

    @property
    def n_targets(self) -> int:
        """Return the number of targets this side evaluates."""
        return int(self.common.shape[0])

    def pair_counters(self, agents: Indices, targets: Indices) -> tuple[Indices, Indices]:
        """Return (applicant index, program index) arrays shaped (agents, 1) and (1, targets), or the reverse."""
        if self.agents_are_applicants:
            return agents[:, None], targets[None, :]
        return targets[None, :], agents[:, None]

    def taste(self, agents: Indices, targets: Indices) -> F64:
        """Return the standardised taste terms T for a block (agents x targets); 0 for agents without taste."""
        d = self.deviation[agents]
        y = self.residual[targets]
        index = d[:, 0:1] * y[:, 0][None, :]
        for k in range(1, d.shape[1]):
            index = index + d[:, k : k + 1] * y[:, k][None, :]
        taste = (index - self.taste_mean[agents][:, None]) / self.taste_sd[agents][:, None]
        result: F64 = np.where(self.has_taste[agents][:, None], taste, 0.0)
        return result

    def utilities(self, agents: Indices, targets: Indices) -> F64:
        """Return the true utilities of `agents` for `targets` (a block, agents x targets)."""
        i, j = self.pair_counters(agents, targets)
        idio = pair_normals(self.seed, self.idio_stream, self.idio_replicate, i, j)
        inner = self.sqrt_tau[agents][:, None] * self.taste(agents, targets)
        inner = inner + self.sqrt_one_minus_tau[agents][:, None] * idio
        result: F64 = self.sqrt_rho * self.common[targets][None, :] + self.sqrt_one_minus_rho * inner
        return result

    def pair_taste(self, agents: Indices, targets: Indices) -> F64:
        """Return the taste terms of aligned (agent, target) pairs, equal to the same entries of `taste`."""
        d = self.deviation[agents]
        y = self.residual[targets]
        index = d[:, 0] * y[:, 0]
        for k in range(1, d.shape[1]):
            index = index + d[:, k] * y[:, k]
        taste = (index - self.taste_mean[agents]) / self.taste_sd[agents]
        result: F64 = np.where(self.has_taste[agents], taste, 0.0)
        return result

    def pair_utilities(self, agents: Indices, targets: Indices) -> F64:
        """Return the true utilities of aligned (agent, target) pairs, equal to the same entries of `utilities`."""
        i, j = (agents, targets) if self.agents_are_applicants else (targets, agents)
        idio = pair_normals(self.seed, self.idio_stream, self.idio_replicate, i, j)
        inner = self.sqrt_tau[agents] * self.pair_taste(agents, targets)
        inner = inner + self.sqrt_one_minus_tau[agents] * idio
        result: F64 = self.sqrt_rho * self.common[targets] + self.sqrt_one_minus_rho * inner
        return result


def build_side(
    *,
    agents_are_applicants: bool,
    weights: F64,
    prior: F64,
    target_attributes: F64,
    target_latent: F64,
    rho: float,
    beta: float,
    tau: float,
    idio_stream: Stream,
    idio_replicate: int,
    seed: int,
) -> SideModel:
    """Precompute one side's common term, residualised attributes and taste moments (§5, §12.5)."""
    mean_weights = prior / prior.sum()
    n_targets, k = target_attributes.shape
    index = mean_weights[0] * target_attributes[:, 0]
    for column in range(1, k):
        index = index + mean_weights[column] * target_attributes[:, column]
    common = standardise((1.0 - beta) * standardise(target_latent) + beta * index)
    # Residualise the attributes on the common term: b = Cov(y, C) / Var(C), with population moments.
    centred_common = common - common.mean()
    variance = float(np.mean(centred_common * centred_common))
    centred = target_attributes - target_attributes.mean(axis=0)
    slopes = (centred * centred_common[:, None]).mean(axis=0) / variance if variance > 0 else np.zeros(k)
    residual = target_attributes - slopes[None, :] * common[:, None]
    # Taste moments over targets, from the mean and covariance of the residualised attributes.
    deviation = weights - mean_weights[None, :]
    residual_mean = residual.mean(axis=0)
    centred_residual = residual - residual_mean
    covariance = (centred_residual.T @ centred_residual) / n_targets
    taste_mean = deviation[:, 0] * residual_mean[0]
    for column in range(1, k):
        taste_mean = taste_mean + deviation[:, column] * residual_mean[column]
    variance_i = np.zeros(deviation.shape[0])
    for a in range(k):
        for b in range(k):
            variance_i = variance_i + deviation[:, a] * covariance[a, b] * deviation[:, b]
    taste_sd = np.sqrt(np.maximum(variance_i, 0.0))
    has_taste = (taste_sd >= TASTE_SD_MIN) & (k >= 2) & (tau > 0)
    tau_i = np.where(has_taste, tau, 0.0)
    return SideModel(
        agents_are_applicants=agents_are_applicants,
        common=common,
        residual=residual,
        deviation=deviation,
        taste_mean=taste_mean,
        taste_sd=np.where(has_taste, taste_sd, 1.0),
        has_taste=has_taste,
        sqrt_tau=np.sqrt(tau_i),
        sqrt_one_minus_tau=np.sqrt(1.0 - tau_i),
        sqrt_rho=float(np.sqrt(rho)),
        sqrt_one_minus_rho=float(np.sqrt(1.0 - rho)),
        idio_stream=idio_stream,
        idio_replicate=idio_replicate,
        seed=seed,
    )


@dataclass(frozen=True, eq=False)
class Observation:
    """Pre-interview observation error of one side (§6): per-target scales and the optional halo."""

    agents_are_applicants: bool
    sigma: float
    scale: F64  # per target: sigma * (1 + gamma_h * (1 - quantile))
    halo: F64 | None  # per target: nu (None when psi = 0)
    sqrt_one_minus_psi: float
    sqrt_psi: float
    stream: Stream
    replicate: int
    seed: int

    def _error(self, i: Indices, j: Indices, targets: Indices) -> F64:
        """Return e = scale * delta for counters (i, j) that broadcast like `targets` (model_spec.md §12.7)."""
        delta = pair_normals(self.seed, self.stream, self.replicate, i, j)
        if self.halo is not None:
            delta = self.sqrt_one_minus_psi * delta + self.sqrt_psi * self.halo[targets]
        result: F64 = self.scale[targets] * delta
        return result

    def observe(self, utilities: F64, agents: Indices, targets: Indices) -> F64:
        """Return the observed scores for a block of true utilities (agents x targets)."""
        if self.sigma == 0:
            return utilities.copy()
        if self.agents_are_applicants:
            i, j = agents[:, None], targets[None, :]
        else:
            i, j = targets[None, :], agents[:, None]
        result: F64 = utilities + self._error(i, j, targets[None, :])
        return result

    def pair_error(self, agents: Indices, targets: Indices) -> F64:
        """Return the pre-interview error terms e of aligned (agent, target) pairs (zeros when sigma is 0)."""
        if self.sigma == 0:
            return np.zeros(agents.shape[0])
        i, j = (agents, targets) if self.agents_are_applicants else (targets, agents)
        return self._error(i, j, targets)


def build_observation(
    *,
    agents_are_applicants: bool,
    sigma: float,
    gamma: float,
    psi: float,
    target_latent: F64,
    stream: Stream,
    halo_stream: Stream,
    replicate: int,
    seed: int,
) -> Observation:
    """Precompute one side's per-target error scales and halo terms."""
    n_targets = target_latent.shape[0]
    scale = sigma * (1.0 + gamma * (1.0 - quantiles(target_latent)))
    halo = None
    if sigma > 0 and psi > 0:
        targets = np.arange(n_targets, dtype=np.int64)
        # The halo of program j is the draw at pair (0, j); of applicant i, the draw at pair (i, 0).
        i, j = (np.zeros_like(targets), targets) if agents_are_applicants else (targets, np.zeros_like(targets))
        halo = pair_normals(seed, halo_stream, replicate, i, j)
    return Observation(
        agents_are_applicants=agents_are_applicants,
        sigma=sigma,
        scale=scale,
        halo=halo,
        sqrt_one_minus_psi=float(np.sqrt(1.0 - psi)),
        sqrt_psi=float(np.sqrt(psi)),
        stream=stream,
        replicate=replicate,
        seed=seed,
    )


@dataclass(frozen=True, eq=False)
class MarketModel:
    """Both sides' utility and observation models for one (population, parameters, seed, replicate)."""

    applicants: SideModel  # applicants evaluating programs: u
    programs: SideModel  # programs evaluating applicants: v
    applicant_view: Observation  # u -> u_hat
    program_view: Observation  # v -> v_hat


def build_market(params: SimulationParams, population: Population, seed: int, replicate: int = 0) -> MarketModel:
    """Precompute the market model; pair-level values are then computed block by block."""
    prefs, info = params.prefs, params.info
    resample = params.run.resample_population
    a, p = population.applicants, population.programs
    applicants = build_side(
        agents_are_applicants=True,
        weights=a.weights,
        prior=np.array([x.applicant_weight_prior for x in params.programs.attributes]),
        target_attributes=p.attributes,
        target_latent=p.quality,
        rho=prefs.applicant_pref_correlation,
        beta=prefs.attribute_weight_share,
        tau=prefs.taste_share,
        idio_stream=Stream.IDIO_A,
        idio_replicate=replicate_for(Stream.IDIO_A, replicate, resample),
        seed=seed,
    )
    programs = build_side(
        agents_are_applicants=False,
        weights=p.weights,
        prior=np.array([x.program_weight_prior for x in params.applicants.attributes]),
        target_attributes=a.attributes,
        target_latent=a.strength,
        rho=prefs.program_pref_correlation,
        beta=prefs.attribute_weight_share,
        tau=prefs.taste_share,
        idio_stream=Stream.IDIO_P,
        idio_replicate=replicate_for(Stream.IDIO_P, replicate, resample),
        seed=seed,
    )
    applicant_view = build_observation(
        agents_are_applicants=True,
        sigma=info.applicant_pre_noise_sd,
        gamma=info.visibility_heteroskedasticity,
        psi=info.halo_share,
        target_latent=p.quality,
        stream=Stream.PRE_A,
        halo_stream=Stream.HALO_A,
        replicate=replicate,
        seed=seed,
    )
    program_view = build_observation(
        agents_are_applicants=False,
        sigma=info.program_pre_noise_sd,
        gamma=info.visibility_heteroskedasticity,
        psi=info.halo_share,
        target_latent=a.strength,
        stream=Stream.PRE_P,
        halo_stream=Stream.HALO_P,
        replicate=replicate,
        seed=seed,
    )
    return MarketModel(applicants, programs, applicant_view, program_view)
