"""The saved example runs (nrmps.examples): files in the repository shown to everyone at /examples/."""

import io
import json
import re

import pytest
from django.core.management import CommandError, call_command
from django.urls import reverse

from nrmps import examples
from nrmps.engine.persistence import population_digest
from nrmps.examples import EXAMPLES, FILES, PAGE_LABELS, PAGE_TITLES, saved_run, saved_runs, stale
from nrmps.models import IMPLEMENTED_STAGES, Simulation, SimulationRun
from nrmps.presets import PRESETS, preset_params
from nrmps.run_views import RUN_TABS
from nrmps.runs import run_now
from nrmps.seo import EXAMPLE_FILES, EXAMPLE_PAGES
from nrmps.views import DEMO_PRESETS

pytestmark = pytest.mark.django_db

SLUGS = list(EXAMPLES)
TABS = ("detail", "population", "pre_interview", "applications", "match", "applicants", "programs")
SMALL, LARGE = "small-classroom-market", "nrmp-like-market"


def _url(slug: str, page: str = "detail", **kwargs) -> str:
    return reverse(f"nrmps:example_{page}", kwargs={"slug": slug, **kwargs})


def _text(response) -> str:
    """Return the response body with runs of whitespace collapsed, as a browser would show it."""
    return " ".join(response.content.decode().split())


# --- The saved files --------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("slug", SLUGS)
def test_the_saved_files_are_what_the_code_gives_now(slug):
    """After a change of the engine, a preset or a seed: run `python manage.py nrmp_examples` and commit the files."""
    assert stale(EXAMPLES[slug]) == [], "Run `python manage.py nrmp_examples` and commit nrmps/example_runs/."


@pytest.mark.parametrize("slug", SLUGS)
def test_a_saved_run_is_complete_and_passed_its_checks(slug):
    saved = saved_run(slug)
    run, data = saved.run, saved.data
    for name in FILES:
        assert (examples.DIRECTORY / slug / name).is_file(), name
    assert run.status == "succeeded"
    assert run.seed == saved.example.seed == run.get_params().run.seed
    assert run.get_params() == preset_params(saved.example.preset, seed=saved.example.seed)
    assert (run.n_applicants, run.n_programs) == (data.population.n_applicants, data.population.n_programs)
    assert run.n_positions == data.population.n_positions
    assert data.stages is not None
    assert data.applicant_results is not None
    assert run.metrics["outcomes"]["checks"]["passed"] is True
    assert run.metrics["outcomes"]["match"]["blocking_pairs"] == 0
    assert run.population_digest == population_digest(data.population)  # the digest of the saved population
    assert [stage.stage for stage in saved.stages] == [stage.value for stage in IMPLEMENTED_STAGES]
    assert set(run.fingerprints) == {stage.value for stage in IMPLEMENTED_STAGES}
    assert all(stage.fingerprint == run.fingerprints[stage.stage] for stage in saved.stages)


def test_a_saved_run_is_not_in_the_database():
    for saved in saved_runs():
        assert saved.run.pk is None
        assert saved.run.simulation.pk is None
        assert all(stage.pk is None for stage in saved.stages)
    assert not SimulationRun.objects.exists()
    assert not Simulation.objects.exists()
    assert saved_run(SMALL) is saved_run(SMALL)  # loaded once


@pytest.mark.parametrize("slug", SLUGS)
def test_running_the_market_with_the_same_seed_gives_the_saved_run(slug, user):
    """A user who runs the example's preset with its seed gets the saved run: same market, same match.

    Numbers are compared within rounding, and the population by its arrays rather than its digest: the saved files
    may come from a processor that rounds the last bit of a number differently.
    """
    saved = saved_run(slug)
    simulation = Simulation.objects.create(
        owner=user, name="Mine", params=preset_params(saved.example.preset, seed=saved.example.seed).to_json_data()
    )
    run = run_now(simulation, user)
    assert run.status == "succeeded", run.error
    assert run.params_hash == saved.run.params_hash
    assert run.fingerprints == saved.run.fingerprints
    for name, kind in examples.ARRAY_FILES.items():
        assert examples._same_arrays((examples.DIRECTORY / slug / name).read_bytes(), run.artifact(kind)), name
    assert examples._close(run.metrics, saved.run.metrics)
    assert [stage.counts for stage in run.stages.order_by("id")] == [stage.counts for stage in saved.stages]


def test_every_example_is_a_demo_market_with_its_own_address():
    assert SLUGS == [LARGE, SMALL]
    for slug, example in EXAMPLES.items():
        assert example.slug == slug
        assert re.fullmatch(r"[a-z]+(-[a-z]+)*", slug)
        assert example.preset in PRESETS
        assert example.preset in DEMO_PRESETS  # "Run this market yourself" opens the demo with it picked
        assert example.phrase.startswith("the ")
        assert example.lead.endswith(".")
        assert {page for page, _text in example.highlights} <= {key for key, _label, _name in RUN_TABS}
    assert len({example.preset for example in EXAMPLES.values()}) == len(EXAMPLES)


def test_the_indexed_pages_are_the_main_tabs_with_the_tabs_labels():
    labels = {key: label for key, label, _name in RUN_TABS}
    assert {key: labels[key] for key in PAGE_LABELS} == PAGE_LABELS
    assert list(PAGE_LABELS) == list(PAGE_TITLES) == list(EXAMPLE_PAGES.values())
    names = {key: name for key, _label, name in RUN_TABS}
    assert {f"nrmps:example_{names[key]}": key for key in PAGE_LABELS} == EXAMPLE_PAGES


# --- The command ------------------------------------------------------------------------------------------------------


def _command(*args) -> str:
    out = io.StringIO()
    call_command("nrmp_examples", *args, stdout=out)
    return out.getvalue()


def test_the_command_reports_examples_that_are_up_to_date():
    assert _command("--check").splitlines() == [f"{slug}: up to date" for slug in SLUGS]
    assert _command().splitlines() == [f"{slug}: up to date" for slug in SLUGS]


def test_the_command_saves_missing_examples_and_finds_changed_ones(tmp_path, monkeypatch):
    repository = examples.DIRECTORY
    monkeypatch.setattr(examples, "DIRECTORY", tmp_path)
    examples.saved_run.cache_clear()
    try:
        with pytest.raises(CommandError, match="Out of date: nrmp-like-market, small-classroom-market"):
            _command("--check")
        assert not any(tmp_path.iterdir())  # --check writes nothing
        report = _command()
        assert "small-classroom-market: saved to" in report
        assert "60 applicants, 8 programs, 50 positions" in report
        for slug in SLUGS:
            assert sorted(path.name for path in (tmp_path / slug).iterdir()) == sorted(FILES)
            assert (tmp_path / slug / "params.json").read_bytes() == (repository / slug / "params.json").read_bytes()
        assert _command("--check").splitlines() == [f"{slug}: up to date" for slug in SLUGS]
        # A different market in the files: one more match than the code gives.
        path = tmp_path / SMALL / "metrics.json"
        record = json.loads(path.read_text())
        record["metrics"]["outcomes"]["match"]["matched"] += 1
        path.write_text(json.dumps(record))
        with pytest.raises(CommandError, match="Out of date: small-classroom-market"):
            _command("--check")
        assert stale(EXAMPLES[SMALL]) == ["metrics.json differs"]
        assert stale(EXAMPLES[LARGE]) == []
        # Saved again; the date and the times may differ, and do not make an example out of date.
        assert "small-classroom-market: saved to" in _command()
        record = json.loads(path.read_text())
        record["saved_at"] = "2020-01-01T00:00:00+00:00"
        record["duration_ms"] += 1000
        record["stamps"]["python_version"] = "0.0"
        record["population_digest"] = "0" * 64  # as from a processor that rounds a last bit differently
        record["metrics"]["outcomes"]["match"]["match_rate"] *= 1 + 1e-13
        path.write_text(json.dumps(record))
        assert stale(EXAMPLES[SMALL]) == []
        (tmp_path / SMALL / "stages.npz").unlink()
        assert stale(EXAMPLES[SMALL]) == ["stages.npz is missing"]
        assert "nrmp-like-market: saved to" in _command("--force")
    finally:
        examples.saved_run.cache_clear()


# --- The pages --------------------------------------------------------------------------------------------------------


def _pages(slug: str) -> list[str]:
    run = saved_run(slug).run
    return [
        *(_url(slug, name) for name in TABS),
        _url(slug, "applicant", index=1),
        _url(slug, "applicant", index=run.n_applicants) + "?view=pre",
        _url(slug, "program", index=1),
        _url(slug, "program", index=run.n_programs) + "?view=pre",
    ]


ALL_PAGES = [reverse("nrmps:examples"), *(page for slug in SLUGS for page in _pages(slug))]


@pytest.mark.parametrize("path", ALL_PAGES)
def test_every_example_page_opens_without_an_account_and_without_the_database(client, django_assert_num_queries, path):
    with django_assert_num_queries(0):
        response = client.get(path)
    assert response.status_code == 200
    body = response.content.decode()
    assert body.count("<h1") == 1
    assert "Not affiliated with, sponsored or endorsed by the" in body
    # Read-only and apart from the accounts: nothing to post, no way into anybody's simulations.
    assert 'method="post"' not in body
    assert "/simulations/" not in body
    assert "/compare/" not in body
    assert "Delete run" not in body
    assert "Back to simulation" not in body


@pytest.mark.parametrize("slug", SLUGS)
def test_an_examples_pages_open_for_a_signed_in_user_too(auth_client, slug):
    for path in _pages(slug):
        response = auth_client.get(path)
        assert response.status_code == 200, path
        assert "Delete run" not in response.content.decode()


def test_the_index_presents_each_example_with_its_numbers(client):
    body = _text(client.get(reverse("nrmps:examples")))
    assert "<h1" in body
    assert "Example runs" in body
    for saved in saved_runs():
        example, run = saved.example, saved.run
        assert example.name in body
        assert example.lead in body.replace("&#x27;", "'")
        assert f'href="{_url(example.slug)}"' in body
        assert f"Open {example.phrase}" in body
        assert f"{run.n_applicants:,}" in body
        assert f"{run.metrics['outcomes']['match']['match_rate'] * 100:.1f}%" in body
        for page, text in example.highlights:
            assert text in body, page
    assert body.index("NRMP-like market") < body.index("Small classroom market")
    assert f'href="{reverse("nrmps:demo")}"' in body


@pytest.mark.parametrize("slug", SLUGS)
def test_the_summary_says_what_the_example_is_and_where_to_go(client, slug):
    saved = saved_run(slug)
    example, run = saved.example, saved.run
    body = _text(client.get(_url(slug)))
    assert f"{example.name}: a saved run" in body
    assert "About this example" in body
    assert example.lead in body.replace("&#x27;", "'")
    assert f"with seed {run.seed} and model {run.model_version}" in body
    assert f"/tree/main/nrmps/example_runs/{slug}" in body
    assert f'href="{reverse("nrmps:demo")}?preset={example.preset}"' in body
    assert "Run this market yourself" in body
    assert "everyone who opens it sees this same market" in body
    assert "not a prediction of any real applicant" in body
    # The tabs, the links and the downloads stay inside the example.
    for name in TABS:
        assert f'href="{_url(slug, name)}"' in body
    for name, _title, _media_type in EXAMPLE_FILES:
        assert f'href="{_url(slug, "download", name=name)}"' in body
    assert ('pairs.csv"' in body) == saved.pairs_download
    assert "Checks passed" in body
    assert "Saved" in body
    assert "Started" not in body
    # Its breadcrumbs lead back to the examples, and the Help panel describes this page, not a user's run.
    assert f'<a href="{reverse("nrmps:examples")}">Examples</a>' in body
    assert "A saved example run" in body
    assert "queued or running" not in body


def test_the_other_tabs_carry_the_examples_name_and_breadcrumbs(client):
    for name, label in (("population", "population"), ("match", "match"), ("applicants", "applicants")):
        body = _text(client.get(_url(SMALL, name)))
        assert f"Small classroom market: {label}" in body
        assert f'<a href="{_url(SMALL)}">Small classroom market</a>' in body
        assert "About this example" not in body
    match = _text(client.get(_url(SMALL, "match")))
    assert "50 of 60 applicants with a rank order list" in match


def test_the_applications_table_sorts_filters_and_pages_inside_the_example(client):
    path = _url(LARGE, "applications")
    body = client.get(path, {"status": "matched", "sort": "program", "page_size": 25, "page": 2}).content.decode()
    assert body.count('<span class="badge badge-success badge-sm">Matched</span>') == 25
    assert f'href="{path}#applications-title"' in body  # Clear
    assert f'href="{_url(LARGE, "applicant", index=1)[:-2]}' in body
    assert "page=3" in body
    assert "Showing 26\u201350 of 886" in body


def test_an_examples_tables_offer_at_most_a_hundred_rows_a_page(client, auth_client, finished_run):
    """Anyone can ask for an example's tables, so its pages stay light; a user's own run offers up to 500 rows."""
    for path in (
        _url(LARGE, "applicants"),
        _url(LARGE, "applications"),
        _url(LARGE, "program", index=1),
        _url(LARGE, "program", index=1) + "?view=pre",
    ):
        body = client.get(path, {"page_size": 500} if "?" not in path else {"view": "pre", "page_size": 500})
        html = body.content.decode()
        assert re.findall(r'<option value="(\d+)"', html) == ["25", "50", "100"], path
        assert '<option value="100" selected>' in html, path
        assert html.split("<tbody>")[-1].count("<tr") <= 100, path
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    own = auth_client.get(reverse("nrmps:run_applicants", kwargs=kwargs), {"page_size": 500}).content.decode()
    assert re.findall(r'<option value="(\d+)"', own) == ["25", "50", "100", "200", "500"]
    assert '<option value="500" selected>' in own


def test_an_agents_page_links_to_the_other_side_inside_the_example(client):
    body = _text(client.get(_url(SMALL, "applicant", index=1)))
    assert "Applicant 1 \u2013 Small classroom market" in body
    assert "<title>Applicant 1 - Small classroom market - NRMP Simulations</title>" in body
    assert f'href="{_url(SMALL, "applicants")}"' in body
    assert re.search(rf'href="{_url(SMALL, "program", index=1)[:-2]}\d+/"', body)
    assert "In the match" in body
    program = _text(client.get(_url(SMALL, "program", index=1)))
    assert "Program 1 \u2013 Small classroom market" in program
    assert re.search(rf'href="{_url(SMALL, "applicant", index=1)[:-2]}\d+/"', program)


@pytest.mark.parametrize(
    "path",
    [
        "/examples/no-such-market/",
        "/examples/no-such-market/match/",
        "/examples/no-such-market/applicants/1/",
        "/examples/no-such-market/download/match.csv",
        f"/examples/{SMALL}/applicants/0/",
        f"/examples/{SMALL}/applicants/61/",
        f"/examples/{SMALL}/programs/9/",
        f"/examples/{SMALL}/download/secrets.csv",
        f"/examples/{LARGE}/download/pairs.csv",
    ],
)
def test_what_an_example_does_not_have_is_not_found(client, path):
    assert client.get(path).status_code == 404


def test_example_pages_only_answer_get(client):
    assert client.post(_url(SMALL)).status_code == 405
    assert client.post(reverse("nrmps:examples")).status_code == 405
    assert client.post(_url(SMALL, "download", name="match.csv")).status_code == 405


def test_a_users_run_keeps_its_own_pages_and_buttons(auth_client, finished_run):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    body = _text(auth_client.get(reverse("nrmps:run_detail", kwargs=kwargs)))
    assert "About this example" not in body
    assert "Run this market yourself" not in body
    assert "Delete run" in body
    assert "Back to simulation" in body
    assert "Started" in body
    assert f'href="{reverse("nrmps:run_match", kwargs=kwargs)}"' in body
    assert f'href="{reverse("nrmps:run_download", kwargs=kwargs | {"name": "match.csv"})}"' in body
    assert "/examples/" not in body.split("<main")[1].split("</main>")[0]


# --- The downloads ----------------------------------------------------------------------------------------------------


def _download(client, slug: str, name: str):
    response = client.get(_url(slug, "download", name=name))
    assert response.status_code == 200, name
    body = b"".join(response.streaming_content) if response.streaming else response.content
    return response, body.decode()


@pytest.mark.parametrize("slug", SLUGS)
def test_an_examples_files_can_be_downloaded(client, slug):
    saved = saved_run(slug)
    run = saved.run
    rows = {
        "applicants.csv": run.n_applicants,
        "programs.csv": run.n_programs,
        "match.csv": run.n_applicants,
        "program_results.csv": run.n_programs,
        "applications.csv": saved.stages[2].counts["applications"],
    }
    for name, expected in rows.items():
        response, text = _download(client, slug, name)
        assert response["Content-Disposition"] == f'attachment; filename="{slug}-{name}"'
        assert response["X-Robots-Tag"] == "noindex"
        assert response["Content-Type"] == "text/csv; charset=utf-8"
        lines = [line for line in text.splitlines() if line and not line.startswith("#")]
        assert len(lines) == expected + 1, name
    response, text = _download(client, slug, "params.json")
    assert json.loads(text) == run.params
    assert response["Content-Disposition"] == f'attachment; filename="{slug}-params.json"'
    record = json.loads(_download(client, slug, "metrics.json")[1])
    assert record["seed"] == run.seed
    assert record["population_digest"] == run.population_digest
    assert record["metrics"] == run.metrics
    assert record["stamps"]["model_version"] == run.model_version


def test_the_pairs_file_is_offered_for_the_small_market_only(client):
    assert saved_run(SMALL).pairs_download
    assert not saved_run(LARGE).pairs_download
    _response, text = _download(client, SMALL, "pairs.csv")
    assert len(text.splitlines()) == 60 * 8 + 1
    assert 'pairs.csv"' not in client.get(_url(LARGE)).content.decode()


def test_downloads_are_limited_per_client_address(client, settings):
    settings.NRMP_RATE_LIMITS = settings.NRMP_RATE_LIMITS | {"example_download": "2/h"}
    path = _url(SMALL, "download", name="params.json")
    assert [client.get(path).status_code for _ in range(3)] == [200, 200, 429]
    assert client.get(path, REMOTE_ADDR="203.0.113.9").status_code == 200  # another address has its own count
    assert client.get(_url(SMALL)).status_code == 200  # the pages are not limited


# --- The way in -------------------------------------------------------------------------------------------------------


def test_visitors_are_shown_the_way_to_the_examples(client):
    home = client.get(reverse("nrmps:index")).content.decode()
    assert f'<a class="btn btn-outline" href="{reverse("nrmps:examples")}">See an example run</a>' in home
    assert "The example runs and the demo markets are open without an account" in home
    assert f'href="{reverse("nrmps:examples")}"' in client.get(reverse("nrmps:demo")).content.decode()
    for path in (reverse("nrmps:index"), reverse("nrmps:help"), reverse("nrmps:login")):
        assert f'<li><a href="{reverse("nrmps:examples")}">Examples</a></li>' in client.get(path).content.decode()


def test_the_menu_marks_examples_as_the_current_section(client, auth_client):
    current = f'<li><a class="menu-active" aria-current="page" href="{reverse("nrmps:examples")}">Examples</a></li>'
    assert current in client.get(reverse("nrmps:examples")).content.decode()
    assert current in client.get(_url(SMALL, "match")).content.decode()
    assert current in auth_client.get(_url(SMALL, "applicant", index=3)).content.decode()
    assert current not in client.get(reverse("nrmps:demo")).content.decode()
    signed_in_home = auth_client.get(reverse("nrmps:index")).content.decode()
    assert "See an example run" not in signed_in_home  # the hero keeps the signed-in user's own buttons
    assert f'href="{reverse("nrmps:examples")}"' in signed_in_home  # the menu has it


def test_the_guide_points_to_the_examples(client):
    assert f'href="{reverse("nrmps:examples")}"' in client.get(reverse("nrmps:help")).content.decode().split("<main")[1]
