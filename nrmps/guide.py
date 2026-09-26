"""The user guide at /help/ (plan step 4.4): Markdown pages with formulas, rendered on the server.

Pages live in nrmps/help_content/<slug>.md with a front matter block (title, order, summary). They are rendered with
markdown-it (CommonMark with tables, definition lists and heading anchors; raw HTML is off) and formulas written in
TeX between dollar signs are turned into MathML, which browsers display and screen readers read without any script.

Pages can use two kinds of shortcode, so numbers come from the code rather than being copied into the text:

- `{{name}}` inline: a value such as the default market size (VALUES);
- `[[name]]` alone in a paragraph: a block of HTML such as the parameter reference, the chart catalog or a worked
  example computed by the engine (BLOCKS).
"""

import functools
import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from django.conf import settings
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils.safestring import SafeString, mark_safe
from django.utils.text import slugify
from latex2mathml.converter import convert as tex_to_mathml
from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.deflist import deflist_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

from .engine import ENGINE_VERSION, MODEL_VERSION
from .engine.population import generate_population
from .engine.rng import pair_normals
from .engine.utility import build_market
from .limits import max_pairs
from .params import SimulationParams
from .population_csv import MAX_UPLOAD_BYTES, MAX_UPLOAD_ROWS, columns
from .versions import app_version

CONTENT = Path(__file__).resolve().parent / "help_content"
INDEX = "index"


@dataclass(frozen=True)
class GuidePage:
    """One page of the guide, from its front matter."""

    slug: str
    title: str
    order: int
    summary: str


@dataclass(frozen=True)
class RenderedPage:
    """A rendered page: its HTML (safe: written by us, with raw HTML off) and its sections for the contents list."""

    page: GuidePage
    html: SafeString
    sections: list[tuple[str, str]]  # (id, title) of each level-2 heading
    ids: frozenset[str]


def _front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split the front matter (key: value lines between two --- lines) from the start of a page."""
    match = re.match(r"---\n(.*?)\n---\n", text, flags=re.DOTALL)
    if not match:
        return {}, text
    meta = dict(line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
    return {key.strip(): value.strip() for key, value in meta.items()}, text[match.end() :]


@functools.cache
def guide_pages() -> tuple[GuidePage, ...]:
    """Return the pages of the guide in reading order."""
    pages = []
    for path in CONTENT.glob("*.md"):
        meta, _body = _front_matter(path.read_text(encoding="utf-8"))
        pages.append(
            GuidePage(path.stem, meta.get("title", path.stem), int(meta.get("order", 99)), meta.get("summary", ""))
        )
    return tuple(sorted(pages, key=lambda page: (page.order, page.slug)))


def _math(content: str, options: dict[str, object]) -> str:
    return tex_to_mathml(content, display="block" if options.get("display_mode") else "inline")


def _markdown() -> MarkdownIt:
    return (
        MarkdownIt("commonmark", {"html": False, "typographer": False})
        .enable("table")
        .use(front_matter_plugin)
        .use(deflist_plugin)
        .use(anchors_plugin, min_level=2, max_level=3, permalink=False)
        .use(dollarmath_plugin, renderer=_math, allow_digits=False)
    )


# --- Shortcodes ------------------------------------------------------------------------------------------------------


def _defaults() -> SimulationParams:
    return SimulationParams()


VALUES: dict[str, Callable[[], str]] = {
    "model_version": lambda: MODEL_VERSION,
    "engine_version": lambda: ENGINE_VERSION,
    "app_version": app_version,
    "default_applicants": lambda: f"{_defaults().market.n_applicants:,}",
    "default_positions": lambda: f"{_defaults().n_positions():,}",
    "default_programs": lambda: f"{_defaults().n_programs():,}",
    "max_pairs": lambda: f"{max_pairs():,}",
    "max_upload_mb": lambda: str(MAX_UPLOAD_BYTES // (1024 * 1024)),
    "max_upload_rows": lambda: f"{MAX_UPLOAD_ROWS:,}",
    "applicant_columns": lambda: ",".join(columns(_defaults(), "applicants")),
    "program_columns": lambda: ",".join(columns(_defaults(), "programs")),
    "project_url": lambda: str(getattr(settings, "PROJECT_URL", "")),
    "applicant_sample": lambda: static("samples/applicants_sample.csv"),
    "program_sample": lambda: static("samples/programs_sample.csv"),
}


def _param_reference() -> str:
    from .help_views import parameter_sections  # the reference is built from the schema

    return render_to_string("nrmps/help/_param_reference.html", {"sections": parameter_sections()})


def worked_example(seed: int = 42) -> dict[str, float | int | str]:
    """Return one applicant's utility for one program, term by term, from the default market and `seed`.

    The terms are the engine's own, so the sum shown in the guide is exactly the utility the engine uses (tested).
    """
    params = SimulationParams().with_seed(seed)
    population = generate_population(params, seed)
    model = build_market(params, population, seed)
    side, view = model.applicants, model.applicant_view
    i, j = np.array([0]), np.array([0])
    common = float(side.common[0])
    taste = float(side.pair_taste(i, j)[0])
    fit = float(pair_normals(seed, side.idio_stream, side.idio_replicate, i, j)[0])
    rho, tau = side.sqrt_rho**2, float(side.sqrt_tau[0]) ** 2
    utility = float(side.pair_utilities(i, j)[0])
    error = float(view.pair_error(i, j)[0])
    return {
        "seed": seed,
        "applicant": population.applicants.name(0),
        "program": population.programs.name(0),
        "rho": rho,
        "tau": tau,
        "common": common,
        "taste": taste,
        "fit": fit,
        "utility": utility,
        "error": error,
        "observed": utility + error,
        "sigma": params.info.applicant_pre_noise_sd,
    }


def _worked_example() -> str:
    return render_to_string("nrmps/help/_worked_example.html", {"example": worked_example()})


def chart_catalog() -> list[dict[str, object]]:
    """Return the chart catalog grouped by where the charts appear, in the order of help_registry.CHART_PLACES."""
    from . import help_registry

    return [
        {
            "title": title,
            "charts": [
                {"key": key, "anchor": help_registry.chart_anchor(key), "entry": entry}
                for key, entry in help_registry.CHARTS.items()
                if entry.tab == place
            ],
        }
        for place, title in help_registry.CHART_PLACES.items()
    ]


def _chart_catalog() -> str:
    return render_to_string("nrmps/help/_chart_catalog.html", {"places": chart_catalog()})


BLOCKS: dict[str, Callable[[], str]] = {
    "param_reference": _param_reference,
    "chart_catalog": _chart_catalog,
    "worked_example": _worked_example,
}


def apply_values(text: str) -> str:
    """Replace the `{{name}}` shortcodes in a text with their values."""

    def value(match: re.Match[str]) -> str:
        return VALUES[match.group(1)]()

    return re.sub(r"\{\{\s*([a-z_]+)\s*\}\}", value, text)


def _term_ids(rendered: str) -> str:
    """Give each term of a definition list (the glossary) an id, "term-<slug>", so it can be linked to."""
    taken: set[str] = set()

    def term(match: re.Match[str]) -> str:
        base = "term-" + (slugify(html.unescape(re.sub(r"<[^>]+>", " ", match.group(1)))) or "entry")
        anchor, n = base, 2
        while anchor in taken:
            anchor, n = f"{base}-{n}", n + 1
        taken.add(anchor)
        return f'<dt id="{anchor}">{match.group(1)}</dt>'

    return re.sub(r"<dt>(.*?)</dt>", term, rendered, flags=re.DOTALL)


def _apply_blocks(rendered: str) -> str:
    def block(match: re.Match[str]) -> str:
        return BLOCKS[match.group(1)]()

    return re.sub(r"<p>\[\[([a-z_]+)\]\]</p>", block, rendered)


@functools.cache
def render_page(slug: str) -> RenderedPage:
    """Return a rendered guide page; raise KeyError for an unknown slug."""
    page = next((page for page in guide_pages() if page.slug == slug), None)
    if page is None:
        raise KeyError(slug)
    text = (CONTENT / f"{slug}.md").read_text(encoding="utf-8")
    rendered = _apply_blocks(_term_ids(_markdown().render(apply_values(text))))
    # A wide formula scrolls sideways on a small screen, so keyboard users must be able to focus it.
    rendered = rendered.replace('<div class="math block">', '<div class="math block" tabindex="0">')
    sections = [
        (anchor, html.unescape(re.sub(r"<[^>]+>", "", title)))
        for anchor, title in re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', rendered)
    ]
    ids = frozenset(re.findall(r'id="([^"]+)"', rendered))
    return RenderedPage(page, mark_safe(rendered), sections, ids)  # noqa: S308 (our own content; raw HTML is off)


def help_url_parts(target: str) -> tuple[str, str]:
    """Split a help target "slug#anchor" (or "slug", or "#anchor" on the index) into slug and anchor."""
    slug, _sep, anchor = target.partition("#")
    return slug or INDEX, anchor
