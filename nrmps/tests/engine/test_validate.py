"""Validation of the lists and the match (plan step 3.7, STG-15): the checks, their power, and the report."""

import dataclasses
import io

import numpy as np
import pytest
from django.core.management import CommandError, call_command

from nrmps.engine.match import UNMATCHED, Lists, MatchResult, applicant_proposing, program_proposing
from nrmps.engine.pipeline import run_pipeline
from nrmps.engine.rol import MAX_LIST
from nrmps.engine.validate import (
    COUNT_CHECKS,
    FLAG_CHECKS,
    alternative_lists,
    list_checks,
    match_checks,
    passed,
    profitable_misreports,
)
from nrmps.params import SimulationParams
from nrmps.validation import validation_report


def _lists(applicant_lists, program_lists, capacity) -> Lists:
    return Lists(
        applicant_lists=[list(choices) for choices in applicant_lists],
        applicant_rank=[{p: r for r, p in enumerate(choices, 1)} for choices in applicant_lists],
        program_lists=[list(choices) for choices in program_lists],
        program_rank=[{a: r for r, a in enumerate(choices, 1)} for choices in program_lists],
        capacity=list(capacity),
    )


# Two applicants and two one-position programs whose preferences are opposed.
OPPOSED = _lists([[0, 1], [1, 0]], [[1, 0], [0, 1]], [1, 1])


def _result(program: list[int], capacity: int = 2, blocking: int = 0) -> MatchResult:
    matched = np.array(program, dtype=np.int32)
    return MatchResult(
        algorithm="applicant_proposing",
        program=matched,
        applicant_list_rank=np.zeros(len(program), dtype=np.int32),
        program_list_rank=np.zeros(len(program), dtype=np.int32),
        filled=np.bincount(matched[matched != UNMATCHED], minlength=capacity).astype(np.int32),
        blocking_pairs=blocking,
        alternative=None,
    )


def test_every_check_of_a_run_passes():
    params = SimulationParams.model_validate({"market": {"n_applicants": 300}, "match": {"compare_both": True}})
    checks = run_pipeline(params, 5).metrics["outcomes"]["checks"]
    assert set(checks) == set(COUNT_CHECKS) | set(FLAG_CHECKS) | {"passed"}
    assert all(checks[key] == 0 for key in COUNT_CHECKS)
    assert checks["rural_hospitals"] is True
    assert checks["applicant_optimal"] is True
    assert checks["passed"] is True


def test_without_the_comparison_the_flags_are_not_checked():
    checks = run_pipeline(SimulationParams.model_validate({"market": {"n_applicants": 100}}), 5).metrics["outcomes"]
    assert checks["checks"]["rural_hospitals"] is None
    assert checks["checks"]["passed"] is True


def test_list_checks_find_broken_lists():
    result = run_pipeline(SimulationParams.model_validate({"market": {"n_applicants": 100}}), 5)
    lists = result.lists
    assert list_checks(result.applications, result.invitations, lists) == {
        "ranked_without_interview": 0,
        "lists_not_strict": 0,
        "lists_too_long": 0,
    }
    ranked = np.flatnonzero(lists.applicant_rank > 0)
    owner = result.applications.i[ranked]
    mine = ranked[owner == np.flatnonzero(np.bincount(owner) >= 2)[0]]
    duplicate = lists.applicant_rank.copy()
    duplicate[mine[1]] = duplicate[mine[0]]  # two entries of one applicant's list share a rank
    not_interviewed = lists.program_rank.copy()
    not_interviewed[np.flatnonzero(~result.invitations.accepted)[0]] = 1
    too_long = lists.applicant_rank.copy()
    too_long[np.flatnonzero(too_long > 0)[0]] = MAX_LIST + 1

    def check(**ranks) -> dict[str, int]:
        return list_checks(result.applications, result.invitations, dataclasses.replace(lists, **ranks))

    assert check(applicant_rank=duplicate)["lists_not_strict"] == 1
    assert check(program_rank=not_interviewed)["ranked_without_interview"] == 1
    assert check(applicant_rank=too_long)["lists_too_long"] == 1
    assert check(program_rank=too_long)["lists_too_long"] == 0  # program lists have no limit


def test_match_checks_find_blocking_pairs_capacity_and_unranked_matches():
    lists = _lists([[0], [0], [1]], [[0, 1], [2]], [1, 1])
    good = match_checks(lists, _result([0, UNMATCHED, 1]))
    assert good == {
        "blocking_pairs": 0,
        "over_capacity": 0,
        "unranked_matches": 0,
        "rural_hospitals": None,
        "applicant_optimal": None,
    }
    assert passed(good)
    crowded = match_checks(lists, _result([0, 0, 1]))
    assert crowded["over_capacity"] == 1
    assert not passed(crowded)
    assert match_checks(lists, _result([0, UNMATCHED, 0]))["unranked_matches"] == 1
    assert not passed({"blocking_pairs": 1})
    assert not passed({"rural_hospitals": False})


def test_misreports_pay_only_when_programs_propose():
    assert applicant_proposing(OPPOSED) == [0, 1]
    assert program_proposing(OPPOSED) == [1, 0]
    assert profitable_misreports(OPPOSED, 0) == 0
    assert profitable_misreports(OPPOSED, 0, mechanism=program_proposing) >= 1  # dropping program 1 gets program 0


def test_alternative_lists_are_exhaustive_for_short_lists_and_sampled_for_long_ones():
    rng = np.random.default_rng(0)
    short = alternative_lists([3, 1, 2, 0], 65, rng)
    assert len(short) == len(set(short)) == 64  # every ordered subset of 4 programs but the list itself
    long = alternative_lists(list(range(10)), 50, rng)
    assert len(long) == len(set(long)) == 50
    assert () in long
    assert (0, 1, 2, 3, 4, 5, 6, 7, 9, 8) in long  # a swap of neighbours
    assert tuple(range(10)) not in long


def test_the_validation_report_passes():
    report = validation_report(markets=12, misreport_markets=3, seed=7)
    assert report.passed
    assert report.checks["blocking_pairs"].checked == 12
    assert report.checks["misreports"].checked > 0
    assert report.checks["oracle_applicants"].checked == 12
    text = report.markdown("manage.py nrmp_validate")
    assert text.startswith("# Validation report")
    assert "**Result: passed.**" in text


def test_the_command_writes_the_report_and_fails_on_a_failed_check(tmp_path, monkeypatch):
    out = io.StringIO()
    call_command("nrmp_validate", markets=3, misreport_markets=1, output=tmp_path / "report.md", stdout=out)
    assert "passed" in out.getvalue()
    assert "| Blocking pairs" in (tmp_path / "report.md").read_text()

    def failing(*args):
        report = validation_report(1, 0, 1)
        report.fail("blocking_pairs", 1, "invented")
        return report

    monkeypatch.setattr("nrmps.management.commands.nrmp_validate.validation_report", failing)
    with pytest.raises(CommandError, match="Validation failed"):
        call_command("nrmp_validate", markets=1, stdout=io.StringIO())
    with pytest.raises(CommandError, match="at least"):
        call_command("nrmp_validate", markets=0, stdout=io.StringIO())


def test_a_failed_report_lists_the_failures():
    report = validation_report(1, 0, 1)
    report.fail("blocking_pairs", 1, "seed 5")
    assert not report.passed
    text = report.markdown()
    assert "- Market 1: Blocking pairs" in text
    assert "**Result: FAILED.**" in text


def test_the_report_counts_a_failed_run_check(monkeypatch):
    def broken(params, seed):
        result = run_pipeline(params, seed)
        result.metrics["outcomes"]["checks"]["blocking_pairs"] = 1
        return result

    monkeypatch.setattr("nrmps.validation.run_pipeline", broken)
    report = validation_report(2, 0, 1)
    assert report.checks["blocking_pairs"].failed == 2
    assert not report.passed
