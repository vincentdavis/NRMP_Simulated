"""Help quality gates (plan step 4.7): every column of every results table has its "?" help."""

import re

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

# Columns whose header says everything (the row number and the name link).
SELF_EXPLANATORY = {"#", "Name"}


def _headers_without_help(html: str) -> list[str]:
    missing = []
    for header in re.findall(r'<th scope="col"[^>]*>(.*?)</th>', html, flags=re.DOTALL):
        text = re.sub(r"<[^>]+>|[▲▼⇅?]", " ", header)
        label = " ".join(text.split())
        if 'popovertarget="help-column-' not in header and label not in SELF_EXPLANATORY and label:
            missing.append(label)
    return missing


@pytest.mark.parametrize(
    ("view", "extra", "query"),
    [
        ("nrmps:run_applicants", {}, {}),
        ("nrmps:run_programs", {}, {}),
        ("nrmps:run_applications", {}, {}),
        ("nrmps:run_applicant", {"index": 1}, {}),
        ("nrmps:run_applicant", {"index": 1}, {"view": "pre"}),
        ("nrmps:run_program", {"index": 1}, {}),
        ("nrmps:run_program", {"index": 1}, {"view": "pre"}),
    ],
)
def test_every_results_column_has_help(auth_client, finished_run, view, extra, query):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number, **extra}
    html = auth_client.get(reverse(view, kwargs=kwargs), query).content.decode()
    table = html[html.index('<table class="table table-zebra') :]
    assert _headers_without_help(table) == []
