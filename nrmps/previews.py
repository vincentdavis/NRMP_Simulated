"""The live preview beside the parameter form (plan step 4.2): what draft parameters give before anything runs.

`market_preview` returns the market's size and tightness, the interview slots and applications they imply, the size
limit, the parameters' warnings, and small inline-SVG pictures of the distributions they ask for: applicant strength
and program quality (the normal mixtures of the groups and tiers) and positions per program (drawn exactly as a run
would, from the seed). The simulation page shows it for the saved parameters and asks for it again, with HTMX, as
the form is edited.
"""

import math
from dataclasses import dataclass, field

import numpy as np

from .engine.population import PopulationError, generate_capacities
from .limits import market_size_error, max_pairs
from .models import PopulationUpload
from .params import ParamWarning, SimulationParams
from .params_forms import IMPLEMENTED_SECTIONS

WIDTH, HEIGHT = 240, 56  # the SVG viewBox of every picture
POINTS = 81


@dataclass
class Picture:
    """A small SVG picture: a filled density curve (`path`) or histogram bars (`bars`), with its range."""

    title: str
    description: str
    low: str
    high: str
    path: str = ""
    bars: list[dict[str, str]] = field(default_factory=list)  # SVG attributes, already formatted


@dataclass
class MarketPreview:
    """What a set of parameters gives, for the preview panel."""

    applicants: int
    programs: int
    positions: int | None
    applicants_per_position: float | None
    pairs: int
    max_pairs: int
    size_error: str | None
    applications: int
    signals: int
    interview_slots: int | None
    applicant_cap: int
    sources: dict[str, str]
    warnings: list[ParamWarning]
    pictures: list[Picture]


def _density(components: list[tuple[float, float, float]], title: str, what: str) -> Picture:
    """Return the picture of a mixture of normals (share, mean, sd) over mean ± 3.5 SD."""
    spread = [(share, mean, max(sd, 0.05)) for share, mean, sd in components if share > 0]
    low = min(mean - 3.5 * sd for _share, mean, sd in spread)
    high = max(mean + 3.5 * sd for _share, mean, sd in spread)
    x = np.linspace(low, high, POINTS)
    y = np.zeros(POINTS)
    for share, mean, sd in spread:
        y += share * np.exp(-0.5 * ((x - mean) / sd) ** 2) / (sd * math.sqrt(2 * math.pi))
    peak = float(y.max()) or 1.0
    xs = (x - low) / (high - low) * WIDTH
    ys = HEIGHT - 2 - y / peak * (HEIGHT - 4)
    points = " ".join(f"L{a:.1f},{b:.1f}" for a, b in zip(xs, ys, strict=True))
    path = f"M0,{HEIGHT} {points} L{WIDTH},{HEIGHT} Z"
    means = ", ".join(f"{share:.0%} around {mean:+.2f} (SD {sd:.2f})" for share, mean, sd in components if share > 0)
    return Picture(title, f"{what}: {means}.", f"{low:.1f}", f"{high:.1f}", path=path)


def _capacity_picture(params: SimulationParams, programs: int, positions: int) -> Picture | None:
    """Return the histogram of positions per program, drawn from the seed as a run would."""
    try:
        capacity = generate_capacities(params, params.run.seed or 0, 0, programs, positions)
    except PopulationError, ValueError:
        return None
    counts, edges = np.histogram(capacity, bins=min(20, max(1, int(capacity.max() - capacity.min()) + 1)))
    peak = int(counts.max()) or 1
    width = WIDTH / counts.size
    bars = []
    for k, count in enumerate(counts.tolist()):
        height = count / peak * (HEIGHT - 4)
        bars.append(
            {
                "x": f"{k * width:.2f}",
                "y": f"{HEIGHT - height:.2f}",
                "width": f"{width * 0.9:.2f}",
                "height": f"{height:.2f}",
            }
        )
    description = (
        f"Positions per program: {programs:,} programs from {int(capacity.min())} to {int(capacity.max())} positions, "
        f"median {float(np.median(capacity)):g}."
    )
    return Picture("Positions per program", description, f"{edges[0]:g}", f"{edges[-1]:g}", bars=bars)


def market_preview(params: SimulationParams, uploads: dict[str, PopulationUpload]) -> MarketPreview:
    """Return what `params` give, with the uploaded sides (if any) in place of generated ones."""
    upload_a, upload_p = uploads.get("applicants"), uploads.get("programs")
    applicants = upload_a.rows if upload_a else params.market.n_applicants
    positions = None if upload_p else params.n_positions(applicants)
    programs = upload_p.rows if upload_p else params.n_programs(applicants)
    slots = None if positions is None else math.ceil(params.invites.interviews_per_position * positions - 1e-9)
    applications = programs if params.apps.strategy == "all" else min(programs, round(params.apps.mean))
    pictures = []
    if not upload_a:
        groups = params.applicants.groups
        pictures.append(
            _density(
                [(g.share, g.strength_mean, g.strength_sd) for g in groups],
                "Applicant strength",
                "Applicant strength by group",
            )
        )
    if not upload_p:
        sd = params.programs.quality_sd
        tiers = [(t.share, t.quality_mean, sd) for t in params.programs.tiers] or [(1.0, 0.0, sd)]
        pictures.append(_density(tiers, "Program quality", "Program quality by tier"))
        if positions is not None and (capacity := _capacity_picture(params, programs, positions)) is not None:
            pictures.append(capacity)
    implemented = set(IMPLEMENTED_SECTIONS)
    return MarketPreview(
        applicants=applicants,
        programs=programs,
        positions=positions,
        applicants_per_position=None if positions is None else applicants / positions,
        pairs=applicants * programs,
        max_pairs=max_pairs(),
        size_error=market_size_error(applicants, programs),
        applications=applications,
        signals=sum(tier.count for tier in params.signals.tiers),
        interview_slots=slots,
        applicant_cap=params.interview.applicant_cap,
        sources={
            "applicants": "uploaded" if upload_a else "generated",
            "programs": "uploaded" if upload_p else "generated",
        },
        warnings=[w for w in params.warnings() if w.path.split(".")[0] in implemented],
        pictures=pictures,
    )
