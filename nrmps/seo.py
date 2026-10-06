"""Search engines and link previews: the public pages' titles and descriptions, the sitemap and structured data.

Only the pages of PAGES, of the guide and of the saved example runs (EXAMPLE_PAGES: an example's summary and its
main tabs) are offered to search engines: they get a title and description written for a search result, a canonical
address, a link preview (Open Graph) and structured data, and they are the sitemap. Every other page carries
"noindex": everything behind the login, the login and sign-up forms, searches, and an example's lists and agents.
Addresses are built from `settings.SITE_URL`, so they name one host however a request arrived.

A new public page needs an entry in PAGES (or, for a guide page, `seo_title` and `description` in its front matter);
the tests fail for a public page without one and for a title or description of the wrong length.
"""

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.http import HttpRequest
from django.templatetags.static import static
from django.urls import reverse

from .examples import EXAMPLES, PAGE_LABELS, SavedRun, page_description, page_title, saved_run
from .guide import INDEX, GuidePage, apply_values, guide_pages
from .versions import app_version

SITE_NAME = "NRMP Simulations"
AUTHOR = "Vincent Davis"  # as in CITATION.cff
LICENCE_URL = "https://opensource.org/licenses/MIT"
SOCIAL_CARD = "img/social-card.png"  # the link preview's image, 1200 x 630 (docs/assets/social-card.html)
SOCIAL_CARD_SIZE = (1200, 630)
SOCIAL_CARD_ALT = "NRMP Simulations: simulate the residency Match, for research, teaching and program strategy"

# What a search result shows: titles up to about 60 characters (the site's name follows), descriptions up to 160.
TITLE_LENGTH = (5, 60)
DESCRIPTION_LENGTH = (70, 160)


@dataclass(frozen=True)
class PageMeta:
    """A public page as a search result and a link preview show it."""

    title: str  # without the site's name
    description: str
    kind: str = "website"  # the Open Graph type: "website", or "article" for a page of the guide


# The public pages outside the guide, by URL name.
PAGES: dict[str, PageMeta] = {
    "nrmps:index": PageMeta(
        "Residency Match simulator for research and program strategy",
        "Simulate the residency Match: applications, preference signals, interviews, rank order lists and the "
        "match. Open source, for research, teaching and programs.",
    ),
    "nrmps:demo": PageMeta(
        "Demo markets: run a simulated residency Match",
        "Ready-made markets to run and compare: an NRMP-like market, perfect and noisy information on either side, "
        "and preference signals. See who matches, and where.",
    ),
    "nrmps:examples": PageMeta(
        "Example runs of a simulated residency Match",
        "Saved runs of a simulated residency Match to explore without an account: an NRMP-like market and a small "
        "classroom market, with every chart, table and download.",
    ),
    "nrmps:contact": PageMeta(
        "Contact",
        "How to reach the maintainer of NRMP Simulations, the open-source simulator of the residency Match, with "
        "questions, problems and ideas.",
    ),
    "nrmps:privacy": PageMeta(
        "Privacy",
        "What NRMP Simulations stores about your account and your simulations, how long it keeps it, and how to "
        "download or delete your data.",
    ),
    "nrmps:terms": PageMeta(
        "Terms of use",
        "The terms of using NRMP Simulations, an independent educational and research simulator of the residency "
        "Match that is not affiliated with the NRMP.",
    ),
}


# The pages of a saved example run (nrmps.examples) that are offered to search engines: URL name -> the page's key.
EXAMPLE_PAGES = {
    "nrmps:example_detail": "summary",
    "nrmps:example_population": "population",
    "nrmps:example_pre_interview": "pre_interview",
    "nrmps:example_applications": "applications",
    "nrmps:example_match": "match",
}
# The files of an example that its summary describes as downloads of a dataset: name, title and media type.
EXAMPLE_FILES = (
    ("applicants.csv", "The applicants", "text/csv"),
    ("programs.csv", "The programs", "text/csv"),
    ("match.csv", "The match: every applicant's result", "text/csv"),
    ("program_results.csv", "Every program's results", "text/csv"),
    ("applications.csv", "Every application, from signal to match", "text/csv"),
    ("params.json", "The parameters with the seed", "application/json"),
    ("metrics.json", "The diagnostics and the version stamps", "application/json"),
)


def example_meta(slug: str, page: str) -> PageMeta | None:
    """Return the title and description of page `page` of example `slug`, with the saved run's numbers."""
    if slug not in EXAMPLES:
        return None
    saved = saved_run(slug)
    return PageMeta(page_title(saved.example, page), page_description(saved, page))


def example_path(slug: str, page: str) -> str:
    """Return the path of page `page` (a value of EXAMPLE_PAGES) of example `slug`."""
    name = next(name for name, key in EXAMPLE_PAGES.items() if key == page)
    return reverse(name, kwargs={"slug": slug})


def guide_meta(page: GuidePage) -> PageMeta:
    """Return a guide page's title and description for search engines, from its front matter."""
    return PageMeta(page.seo_title or page.title, apply_values(page.description or page.summary), "article")


def _guide_page(slug: str) -> GuidePage | None:
    return next((page for page in guide_pages() if page.slug == slug), None)


def page_meta(request: HttpRequest) -> PageMeta | None:
    """Return the request's page as search engines may show it, or None for a page they should not index."""
    match = request.resolver_match
    if match is None:
        return None
    if match.view_name in EXAMPLE_PAGES:
        return example_meta(match.kwargs.get("slug", ""), EXAMPLE_PAGES[match.view_name])
    if match.view_name == "nrmps:help":
        page = _guide_page(INDEX)
    elif match.view_name == "nrmps:help_page":
        page = _guide_page(match.kwargs.get("slug", ""))
    else:
        return PAGES.get(match.view_name)
    return guide_meta(page) if page is not None else None


def absolute(path: str) -> str:
    """Return the public address of a path of the site."""
    return f"{settings.SITE_URL}{path}"


def guide_path(page: GuidePage) -> str:
    """Return a guide page's path."""
    return reverse("nrmps:help") if page.slug == INDEX else reverse("nrmps:help_page", kwargs={"slug": page.slug})


def sitemap_urls() -> list[str]:
    """Return the address of every page offered to search engines: PAGES, the examples, the guide in reading order."""
    paths = [reverse(name) for name in PAGES]
    paths += [example_path(slug, page) for slug in EXAMPLES for page in EXAMPLE_PAGES.values()]
    paths += [guide_path(page) for page in guide_pages()]
    return [absolute(path) for path in paths]


def _site() -> dict[str, Any]:
    return {"@type": "WebSite", "@id": absolute("/#website"), "url": absolute("/"), "name": SITE_NAME}


def _breadcrumbs(crumbs: list[tuple[str, str]]) -> dict[str, Any]:
    """Return a page's place in the site: (name, address) from the home page down to the page itself."""
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": position, "name": crumb, "item": address}
            for position, (crumb, address) in enumerate(crumbs, start=1)
        ],
    }


def _dataset(saved: SavedRun, url: str, meta: PageMeta) -> dict[str, Any]:
    """Return a saved example run as a dataset: what it is, its licence and the files to download."""
    run, slug = saved.run, saved.example.slug
    return {
        "@type": "Dataset",
        "@id": f"{url}#dataset",
        "name": meta.title,
        "description": (
            f"{meta.description} Synthetic data from {SITE_NAME}, model {run.model_version}: simulated applicants "
            "and programs, not real applicants, real programs or NRMP data."
        ),
        "url": url,
        "isAccessibleForFree": True,
        "license": LICENCE_URL,
        "creator": {"@type": "Person", "name": AUTHOR},
        "version": str(run.model_version),
        "dateModified": run.created_at.date().isoformat(),
        "keywords": ["residency match", "simulation", "synthetic data", "matching markets", "deferred acceptance"],
        "isPartOf": {"@id": absolute("/#website")},
        "distribution": [
            {
                "@type": "DataDownload",
                "name": title,
                "encodingFormat": media_type,
                "contentUrl": absolute(reverse("nrmps:example_download", kwargs={"slug": slug, "name": name})),
            }
            for name, title, media_type in EXAMPLE_FILES
        ],
    }


def _example_data(name: str, slug: str, url: str, meta: PageMeta) -> dict[str, Any]:
    """Return the structured data of the examples' index (no `slug`) or of one of an example's indexed pages."""
    crumbs = [("Home", absolute("/")), ("Examples", absolute(reverse("nrmps:examples")))]
    graph: list[dict[str, Any]] = [_site()]
    if name in EXAMPLE_PAGES:
        saved, page = saved_run(slug), EXAMPLE_PAGES[name]
        crumbs.append((saved.example.name, absolute(example_path(slug, "summary"))))
        if page == "summary":
            graph.append(_dataset(saved, url, meta))
        else:
            crumbs.append((PAGE_LABELS[page], url))
    return {"@context": "https://schema.org", "@graph": [*graph, _breadcrumbs(crumbs)]}


def structured_data(request: HttpRequest, meta: PageMeta) -> dict[str, Any] | None:
    """Return the page's schema.org description (JSON-LD), or None for a page that needs none.

    The home page describes the site and the simulator as a free web application; a page of the guide is an article
    of the site, with its place in it (breadcrumbs); a saved example run is a dataset with its downloads, and its
    pages have their place in the site.
    """
    match = request.resolver_match
    name = match.view_name if match is not None else ""
    url = absolute(request.path)
    author = {"@type": "Person", "name": AUTHOR}
    if match is not None and (name == "nrmps:examples" or name in EXAMPLE_PAGES):
        return _example_data(name, match.kwargs.get("slug", ""), url, meta)
    if name == "nrmps:index":
        application = {
            "@type": "WebApplication",
            "@id": absolute("/#simulator"),
            "name": SITE_NAME,
            "url": url,
            "description": meta.description,
            "applicationCategory": "EducationalApplication",
            "operatingSystem": "Any (web browser)",
            "softwareVersion": app_version(),
            "isAccessibleForFree": True,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "license": LICENCE_URL,
            "author": author,
            "audience": {"@type": "Audience", "audienceType": "Researchers, educators and residency programs"},
            "sameAs": [settings.PROJECT_URL],
        }
        return {"@context": "https://schema.org", "@graph": [_site() | {"description": meta.description}, application]}
    if name in {"nrmps:help", "nrmps:help_page"}:
        crumbs = [("Home", absolute("/")), ("Help", absolute(reverse("nrmps:help")))]
        if name == "nrmps:help_page":
            crumbs.append((meta.title, url))
        article = {
            "@type": "TechArticle",
            "@id": f"{url}#article",
            "headline": meta.title,
            "description": meta.description,
            "url": url,
            "inLanguage": "en",
            "isPartOf": {"@id": absolute("/#website")},
            "author": author,
        }
        return {"@context": "https://schema.org", "@graph": [_site(), article, _breadcrumbs(crumbs)]}
    return None


def page_context(request: HttpRequest) -> dict[str, Any]:
    """Return what the page's <head> needs: whether to index it and, if so, its title, description and preview."""
    meta = page_meta(request)
    if meta is None:
        return {"index": False}
    width, height = SOCIAL_CARD_SIZE
    return {
        "index": True,
        "title": f"{meta.title} - {SITE_NAME}",
        "heading": meta.title,
        "description": meta.description,
        "url": absolute(request.path),
        "type": meta.kind,
        "site_name": SITE_NAME,
        "image": absolute(static(SOCIAL_CARD)),
        "image_width": width,
        "image_height": height,
        "image_alt": SOCIAL_CARD_ALT,
        "structured": structured_data(request, meta),
    }
