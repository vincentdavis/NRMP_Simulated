"""Template hygiene that rendering does not catch."""

import re
from pathlib import Path

from django.conf import settings

UNCLOSED_COMMENT = re.compile(r"\{#(?![^\n]*#\})")


def test_template_comments_close_on_their_line():
    """`{# ... #}` must open and close on one line: Django prints a comment spread over lines as text (it showed
    above the run tabs once). Longer comments use {% comment %} ... {% endcomment %}."""
    offenders = []
    for root in (Path(d) for d in settings.TEMPLATES[0]["DIRS"]):
        for path in root.rglob("*.html"):
            text = path.read_text()
            offenders.extend(
                f"{path}:{text.count(chr(10), 0, match.start()) + 1}" for match in UNCLOSED_COMMENT.finditer(text)
            )
    assert offenders == []


def test_the_comment_check_finds_a_comment_over_two_lines():
    assert UNCLOSED_COMMENT.search("<p>{# one line #}</p>") is None
    assert UNCLOSED_COMMENT.search("<p>{# first line\n   second line #}</p>") is not None
