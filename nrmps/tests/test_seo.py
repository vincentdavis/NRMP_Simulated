"""Search engines and link previews: titles, descriptions, canonical addresses, the sitemap and robots.txt."""

import json
import re
from pathlib import Path
from xml.etree import ElementTree

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.template import Context, Template
from django.urls import reverse

from nrmps import urls
from nrmps.guide import guide_pages
from nrmps.seo import (
    DESCRIPTION_LENGTH,
    PAGES,
    SITE_NAME,
    SOCIAL_CARD,
    SOCIAL_CARD_SIZE,
    TITLE_LENGTH,
    guide_meta,
    guide_path,
    sitemap_urls,
)
from nrmps.views import ROBOTS_DISALLOW

pytestmark = pytest.mark.django_db

SITE = "https://nrmp-simulated.heteroskedastic.org"
# Every page offered to search engines: (path, what a search result shows).
INDEXED = [(reverse(name), meta) for name, meta in PAGES.items()] + [
    (guide_path(page), guide_meta(page)) for page in guide_pages()
]
# Public pages that are not for search results (forms and searches), and public endpoints that are not pages.
NOT_INDEXED = {"login", "signup", "help_search", "password_reset", "password_reset_done", "password_reset_complete"}
NOT_PAGES = {"healthz", "csp_report", "robots_txt", "sitemap", "favicon", "documentation", "logout"}


def _head(body: str) -> str:
    return body.split("</head>")[0]


def _meta(head: str, name: str) -> str | None:
    """Return the content of a <meta name=...> or <meta property=...> tag of the head, unescaped as browsers do."""
    match = re.search(rf'<meta (?:name|property)="{re.escape(name)}" content="([^"]*)"', head)
    return None if match is None else match[1].replace("&#x27;", "'").replace("&amp;", "&").replace("&quot;", '"')


def _structured(head: str) -> dict | None:
    match = re.search(r'<script type="application/ld\+json">(.*?)</script>', head, flags=re.DOTALL)
    return json.loads(match[1]) if match else None


# --- What a search result shows ---------------------------------------------------------------------------------------


def test_titles_and_descriptions_fit_a_search_result_and_differ_from_page_to_page():
    metas = [meta for _path, meta in INDEXED]
    for path, meta in INDEXED:
        assert TITLE_LENGTH[0] <= len(meta.title) <= TITLE_LENGTH[1], (path, len(meta.title))
        assert DESCRIPTION_LENGTH[0] <= len(meta.description) <= DESCRIPTION_LENGTH[1], (path, len(meta.description))
        assert meta.description.endswith("."), path
        assert "{{" not in meta.description, path  # a shortcode of the guide left in
    assert len({meta.title for meta in metas}) == len(metas)
    assert len({meta.description for meta in metas}) == len(metas)


def test_every_guide_page_has_its_own_search_title_and_description():
    for page in guide_pages():
        assert page.seo_title, page.slug
        assert page.description, page.slug
        assert page.description != page.summary, page.slug
    assert all(meta.kind == "article" for _path, meta in INDEXED if _path.startswith("/help/"))


@pytest.mark.parametrize(("path", "meta"), INDEXED, ids=[path for path, _meta in INDEXED])
def test_an_indexed_page_tells_search_engines_what_it_is(client, path, meta):
    response = client.get(path)
    assert response.status_code == 200
    head = _head(response.content.decode())
    title = re.search(r"<title>(.*?)</title>", head)[1].replace("&#x27;", "'")
    assert title == f"{meta.title} - {SITE_NAME}"
    assert _meta(head, "description") == meta.description
    assert f'<link rel="canonical" href="{SITE}{path}">' in head
    assert _meta(head, "robots") is None
    assert _meta(head, "og:title") == meta.title
    assert _meta(head, "og:description") == meta.description
    assert _meta(head, "og:url") == f"{SITE}{path}"
    assert _meta(head, "og:type") == meta.kind
    assert _meta(head, "og:site_name") == SITE_NAME
    assert _meta(head, "twitter:card") == "summary_large_image"
    image = _meta(head, "og:image")
    assert image.startswith(f"{SITE}/static/img/social-card")
    assert image.endswith(".png")
    assert (_meta(head, "og:image:width"), _meta(head, "og:image:height")) == tuple(map(str, SOCIAL_CARD_SIZE))
    assert _meta(head, "og:image:alt")
    assert response.content.decode().count("<h1") == 1


def test_the_canonical_address_has_no_query_and_one_host(client):
    head = _head(client.get(reverse("nrmps:demo"), {"preset": "noisy"}).content.decode())
    assert f'<link rel="canonical" href="{SITE}/demo/">' in head
    assert _meta(head, "og:url") == f"{SITE}/demo/"
    assert settings.SITE_URL == SITE


# --- What search engines should leave alone -------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(NOT_INDEXED))
def test_forms_and_searches_are_not_indexed(client, name):
    response = client.get(reverse(f"nrmps:{name}"))
    assert response.status_code == 200
    head = _head(response.content.decode())
    assert _meta(head, "robots") == "noindex"
    assert "canonical" not in head
    assert _meta(head, "description") is None
    assert _meta(head, "og:title") is None
    assert "application/ld+json" not in head


def test_pages_behind_the_login_are_not_indexed(auth_client, finished_run):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    for url in (
        reverse("nrmps:simulation_list"),
        reverse("nrmps:run_detail", kwargs=kwargs),
        reverse("nrmps:run_match", kwargs=kwargs),
        reverse("nrmps:compare"),
        reverse("nrmps:account"),
    ):
        head = _head(auth_client.get(url).content.decode())
        assert _meta(head, "robots") == "noindex", url
        assert "canonical" not in head, url


def test_every_public_page_is_either_indexed_or_deliberately_not():
    """A new page that visitors can open must be given a title and description in nrmps.seo, or be listed here."""
    indexed = {name.removeprefix("nrmps:") for name in PAGES} | {"help", "help_page"}
    public = {
        pattern.name
        for pattern in urls.urlpatterns
        if getattr(pattern.callback, "login_required", True) is False and "token" not in str(pattern.pattern)
    }
    assert public - NOT_PAGES - NOT_INDEXED - {"password_reset_confirm"} == indexed
    assert indexed <= public


# --- The sitemap and robots.txt ---------------------------------------------------------------------------------------


def test_the_sitemap_lists_every_indexed_page_and_nothing_else(client):
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/xml"
    root = ElementTree.fromstring(response.content)  # noqa: S314 (our own page)
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    listed = [loc.text for loc in root.findall("s:url/s:loc", namespace)]
    assert listed == sitemap_urls() == [f"{SITE}{path}" for path, _meta in INDEXED]
    assert len(set(listed)) == len(listed)
    assert f"{SITE}/" in listed
    assert f"{SITE}/help/model/" in listed
    assert not any("login" in url or "signup" in url or "search" in url for url in listed)


def test_robots_txt_keeps_crawlers_out_of_private_pages_and_names_the_sitemap(client):
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/plain")
    lines = response.content.decode().splitlines()
    assert lines[0] == "User-agent: *"
    assert f"Sitemap: {SITE}/sitemap.xml" in lines
    for path in ("/admin/", "/simulations/", "/compare/", "/account/", "/ops/", "/help/search/"):
        assert f"Disallow: {path}" in lines
    # Nothing in the sitemap is disallowed, and the forms stay crawlable so that their "noindex" can be read.
    for path, _meta in INDEXED:
        assert not any(path.startswith(blocked) for blocked in ROBOTS_DISALLOW), path
    for name in ("login", "signup"):
        assert not any(reverse(f"nrmps:{name}").startswith(blocked) for blocked in ROBOTS_DISALLOW)


def test_visitors_can_fetch_the_sitemap_robots_and_the_icon(client):
    assert client.get("/sitemap.xml").status_code == 200
    assert client.get("/robots.txt").status_code == 200
    icon = client.get("/favicon.ico")
    assert icon.status_code == 301
    assert re.fullmatch(r"/static/img/icon-96(\.[0-9a-f]+)?\.png", icon["Location"])
    assert client.post("/robots.txt").status_code == 405


def test_the_preview_image_and_icons_exist_and_are_linked(client):
    for name in (SOCIAL_CARD, "img/icon-96.png", "img/icon-180.png"):
        path = finders.find(name)
        assert path, name
        assert Path(path).read_bytes().startswith(b"\x89PNG"), name
    head = _head(client.get("/").content.decode())
    assert re.search(r'<link rel="icon" type="image/png" sizes="96x96" href="/static/img/icon-96[^"]*\.png">', head)
    assert re.search(r'<link rel="apple-touch-icon" href="/static/img/icon-180[^"]*\.png">', head)


# --- Structured data --------------------------------------------------------------------------------------------------


def test_the_home_page_describes_the_site_and_the_simulator(client):
    data = _structured(_head(client.get("/").content.decode()))
    assert data["@context"] == "https://schema.org"
    site, application = data["@graph"]
    assert site["@type"] == "WebSite"
    assert site["url"] == f"{SITE}/"
    assert site["name"] == SITE_NAME
    assert application["@type"] == "WebApplication"
    assert application["url"] == f"{SITE}/"
    assert application["isAccessibleForFree"] is True
    assert application["offers"] == {"@type": "Offer", "price": "0", "priceCurrency": "USD"}
    assert application["description"] == PAGES["nrmps:index"].description
    assert application["sameAs"] == [settings.PROJECT_URL]
    assert application["softwareVersion"]


def test_a_guide_page_is_an_article_of_the_site_with_breadcrumbs(client):
    data = _structured(_head(client.get("/help/model/").content.decode()))
    site, article, breadcrumbs = data["@graph"]
    assert site["@id"] == f"{SITE}/#website"
    assert article["@type"] == "TechArticle"
    assert article["headline"] == "The simulation model of the residency Match"
    assert article["url"] == f"{SITE}/help/model/"
    assert article["isPartOf"] == {"@id": f"{SITE}/#website"}
    assert [item["name"] for item in breadcrumbs["itemListElement"]] == ["Home", "Help", article["headline"]]
    assert [item["position"] for item in breadcrumbs["itemListElement"]] == [1, 2, 3]
    assert breadcrumbs["itemListElement"][-1]["item"] == f"{SITE}/help/model/"
    index = _structured(_head(client.get("/help/").content.decode()))
    assert [item["name"] for item in index["@graph"][2]["itemListElement"]] == ["Home", "Help"]
    assert _structured(_head(client.get("/demo/").content.decode())) is None  # a title and description are enough


def test_structured_data_cannot_break_out_of_its_script_element():
    template = Template("{% load seo_tags %}{% jsonld data %}")
    html = template.render(Context({"data": {"name": "</script><script>alert(1)</script> & more"}}))
    assert html.count("<script") == 1
    assert html.count("</script>") == 1
    assert json.loads(re.search(r">(.*)</script>", html)[1]) == {"name": "</script><script>alert(1)</script> & more"}
    assert template.render(Context({"data": None})) == ""


# --- Verifying the site with a search console -------------------------------------------------------------------------


def test_verification_codes_are_shown_only_when_set(client, settings):
    head = _head(client.get("/").content.decode())
    assert "google-site-verification" not in head
    assert "msvalidate.01" not in head
    settings.GOOGLE_SITE_VERIFICATION = "google-code-123"
    settings.BING_SITE_VERIFICATION = "bing-code-456"
    head = _head(client.get("/").content.decode())
    assert _meta(head, "google-site-verification") == "google-code-123"
    assert _meta(head, "msvalidate.01") == "bing-code-456"
