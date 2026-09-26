"""Search of the help (plan step 5.1, HELP-25): one index of everything the help explains, searched on the server.

The index holds the guide's pages and their sections (with their text), the glossary's terms, the parameters, the
charts of the catalog, and the registry's table columns and buttons, each with the URL of its explanation. It is
built once per process from the same sources the pages render, so it cannot drift from them. A query matches an
entry that contains every word of it; entries whose title contains the query come first.
"""

import functools
import html
import re
from dataclasses import dataclass, field

from . import help_registry
from .guide import INDEX, apply_values, guide_pages, render_page
from .help_registry import chart_target, param_target

MAX_RESULTS = 50
SNIPPET = 200  # characters of text shown under a result

# Kinds in the order results of equal relevance are listed.
KINDS = ("Guide", "Glossary", "Parameter", "Chart", "Column", "Button")

_HEADING = re.compile(r'<h([23]) id="([^"]+)">(.*?)</h\1>', re.DOTALL)
_TERM = re.compile(r'<dt id="([^"]+)">(.*?)</dt>\s*<dd>(.*?)</dd>', re.DOTALL)
_TAGS = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    """Return the text of an HTML fragment: tags removed, entities decoded, whitespace collapsed."""
    return " ".join(html.unescape(_TAGS.sub(" ", fragment)).split())


@dataclass(frozen=True)
class SearchEntry:
    """One thing the help explains: its title, its text, where it is explained and what kind of thing it is."""

    title: str
    text: str
    url: str
    kind: str
    haystack: str = field(default="", compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "haystack", f"{self.title} {self.text}".casefold())


def _guide_entries(url_of) -> list[SearchEntry]:
    entries = []
    for page in guide_pages():
        page_html = str(render_page(page.slug).html)
        url = url_of(page.slug)
        headings = list(_HEADING.finditer(page_html))
        intro = page_html[: headings[0].start()] if headings else page_html
        entries.append(SearchEntry(page.title, f"{apply_values(page.summary)} {_text(intro)}".strip(), url, "Guide"))
        for k, heading in enumerate(headings):
            end = headings[k + 1].start() if k + 1 < len(headings) else len(page_html)
            title = _text(heading.group(3))
            text = _text(page_html[heading.end() : end])
            entries.append(SearchEntry(title, text, f"{url}#{heading.group(2)}", "Guide"))
        kind = "Glossary" if page.slug == "glossary" else "Guide"  # other pages define a few words too
        entries += [
            SearchEntry(_text(term), _text(definition), f"{url}#{anchor}", kind)
            for anchor, term, definition in _TERM.findall(page_html)
        ]
    return entries


def _parameter_entries(url_of) -> list[SearchEntry]:
    from .help_views import parameter_sections

    entries = []
    for section in parameter_sections():
        entries += [
            SearchEntry(str(row["title"]), str(row["description"]), url_of(param_target(row["path"])), "Parameter")
            for row in section["rows"]
        ]
        for table in section["tables"]:  # a list parameter and its columns, explained in its table
            url = url_of(param_target(table["path"]))
            entries.append(SearchEntry(str(table["title"]), str(table["description"]), url, "Parameter"))
            entries += [
                SearchEntry(f"{table['title']}: {column['title']}", str(column["description"]), url, "Parameter")
                for column in table["columns"]
            ]
    return entries


@functools.cache
def search_index() -> tuple[SearchEntry, ...]:
    """Return every entry of the help, built once per process."""
    from .help_views import help_url

    entries = _guide_entries(help_url) + _parameter_entries(help_url)
    entries += [
        SearchEntry(str(chart.title), chart.text, help_url(chart_target(key)), "Chart")
        for key, chart in help_registry.CHARTS.items()
    ]
    for kind, registry in (("Column", help_registry.COLUMNS), ("Button", help_registry.ACTIONS)):
        entries += [
            SearchEntry(str(entry.title), str(entry.text), help_url(entry.more or INDEX), kind)
            for entry in registry.values()
        ]
    unique: dict[tuple[str, str, str], SearchEntry] = {}
    for entry in entries:
        unique.setdefault((entry.kind, entry.title.casefold(), entry.url), entry)
    return tuple(unique.values())


@dataclass(frozen=True)
class SearchResult:
    """A matching entry and the part of its text around the first match."""

    entry: SearchEntry
    snippet: str


def _snippet(text: str, words: list[str]) -> str:
    folded = text.casefold()
    first = min((position for word in words if (position := folded.find(word)) >= 0), default=0)
    start = max(0, first - SNIPPET // 3)
    end = start + SNIPPET
    return f"{'…' if start else ''}{text[start:end].strip()}{'…' if end < len(text) else ''}"


def search(query: str, limit: int = MAX_RESULTS) -> list[SearchResult]:
    """Return the entries that contain every word of `query`, the most relevant first (at most `limit`).

    Relevance: the query in the title, then all its words in the title, then the most words in the title; ties go
    to the kinds in KINDS order and then to shorter titles.
    """
    words = query.casefold().split()
    if not words:
        return []
    phrase = " ".join(words)
    ranked = []
    for entry in search_index():
        if not all(word in entry.haystack for word in words):
            continue
        title = entry.title.casefold()
        in_title = sum(word in title for word in words)
        relevance = 0 if phrase in title else 1 if in_title == len(words) else 2
        ranked.append(((relevance, -in_title, KINDS.index(entry.kind), len(entry.title)), entry))
    ranked.sort(key=lambda item: item[0])
    return [SearchResult(entry, _snippet(entry.text, words)) for _key, entry in ranked[:limit]]
