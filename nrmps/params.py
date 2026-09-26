"""Typed, versioned simulation parameters (schema v1): the one source for validation, forms and help.

The schema implements docs/model_spec.md §11-12 and Appendix C §3 of the project review. Parameters are grouped by
the part of the model or the stage that reads them. Parameters of stages the engine does not implement yet are part
of the schema, so saved settings keep their meaning when those stages arrive, but they are marked
`implemented=False` and have no effect.

Field-level ranges are always errors. Cross-field rules on implemented parameters are errors too; cross-field rules
on planned stages are warnings (`SimulationParams.warnings()`).
"""

import hashlib
import json
import math
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.fields import FieldInfo

SCHEMA_VERSION = 1

KEY_PATTERN = r"^[a-z][a-z0-9_]{0,39}$"
KEY_HELP = "1 to 40 lowercase letters, digits or underscores, starting with a letter"
MAX_ATTRIBUTES = 10
MAX_GROUPS = 10
MAX_TIERS = 10
MAX_SIGNAL_TIERS = 5
# Hard limit on applicants x programs (model_spec.md §12.10); deployments set lower limits in the settings.
MAX_PAIRS = 50_000_000
SHARE_TOLERANCE = 1e-6

Level = Literal["basic", "advanced"]


def param(
    default: Any = ...,
    *,
    title: str,
    description: str,
    unit: str = "",
    implemented: bool = True,
    level: Level = "basic",
    default_factory: Callable[[], Any] | None = None,
    **constraints: Any,
) -> Any:
    """Declare a parameter: a pydantic Field with a label, help text, unit, level and implementation status."""
    extra: dict[str, Any] = {"implemented": implemented, "level": level}
    if unit:
        extra["unit"] = unit
    if default_factory is not None:
        return Field(
            default_factory=default_factory,
            title=title,
            description=description,
            json_schema_extra=extra,
            **constraints,
        )
    return Field(default, title=title, description=description, json_schema_extra=extra, **constraints)


def key_field(title: str, description: str, default: Any = ...) -> Any:
    """Declare a name or attribute key: lowercase identifier, used in files, charts and page text."""
    return param(default, title=title, description=f"{description} ({KEY_HELP}).", pattern=KEY_PATTERN)


class ParamGroup(BaseModel):
    """Base for every parameter group: unknown keys, NaN and infinity are rejected; instances are immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


def _unique(values: list[str], what: str) -> None:
    """Raise ValueError naming the first duplicate in `values`."""
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"The {what} {value!r} is used twice; names must be unique.")
        seen.add(value)


def _shares_sum_to_one(shares: list[float], what: str) -> None:
    """Raise ValueError unless the shares add up to 1 within SHARE_TOLERANCE."""
    total = math.fsum(shares)
    if abs(total - 1.0) > SHARE_TOLERANCE:
        raise ValueError(f"The {what} shares add up to {total:.6g}; they must add up to 1.")


# --- run ---------------------------------------------------------------------------------------------------------


class RunParams(ParamGroup):
    """How a run is seeded and repeated."""

    seed: int | None = param(
        None,
        title="Random seed",
        description=(
            "Runs with the same seed and parameters give identical results, and changing one parameter then changes "
            "only what depends on it. Leave blank to draw a new seed for every run (the seed used is stored with the "
            "results)."
        ),
        ge=0,
        le=2**63 - 1,
    )
    replicates: int = param(
        1,
        title="Replicates",
        description="Independent repeats of the random stages, for averages and uncertainty bands.",
        implemented=False,
        ge=1,
        le=1000,
    )
    resample_population: bool = param(
        False,
        title="New population per replicate",
        description=(
            "Off: every replicate keeps the same applicants, programs and true preferences, so only process noise "
            "varies. On: every replicate draws a new market."
        ),
        implemented=False,
    )
    ci_level: float = param(
        0.95,
        title="Confidence level",
        description="Confidence level of the intervals reported over replicates.",
        implemented=False,
        ge=0.5,
        le=0.99,
    )


# --- market ------------------------------------------------------------------------------------------------------


class MarketParams(ParamGroup):
    """Market size and tightness."""

    n_applicants: int = param(
        1000,
        title="Applicants",
        description="Number of applicants in the market.",
        ge=10,
        le=60_000,
    )
    applicants_per_position: float = param(
        1.08,
        title="Applicants per position",
        description=(
            "Market tightness: applicants divided by positions, which sets the number of positions (NRMP 2026 Main "
            "Match: 48,050 applicants for 44,344 positions, about 1.08)."
        ),
        ge=0.5,
        le=3.0,
    )
    n_programs: int | None = param(
        None,
        title="Programs",
        description="Number of programs. Leave blank to derive it from the positions and the mean program size.",
        ge=1,
        le=7_000,
    )
    program_size_dist: Literal["fixed", "lognormal", "shifted_multinomial"] = param(
        "lognormal",
        title="Program sizes",
        description=(
            "How the positions are spread over programs; every program has at least one. Fixed: as equal as "
            "possible. Lognormal: right-skewed, like real programs. Shifted multinomial: random, close to 1 + Poisson."
        ),
    )
    program_size_mean: float = param(
        6.5,
        title="Mean positions per program",
        description=(
            "Average program size, used to derive the number of programs when it is blank (NRMP 2026: 44,344 "
            "positions in 6,809 programs, about 6.5)."
        ),
        unit="positions",
        ge=1,
        le=60,
    )
    program_size_dispersion: float = param(
        0.8,
        title="Program size spread",
        description="Spread of lognormal program sizes (SD of the log size); 0 makes them as equal as possible.",
        level="advanced",
        ge=0,
        le=3,
    )

    def n_positions(self, n_applicants: int | None = None) -> int:
        """Return the number of positions P = max(1, round(N / applicants per position)) (round half to even)."""
        n = self.n_applicants if n_applicants is None else n_applicants
        return max(1, round(n / self.applicants_per_position))

    def resolved_n_programs(self, n_positions: int | None = None) -> int:
        """Return M: `n_programs` if set, else max(1, round(P / mean program size))."""
        if self.n_programs is not None:
            return self.n_programs
        positions = self.n_positions() if n_positions is None else n_positions
        return max(1, round(positions / self.program_size_mean))

    @model_validator(mode="after")
    def _check_shape(self) -> MarketParams:
        positions = self.n_positions()
        programs = self.resolved_n_programs(positions)
        if programs > positions:
            raise ValueError(
                f"{programs:,} programs need at least {programs:,} positions, but {self.n_applicants:,} applicants at "
                f"{self.applicants_per_position:g} applicants per position give only {positions:,}. Use fewer programs "
                "or fewer applicants per position."
            )
        pairs = self.n_applicants * programs
        if pairs > MAX_PAIRS:
            raise ValueError(
                f"{self.n_applicants:,} applicants x {programs:,} programs = {pairs:,} pairs, above the model's limit "
                f"of {MAX_PAIRS:,}."
            )
        return self


# --- applicants and programs ------------------------------------------------------------------------------------


class ApplicantGroup(ParamGroup):
    """One applicant group (for example US MD seniors) with its share and strength distribution."""

    name: str = key_field("Name", "Group name, for example us_md")
    share: float = param(
        title="Share", description="Fraction of applicants in this group; the shares add up to 1.", gt=0, le=1
    )
    strength_mean: float = param(
        0.0,
        title="Strength mean",
        description="Mean latent strength of the group, in SD units; only differences between groups matter.",
        unit="SD",
        ge=-3,
        le=3,
    )
    strength_sd: float = param(
        1.0, title="Strength SD", description="Spread of strength within the group.", unit="SD", gt=0, le=3
    )
    applications_mean: float | None = param(
        None,
        title="Applications (mean)",
        description="Mean applications for this group; blank uses the overall mean.",
        ge=1,
        le=7_000,
    )
    n_signals: int | None = param(
        None,
        title="Signals",
        description="Most signals an applicant in this group sends; blank uses the signal tiers in full.",
        ge=0,
        le=100,
    )


class ApplicantAttribute(ParamGroup):
    """An applicant attribute that programs evaluate, for example board_scores."""

    key: str = key_field("Attribute", "Attribute name, for example board_scores")
    corr_with_strength: float = param(
        0.5,
        title="Correlation with strength",
        description="How closely this attribute tracks the applicant's overall strength (0 = unrelated, 1 = the same).",
        ge=0,
        le=1,
    )
    program_weight_prior: float = param(
        0.2,
        title="Average weight",
        description="How much programs value this attribute on average, relative to the others (renormalised to 1).",
        gt=0,
        le=100,
    )


def default_groups() -> list[ApplicantGroup]:
    """Return the default applicant groups (model_spec.md §11; NRMP-like shares)."""
    return [
        ApplicantGroup(name="us_md", share=0.44, strength_mean=0.5),
        ApplicantGroup(name="us_do", share=0.18, strength_mean=0.35),
        ApplicantGroup(name="us_img", share=0.09, strength_mean=-1.0),
        ApplicantGroup(name="non_us_img", share=0.25, strength_mean=-1.3),
        ApplicantGroup(name="other", share=0.04, strength_mean=-0.5),
    ]


def default_applicant_attributes() -> list[ApplicantAttribute]:
    """Return the default applicant attributes (model_spec.md §4.2 and §4.4)."""
    return [
        ApplicantAttribute(key="board_scores", corr_with_strength=0.8, program_weight_prior=0.5),
        ApplicantAttribute(key="research", corr_with_strength=0.5, program_weight_prior=0.3),
        ApplicantAttribute(key="honors", corr_with_strength=0.6, program_weight_prior=0.2),
    ]


class ApplicantsParams(ParamGroup):
    """Who the applicants are and what programs evaluate about them."""

    groups: list[ApplicantGroup] = param(
        title="Applicant groups",
        description="Applicant types, their shares and strength distributions.",
        default_factory=default_groups,
        min_length=1,
        max_length=MAX_GROUPS,
    )
    attributes: list[ApplicantAttribute] = param(
        title="Applicant attributes",
        description="What programs evaluate about applicants.",
        default_factory=default_applicant_attributes,
        min_length=1,
        max_length=MAX_ATTRIBUTES,
    )

    @field_validator("groups")
    @classmethod
    def _check_groups(cls, groups: list[ApplicantGroup]) -> list[ApplicantGroup]:
        _unique([group.name for group in groups], "group name")
        _shares_sum_to_one([group.share for group in groups], "group")
        return groups

    @field_validator("attributes")
    @classmethod
    def _check_attributes(cls, attributes: list[ApplicantAttribute]) -> list[ApplicantAttribute]:
        _unique([attribute.key for attribute in attributes], "applicant attribute")
        return attributes


class ProgramTier(ParamGroup):
    """An optional program quality tier."""

    name: str = key_field("Name", "Tier name, for example top")
    share: float = param(
        title="Share", description="Fraction of programs in this tier; the shares add up to 1.", gt=0, le=1
    )
    quality_mean: float = param(
        0.0,
        title="Quality mean",
        description="Mean latent quality of the tier, relative to the within-tier spread.",
        unit="SD",
        ge=-3,
        le=3,
    )


class ProgramAttribute(ParamGroup):
    """A program attribute that applicants evaluate, for example reputation."""

    key: str = key_field("Attribute", "Attribute name, for example reputation")
    corr_with_quality: float = param(
        0.5,
        title="Correlation with quality",
        description=(
            "How closely this attribute tracks the program's overall quality. Ignored for program_size, which is "
            "computed from the program's positions."
        ),
        ge=0,
        le=1,
    )
    applicant_weight_prior: float = param(
        0.2,
        title="Average weight",
        description="How much applicants value this attribute on average, relative to the others (renormalised to 1).",
        gt=0,
        le=100,
    )


def default_program_attributes() -> list[ProgramAttribute]:
    """Return the default program attributes (model_spec.md §4.2 and §4.4)."""
    return [
        ProgramAttribute(key="reputation", corr_with_quality=0.9, applicant_weight_prior=0.5),
        ProgramAttribute(key="program_size", corr_with_quality=0.0, applicant_weight_prior=0.2),
        ProgramAttribute(key="location", corr_with_quality=0.0, applicant_weight_prior=0.3),
    ]


class ProgramsParams(ParamGroup):
    """Program quality and what applicants evaluate about programs."""

    quality_sd: float = param(
        1.0,
        title="Quality SD within tiers",
        description="Spread of latent quality within a tier. Without tiers it has no effect on results.",
        unit="SD",
        level="advanced",
        gt=0,
        le=3,
    )
    tiers: list[ProgramTier] = param(
        title="Program tiers",
        description="Optional quality tiers; leave empty for one tier with mean 0.",
        default_factory=list,
        max_length=MAX_TIERS,
        level="advanced",
    )
    attributes: list[ProgramAttribute] = param(
        title="Program attributes",
        description="What applicants evaluate about programs.",
        default_factory=default_program_attributes,
        min_length=1,
        max_length=MAX_ATTRIBUTES,
    )

    @field_validator("tiers")
    @classmethod
    def _check_tiers(cls, tiers: list[ProgramTier]) -> list[ProgramTier]:
        _unique([tier.name for tier in tiers], "tier name")
        if tiers:
            _shares_sum_to_one([tier.share for tier in tiers], "tier")
        return tiers

    @field_validator("attributes")
    @classmethod
    def _check_attributes(cls, attributes: list[ProgramAttribute]) -> list[ProgramAttribute]:
        _unique([attribute.key for attribute in attributes], "program attribute")
        return attributes


# --- preferences and information --------------------------------------------------------------------------------


class PrefsParams(ParamGroup):
    """How much the two sides agree (model_spec.md §4.4-5)."""

    applicant_pref_correlation: float = param(
        0.6,
        title="Applicant agreement",
        description=(
            "How similarly applicants rank programs: the average correlation between two applicants' true utilities "
            "(1 = everyone agrees, 0 = purely personal tastes)."
        ),
        ge=0,
        le=1,
    )
    program_pref_correlation: float = param(
        0.7,
        title="Program agreement",
        description="How similarly programs rank applicants (1 = all programs agree, 0 = purely personal).",
        ge=0,
        le=1,
    )
    attribute_weight_share: float = param(
        0.3,
        title="Attribute share of the common view",
        description=(
            "Mixing weight of the average-weighted attributes, rather than latent quality or strength, in the view "
            "everyone shares."
        ),
        level="advanced",
        ge=0,
        le=1,
    )
    taste_share: float = param(
        0.5,
        title="Taste share of personal preferences",
        description=(
            "Part of the personal (non-shared) utility that comes from individual attribute weights rather than "
            "pure fit."
        ),
        ge=0,
        le=1,
    )
    weight_concentration: float = param(
        10.0,
        title="Weight concentration",
        description=(
            "Shape of individual attribute weights: low values give sparse tastes (one attribute dominates), high "
            "values keep everyone's weights close to the average. It does not change how much agents agree."
        ),
        level="advanced",
        ge=0.1,
        le=1000,
    )


class InfoParams(ParamGroup):
    """How accurately each side sees the other (model_spec.md §6-7)."""

    applicant_pre_noise_sd: float = param(
        0.5,
        title="Applicant pre-interview noise",
        description=(
            "Error in applicants' view of programs before interviews, in utility SD units: 0 = perfect information, "
            "0.5 keeps a correlation of about 0.89 between true and perceived utility."
        ),
        unit="SD",
        ge=0,
        le=3,
    )
    program_pre_noise_sd: float = param(
        0.5,
        title="Program pre-interview noise",
        description="Error in programs' view of applicants from the application alone, in utility SD units.",
        unit="SD",
        ge=0,
        le=3,
    )
    interview_informativeness: float = param(
        0.6,
        title="Interview informativeness",
        description="How much an interview shrinks the pre-interview error (0 = not at all, 1 = reveals the truth).",
        ge=0,
        le=1,
    )
    fit_shock_sd: float = param(
        0.3,
        title="Interview fit shock",
        description="New fit, good or bad, that only shows at the interview.",
        unit="SD",
        ge=0,
        le=2,
    )
    visibility_heteroskedasticity: float = param(
        0.0,
        title="Visibility effect",
        description="Extra pre-interview error for less-known programs and applicants (0 = the same error for all).",
        level="advanced",
        ge=0,
        le=2,
    )
    halo_share: float = param(
        0.0,
        title="Shared error (halo)",
        description=(
            "Part of the pre-interview error that everyone makes about the same program or applicant, so errors "
            "herd (0 = independent errors)."
        ),
        level="advanced",
        ge=0,
        le=1,
    )


# --- from applications to the match (model_spec.md §7-8) ------------------------------------------------------


class PortfolioShares(ParamGroup):
    """The reach / target / safety mix of the portfolio application strategy."""

    reach: float = param(0.25, title="Reach", description="Share of applications to reach programs.", ge=0, le=1)
    target: float = param(0.5, title="Target", description="Share of applications to target programs.", ge=0, le=1)
    safety: float = param(0.25, title="Safety", description="Share of applications to safety programs.", ge=0, le=1)


class AppsParams(ParamGroup):
    """Applications (model_spec.md §7.1)."""

    count_dist: Literal["fixed", "poisson", "negbin"] = param(
        "negbin",
        title="Application count",
        description="Distribution of the number of applications per applicant.",
    )
    mean: float = param(
        30.0,
        title="Applications (mean)",
        description=(
            "Mean applications per applicant; a group's own mean replaces it (ERAS 2025-26 real average: about 82)."
        ),
        ge=1,
        le=7_000,
    )
    dispersion: float = param(
        0.5,
        title="Application dispersion",
        description="Spread of the negative-binomial application count: the variance is mean + dispersion x mean².",
        level="advanced",
        ge=0.01,
        le=10,
    )
    strategy: Literal["top_n", "portfolio", "all", "random"] = param(
        "portfolio",
        title="Application strategy",
        description=(
            "How applicants choose programs: the best by their pre-interview view (top n), a reach / target / safety "
            "portfolio, every program, or at random."
        ),
    )
    portfolio_shares: PortfolioShares = param(
        title="Portfolio mix",
        description="Reach, target and safety shares of the portfolio strategy; they add up to 1.",
        default_factory=PortfolioShares,
    )
    target_band: float = param(
        0.15,
        title="Target band",
        description=(
            "How close a program's prestige percentile must be to the applicant's self-assessed standing to count "
            "as a target (portfolio strategy and realistic signals)."
        ),
        level="advanced",
        ge=0,
        le=0.5,
    )
    self_assessment_noise_sd: float = param(
        0.5,
        title="Self-assessment error",
        description="Error in applicants' estimate of their own competitiveness (0 = perfect self-knowledge).",
        unit="SD",
        ge=0,
        le=2,
    )


class SignalTier(ParamGroup):
    """A preference-signal tier, for example gold."""

    name: str = key_field("Name", "Tier name, for example gold")
    count: int = param(1, title="Signals", description="Signals per applicant in this tier.", ge=1, le=100)
    boost: float = param(
        0.4, title="Screening boost", description="Boost to the program's screening score.", unit="SD", ge=0, le=3
    )


class SignalsParams(ParamGroup):
    """Preference signals (model_spec.md §7.2)."""

    tiers: list[SignalTier] = param(
        title="Signal tiers",
        description="Signal tiers, for example gold 3 / boost 0.8 and silver 12 / boost 0.4.",
        default_factory=list,
        max_length=MAX_SIGNAL_TIERS,
    )
    allocation: Literal["top_utility", "realistic", "random"] = param(
        "realistic",
        title="Signal allocation",
        description="Where applicants send their signals.",
    )
    program_use_share: float = param(
        1.0,
        title="Programs using signals",
        description="Share of programs that use signals when screening.",
        ge=0,
        le=1,
    )
    use_in_ranking: bool = param(
        False,
        title="Signals affect rank lists",
        description="Whether a signal also affects programs' rank lists.",
    )


class InvitesParams(ParamGroup):
    """Screening and interview invitations (model_spec.md §7.3)."""

    interviews_per_position: float = param(
        10.0,
        title="Interviews per position",
        description="Interview slots per position: each program has ceil(ratio x positions) slots.",
        ge=1,
        le=30,
    )
    strategy: Literal["top_score", "threshold_then_top", "threshold_then_random", "signal_first"] = param(
        "top_score",
        title="Invitation strategy",
        description=(
            "How programs choose whom to invite: by screening score; after the hard screen by score or at random; "
            "or signalled applicants first."
        ),
    )
    screen_attribute: str | None = param(
        None,
        title="Screening attribute",
        description="Applicant attribute used as a hard screen (blank = none).",
        level="advanced",
        pattern=KEY_PATTERN,
    )
    screen_min_percentile: float = param(
        0.0,
        title="Screening minimum percentile",
        description=(
            "Applicants below this percentile of the screening attribute are not invited (threshold strategies)."
        ),
        level="advanced",
        ge=0,
        le=1,
    )
    yield_protection: float = param(
        0.0,
        title="Yield protection",
        description=(
            "Screening penalty per percentile an applicant stands above the program, unless they signalled it."
        ),
        level="advanced",
        ge=0,
        le=2,
    )
    rounds: int = param(
        3,
        title="Invitation rounds",
        description="Invitation waves; programs invite again to fill the slots that were declined.",
        ge=1,
        le=10,
    )


class InterviewParams(ParamGroup):
    """Interviews (model_spec.md §7.3-7.4); interview dates are planned."""

    applicant_cap: int = param(
        12,
        title="Interviews per applicant (max)",
        description="The most interviews an applicant accepts and attends.",
        ge=1,
        le=50,
    )
    acceptance_order: Literal["best_first", "first_come"] = param(
        "first_come",
        title="Acceptance order",
        description=(
            "In which order applicants accept invitations: the best first (by pre-interview view), or in the order "
            "they arrive."
        ),
    )
    n_dates: int = param(
        0,
        title="Interview dates",
        description="Number of interview dates for scheduling conflicts (0 = no conflicts).",
        implemented=False,
        level="advanced",
        ge=0,
        le=60,
    )
    dates_per_program: int = param(
        3,
        title="Dates per program",
        description="Interview dates each program offers.",
        implemented=False,
        level="advanced",
        ge=1,
        le=10,
    )


class RolParams(ParamGroup):
    """Rank order lists (model_spec.md §8)."""

    applicant_policy: Literal["all_interviewed", "top_k", "above_reservation", "truncate_k", "likelihood_weighted"] = (
        param(
            "all_interviewed",
            title="Applicant rank lists",
            description=(
                "Which interviewed programs applicants rank: all, the top k, those above the reservation utility, or "
                "all with the ones they are less likely to match moved down (likelihood weighted)."
            ),
        )
    )
    applicant_top_k: int = param(
        20,
        title="Applicant list length",
        description="List length for the top-k policies.",
        ge=1,
        le=300,
    )
    reservation_utility: float = param(
        -1.0,
        title="Reservation utility",
        description=(
            "Applicants (above-reservation policy) and programs (do-not-rank threshold) rank only above this "
            "post-interview utility."
        ),
        unit="SD",
        level="advanced",
        ge=-5,
        le=5,
    )
    program_policy: Literal["all_interviewed", "dnr_quantile", "dnr_threshold"] = param(
        "dnr_quantile",
        title="Program rank lists",
        description=(
            "Which interviewed applicants programs rank: all, all but the bottom share, or those above the "
            "reservation utility."
        ),
    )
    program_dnr_quantile: float = param(
        0.1,
        title="Do-not-rank share",
        description="Bottom share of interviewees a program does not rank.",
        ge=0,
        le=0.9,
    )


class MatchParams(ParamGroup):
    """The matching mechanism (model_spec.md §8)."""

    algorithm: Literal["applicant_proposing", "program_proposing"] = param(
        "applicant_proposing",
        title="Algorithm",
        description="Deferred acceptance proposed by applicants (as the NRMP) or by programs.",
    )
    compare_both: bool = param(
        False,
        title="Compare both sides proposing",
        description="Also run the other proposing side and report the differences.",
    )


# --- the whole schema ------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ParamWarning:
    """A soft problem with the parameters: `path` is the group or field it concerns."""

    path: str
    message: str


class SimulationParams(ParamGroup):
    """All parameters of a simulation (schema v1)."""

    schema_version: Literal[1] = Field(1, title="Schema version", description="Version of this parameter schema.")
    run: RunParams = param(title="Run", description="Seed and repeats.", default_factory=RunParams)
    market: MarketParams = param(title="Market", description="Size and tightness.", default_factory=MarketParams)
    applicants: ApplicantsParams = param(
        title="Applicants", description="Groups and attributes.", default_factory=ApplicantsParams
    )
    programs: ProgramsParams = param(
        title="Programs", description="Quality, tiers and attributes.", default_factory=ProgramsParams
    )
    prefs: PrefsParams = param(title="Preferences", description="Agreement and tastes.", default_factory=PrefsParams)
    info: InfoParams = param(title="Information", description="Noise and interviews.", default_factory=InfoParams)
    apps: AppsParams = param(
        title="Applications",
        description="How many programs applicants apply to, and which.",
        default_factory=AppsParams,
    )
    signals: SignalsParams = param(
        title="Signals", description="Preference signals and how programs use them.", default_factory=SignalsParams
    )
    invites: InvitesParams = param(
        title="Invitations",
        description="Interview slots, screening and invitation waves.",
        default_factory=InvitesParams,
    )
    interview: InterviewParams = param(
        title="Interviews", description="How many interviews applicants accept.", default_factory=InterviewParams
    )
    rol: RolParams = param(
        title="Rank order lists", description="Who ranks whom after interviews.", default_factory=RolParams
    )
    match: MatchParams = param(title="Match", description="The matching algorithm.", default_factory=MatchParams)

    # Derived market shape (model_spec.md §4.3).

    def n_positions(self, n_applicants: int | None = None) -> int:
        """Return the number of positions for `n_applicants` (default: the parameter)."""
        return self.market.n_positions(n_applicants)

    def n_programs(self, n_applicants: int | None = None) -> int:
        """Return the number of programs for `n_applicants` (default: the parameter)."""
        return self.market.resolved_n_programs(self.n_positions(n_applicants))

    def warnings(self) -> list[ParamWarning]:
        """Return soft problems: unusual but valid settings, and cross-field rules on planned stages."""
        found: list[ParamWarning] = []
        ratio = self.market.applicants_per_position
        if not 0.7 <= ratio <= 1.6:
            found.append(
                ParamWarning(
                    "market.applicants_per_position",
                    f"{ratio:g} applicants per position is unusual; real markets are between about 0.7 and 1.6.",
                )
            )
        for side, attributes, judge in (
            ("applicants", self.applicants.attributes, "programs"),
            ("programs", self.programs.attributes, "applicants"),
        ):
            if len(attributes) < 2 and self.prefs.taste_share > 0:
                found.append(
                    ParamWarning(
                        f"{side}.attributes",
                        f"With one {side[:-1]} attribute, {judge} cannot differ in taste: the personal part of their "
                        "utilities is pure fit, whatever the taste share.",
                    )
                )
        # Settings that are valid but work against each other.
        n_programs = self.n_programs()
        max_signals = max((tier.count for tier in self.signals.tiers), default=0)
        if not max_signals <= self.apps.mean <= n_programs:
            found.append(
                ParamWarning(
                    "apps.mean",
                    f"The mean number of applications ({self.apps.mean:g}) should be at least the largest "
                    f"signal count ({max_signals}) and at most the number of programs ({n_programs:,}).",
                )
            )
        shares = self.apps.portfolio_shares
        if abs(math.fsum((shares.reach, shares.target, shares.safety)) - 1.0) > SHARE_TOLERANCE:
            found.append(
                ParamWarning(
                    "apps.portfolio_shares",
                    "The portfolio shares should add up to 1; the target share is what remains after reach and safety.",
                )
            )
        slots = self.invites.interviews_per_position * self.n_positions()
        if slots / self.market.n_applicants < self.interview.applicant_cap / 2:
            found.append(
                ParamWarning(
                    "invites.interviews_per_position",
                    f"{slots / self.market.n_applicants:.1f} interview slots per applicant is less than half "
                    f"the interview cap ({self.interview.applicant_cap}), so most applicants could never reach it.",
                )
            )
        keys = {attribute.key for attribute in self.applicants.attributes}
        if self.invites.screen_attribute is not None and self.invites.screen_attribute not in keys:
            found.append(
                ParamWarning(
                    "invites.screen_attribute",
                    f"The screening attribute {self.invites.screen_attribute!r} is not an applicant attribute.",
                )
            )
        return found

    # Serialisation and fingerprints.

    def to_json_data(self) -> dict[str, Any]:
        """Return the parameters as JSON-compatible data (what is stored)."""
        return self.model_dump(mode="json")

    def canonical_json(self) -> str:
        """Return the parameters as canonical JSON (sorted keys, no spaces), the input of `params_hash`."""
        return canonical_json(self.to_json_data())

    def params_hash(self) -> str:
        """Return the SHA-256 of the canonical JSON."""
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    def implemented_data(self) -> dict[str, Any]:
        """Return the JSON data without the parameters the engine does not use yet."""
        data: dict[str, Any] = _implemented(type(self), self.to_json_data())
        return data

    def with_seed(self, seed: int | None) -> SimulationParams:
        """Return a validated copy with `run.seed` replaced (raises ValidationError for a bad seed)."""
        data = self.to_json_data()
        data["run"]["seed"] = seed
        return SimulationParams.model_validate(data)


def canonical_json(data: Any) -> str:
    """Serialise JSON data canonically: sorted keys, no whitespace, no NaN."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _is_implemented(field: FieldInfo) -> bool:
    extra = field.json_schema_extra
    return not isinstance(extra, dict) or extra.get("implemented", True) is not False


def _model_type(annotation: Any) -> type[BaseModel] | None:
    """Return the model class of a field annotation that is a model or a list of models, else None."""
    args = getattr(annotation, "__args__", ())
    for candidate in (annotation, *args):
        if isinstance(candidate, type) and issubclass(candidate, BaseModel):
            return candidate
    return None


def _implemented(model: type[BaseModel], data: Any) -> Any:
    """Drop the fields marked implemented=False from JSON data of `model`, recursively."""
    if not isinstance(data, dict):
        return data
    result: dict[str, Any] = {}
    for name, field in model.model_fields.items():
        if name not in data or not _is_implemented(field):
            continue
        value = data[name]
        sub = _model_type(field.annotation)
        if sub is None:
            result[name] = value
        elif isinstance(value, list):
            result[name] = [_implemented(sub, item) for item in value]
        else:
            result[name] = _implemented(sub, value)
    return result


# Implemented stages and the parameters each reads (model_spec.md). A path selects a group or a field; "[a,b]" after a
# list keeps only those fields of its items. Fingerprints hash these, the seed and the upstream stage's fingerprint,
# so a stage is stale exactly when something it depends on changed.
STAGE_INPUTS: dict[str, tuple[str, ...]] = {
    "population": (
        "market",
        "applicants.groups[name,share,strength_mean,strength_sd]",
        "applicants.attributes",
        "programs",
        "prefs.weight_concentration",
    ),
    "pre_interview": (
        "prefs",
        "info.applicant_pre_noise_sd",
        "info.program_pre_noise_sd",
        "info.visibility_heteroskedasticity",
        "info.halo_share",
    ),
    "applications": ("apps", "applicants.groups[name,applications_mean]"),
    "signals": ("signals", "applicants.groups[name,n_signals]"),
    "invitations": ("invites", "interview.applicant_cap", "interview.acceptance_order"),
    "interviews": ("info.interview_informativeness", "info.fit_shock_sd"),
    "rank_lists": ("rol", "signals.use_in_ranking"),
    "match": ("match",),
}


def _select(data: Any, path: str) -> Any:
    """Return the value at a dotted STAGE_INPUTS path, projecting list items to the fields in brackets."""
    fields: list[str] = []
    if path.endswith("]"):
        path, _, selection = path[:-1].partition("[")
        fields = selection.split(",")
    value: Any = data
    for part in path.split("."):
        value = value[part]
    if fields:
        return [{name: item.get(name) for name in fields} for item in value]
    return value


def stage_inputs(params: SimulationParams, stage: str) -> dict[str, Any]:
    """Return the implemented parameters `stage` reads, keyed by their STAGE_INPUTS path."""
    data = params.implemented_data()
    return {path: _select(data, path) for path in STAGE_INPUTS[stage]}


# --- loading and field descriptions ------------------------------------------------------------------------------

# Upgrades from older schema versions, keyed by the version they upgrade from. Schema v1 is the first.
UPGRADES: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def load_params(data: dict[str, Any] | None) -> SimulationParams:
    """Validate stored parameters, upgrading older schema versions first. Empty data gives the defaults."""
    data = dict(data or {})
    version = int(data.get("schema_version", SCHEMA_VERSION))
    while version < SCHEMA_VERSION:
        data = UPGRADES[version](data)
        version = int(data["schema_version"])
    return SimulationParams.model_validate(data)


@dataclass(frozen=True)
class ParamField:
    """A leaf parameter, for forms and the help page."""

    path: str
    title: str
    description: str
    unit: str
    implemented: bool
    level: str
    default: Any
    minimum: float | None
    maximum: float | None
    exclusive_minimum: bool
    choices: tuple[str, ...]
    field: FieldInfo


def _bounds(field: FieldInfo) -> tuple[float | None, float | None, bool]:
    """Return (minimum, maximum, minimum is exclusive) from a field's ge/gt/le/lt constraints."""
    minimum = maximum = None
    exclusive = False
    for constraint in field.metadata:
        if (value := getattr(constraint, "ge", None)) is not None:
            minimum = value
        if (value := getattr(constraint, "gt", None)) is not None:
            minimum, exclusive = value, True
        if (value := getattr(constraint, "le", None)) is not None:
            maximum = value
        if (value := getattr(constraint, "lt", None)) is not None:
            maximum = value
    return minimum, maximum, exclusive


def _choices(annotation: Any) -> tuple[str, ...]:
    if getattr(annotation, "__origin__", None) is Literal:
        return tuple(str(arg) for arg in annotation.__args__)
    return ()


def iter_fields(model: type[BaseModel], prefix: str = "", implemented: bool = True) -> Iterator[ParamField]:
    """Yield the scalar parameters of `model` in declaration order, descending into nested groups.

    Lists of groups (applicant groups, attributes, tiers) are not descended into; `iter_fields` on their item model
    describes their columns. A field inside a group marked implemented=False is reported as not implemented.
    """
    for name, field in model.model_fields.items():
        if name == "schema_version":
            continue
        path = f"{prefix}{name}"
        is_implemented = implemented and _is_implemented(field)
        sub = _model_type(field.annotation)
        if sub is not None:
            if getattr(field.annotation, "__origin__", None) is list:
                continue
            yield from iter_fields(sub, f"{path}.", is_implemented)
            continue
        extra = field.json_schema_extra if isinstance(field.json_schema_extra, dict) else {}
        minimum, maximum, exclusive = _bounds(field)
        yield ParamField(
            path=path,
            title=field.title or name,
            description=field.description or "",
            unit=str(extra.get("unit", "")),
            implemented=is_implemented,
            level=str(extra.get("level", "basic")),
            default=field.get_default(call_default_factory=True),
            minimum=minimum,
            maximum=maximum,
            exclusive_minimum=exclusive,
            choices=_choices(field.annotation),
            field=field,
        )


def list_fields(model: type[BaseModel] = SimulationParams, prefix: str = "") -> Iterator[tuple[str, FieldInfo, type]]:
    """Yield (path, field, item model) for every list-of-groups parameter, for example applicants.groups."""
    for name, field in model.model_fields.items():
        sub = _model_type(field.annotation)
        if sub is None:
            continue
        path = f"{prefix}{name}"
        if getattr(field.annotation, "__origin__", None) is list:
            yield path, field, sub
        else:
            yield from list_fields(sub, f"{path}.")
