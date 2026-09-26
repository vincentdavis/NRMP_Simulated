"""The Content Security Policy (plan step 5.1, ENG-22): report-only, with a nonce and a report endpoint."""

import json
import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

from nrmps import views

pytestmark = pytest.mark.django_db

HEADER = "Content-Security-Policy-Report-Only"


def test_pages_carry_the_report_only_policy_with_the_nonce_of_their_inline_script(client):
    response = client.get(reverse("nrmps:index"))
    policy = response[HEADER]
    assert "Content-Security-Policy" not in response.headers  # nothing is enforced yet (step 5.5)
    nonce = re.search(r"'nonce-([^']+)'", policy).group(1)
    assert f'<script nonce="{nonce}">' in response.content.decode()
    for directive in ("default-src 'self'", "object-src 'none'", "frame-ancestors 'none'", "report-uri /csp-report/"):
        assert directive in policy
    assert "https:" not in policy  # everything is served from the site itself
    other = re.search(r"'nonce-([^']+)'", client.get(reverse("nrmps:index"))[HEADER]).group(1)
    assert other != nonce  # a fresh nonce per response


def test_the_only_inline_script_is_the_theme_and_there_are_no_inline_handlers():
    """Scripts live in static files; inline event handlers would break the policy once it is enforced."""
    folders = [Path(settings.BASE_DIR, "templates"), Path(settings.BASE_DIR, "theme", "templates")]
    inline, handlers = [], []
    for template in (path for folder in folders for path in folder.rglob("*.html")):
        text = template.read_text(encoding="utf-8")
        tags = re.finditer(r"<script(?![^>]*\bsrc=)([^>]*)>", text)
        inline += [template.name for tag in tags if "nonce=" not in tag.group(1)]
        handlers += [template.name for _ in re.finditer(r"\son(click|change|submit|input|load|error)=", text)]
    assert inline == []
    assert handlers == []


def _report(client, body, content_type="application/csp-report"):
    return client.post(reverse("nrmps:csp_report"), body, content_type=content_type)


REPORT = {
    "csp-report": {
        "document-uri": "https://example.test/simulations/3/?q=private",
        "effective-directive": "script-src-elem",
        "blocked-uri": "inline",
        "source-file": "https://example.test/simulations/3/",
        "line-number": 12,
    }
}


def test_reports_are_logged_once_without_query_strings(client, caplog, monkeypatch):
    monkeypatch.setattr(views, "_csp_seen", set())
    with caplog.at_level("WARNING", logger="nrmps.views"):
        assert _report(client, json.dumps(REPORT)).status_code == 204
        assert _report(client, json.dumps(REPORT)).status_code == 204
    lines = [record.getMessage() for record in caplog.records if "CSP violation" in record.getMessage()]
    assert lines == [
        "CSP violation (report-only): script-src-elem blocked inline on https://example.test/simulations/3/ "
        "(https://example.test/simulations/3/ line 12)"
    ]


def test_bad_reports_are_refused(client):
    assert _report(client, "not json").status_code == 400
    assert _report(client, json.dumps({"csp-report": "x"})).status_code == 400
    assert _report(client, json.dumps([1, 2])).status_code == 400
    assert _report(client, "x" * (views.MAX_CSP_REPORT_BYTES + 1)).status_code == 413
    assert client.get(reverse("nrmps:csp_report")).status_code == 405


def test_the_log_forgets_old_reports_rather_than_growing(client, monkeypatch):
    monkeypatch.setattr(views, "_csp_seen", set())
    monkeypatch.setattr(views, "CSP_SEEN_MAX", 2)
    for k in range(5):
        report = {"csp-report": {**REPORT["csp-report"], "blocked-uri": f"https://cdn{k}.example/x.js"}}
        _report(client, json.dumps(report))
    assert len(views._csp_seen) <= 2
