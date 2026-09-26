"""The guide at /help/ (plan step 4.4): Markdown pages, MathML formulas, live values and a worked example."""

import math
import re

import pytest
from django.urls import reverse

from nrmps.guide import BLOCKS, VALUES, guide_pages, render_page, worked_example

pytestmark = pytest.mark.django_db


def test_every_page_renders_with_a_title_and_a_menu(client):
    slugs = [page.slug for page in guide_pages()]
    assert slugs[0] == "index"
    assert {"nrmp", "model", "results", "parameters", "csv", "glossary", "faq", "about"} <= set(slugs)
    for page in guide_pages():
        url = reverse("nrmps:help") if page.slug == "index" else reverse("nrmps:help_page", kwargs={"slug": page.slug})
        body = client.get(url).content.decode()
        assert f">{page.title}</h1>" in body, page.slug
        assert 'aria-current="page"' in body
        assert "{{" not in body, page.slug  # every shortcode was replaced
        assert "[[" not in body, page.slug


def test_unknown_pages_are_not_found_and_the_index_slug_redirects(client):
    assert client.get(reverse("nrmps:help_page", kwargs={"slug": "nonsense"})).status_code == 404
    response = client.get(reverse("nrmps:help_page", kwargs={"slug": "index"}))
    assert response.status_code == 301
    assert response["Location"] == reverse("nrmps:help")


def test_formulas_become_mathml():
    html = str(render_page("model").html)
    assert html.count("<math") >= 6
    assert 'display="block"' in html
    assert "$" not in re.sub(r"<[^>]+>", "", html)  # no TeX left over


def test_raw_html_in_pages_is_escaped(tmp_path, monkeypatch):
    from nrmps import guide

    (tmp_path / "evil.md").write_text("---\ntitle: Evil\norder: 1\n---\n<script>alert(1)</script>\n")
    monkeypatch.setattr(guide, "CONTENT", tmp_path)
    guide.guide_pages.cache_clear()
    guide.render_page.cache_clear()
    try:
        assert "<script>" not in str(guide.render_page("evil").html)
    finally:
        guide.guide_pages.cache_clear()
        guide.render_page.cache_clear()


def test_the_worked_example_adds_up_to_the_engines_utility():
    example = worked_example()
    rho, tau = example["rho"], example["tau"]
    parts = math.sqrt(rho) * example["common"] + math.sqrt(1 - rho) * (
        math.sqrt(tau) * example["taste"] + math.sqrt(1 - tau) * example["fit"]
    )
    assert parts == pytest.approx(example["utility"], abs=1e-12)
    assert example["observed"] == pytest.approx(example["utility"] + example["error"])
    html = str(render_page("model").html)
    assert f"{example['utility']:.4f}" in html


def test_every_shortcode_has_a_value():
    for name, value in VALUES.items():
        assert str(value()), name
    for name, block in BLOCKS.items():
        assert "<" in block(), name


def test_internal_links_of_the_guide_resolve(client, simulation):
    for page in guide_pages():
        for href in re.findall(r'href="(/[^"#]*)', str(render_page(page.slug).html)):
            if href.startswith("/static/"):
                continue
            assert client.get(href).status_code in {200, 302}, (page.slug, href)
