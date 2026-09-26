"""Applicant and program populations (model_spec.md §4, §12.2 and §12.9).

A population is two sides of plain arrays. Generated sides are drawn from the population streams; uploaded sides
(CSV) are built by `nrmps.population_csv` and must pass `validate_population` like generated ones.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

from nrmps.params import MAX_PAIRS, SimulationParams

from .numeric import largest_remainder, standardise
from .rng import Stream, check_seed, replicate_for, stream_generator

F64 = NDArray[np.float64]
I16 = NDArray[np.int16]
I32 = NDArray[np.int32]

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
PROGRAM_SIZE = "program_size"
MAX_NAME_LENGTH = 100
WEIGHT_TOLERANCE = 1e-6
IMPLICIT_TIER = "all"


class PopulationError(ValueError):
    """A population is not valid, or does not fit the parameters; the message says why."""


@dataclass(frozen=True, eq=False)
class ApplicantSide:
    """The applicants: groups, latent strength, attributes (what programs evaluate) and weights over programs'."""

    group_names: tuple[str, ...]
    group: I16
    strength: F64
    keys: tuple[str, ...]
    attributes: F64
    weight_keys: tuple[str, ...]
    weights: F64
    names: tuple[str, ...] | None = None

    @property
    def size(self) -> int:
        """Return N."""
        return int(self.strength.shape[0])

    def name(self, index: int) -> str:
        """Return the display name of applicant `index` (0-based)."""
        return self.names[index] if self.names is not None else f"Applicant {index + 1}"


@dataclass(frozen=True, eq=False)
class ProgramSide:
    """The programs: tiers, latent quality, attributes (what applicants evaluate), weights and capacities."""

    tier_names: tuple[str, ...]
    tier: I16
    quality: F64
    keys: tuple[str, ...]
    attributes: F64
    weight_keys: tuple[str, ...]
    weights: F64
    capacity: I32
    names: tuple[str, ...] | None = None

    @property
    def size(self) -> int:
        """Return M."""
        return int(self.quality.shape[0])

    def name(self, index: int) -> str:
        """Return the display name of program `index` (0-based)."""
        return self.names[index] if self.names is not None else f"Program {index + 1}"


@dataclass(frozen=True, eq=False)
class Population:
    """Both sides of a market."""

    applicants: ApplicantSide
    programs: ProgramSide

    @property
    def n_applicants(self) -> int:
        """Return N."""
        return self.applicants.size

    @property
    def n_programs(self) -> int:
        """Return M."""
        return self.programs.size

    @property
    def n_positions(self) -> int:
        """Return P, the total capacity."""
        return int(self.programs.capacity.sum())


# --- Generation ---------------------------------------------------------------------------------------------------


def _prior(values: Sequence[float]) -> F64:
    """Return prior weights renormalised to sum to 1."""
    prior = np.asarray(values, dtype=np.float64)
    return prior / prior.sum()


def dirichlet_rows(rng: np.random.Generator, n: int, prior: ArrayLike, concentration: float) -> F64:
    """Draw n Dirichlet(concentration x prior) rows in log space (§12.2), robust to tiny concentrations.

    Gamma(alpha + 1) variates G and uniforms U in (0, 1] give log g = log G + log(U) / alpha (Marsaglia-Tsang), then
    each row is normalised after subtracting its maximum. With one attribute every weight is 1 and nothing is drawn.
    """
    mean = np.asarray(prior, dtype=np.float64)
    k = mean.size
    if k == 1:
        return np.ones((n, 1))
    alpha = concentration * mean
    gamma = rng.gamma(alpha + 1.0, size=(n, k))
    uniform = 1.0 - rng.random((n, k))
    log_g = np.log(gamma) + np.log(uniform) / alpha
    log_g -= log_g.max(axis=1, keepdims=True)
    g = np.exp(log_g)
    result: F64 = g / g.sum(axis=1, keepdims=True)
    return result


def _labels(rng: np.random.Generator, n: int, shares: Sequence[float]) -> I16:
    """Return n group or tier labels: largest-remainder sizes, shuffled over the indices."""
    sizes = largest_remainder(n, shares)
    labels = np.repeat(np.arange(len(shares), dtype=np.int16), sizes)
    shuffled: I16 = rng.permutation(labels)
    return shuffled


def generate_applicants(
    params: SimulationParams, seed: int, replicate: int = 0, n_applicants: int | None = None
) -> ApplicantSide:
    """Generate the applicants (§4.1, §4.2, §4.4) from streams POP_A and WEIGHTS_A."""
    seed = check_seed(seed)
    n = params.market.n_applicants if n_applicants is None else n_applicants
    resample = params.run.resample_population
    groups = params.applicants.groups
    attributes = params.applicants.attributes
    rng = stream_generator(seed, Stream.POP_A, replicate_for(Stream.POP_A, replicate, resample))
    group = _labels(rng, n, [g.share for g in groups])
    z = rng.standard_normal(n)
    e = rng.standard_normal((n, len(attributes)))
    strength = np.array([g.strength_mean for g in groups])[group] + np.array([g.strength_sd for g in groups])[group] * z
    rho = np.array([a.corr_with_strength for a in attributes])
    x = rho * standardise(strength)[:, None] + np.sqrt(1.0 - rho**2) * e
    program_attributes = params.programs.attributes
    weights_rng = stream_generator(seed, Stream.WEIGHTS_A, replicate_for(Stream.WEIGHTS_A, replicate, resample))
    weights = dirichlet_rows(
        weights_rng,
        n,
        _prior([a.applicant_weight_prior for a in program_attributes]),
        params.prefs.weight_concentration,
    )
    return ApplicantSide(
        group_names=tuple(g.name for g in groups),
        group=group,
        strength=strength,
        keys=tuple(a.key for a in attributes),
        attributes=x,
        weight_keys=tuple(a.key for a in program_attributes),
        weights=weights,
    )


def generate_capacities(params: SimulationParams, seed: int, replicate: int, n_programs: int, n_positions: int) -> I32:
    """Spread n_positions over n_programs, at least one each (§4.3), from stream CAP."""
    rng = stream_generator(seed, Stream.CAP, replicate_for(Stream.CAP, replicate, params.run.resample_population))
    extra = n_positions - n_programs
    distribution = params.market.program_size_dist
    if distribution == "fixed":
        keys = rng.random(n_programs)
        counts = largest_remainder(extra, np.ones(n_programs), keys)
    elif distribution == "lognormal":
        scores = rng.lognormal(0.0, params.market.program_size_dispersion, n_programs)
        keys = rng.random(n_programs)
        counts = largest_remainder(extra, scores, keys)
    else:
        counts = rng.multinomial(extra, np.full(n_programs, 1.0 / n_programs))
    return (1 + counts).astype(np.int32)


def program_size_attribute(capacity: ArrayLike) -> F64:
    """Return the program_size attribute: the standardised log capacity (§4.2)."""
    return standardise(np.log(np.asarray(capacity, dtype=np.float64)))


def generate_programs(params: SimulationParams, seed: int, replicate: int = 0, n_applicants: int = 0) -> ProgramSide:
    """Generate the programs (§4.1-4.4) for `n_applicants` applicants from streams POP_P, CAP and WEIGHTS_P."""
    seed = check_seed(seed)
    resample = params.run.resample_population
    positions = params.market.n_positions(n_applicants or params.market.n_applicants)
    m = params.market.resolved_n_programs(positions)
    if m > positions:
        raise PopulationError(
            f"{m:,} programs need at least {m:,} positions, but the applicants give only {positions:,}. Use fewer "
            "programs or fewer applicants per position."
        )
    tiers = params.programs.tiers
    shares = [t.share for t in tiers] or [1.0]
    means = np.array([t.quality_mean for t in tiers] or [0.0])
    attributes = params.programs.attributes
    rng = stream_generator(seed, Stream.POP_P, replicate_for(Stream.POP_P, replicate, resample))
    tier = _labels(rng, m, shares)
    z = rng.standard_normal(m)
    e = rng.standard_normal((m, len(attributes)))
    quality = means[tier] + params.programs.quality_sd * z
    capacity = generate_capacities(params, seed, replicate, m, positions)
    rho = np.array([a.corr_with_quality for a in attributes])
    y = rho * standardise(quality)[:, None] + np.sqrt(1.0 - rho**2) * e
    keys = tuple(a.key for a in attributes)
    if PROGRAM_SIZE in keys:
        y[:, keys.index(PROGRAM_SIZE)] = program_size_attribute(capacity)
    applicant_attributes = params.applicants.attributes
    weights_rng = stream_generator(seed, Stream.WEIGHTS_P, replicate_for(Stream.WEIGHTS_P, replicate, resample))
    weights = dirichlet_rows(
        weights_rng,
        m,
        _prior([a.program_weight_prior for a in applicant_attributes]),
        params.prefs.weight_concentration,
    )
    return ProgramSide(
        tier_names=tuple(t.name for t in tiers) or (IMPLICIT_TIER,),
        tier=tier,
        quality=quality,
        keys=keys,
        attributes=y,
        weight_keys=tuple(a.key for a in applicant_attributes),
        weights=weights,
        capacity=capacity,
    )


def generate_population(
    params: SimulationParams,
    seed: int,
    replicate: int = 0,
    applicants: ApplicantSide | None = None,
    programs: ProgramSide | None = None,
) -> Population:
    """Generate a population, or complete one whose applicants or programs were uploaded.

    The number of programs and positions derives from the actual number of applicants, so uploaded applicants with
    generated programs still give the requested tightness.
    """
    if applicants is None:
        applicants = generate_applicants(params, seed, replicate)
    if programs is None:
        programs = generate_programs(params, seed, replicate, n_applicants=applicants.size)
    population = Population(applicants, programs)
    validate_population(population, params)
    return population


# --- Validation (§12.9) --------------------------------------------------------------------------------------------


def _check_keys(values: tuple[str, ...], what: str) -> None:
    if not values:
        raise PopulationError(f"There are no {what}.")
    for value in values:
        if not isinstance(value, str) or not KEY_RE.fullmatch(value):
            raise PopulationError(
                f"{value!r} is not a valid {what[:-1]} name: use 1 to 40 lowercase letters, digits "
                "or underscores, starting with a letter."
            )
    if len(set(values)) != len(values):
        raise PopulationError(f"The {what} are not unique.")


def _check_names(names: tuple[str, ...] | None, n: int, what: str) -> None:
    if names is None:
        return
    if len(names) != n:
        raise PopulationError(f"There are {len(names)} {what} names for {n} {what}.")
    for name in names:
        if not isinstance(name, str) or not name.strip() or len(name) > MAX_NAME_LENGTH:
            raise PopulationError(f"Every {what[:-1]} needs a name of 1 to {MAX_NAME_LENGTH} characters.")
    if len(set(names)) != n:
        raise PopulationError(f"The {what} names are not unique.")


def _check_array(array: NDArray[np.generic], shape: tuple[int, ...], dtype: type, what: str) -> None:
    if not isinstance(array, np.ndarray) or array.shape != shape or array.dtype != dtype:
        raise PopulationError(f"The {what} array has the wrong shape or type.")
    if array.dtype.kind == "f" and not np.all(np.isfinite(array)):
        raise PopulationError(f"The {what} contain missing or infinite values.")


def _check_weights(weights: F64, what: str) -> None:
    if np.any(weights < 0):
        raise PopulationError(f"The {what} weights must not be negative.")
    sums = weights.sum(axis=1)
    if not np.all(np.abs(sums - 1.0) <= WEIGHT_TOLERANCE):
        raise PopulationError(f"Each row of {what} weights must add up to 1.")


def validate_population(population: Population, params: SimulationParams | None = None) -> None:
    """Raise PopulationError unless the population is complete, consistent and matches the parameters' attributes."""
    applicants, programs = population.applicants, population.programs
    n, m = applicants.size, programs.size
    if n < 1 or m < 1:
        raise PopulationError("A market needs at least one applicant and one program.")
    if n * m > MAX_PAIRS:
        raise PopulationError(f"{n:,} applicants x {m:,} programs is above the model's limit of {MAX_PAIRS:,} pairs.")
    _check_keys(applicants.group_names, "groups")
    _check_keys(applicants.keys, "applicant attributes")
    _check_keys(programs.tier_names, "tiers")
    _check_keys(programs.keys, "program attributes")
    _check_names(applicants.names, n, "applicants")
    _check_names(programs.names, m, "programs")
    k_a, k_p = len(applicants.keys), len(programs.keys)
    _check_array(applicants.group, (n,), np.int16, "applicant group")
    _check_array(applicants.strength, (n,), np.float64, "applicant strengths")
    _check_array(applicants.attributes, (n, k_a), np.float64, "applicant attributes")
    _check_array(applicants.weights, (n, k_p), np.float64, "applicant weights")
    _check_array(programs.tier, (m,), np.int16, "program tier")
    _check_array(programs.quality, (m,), np.float64, "program qualities")
    _check_array(programs.attributes, (m, k_p), np.float64, "program attributes")
    _check_array(programs.weights, (m, k_a), np.float64, "program weights")
    _check_array(programs.capacity, (m,), np.int32, "program capacity")
    if np.any(applicants.group < 0) or np.any(applicants.group >= len(applicants.group_names)):
        raise PopulationError("An applicant's group is out of range.")
    if np.any(programs.tier < 0) or np.any(programs.tier >= len(programs.tier_names)):
        raise PopulationError("A program's tier is out of range.")
    if np.any(programs.capacity < 1):
        raise PopulationError("Every program needs at least one position.")
    _check_weights(applicants.weights, "applicant")
    _check_weights(programs.weights, "program")
    if applicants.weight_keys != programs.keys:
        raise PopulationError("Applicants' weights must cover exactly the program attributes, in the same order.")
    if programs.weight_keys != applicants.keys:
        raise PopulationError("Programs' weights must cover exactly the applicant attributes, in the same order.")
    if params is not None:
        expected_a = tuple(a.key for a in params.applicants.attributes)
        expected_p = tuple(a.key for a in params.programs.attributes)
        if applicants.keys != expected_a:
            raise PopulationError(
                f"The applicants have the attributes {', '.join(applicants.keys)}, but the parameters list "
                f"{', '.join(expected_a)}."
            )
        if programs.keys != expected_p:
            raise PopulationError(
                f"The programs have the attributes {', '.join(programs.keys)}, but the parameters list "
                f"{', '.join(expected_p)}."
            )
