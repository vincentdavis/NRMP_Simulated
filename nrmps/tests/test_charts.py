"""Diagnostic chart payloads (plan step 3.8): requested against realised, samples, demand and the funnel."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from django.urls import reverse
from django.utils.html import escape
from scipy.stats import spearmanr

from nrmps import help_registry
from nrmps.charts import (
    CHOICE_BINS,
    EGO_MAX_NODES,
    FUNNEL_ROWS,
    STRENGTH_BANDS,
    STRENGTH_RANGES,
    TAB_CHARTS,
    _bands_note,
    _count_bins,
    _count_names,
    agent_funnel,
    applicant_flow,
    digits,
    ego_network,
    fit_check,
    funnel,
    gini,
    interviews_per_applicant,
    match_by_list_length,
    match_by_strength,
    matched_choice,
    perception_samples,
    program_fill,
    requested_histogram,
    run_charts,
    sorting,
    strength_bands,
)
from nrmps.engine.metrics import histogram
from nrmps.engine.population import generate_population
from nrmps.models import RunArtifact, SimulationRun
from nrmps.params import SimulationParams
from nrmps.runs import RunData, StageRows

TIERS = [{"name": "top", "share": 0.2, "quality_mean": 1.5}, {"name": "rest", "share": 0.8, "quality_mean": -0.4}]

pytestmark = pytest.mark.django_db


def test_every_chart_of_a_run(finished_run):
    charts = run_charts(RunData(finished_run))
    assert set(charts) == {
        "strength",
        "quality",
        "capacity",
        "applicant_fidelity",
        "program_fidelity",
        "perception_applicants",
        "perception_programs",
        "demand",
        "lorenz",
        "funnel",
        "applicant_flow",
        "interviews",
        "matched_choice",
        "list_length",
        "sorting",
        "program_fill",
        "match_by_strength",
    }
    for chart in charts.values():
        assert chart["summary"]
    json.dumps({key: chart["payload"] for key, chart in charts.items()})  # plain JSON


def test_the_requested_distribution_matches_what_was_generated(finished_run):
    charts = run_charts(RunData(finished_run))
    for key, total in (("strength", 60), ("quality", 8)):
        payload = charts[key]["payload"]
        assert sum(payload["counts"]) == total
        assert sum(payload["requested"]) == pytest.approx(total, abs=0.1)
    assert charts["capacity"]["payload"].get("requested") is None


@pytest.mark.parametrize("side", ["applicants", "programs"])
def test_a_large_generated_market_follows_the_request(side):
    params = SimulationParams.model_validate(
        {"market": {"n_applicants": 20_000, "n_programs": 2_000}, "programs": {"tiers": TIERS}}
    )
    population = generate_population(params, 4)
    metrics = {
        "histograms": {
            "strength": histogram(population.applicants.strength),
            "quality": histogram(population.programs.quality),
        }
    }
    payload = requested_histogram(metrics, params, {"applicants": "generated", "programs": "generated"}, side)
    assert fit_check(payload) < 4


def test_a_bad_generator_would_show():
    payload = {"counts": [0, 50, 0], "requested": [25.0, 0.0, 25.0], "edges": [0, 1, 2, 3]}
    assert fit_check(payload) == 5.0
    assert fit_check({"counts": [1], "requested": [1.0]}) is None  # too few expected to judge
    assert fit_check({"counts": [1], "requested": None}) is None


def test_uploaded_sides_have_no_requested_distribution(finished_run):
    SimulationRun.objects.filter(pk=finished_run.pk).update(
        population_source={"applicants": "mine.csv", "programs": "generated"}
    )
    finished_run.refresh_from_db()
    charts = run_charts(RunData(finished_run))
    assert charts["strength"]["payload"]["requested"] is None
    assert charts["strength"]["deviation"] is None
    assert charts["quality"]["payload"]["requested"] is not None


def test_bin_labels_get_enough_decimals():
    assert digits([0.0, 0.5, 1.0]) == 2
    assert digits([0.88, 0.8805, 0.881]) == 5
    assert digits([3.0, 19.5, 36.0]) == 0


def test_gini():
    assert gini(np.array([5, 5, 5, 5])) == pytest.approx(0.0)
    assert gini(np.array([0, 0, 0, 12])) == pytest.approx(0.75)
    assert gini(np.array([0, 0])) is None


def test_the_funnel_adds_up(finished_run):
    data = RunData(finished_run)
    counts = funnel(data.stages)
    assert counts["applied"] == counts["invited"] + counts["not_invited"]
    assert counts["invited"] == counts["interviewed"] + counts["declined"]
    assert counts["interviewed"] == counts["ranked"] + counts["not_ranked"]
    assert counts["ranked"] == counts["matched"] + counts["not_matched"]
    assert counts["matched"] == finished_run.metrics["outcomes"]["match"]["matched"]
    assert funnel(None) is None


def test_the_scatter_sample_repeats_and_is_bounded(finished_run):
    data = RunData(finished_run)
    first, again = perception_samples(data, size=100), perception_samples(RunData(finished_run), size=100)
    assert first == again
    assert len(first["applicants"]["pre"][0]) == 100
    assert len(first["applicants"]["post"][0]) <= 100
    small = perception_samples(data, size=10_000)  # 480 pairs: every pair once
    assert len(small["programs"]["pre"][0]) == 480


@pytest.mark.parametrize(
    ("view", "kinds"),
    [
        ("run_population", {"strength", "quality", "capacity"}),
        ("run_pre_interview", {"applicant-fidelity", "program-fidelity", "perception-applicants", "demand"}),
        ("run_applications", {"funnel", "applicant-flow", "interviews"}),
        ("run_match", {"matched-choice", "list-length", "sorting", "program-fill", "match-by-strength"}),
    ],
)
def test_the_run_tabs_embed_their_charts_and_numbers(auth_client, finished_run, view, kinds):
    url = reverse(f"nrmps:{view}", kwargs={"pk": finished_run.simulation_id, "number": finished_run.number})
    body = auth_client.get(url).content.decode()
    for key in kinds:
        assert f'id="chart-{key}"' in body, key
        assert f'aria-describedby="chart-{key}-summary"' in body, key
    for text in ("vendor/echarts/6.1.0/echarts.min.js", "js/nrmp-charts.js"):
        assert text in body, text


def test_a_summary_without_the_applicants_flow_loads_no_chart_code(auth_client, finished_run):
    """The summary's only chart is the applicants' flow; a run without stage decisions has none, and no chart code."""
    finished_run.artifacts.filter(kind=RunArtifact.Kind.STAGES).delete()
    url = reverse("nrmps:run_detail", kwargs={"pk": finished_run.simulation_id, "number": finished_run.number})
    body = auth_client.get(url).content
    assert b"echarts" not in body
    assert b"data-chart" not in body


def test_runs_without_results_load_no_chart_code(auth_client, simulation, user, monkeypatch):
    from nrmps.runs import run_now

    monkeypatch.setattr("nrmps.runs.run_pipeline", lambda *a, **k: (_ for _ in ()).throw(ValueError("No luck.")))
    run = run_now(simulation, user)
    body = auth_client.get(reverse("nrmps:run_detail", kwargs={"pk": simulation.pk, "number": run.number})).content
    assert b"echarts" not in body
    assert b"data-chart" not in body


def test_runs_from_before_the_match_draw_the_population_charts(auth_client, finished_run):
    finished_run.artifacts.filter(kind=RunArtifact.Kind.STAGES).delete()
    charts = run_charts(RunData(finished_run))
    assert "funnel" not in charts
    assert charts["perception_applicants"]["payload"]["post"] is None
    # The charts of the later tabs need the stage decisions, except the choices, which the diagnostics keep.
    for key in ("interviews", "list_length", "sorting", "program_fill", "match_by_strength"):
        assert charts[key] is None, key
    assert charts["matched_choice"]["summary"]


# --- Plan step 5.1: the chart catalog and the network of one agent ---------------------------------------------------


def test_every_chart_on_the_run_tabs_has_its_question_and_help(auth_client, finished_run):
    """Captions and "?" popovers come from the chart catalog; each chart carries its colour role."""
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    shown = set()
    for view in ("nrmps:run_population", "nrmps:run_pre_interview", "nrmps:run_applications", "nrmps:run_match"):
        body = auth_client.get(reverse(view, kwargs=kwargs)).content.decode()
        for key, chart in help_registry.CHARTS.items():
            if f'popovertarget="help-chart-{key.replace("_", "-")}"' in body:
                shown.add(key)
                assert escape(str(chart.title)) in body
        assert 'data-series="program"' in body or view == "nrmps:run_applications"
    assert shown == {key for key, chart in help_registry.CHARTS.items() if chart.tab != "agent"}


def _stage_rows(**changes):
    rows = StageRows.empty(10)
    rows.applied[:8] = True
    rows.wave[:5] = 1
    rows.interviewed[:4] = True
    rows.list_rank[:3] = [1, 2, 3]
    rows.matched[1] = True
    for name, value in changes.items():
        setattr(rows, name, value)
    return rows


def test_the_network_places_each_application_at_the_stage_it_reached():
    names = [f"Program {k}" for k in range(10)]
    chart = ego_network(_stage_rows(), names, "Ann", applicant=True)
    stages = dict(chart["payload"]["nodes"])
    assert stages == {
        "Program 1": 4,  # matched
        "Program 0": 3,  # ranked, not matched
        "Program 2": 3,
        "Program 3": 2,  # interviewed, not ranked
        "Program 4": 1,  # invited, no interview
        "Program 5": 0,  # applied only
        "Program 6": 0,
        "Program 7": 0,
    }
    assert [node[1] for node in chart["payload"]["nodes"]] == sorted(stages.values(), reverse=True)
    assert chart["summary"] == (
        "Ann's 8 applications by how far each got: 1 matched; 2 ranked, not matched; 1 interviewed, not ranked; "
        "1 invited, no interview; 3 not invited."
    )
    assert [item.get("count") for item in chart["legend"]] == [None, 3, 1, 1, 2, 1]
    assert chart["legend"][0] == {"label": "This applicant", "dot": "viz-dot-series-1"}


def test_the_network_of_a_program_and_its_limits():
    names = [f"Applicant {k}" for k in range(10)]
    chart = ego_network(_stage_rows(), names, "General", applicant=False)
    assert chart["payload"]["side"] == "program"
    assert chart["summary"].startswith("The 8 applications to General by how far each got")
    assert ego_network(StageRows.empty(10), names, "Empty", applicant=False) is None


def test_a_large_network_keeps_the_applications_that_got_furthest(monkeypatch):
    monkeypatch.setattr("nrmps.charts.EGO_MAX_NODES", 5)
    names = [f"Applicant {k}" for k in range(10)]
    chart = ego_network(_stage_rows(), names, "General", applicant=False)
    assert [node[1] for node in chart["payload"]["nodes"]] == [4, 3, 3, 2, 1]
    assert chart["summary"].endswith("The network shows the 5 that got furthest.")
    assert EGO_MAX_NODES >= 1000  # the real limit leaves room for large programs


def test_the_agent_pages_embed_the_network_and_load_its_libraries(auth_client, finished_run):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number, "index": 1}
    for view, key in (("nrmps:run_applicant", "ego_applicant"), ("nrmps:run_program", "ego_program")):
        body = auth_client.get(reverse(view, kwargs=kwargs)).content.decode()
        assert 'data-chart="ego"' in body
        assert escape(str(help_registry.CHARTS[key].title)) in body
        assert "vendor/sigma/3.0.3/sigma.min.js" in body
        assert "vendor/graphology/0.26.0/graphology.umd.min.js" in body
        assert "vendor/echarts/6.1.0/echarts.min.js" in body  # for the funnel beside the network
        side = key.removeprefix("ego_")
        script = body.split(f'id="chart-ego-{side}" type="application/json">')[1].split("</script>")[0]
        assert json.loads(script)["side"] == side


def test_an_agents_funnel_matches_its_network(finished_run):
    """The funnel on an agent's page counts the same applications as its network, stage by stage."""
    data = RunData(finished_run)
    population = data.population
    for applicant in (True, False):
        others = population.programs if applicant else population.applicants
        names = [others.name(k) for k in range(others.size)]
        stages = data.stage_rows(0, applicant=applicant)
        funnel_chart = agent_funnel(stages, "Agent", applicant=applicant)
        network = ego_network(stages, names, "Agent", applicant=applicant)
        counts = funnel_chart["payload"]
        exclusive = [item["count"] for item in network["legend"][1:]]  # not invited ... matched
        assert exclusive == [
            counts["not_invited"],
            counts["declined"],
            counts["not_ranked"],
            counts["not_matched"],
            counts["matched"],
        ]
        assert counts["applied"] == sum(exclusive)
        whose = "applicant's" if applicant else "program's"
        assert f"to a place on the {whose} rank order list" in funnel_chart["summary"]
        assert funnel_chart["rows"][3]["stage"] == f"On the {whose} list"


def test_an_agent_without_applications_has_no_funnel():
    assert agent_funnel(StageRows.empty(5), "Nobody", applicant=True) is None


FUNNEL_KEYS = ("applied", "invited", "not_invited", "interviewed", "declined", "ranked", "not_ranked", "matched")


def test_a_programs_funnel_splits_by_the_strength_fifth_of_its_applicants(finished_run):
    """On a program's page each stage of the funnel is also counted per strength fifth of all applicants, the fifths
    of the applicants' flow (same labels and strength ranges), for the Colour by strength switch and the table."""
    data = RunData(finished_run)
    population = data.population
    strength = np.asarray(population.applicants.strength, dtype=np.float64)
    fifth = strength_bands(strength)
    flow_fifths = applicant_flow(data)["bands"]
    checked = 0
    for program in range(population.programs.size):
        stages = data.stage_rows(program, applicant=False)
        chart = agent_funnel(stages, "Program", applicant=False, strength=strength)
        if chart is None:
            continue
        counts, groups = chart["payload"], chart["payload"]["bands"]
        assert [(g["label"], g["low"], g["high"]) for g in groups] == [
            (f["label"], f["low"], f["high"]) for f in flow_fifths
        ]
        for key in (*FUNNEL_KEYS, "not_matched"):
            assert sum(group["counts"][key] for group in groups) == counts[key], key
        for b, group in enumerate(groups):  # against the stage rows directly
            mine = stages.applied & (fifth == b)
            assert group["counts"]["applied"] == int(mine.sum())
            assert group["counts"]["interviewed"] == int((mine & stages.interviewed).sum())
            assert group["counts"]["matched"] == int((mine & stages.matched).sum())
        for row, key in zip(chart["rows"], FUNNEL_ROWS, strict=True):
            assert row["bands"] == [group["counts"][key] for group in groups]
        assert chart["band_ranges"] == STRENGTH_RANGES
        assert chart["switchable"] is True
        assert chart["switch_note"] == ""
        assert [step["dot"] for step in chart["switch_key"]["steps"]] == [f"viz-dot-div-{k}" for k in range(1, 6)]
        top = groups[-1]["counts"]
        sent = f"{100 * top['applied'] / counts['applied']:.1f}%"
        assert f" The top 20% of applicants by strength sent {sent} of these applications" in chart["summary"]
        if counts["matched"]:
            assert f"{100 * top['matched'] / counts['matched']:.1f}% of the matches." in chart["summary"]
        checked += 1
    assert checked >= 2
    # An applicant's funnel is not split: all its applications come from one applicant.
    applicant_chart = agent_funnel(data.stage_rows(0, applicant=True), "Applicant", applicant=True)
    assert "switchable" not in applicant_chart
    assert "bands" not in applicant_chart["payload"]


def test_a_programs_funnel_without_fifths_says_why(finished_run, monkeypatch):
    monkeypatch.setattr("nrmps.charts.strength_bands", lambda strength: None)
    data = RunData(finished_run)
    strength = np.asarray(data.population.applicants.strength, dtype=np.float64)
    chart = agent_funnel(data.stage_rows(0, applicant=False), "Program", applicant=False, strength=strength)
    assert chart["payload"]["bands"] is None
    assert chart["switchable"] is False
    assert chart["switch_note"] == "too many applicants share a strength to split them into fifths"
    assert chart["switch_key"] is None
    assert "band_ranges" not in chart
    assert "top 20%" not in chart["summary"]


def test_the_agent_pages_show_the_funnel_with_its_numbers(auth_client, finished_run):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number, "index": 1}
    for view, key in (("nrmps:run_applicant", "funnel_applicant"), ("nrmps:run_program", "funnel_program")):
        body = auth_client.get(reverse(view, kwargs=kwargs)).content.decode()
        assert 'data-chart="funnel"' in body
        assert escape(str(help_registry.CHARTS[key].title)) in body
        assert "The numbers" in body
        # Only a program's funnel has the Colour by strength switch, its key and the table's columns per fifth.
        program = key == "funnel_program"
        assert ('data-chart-switch="bands"' in body) is program
        assert ('aria-label="Key: strength percentile, from weaker to stronger"' in body) is program
        assert ('<th scope="colgroup" colspan="5" class="text-center">By strength percentile</th>' in body) is program


# --- The applicants' flow and its strength fifths ----------------------------------------------------------------


def test_strength_fifths_are_by_rank_and_keep_ties_together():
    strength = np.array([5.0, 1.0, 3.0, 2.0, 4.0, 9.0, 8.0, 7.0, 6.0, 0.0])
    assert strength_bands(strength).tolist() == [2, 0, 1, 1, 2, 4, 4, 3, 3, 0]  # two per fifth, weakest first
    tied = np.array([1.0, 1.0, 1.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    assert strength_bands(tied) is None  # a tie is never split, and 40% in one "fifth" is not a fifth
    assert strength_bands(np.zeros(20)) is None
    assert strength_bands(np.arange(4.0)) is None
    bands = strength_bands(np.random.default_rng(1).normal(size=1001))
    assert np.bincount(bands).tolist() == [200, 200, 201, 200, 200]  # the leftover applicant is not the weakest's
    assert [np.bincount(strength_bands(np.arange(float(n)))).tolist() for n in (5, 6)] == [[1] * 5, [1, 1, 2, 1, 1]]


def test_ties_at_the_top_and_bottom_are_treated_alike():
    """A tie group goes to the fifth of its middle rank, so ties at either end give mirror-image fifths."""
    top = strength_bands(np.r_[np.arange(79.0), np.full(21, 100.0)])
    bottom = strength_bands(np.r_[np.full(21, -1.0), np.arange(79.0)])
    assert np.bincount(top).tolist() == [20, 20, 20, 19, 21]
    assert np.bincount(bottom).tolist() == [21, 19, 20, 20, 20]
    assert len(set(top[79:].tolist())) == 1  # the tie stays together
    # Tiered strengths (35% at one value, 5% at the next) would give very unequal "fifths": refused.
    tiered = np.r_[np.zeros(140), np.full(20, 0.5), np.full(80, 1.0), np.full(80, 1.5), np.full(80, 2.0)]
    assert strength_bands(tiered) is None
    assert strength_bands(np.r_[np.full(39, -1.0), np.arange(61.0)]) is None


def test_a_tie_is_refused_or_accepted_the_same_at_either_end():
    """For every market size up to 120 and every size of one tie, a tie at the top and the same tie at the bottom are
    both split into fifths or both refused (mirror images)."""
    for n in range(5, 121):
        for size in range(2, n):
            bottom = np.r_[np.zeros(size), np.arange(1.0, n - size + 1)]
            low, high = strength_bands(bottom), strength_bands(-bottom)
            assert (low is None) == (high is None), (n, size)
            if low is not None:
                sizes = np.bincount(low, minlength=5).tolist()
                assert sizes == np.bincount(high, minlength=5).tolist()[::-1], (n, size)


def test_the_disabled_switch_says_why():
    few = {"bands": None, "counts": {"Applicants": 4}}
    tied = {"bands": None, "counts": {"Applicants": 400}}
    assert _bands_note(few) == "fewer than 5 applicants"
    assert _bands_note(tied) == "too many applicants share a strength to split them into fifths"
    assert _bands_note({"bands": [{}], "counts": {"Applicants": 400}}) == ""


def test_the_applicants_flow_adds_up_in_total_and_per_fifth(finished_run):
    data = RunData(finished_run)
    flow = applicant_flow(data)
    assert flow["stages"] == ["Applicants", "Interviewed", "Matched"]
    assert flow["drops"] == ["No interview", "Interviewed, not matched"]
    for counts in [flow["counts"], *(band["counts"] for band in flow["bands"])]:
        assert counts["Applicants"] == counts["Interviewed"] + counts["No interview"]
        assert counts["Interviewed"] == counts["Matched"] + counts["Interviewed, not matched"]
        assert counts["No interview"] == counts["never_invited"] + counts["invited_no_interview"]
    assert [band["label"] for band in flow["bands"]] == list(STRENGTH_BANDS)
    for key in ("Applicants", "Interviewed", "Matched", "No interview", "never_invited"):
        assert sum(band["counts"][key] for band in flow["bands"]) == flow["counts"][key], key
    # Against independent sources: the engine's arrays and the run's own diagnostics.
    record, n = data.stages, data.population.n_applicants
    assert flow["counts"]["Applicants"] == n
    assert flow["counts"]["Matched"] == int((record.match_program >= 0).sum())
    assert flow["counts"]["Interviewed"] == np.unique(record.i[record.accepted.astype(bool)]).size
    assert flow["counts"]["never_invited"] == n - np.unique(record.i[record.invite_wave > 0]).size
    funnel_metrics = finished_run.metrics["outcomes"]["funnel"]
    assert flow["counts"]["No interview"] == funnel_metrics["applicants_without_interview"]
    assert flow["counts"]["invited_no_interview"] >= 1  # this run has one: invited and interviewed differ
    strength = np.asarray(data.population.applicants.strength)
    weakest = strength <= flow["bands"][0]["high"]
    assert flow["bands"][0]["counts"]["Applicants"] == int(weakest.sum())
    assert flow["bands"][0]["counts"]["Matched"] == int((record.match_program[weakest] >= 0).sum())
    lows = [band["low"] for band in flow["bands"]]
    assert lows == sorted(lows)
    assert all(band["low"] <= band["high"] for band in flow["bands"])


def test_the_applicants_flow_chart_has_a_summary_table_and_a_switch(finished_run):
    chart = run_charts(RunData(finished_run), ("applicant_flow",))["applicant_flow"]
    assert chart["summary"].startswith("Of 60 applicants,")
    assert "of the bottom 20% matched, against" in chart["summary"]
    assert [row["label"] for row in chart["rows"]] == [*STRENGTH_BANDS, "All applicants"]
    counts = chart["payload"]["counts"]
    # Who makes up each (non-empty) drop-off: the bottom fifth's share of it, as the drop-off bars show.
    weakest = chart["payload"]["bands"][0]["counts"]
    held = [
        f"{weakest[drop]:,} of the {counts[drop]:,} {who}"
        for drop, who in (
            ("No interview", "with no interview"),
            ("Interviewed, not matched", "interviewed but not matched"),
        )
        if counts[drop]
    ]
    assert held
    assert chart["summary"].endswith(f" The bottom 20% make up {' and '.join(held)}.")
    assert chart["rows"][-1] == {
        "label": "All applicants",
        "low": None,
        "high": None,
        "applicants": counts["Applicants"],
        "never_invited": counts["never_invited"],
        "invited_no_interview": counts["invited_no_interview"],
        "interviewed": counts["Interviewed"],
        "not_matched": counts["Interviewed, not matched"],
        "matched": counts["Matched"],
        "match_share": counts["Matched"] / counts["Applicants"],
    }
    assert chart["payload"]["notes"]["No interview"] == [
        ["Never invited", counts["never_invited"]],
        ["Invited, no interview", counts["invited_no_interview"]],
    ]
    assert chart["switchable"] is True
    key = chart["switch_key"]  # a scale from the bottom 20% (red) to the top 20% (blue), in the diverging tokens
    assert [step["label"] for step in key["steps"]] == list(STRENGTH_BANDS)
    assert [step["range"] for step in key["steps"]] == [
        "0\u201320",
        "20\u201340",
        "40\u201360",
        "60\u201380",
        "80\u2013100",
    ]
    assert [step["dot"] for step in key["steps"]] == [f"viz-dot-div-{k}" for k in range(1, 6)]
    assert (key["caption"], key["low"], key["high"]) == ("Strength percentile", "weaker", "stronger")


def test_strengths_too_alike_disable_the_switch(finished_run, monkeypatch):
    monkeypatch.setattr("nrmps.charts.strength_bands", lambda strength: None)
    chart = run_charts(RunData(finished_run), ("applicant_flow",))["applicant_flow"]
    assert chart["payload"]["bands"] is None
    assert chart["switchable"] is False
    assert chart["switch_note"] == "too many applicants share a strength to split them into fifths"
    assert chart["switch_key"] is None
    assert [row["label"] for row in chart["rows"]] == ["All applicants"]


def test_the_summary_shows_the_applicants_flow_split_by_strength(auth_client, finished_run):
    """The summary card ends with the applicants' flow, its Colour by strength switch on from the start (a remembered
    choice still wins in the browser); the Applications and interviews tab's starts off."""
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    summary = auth_client.get(reverse("nrmps:run_detail", kwargs=kwargs)).content.decode()
    assert 'data-chart="flow"' in summary
    assert 'id="chart-applicant-flow" type="application/json"' in summary
    assert 'data-chart-switch="bands" checked>' in summary
    assert "vendor/echarts/6.1.0/echarts.min.js" in summary
    applications = auth_client.get(reverse("nrmps:run_applications", kwargs=kwargs)).content.decode()
    assert 'data-chart-switch="bands">' in applications


def test_the_applications_tab_shows_the_flow_with_its_switch(auth_client, finished_run):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    body = auth_client.get(reverse("nrmps:run_applications", kwargs=kwargs)).content.decode()
    assert 'data-chart="flow"' in body
    assert 'role="switch"' in body
    assert 'data-chart-switch="bands"' in body
    assert 'data-chart-switch-key="bands" hidden' in body
    assert "Colour by strength" in body
    assert 'aria-label="Key: strength percentile, from weaker to stronger"' in body
    assert "viz-dot-div-1" in body
    assert "viz-dot-div-5" in body
    assert escape(str(help_registry.CHARTS["applicant_flow"].title)) in body


# --- Plan step 5.3: the charts of the Match tab -----------------------------------------------------------------------


def _market(strength, quality, capacity, program, certified=None, filled=None):
    """Return a stand-in for a run's data: applicants with strengths matched to `program` (-1: not matched)."""
    program = np.asarray(program)
    capacity = np.asarray(capacity)
    return SimpleNamespace(
        population=SimpleNamespace(
            applicants=SimpleNamespace(strength=np.asarray(strength, dtype=float)),
            programs=SimpleNamespace(quality=np.asarray(quality, dtype=float), capacity=capacity),
        ),
        stages=SimpleNamespace(
            match_program=program,
            certified=program >= 0 if certified is None else np.asarray(certified),
            filled=np.bincount(program[program >= 0], minlength=capacity.size) if filled is None else filled,
        ),
    )


def test_the_choices_of_matched_applicants_are_the_run_s_distribution(finished_run):
    match = finished_run.metrics["outcomes"]["match"]
    payload = matched_choice(finished_run.metrics)
    assert payload["labels"] == list(CHOICE_BINS)
    assert payload["names"][0] == "1st choice"
    assert payload["names"][2] == "3rd choice"
    assert payload["names"][-1] == "11th choice or lower"
    assert payload["counts"] == [match["rank_distribution"][label] for label in CHOICE_BINS]
    assert sum(payload["counts"]) == match["matched"]
    chart = run_charts(RunData(finished_run), ("matched_choice",))["matched_choice"]
    assert sum(row["share"] for row in chart["rows"]) == pytest.approx(1)
    assert f"({match['first_choice_share'] * 100:.1f}%) matched to their first choice" in chart["summary"]
    assert f"({match['top3_share'] * 100:.1f}%) to one of their first three" in chart["summary"]


def test_no_choices_without_a_match():
    assert matched_choice({}) is None
    assert matched_choice({"outcomes": {"match": {"rank_distribution": dict.fromkeys(CHOICE_BINS, 0)}}}) is None


def test_who_matched_where_counts_every_applicant_once(finished_run):
    data = RunData(finished_run)
    record, population = data.stages, data.population
    payload = sorting(data)
    counts = np.asarray(payload["counts"])
    assert counts.shape == (5, 6)
    assert counts.sum() == population.n_applicants
    matched = record.match_program >= 0
    assert counts[:, 0].sum() == int((~matched).sum())
    assert [row["total"] for row in payload["rows"]] == counts.sum(axis=1).tolist()
    assert [row["label"] for row in payload["rows"]] == list(STRENGTH_BANDS)
    assert [column["label"] for column in payload["columns"]] == ["Not matched", *STRENGTH_BANDS]
    # Each matched column holds the applicants matched to the programs of that quality fifth.
    fifth = strength_bands(np.asarray(population.programs.quality, dtype=float))
    for b in range(5):
        assert counts[:, b + 1].sum() == int(record.filled[fifth == b].sum())
    expected = spearmanr(
        population.applicants.strength[matched], population.programs.quality[record.match_program[matched]]
    ).statistic
    assert payload["sorting"] == pytest.approx(expected, abs=0.001)


def test_a_perfectly_sorted_market_lies_on_the_diagonal():
    """Ten applicants, five programs with two positions: the strongest two at the best program, and so on down.

    The sorting is just under 1: the two applicants of a program share its quality, and a rank correlation with ties
    cannot reach 1 (with one position per program it does).
    """
    data = _market(strength=range(10), quality=range(5), capacity=[2] * 5, program=np.arange(10) // 2)
    payload = sorting(data)
    assert payload["sorting"] == 0.985
    assert payload["counts"] == [[0, *(2 if column == row else 0 for column in range(5))] for row in range(5)]
    reverse = sorting(_market(strength=range(10), quality=range(5), capacity=[2] * 5, program=(9 - np.arange(10)) // 2))
    assert reverse["sorting"] == -0.985
    assert reverse["counts"][0] == [0, 0, 0, 0, 0, 2]  # the weakest two at the best program
    singles = _market(strength=range(10), quality=range(10), capacity=[1] * 10, program=np.arange(10))
    assert sorting(singles)["sorting"] == 1


def test_unmatched_applicants_fill_the_first_column_and_stay_out_of_the_sorting():
    program = np.array([-1, -1, -1, -1, 0, 1, 2, 3, 4, 4])
    payload = sorting(_market(strength=range(10), quality=range(5), capacity=[1, 1, 1, 1, 2], program=program))
    assert [row[0] for row in payload["counts"]] == [2, 2, 0, 0, 0]
    assert payload["counts"][4] == [0, 0, 0, 0, 0, 2]
    assert payload["sorting"] == pytest.approx(spearmanr(range(4, 10), [0, 1, 2, 3, 4, 4]).statistic, abs=0.001)


def test_the_sorting_chart_s_summary_and_table(finished_run):
    chart = run_charts(RunData(finished_run), ("sorting",))["sorting"]
    payload = chart["payload"]
    assert chart["summary"].startswith(f"Sorting is {payload['sorting']:.2f}: the rank correlation")
    assert "of the bottom 20%" in chart["summary"]
    assert [row["label"] for row in chart["rows"]] == list(reversed(STRENGTH_BANDS))  # the strongest first
    assert chart["column_ranges"] == STRENGTH_RANGES
    for row, counts in zip(chart["rows"], reversed(payload["counts"]), strict=True):
        assert [cell["count"] for cell in row["cells"]] == counts
        assert sum(cell["share"] for cell in row["cells"]) == pytest.approx(1)
    json.dumps(payload)


def test_sides_that_cannot_be_split_into_fifths_have_no_sorting_chart():
    few_programs = _market(strength=range(10), quality=range(4), capacity=[3] * 4, program=np.arange(10) % 4)
    assert sorting(few_programs) is None
    assert program_fill(few_programs) is None
    same_quality = _market(strength=range(10), quality=[1] * 5, capacity=[2] * 5, program=np.arange(10) // 2)
    assert sorting(same_quality) is None
    nobody_matched = _market(strength=range(10), quality=range(5), capacity=[2] * 5, program=[-1] * 10)
    assert sorting(nobody_matched)["sorting"] is None
    assert [row[0] for row in sorting(nobody_matched)["counts"]] == [2] * 5


def test_positions_filled_by_program_quality_add_up(finished_run):
    data = RunData(finished_run)
    match = finished_run.metrics["outcomes"]["match"]
    payload = program_fill(data)
    filled, unfilled = (series["counts"] for series in payload["series"])
    programs, short = (extra["values"] for extra in payload["extra"])
    assert [series["name"] for series in payload["series"]] == ["Filled", "Unfilled"]
    assert sum(filled) == match["matched"]
    assert sum(unfilled) == match["unfilled_positions"]
    assert sum(filled) + sum(unfilled) == data.population.n_positions
    assert sum(programs) == data.population.n_programs
    assert sum(short) == match["programs_unfilled"]
    assert payload["labels"] == list(STRENGTH_RANGES)
    chart = run_charts(data, ("program_fill",))["program_fill"]
    assert f"The match filled {match['matched']:,} of {data.population.n_positions:,} positions" in chart["summary"]
    assert f"{match['programs_unfilled']:,} of {data.population.n_programs:,} programs" in chart["summary"]
    assert [row["positions"] for row in chart["rows"]] == [a + b for a, b in zip(filled, unfilled, strict=True)]


def test_unfilled_positions_are_counted_in_their_programs_fifth():
    """Five programs of two positions; only the best two fill, and the middle one fills one."""
    program = np.array([-1] * 5 + [2, 3, 3, 4, 4])
    payload = program_fill(_market(strength=range(10), quality=range(5), capacity=[2] * 5, program=program))
    filled, unfilled = (series["counts"] for series in payload["series"])
    assert filled == [0, 0, 1, 2, 2]
    assert unfilled == [2, 2, 1, 0, 0]
    assert payload["extra"][0]["values"] == [1, 1, 1, 1, 1]
    assert payload["extra"][1]["values"] == [1, 1, 1, 0, 0]
    assert payload["names"][0] == "Bottom 20% of programs by quality"


def test_who_matched_by_strength_agrees_with_the_run_s_table(finished_run):
    """The chart's deciles are the table's: the same applicants, lists and match rates."""
    data = RunData(finished_run)
    outcomes = finished_run.metrics["outcomes"]
    payload = match_by_strength(data)
    got, listed, unlisted = (series["counts"] for series in payload["series"])
    assert [series["name"] for series in payload["series"]] == ["Matched", "Not matched", "No rank order list"]
    for d, row in enumerate(outcomes["by_strength_decile"]):
        assert got[d] + listed[d] + unlisted[d] == row["applicants"]
        assert got[d] + listed[d] == row["certified"]
        assert payload["extra"][0]["values"][d] == (pytest.approx(row["match_rate"]) if row["certified"] else None)
    assert sum(got) == outcomes["match"]["matched"]
    assert sum(unlisted) == data.population.n_applicants - outcomes["match"]["certified"]
    assert payload["labels"] == [str(d) for d in range(1, 11)]
    assert payload["names"][0] == "Strength decile 1 (the weakest tenth)"
    assert payload["names"][9] == "Strength decile 10 (the strongest tenth)"
    chart = run_charts(data, ("match_by_strength",))["match_by_strength"]
    assert f"{outcomes['match']['matched']:,} matched" in chart["summary"]
    assert [row["total"] for row in chart["rows"]] == [row["applicants"] for row in outcomes["by_strength_decile"]]


def test_who_matched_by_strength_needs_ten_applicants():
    nine = _market(strength=range(9), quality=range(5), capacity=[2] * 5, program=np.arange(9) // 2)
    assert match_by_strength(nine) is None
    ten = _market(
        strength=range(10),
        quality=range(5),
        capacity=[2] * 5,
        program=[-1, -1, 0, 0, 1, 1, 2, 2, 3, 3],
        certified=[False, True, True, True, True, True, True, True, True, True],
    )
    payload = match_by_strength(ten)
    got, listed, unlisted = (series["counts"] for series in payload["series"])
    assert (got, listed, unlisted) == ([0, 0, 1, 1, 1, 1, 1, 1, 1, 1], [0, 1, *[0] * 8], [1, *[0] * 9])
    assert payload["extra"][0]["values"][:3] == [None, 0, 1]


def test_the_match_tab_shows_its_charts_with_their_numbers(auth_client, finished_run):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    body = auth_client.get(reverse("nrmps:run_match", kwargs=kwargs)).content.decode()
    for kind in ("bars", "heatmap", "shares"):
        assert f'data-chart="{kind}"' in body, kind
    assert body.count('data-chart="shares"') == 3
    assert 'data-chart="shares" data-payload="chart-program-fill" data-series="program"' in body
    for text in (
        "Who matched where",
        "Matched to a program, by its quality percentile",
        "Programs with an unfilled position",
        "Match rate with a list",
        "Share of matched",
        "11th choice or lower",
        "Sorting is ",
        "Programs ranked",
        "applicants with a rank order list",
    ):
        assert text in body, text
    assert body.count("The numbers") == len(TAB_CHARTS["match"])
    for key in TAB_CHARTS["match"]:
        assert escape(str(help_registry.CHARTS[key].title)) in body
        assert help_registry.CHARTS[key].tab == "match"


# --- Plan step 5.3: interviews per applicant, and the match rate by list length ---------------------------------------


def _interviewed(interviews, *, matched=None, ranked=None, strength=None):
    """Return a stand-in for a run's data: applicant k had interviews[k] interviews and ranked them all (or `ranked`
    of them), and matched if matched[k]."""
    interviews = np.asarray(interviews)
    n = interviews.size
    i = np.repeat(np.arange(n), interviews)
    place = np.concatenate([np.arange(1, count + 1) for count in interviews]) if i.size else np.zeros(0, dtype=int)
    keep = interviews if ranked is None else np.asarray(ranked)
    return SimpleNamespace(
        population=SimpleNamespace(
            n_applicants=n,
            applicants=SimpleNamespace(
                strength=np.arange(n, dtype=float) if strength is None else np.asarray(strength)
            ),
        ),
        stages=SimpleNamespace(
            i=i,
            accepted=np.ones(i.size, dtype=bool),
            applicant_rank=np.where(place <= keep[i], place, 0),
            match_program=np.where(np.zeros(n, dtype=bool) if matched is None else np.asarray(matched), 0, -1),
        ),
    )


def test_counts_per_applicant_get_a_bin_each_and_share_the_last_from_twenty():
    labels, bins = _count_bins(np.array([0, 3, 3, 1]), 0)
    assert labels == ["0", "1", "2", "3"]
    assert bins.tolist() == [0, 3, 3, 1]
    labels, bins = _count_bins(np.array([1, 20, 25, 7]), 1)
    assert labels[0] == "1"
    assert labels[-1] == "20+"
    assert len(labels) == 20
    assert bins.tolist() == [0, 19, 19, 6]
    assert _count_bins(np.array([20, 2]), 1)[0][-1] == "20"  # exactly twenty is its own bin, not "20+"
    assert _count_names(["1", "2", "20+"], "interview", "interviews") == [
        "1 interview",
        "2 interviews",
        "20 or more interviews",
    ]


def test_interviews_per_applicant_are_the_run_s(finished_run):
    data = RunData(finished_run)
    funnel_metrics = finished_run.metrics["outcomes"]["funnel"]
    payload = interviews_per_applicant(data)
    n = data.population.n_applicants
    assert sum(payload["counts"]) == n
    assert payload["counts"][0] == funnel_metrics["applicants_without_interview"]
    assert payload["mean"] == pytest.approx(funnel_metrics["interviews_per_applicant"])
    held = sum(int(label) * count for label, count in zip(payload["labels"], payload["counts"], strict=True))
    assert held == int(data.stages.accepted.sum())
    assert payload["names"][:3] == ["No interview", "1 interview", "2 interviews"]
    assert len(payload["bands"]) == 5
    for k, count in enumerate(payload["counts"]):
        assert sum(band["counts"][k] for band in payload["bands"]) == count
    assert 0 <= payload["gini"] < 1
    assert 0.1 <= payload["top_share"] <= 1
    json.dumps(payload)


def test_the_interviews_chart_has_a_summary_a_table_and_the_strength_switch(finished_run):
    chart = run_charts(RunData(finished_run), ("interviews",))["interviews"]
    payload = chart["payload"]
    assert chart["summary"].startswith(f"Applicants had {payload['mean']:.1f} interviews on average: ")
    assert f"(Gini {payload['gini']:.2f})" in chart["summary"]
    assert "By strength, the bottom 20% had " in chart["summary"]
    assert chart["switchable"] is True
    assert chart["switch_note"] == ""
    assert [step["dot"] for step in chart["switch_key"]["steps"]] == [f"viz-dot-div-{k}" for k in range(1, 6)]
    assert chart["band_ranges"] == STRENGTH_RANGES
    assert [row["count"] for row in chart["rows"]] == payload["counts"]
    assert [row["bands"] for row in chart["rows"]] == [
        [band["counts"][k] for band in payload["bands"]] for k in range(len(payload["counts"]))
    ]


def test_interviews_concentrate_and_follow_strength_in_a_constructed_market():
    """Ten applicants: the weakest five have none, the strongest five have four each."""
    payload = interviews_per_applicant(_interviewed([0] * 5 + [4] * 5))
    assert payload["labels"] == ["0", "1", "2", "3", "4"]
    assert payload["counts"] == [5, 0, 0, 0, 5]
    assert payload["mean"] == 2
    assert payload["top_share"] == pytest.approx(0.2)  # one applicant of ten holds four of the twenty interviews
    assert payload["gini"] == pytest.approx(0.5)
    assert [band["mean"] for band in payload["bands"]] == [0, 0, 2, 4, 4]
    assert payload["bands"][0]["counts"] == [2, 0, 0, 0, 0]
    assert payload["bands"][4]["counts"] == [0, 0, 0, 0, 2]
    nobody = interviews_per_applicant(_interviewed([0] * 10))
    assert (nobody["counts"], nobody["top_share"], nobody["gini"]) == ([10], None, None)
    many = interviews_per_applicant(_interviewed([25, 20, 3]))
    assert many["labels"][-1] == "20+"
    assert many["counts"][-1] == 2
    assert many["names"][-1] == "20 or more interviews"
    assert many["bands"] is None  # three applicants cannot be split into fifths
    chart = run_charts(
        SimpleNamespace(run=SimpleNamespace(metrics={}, population_source={}), **vars(_interviewed([25, 20, 3]))),
        ("interviews",),
    )
    assert chart["interviews"]["switchable"] is False
    assert chart["interviews"]["switch_note"] == "fewer than 5 applicants"
    assert "had 20 or more." in chart["interviews"]["summary"]


def test_the_match_rate_by_list_length_counts_applicants_with_a_list(finished_run):
    data = RunData(finished_run)
    match = finished_run.metrics["outcomes"]["match"]
    payload = match_by_list_length(data)
    got, missed = (series["counts"] for series in payload["series"])
    assert [series["name"] for series in payload["series"]] == ["Matched", "Not matched"]
    assert sum(got) == match["matched"]
    assert sum(got) + sum(missed) == match["certified"]
    assert payload["labels"][0] == "1"
    assert payload["names"][0] == "1 program ranked"
    assert payload["names"][1] == "2 programs ranked"
    lengths = sum(int(label) * (g + m) for label, g, m in zip(payload["labels"], got, missed, strict=True))
    assert lengths == int((data.stages.applicant_rank > 0).sum())
    chart = run_charts(data, ("list_length",))["list_length"]
    assert chart["summary"].startswith(f"Of {match['certified']:,} applicants with a rank order list, ")
    assert f"{match['matched']:,} matched ({match['match_rate'] * 100:.1f}%)" in chart["summary"]
    assert [row["total"] for row in chart["rows"]] == [g + m for g, m in zip(got, missed, strict=True)]
    json.dumps(payload)


def test_the_match_rate_by_list_length_in_a_constructed_market():
    """Six applicants: no list, lists of 1, 1, 3, 3 and 3; one of the short lists and two of the long ones match."""
    data = _interviewed([0, 1, 1, 3, 3, 3], matched=[False, True, False, True, True, False])
    payload = match_by_list_length(data)
    assert payload["labels"] == ["1", "2", "3"]
    assert [series["counts"] for series in payload["series"]] == [[1, 0, 2], [1, 0, 1]]
    chart = run_charts(
        SimpleNamespace(run=SimpleNamespace(metrics={}, population_source={}), **vars(data)), ("list_length",)
    )
    chart = chart["list_length"]
    assert chart["summary"] == (
        "Of 5 applicants with a rank order list, 3 matched (60.0%): 50.0% of the 2 who ranked 1 program, and 66.7% "
        "of the 3 who ranked 3 programs."
    )
    assert [row["rate"] for row in chart["rows"]] == [0.5, None, pytest.approx(2 / 3)]
    assert [row["label"] for row in chart["rows"]] == ["1 program", "2 programs", "3 programs"]


def test_lists_shorter_than_the_interviews_and_lists_all_alike():
    """A list holds the programs the applicant ranked, which can be fewer than their interviews."""
    shorter = _interviewed([4, 4, 2], ranked=[1, 3, 0], matched=[True, True, False])
    assert match_by_list_length(shorter)["labels"] == ["1", "2", "3"]
    assert [series["counts"] for series in match_by_list_length(shorter)["series"]] == [[1, 0, 1], [0, 0, 0]]
    assert match_by_list_length(_interviewed([2, 2, 2], matched=[True, False, True])) is None  # one bar says nothing
    assert match_by_list_length(_interviewed([0, 0])) is None
    long_lists = match_by_list_length(_interviewed([1, 22, 30], matched=[False, True, True]))
    assert long_lists["labels"][-1] == "20+"
    assert long_lists["names"][-1] == "20 or more programs ranked"
    assert long_lists["series"][0]["counts"][-1] == 2


def test_the_applications_tab_shows_who_gets_the_interviews(auth_client, finished_run):
    kwargs = {"pk": finished_run.simulation_id, "number": finished_run.number}
    body = auth_client.get(reverse("nrmps:run_applications", kwargs=kwargs)).content.decode()
    assert 'data-chart="bars" data-payload="chart-interviews"' in body
    assert escape(str(help_registry.CHARTS["interviews"].title)) in body
    assert body.count('data-chart-switch="bands"') == 2  # the applicants' flow and the interviews
    assert body.count('data-chart-switch-key="bands" hidden') == 2
    assert "interviews on average" in body
    assert "No interview</th>" in body
