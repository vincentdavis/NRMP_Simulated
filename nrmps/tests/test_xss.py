"""User-supplied text cannot inject markup (plan steps 0.5 and 2.3: UX-10, ENG-7)."""

from pathlib import Path

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from nrmps.models import SimulationRun
from nrmps.params_forms import post_data
from nrmps.runs import run_now

PAYLOAD = 'x"><img src=x onerror=alert(document.domain)>'
MARKUP = "<img src=x onerror"

pytestmark = pytest.mark.django_db


def test_markup_in_an_attribute_name_is_rejected_not_stored(auth_client, simulation):
    """A POST that bypasses the browser cannot store markup as an attribute key: keys must be identifiers."""
    manage = reverse("nrmps:simulation_manage", kwargs={"pk": simulation.pk})
    data = post_data(simulation.get_params()) | {"form_id": "params", "applicants__attributes-0-key": PAYLOAD}
    response = auth_client.post(manage, data)
    assert response.status_code == 200  # re-rendered with errors
    assert "Use 1 to 40 lowercase letters, digits or underscores, starting with a letter." in response.content.decode()
    simulation.refresh_from_db()
    assert PAYLOAD not in str(simulation.params)
    assert MARKUP not in response.content.decode()


def test_markup_in_uploaded_names_is_escaped_everywhere(auth_client, simulation, user):
    content = f'name,strength,board_scores,research,honors\n"{PAYLOAD}",0.5,0,0,0\n'.encode()
    content += b"".join(b"a%d,0.1,0,0,0\n" % i for i in range(20))
    response = auth_client.post(
        reverse("nrmps:population_upload", kwargs={"pk": simulation.pk, "side": "applicants"}),
        {"file": SimpleUploadedFile("x.csv", content, "text/csv")},
        headers={"hx-request": "true"},
    )
    assert b"not loaded" not in response.content
    data = simulation.get_params().model_copy(
        update={"market": simulation.get_params().market.model_copy(update={"n_programs": 2})}
    )
    simulation.set_params(data)
    simulation.save()
    run = run_now(simulation, user)
    assert run.status == SimulationRun.Status.SUCCEEDED, run.error
    kwargs = {"pk": simulation.pk, "number": run.number}
    for url in (
        reverse("nrmps:run_applicants", kwargs=kwargs),
        reverse("nrmps:run_applicant", kwargs=kwargs | {"index": 1}),
        reverse("nrmps:run_program", kwargs=kwargs | {"index": 1}),
    ):
        body = auth_client.get(url).content.decode()
        assert MARKUP not in body, url
        assert "&lt;img src=x onerror" in body, url


def test_templates_never_mark_content_safe():
    """`|safe` and `{% autoescape off %}` are banned in templates (ENG-7)."""
    roots = [Path(d) for d in settings.TEMPLATES[0]["DIRS"]]
    offenders = [
        str(path)
        for root in roots
        for path in root.rglob("*.html")
        if "|safe" in (text := path.read_text()) or "autoescape off" in text
    ]
    assert offenders == []
