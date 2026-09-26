"""Search of the help (plan step 5.1, HELP-25): the index, the ranking and the search page."""

import pytest
from django.urls import reverse

from nrmps import help_registry
from nrmps.help_search import KINDS, MAX_RESULTS, search, search_index

pytestmark = pytest.mark.django_db


def test_the_index_covers_everything_the_help_explains():
    kinds = {entry.kind for entry in search_index()}
    assert kinds == set(KINDS)
    titles = {entry.title for entry in search_index()}
    assert "Blocking pair" in titles  # a glossary term
    assert str(help_registry.CHARTS["lorenz"].title) in titles
    assert all(entry.url.startswith("/help/") for entry in search_index())


def test_every_word_must_match_and_titles_come_first():
    results = search("blocking pair")
    assert results[0].entry.title == "Blocking pair"
    assert results[0].entry.kind == "Glossary"
    assert results[0].entry.url == "/help/glossary/#term-blocking-pair"
    assert all("blocking" in r.entry.haystack and "pair" in r.entry.haystack for r in results)
    assert search("blocking zebra") == []
    assert search("   ") == []


def test_results_link_to_parameters_charts_and_columns():
    urls = {result.entry.url for result in search("signal")}
    assert "/help/parameters/#param-signals-tiers" in urls
    assert search("lorenz")[0].entry.kind in {"Guide", "Chart"}
    assert any(result.entry.url == "/help/results/#chart-lorenz" for result in search("lorenz"))


def test_snippets_show_the_text_around_the_match():
    result = next(r for r in search("gini") if r.entry.kind == "Chart")
    assert "Gini" in result.snippet
    assert len(result.snippet) <= 202  # SNIPPET characters and the ellipses


def test_the_search_page(client):
    url = reverse("nrmps:help_search")
    body = client.get(url).content.decode()
    assert "Type a word or two" in body
    body = client.get(url, {"q": "blocking pair"}).content.decode()
    assert "result" in body
    assert 'href="/help/glossary/#term-blocking-pair"' in body
    body = client.get(url, {"q": "zebra crossing"}).content.decode()
    assert "Nothing in the help mentions “zebra crossing”." in body


def test_the_query_is_escaped_and_bounded(client):
    body = client.get(reverse("nrmps:help_search"), {"q": "<script>alert(1)</script>" + "x" * 500}).content.decode()
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "x" * 101 not in body


def test_results_are_capped():
    assert len(search("the")) == MAX_RESULTS


def test_every_guide_page_has_the_search_box(client):
    body = client.get(reverse("nrmps:help")).content.decode()
    assert 'role="search"' in body
    assert f'action="{reverse("nrmps:help_search")}"' in body
