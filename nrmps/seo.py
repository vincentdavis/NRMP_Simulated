"""Search engines and link previews: the public pages' titles and descriptions, the sitemap and structured data.

Only the pages of PAGES and of the guide are offered to search engines: they get a title and description written
for a search result, a canonical address, a link preview (Open Graph) and structured data, and they are the
sitemap. Every other page carries "noindex": everything behind the login, the login and sign-up forms, searches.
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
    """Return the address of every page offered to search engines: PAGES, then the guide in reading order."""
    paths = [reverse(name) for name in PAGES] + [guide_path(page) for page in guide_pages()]
    return [absolute(path) for path in paths]


def _site() -> dict[str, Any]:
    return {"@type": "WebSite", "@id": absolute("/#website"), "url": absolute("/"), "name": SITE_NAME}


def structured_data(request: HttpRequest, meta: PageMeta) -> dict[str, Any] | None:
    """Return the page's schema.org description (JSON-LD), or None for a page that needs none.

    The home page describes the site and the simulator as a free web application; a page of the guide is an article
    of the site, with its place in it (breadcrumbs).
    """
    match = request.resolver_match
    name = match.view_name if match is not None else ""
    url = absolute(request.path)
    author = {"@type": "Person", "name": AUTHOR}
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
        breadcrumbs = {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": position, "name": crumb, "item": address}
                for position, (crumb, address) in enumerate(crumbs, start=1)
            ],
        }
        return {"@context": "https://schema.org", "@graph": [_site(), article, breadcrumbs]}
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
