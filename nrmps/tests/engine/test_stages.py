"""Applications to the match (model_spec.md §7-8): invariants, strategies, exactness, CRN and the match oracle."""

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nrmps.engine.match import (
    UNMATCHED,
    Lists,
    applicant_proposing,
    blocking_pairs,
    program_proposing,
)
from nrmps.engine.pipeline import run_pipeline
from nrmps.engine.rol import MAX_LIST
from nrmps.engine.signals import NO_SIGNAL
from nrmps.engine.validate import oracle_match
from nrmps.params import SimulationParams

GOLD_SILVER = [{"name": "gold", "count": 3, "boost": 0.8}, {"name": "silver", "count": 5, "boost": 0.4}]


def _run(seed: int = 3, **groups):
    base = {"market": {"n_applicants": 400}}
    return run_pipeline(SimulationParams.model_validate(base | groups), seed)


def _per_applicant(result, mask) -> np.ndarray:
    return np.bincount(result.applications.i[mask], minlength=result.population.n_applicants)


def _per_program(result, mask) -> np.ndarray:
    return np.bincount(result.applications.j[mask], minlength=result.population.n_programs)


# --- Applications -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", ["top_n", "portfolio", "random", "all"])
def test_each_applicant_applies_to_k_distinct_programs(strategy):
    result = _run(apps={"strategy": strategy})
    apps = result.applications
    m = result.population.n_programs
    assert np.array_equal(_per_applicant(result, np.ones(apps.size, bool)), apps.count)
    assert apps.count.min() >= 1
    assert apps.count.max() <= m
    pairs = apps.i.astype(np.int64) * m + apps.j
    assert np.unique(pairs).size == pairs.size
    assert np.all(np.diff(pairs) > 0)  # sorted by applicant, then program
    if strategy == "all":
        assert apps.size == result.population.n_applicants * m


def test_top_n_applies_to_the_best_ranked_programs():
    apps = _run(apps={"strategy": "top_n"}).applications
    assert np.all(apps.pre_rank <= apps.count[apps.i])


def test_fixed_count_and_group_overrides():
    groups = SimulationParams().applicants.groups
    groups = [g.model_dump() | ({"applications_mean": 5.0} if g.name == "us_img" else {}) for g in groups]
    result = _run(apps={"count_dist": "fixed", "mean": 12}, applicants={"groups": groups})
    applicants = result.population.applicants
    img = applicants.group == applicants.group_names.index("us_img")
    assert np.all(result.applications.count[img] == 5)
    assert np.all(result.applications.count[~img] == 12)


def test_portfolio_takes_reach_target_and_safety_programs():
    result = _run(apps={"strategy": "portfolio", "count_dist": "fixed", "mean": 20})
    categories = np.bincount(result.applications.category, minlength=3) / result.applications.size
    assert categories[1] > 0.1  # reach
    assert categories[2] > 0.1  # safety


def test_counts_follow_the_distribution():
    result = _run(market={"n_applicants": 3000}, apps={"count_dist": "poisson", "mean": 25})
    assert result.applications.count.mean() == pytest.approx(25, abs=0.5)


# --- Signals ----------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("allocation", ["top_utility", "realistic", "random"])
def test_signals_go_to_applications_within_the_tier_counts(allocation):
    result = _run(signals={"tiers": GOLD_SILVER, "allocation": allocation})
    tier = result.signals.tier
    for index, count in enumerate((3, 5)):
        assert _per_applicant(result, tier == index).max() <= count
    total = _per_applicant(result, tier != NO_SIGNAL)
    assert np.all(total == np.minimum(8, result.applications.count))


def test_top_utility_signals_the_best_applications():
    result = _run(signals={"tiers": GOLD_SILVER, "allocation": "top_utility"})
    gold = result.signals.tier == 0
    assert result.applications.pre_rank[gold].max() <= result.applications.pre_rank[~gold].max()
    for applicant in range(20):
        mine = result.applications.i == applicant
        ranks = result.applications.pre_rank[mine]
        tiers = result.signals.tier[mine]
        assert np.all(np.diff(tiers[np.argsort(ranks)].astype(int)[tiers[np.argsort(ranks)] >= 0]) >= 0)


def test_group_signal_limit_and_program_use():
    groups = [g.model_dump() | {"n_signals": 2} for g in SimulationParams().applicants.groups]
    result = _run(signals={"tiers": GOLD_SILVER, "program_use_share": 0.0}, applicants={"groups": groups})
    assert _per_applicant(result, result.signals.tier != NO_SIGNAL).max() <= 2
    assert not result.signals.program_uses.any()
    assert result.metrics["outcomes"]["signals"]["programs_using_signals"] == 0


# --- Invitations and interviews ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("strategy", ["top_score", "threshold_then_top", "threshold_then_random", "signal_first"])
@pytest.mark.parametrize("order", ["best_first", "first_come"])
def test_invitations_respect_slots_caps_and_applications(strategy, order):
    result = _run(
        signals={"tiers": GOLD_SILVER},
        invites={"strategy": strategy, "screen_attribute": "board_scores", "screen_min_percentile": 0.2},
        interview={"acceptance_order": order, "applicant_cap": 6},
    )
    inv = result.invitations
    invited, accepted = inv.wave > 0, inv.accepted
    assert np.all(invited[accepted])  # accepted implies invited (and every pair is an application)
    assert _per_applicant(result, accepted).max() <= 6
    assert np.all(_per_program(result, accepted) <= inv.slots)
    if strategy.startswith("threshold"):
        board = result.population.applicants.attributes[:, 0]
        passed = np.argsort(np.argsort(board, kind="stable"), kind="stable") / (board.size - 1) >= 0.2
        assert np.all(passed[result.applications.i[invited]])


def test_signal_first_invites_signalled_applicants_before_others():
    result = _run(signals={"tiers": GOLD_SILVER}, invites={"strategy": "signal_first", "rounds": 1})
    signalled = result.signals.tier != NO_SIGNAL
    invited = result.invitations.wave > 0
    # For each program, no unsignalled applicant is invited while a signalled one is left out.
    for program in range(result.population.n_programs):
        mine = result.applications.j == program
        if (invited & mine & ~signalled).any():
            assert not (mine & signalled & ~invited & result.invitations.eligible).any()


def test_interview_slots_are_rounded_up_without_float_noise():
    from nrmps.engine.invitations import interview_slots

    result = _run(invites={"interviews_per_position": 1.1})
    slots = interview_slots(
        SimulationParams.model_validate({"invites": {"interviews_per_position": 1.1}}), result.population
    )
    assert np.all(slots == np.ceil(np.round(1.1 * result.population.programs.capacity, 9)))


def test_full_informativeness_reveals_the_realised_utility():
    result = _run(info={"interview_informativeness": 1.0})
    held = result.invitations.accepted
    interviews = result.interviews
    assert np.array_equal(interviews.applicant_post[held], interviews.applicant_realised[held])
    assert np.array_equal(interviews.program_post[held], interviews.program_realised[held])
    assert np.all(np.isnan(interviews.applicant_post[~held]))


def test_no_fit_shock_and_no_information_keeps_the_pre_interview_view():
    result = _run(info={"interview_informativeness": 0.0, "fit_shock_sd": 0.0})
    held = result.invitations.accepted
    assert np.allclose(result.interviews.applicant_post[held], result.applications.observed[held], rtol=0, atol=1e-12)
    assert np.allclose(result.interviews.program_post[held], result.invitations.program_view[held], rtol=0, atol=1e-12)


def test_changing_informativeness_keeps_everything_before_interviews():
    """Acceptance test 2: kappa changes only the interview stage and what follows."""
    first = _run(signals={"tiers": GOLD_SILVER}, info={"interview_informativeness": 0.6})
    second = _run(signals={"tiers": GOLD_SILVER}, info={"interview_informativeness": 0.1})
    assert np.array_equal(first.applications.j, second.applications.j)
    assert np.array_equal(first.signals.tier, second.signals.tier)
    assert np.array_equal(first.invitations.accepted, second.invitations.accepted)
    assert np.array_equal(first.interviews.applicant_realised, second.interviews.applicant_realised, equal_nan=True)
    assert not np.array_equal(first.interviews.applicant_post, second.interviews.applicant_post, equal_nan=True)


# --- Rank order lists -------------------------------------------------------------------------------------------------


def _consecutive(groups: np.ndarray, ranks: np.ndarray) -> bool:
    """True if, within each group, the ranks are exactly 1..n."""
    for group in np.unique(groups):
        values = np.sort(ranks[groups == group])
        if not np.array_equal(values, np.arange(1, values.size + 1)):
            return False
    return True


@pytest.mark.parametrize(
    "rol",
    [
        {"applicant_policy": "all_interviewed", "program_policy": "all_interviewed"},
        {"applicant_policy": "top_k", "applicant_top_k": 3, "program_policy": "dnr_quantile"},
        {"applicant_policy": "above_reservation", "reservation_utility": 0.0, "program_policy": "dnr_threshold"},
        {"applicant_policy": "likelihood_weighted", "program_policy": "dnr_quantile", "program_dnr_quantile": 0.5},
    ],
)
def test_lists_are_strict_and_hold_only_interviews(rol):
    result = _run(rol=rol)
    lists, held = result.lists, result.invitations.accepted
    on_applicant, on_program = lists.applicant_rank > 0, lists.program_rank > 0
    assert np.all(held[on_applicant])
    assert np.all(held[on_program])
    assert _consecutive(result.applications.i[on_applicant], lists.applicant_rank[on_applicant])
    assert _consecutive(result.applications.j[on_program], lists.program_rank[on_program])
    assert lists.applicant_rank.max() <= MAX_LIST
    if rol.get("applicant_policy") == "top_k":
        assert lists.applicant_rank.max() <= 3
    if rol.get("applicant_policy") == "above_reservation":
        assert np.all(result.interviews.applicant_post[on_applicant] >= 0.0)


def test_only_applicant_lists_are_limited_to_300():
    params = {
        "market": {"n_applicants": 1200, "applicants_per_position": 1.0, "n_programs": 2},
        "apps": {"strategy": "all"},
        "invites": {"interviews_per_position": 1.0},
        "interview": {"applicant_cap": 2},
        "rol": {"program_policy": "all_interviewed"},
    }
    result = run_pipeline(SimulationParams.model_validate(params), 3)
    ranked = _per_program(result, result.lists.program_rank > 0)
    assert ranked.max() > MAX_LIST  # a 600-position program ranks everyone it interviewed
    assert np.array_equal(ranked, _per_program(result, result.invitations.accepted))
    assert result.metrics["outcomes"]["checks"]["passed"]


def test_do_not_rank_share_is_rounded_up():
    result = _run(rol={"program_policy": "dnr_quantile", "program_dnr_quantile": 0.1})
    interviewed = _per_program(result, result.invitations.accepted)
    ranked = _per_program(result, result.lists.program_rank > 0)
    expected = np.where(interviewed > 0, np.maximum(1, np.ceil(np.round(interviewed * 0.9, 9))), 0)
    assert np.array_equal(ranked, expected)


def test_applicant_lists_follow_the_post_interview_view():
    result = _run()
    on_list = result.lists.applicant_rank > 0
    for applicant in range(30):
        mine = on_list & (result.applications.i == applicant)
        order = np.argsort(result.lists.applicant_rank[mine])
        assert np.all(np.diff(result.interviews.applicant_post[mine][order]) <= 0)


# --- The match ------------------------------------------------------------------------------------------------------


def test_every_run_is_stable_and_within_capacity():
    result = _run(match={"compare_both": True})
    match = result.match
    assert match.blocking_pairs == 0
    assert np.all(match.filled <= result.population.programs.capacity)
    matched = np.flatnonzero(match.program != UNMATCHED)
    for applicant in matched[:50]:
        pair = np.flatnonzero(
            (result.applications.i == applicant) & (result.applications.j == match.program[applicant])
        )
        assert result.lists.applicant_rank[pair] > 0
        assert result.lists.program_rank[pair] > 0
    comparison = result.metrics["outcomes"]["match"]["comparison"]
    assert comparison["same_matched_applicants"]
    assert comparison["same_fill_per_program"]
    assert comparison["applicants_worse_off_when_applicants_propose"] == 0


def test_same_seed_gives_the_same_match_and_metrics():
    first, second = _run(seed=11), _run(seed=11)
    assert np.array_equal(first.match.program, second.match.program)
    assert first.metrics == second.metrics
    assert not np.array_equal(first.match.program, _run(seed=12).match.program)


@st.composite
def markets(draw):
    """Small random markets: applicants' lists, programs' lists (possibly leaving applicants out) and capacities."""
    n, m = draw(st.integers(1, 9)), draw(st.integers(1, 5))
    capacity = draw(st.lists(st.integers(1, 3), min_size=m, max_size=m))
    applicant_lists = [draw(st.permutations(range(m)).map(lambda p: p[: draw(st.integers(0, m))])) for _ in range(n)]
    program_lists = []
    for program in range(m):
        proposers = [a for a in range(n) if program in applicant_lists[a]]
        order = draw(st.permutations(proposers)) if proposers else []
        keep = draw(st.integers(0, len(order)))
        program_lists.append(list(order[:keep]))
    return applicant_lists, program_lists, capacity


def _lists(applicant_lists, program_lists, capacity) -> Lists:
    return Lists(
        applicant_lists=[list(choices) for choices in applicant_lists],
        applicant_rank=[{p: r for r, p in enumerate(choices, 1)} for choices in applicant_lists],
        program_lists=[list(choices) for choices in program_lists],
        program_rank=[{a: r for r, a in enumerate(choices, 1)} for choices in program_lists],
        capacity=list(capacity),
    )


@settings(max_examples=200, deadline=None)
@given(markets())
def test_deferred_acceptance_is_stable_and_agrees_with_the_oracle(market):
    lists = _lists(*market)
    by_applicants, by_programs = applicant_proposing(lists), program_proposing(lists)
    for match in (by_applicants, by_programs):
        assert blocking_pairs(lists, match) == []
        for program, capacity in enumerate(lists.capacity):
            assert match.count(program) <= capacity
        for applicant, program in enumerate(match):
            if program != UNMATCHED:
                assert program in lists.applicant_rank[applicant]
                assert applicant in lists.program_rank[program]
    assert by_applicants == oracle_match(lists, "resident")
    assert by_programs == oracle_match(lists, "hospital")
    # Rural hospitals theorem: the same applicants are matched and every program fills the same number of positions.
    assert [p == UNMATCHED for p in by_applicants] == [p == UNMATCHED for p in by_programs]
    for program in range(len(lists.capacity)):
        assert by_applicants.count(program) == by_programs.count(program)


def test_stage_decisions_round_trip_byte_for_byte():
    from nrmps.engine.persistence import stage_record, stages_from_npz, stages_to_npz

    result = _run(signals={"tiers": GOLD_SILVER}, match={"compare_both": True})
    data = stages_to_npz(stage_record(result))
    assert data == stages_to_npz(stage_record(_run(signals={"tiers": GOLD_SILVER}, match={"compare_both": True})))
    record = stages_from_npz(data)
    assert np.array_equal(record.match_program, result.match.program)
    assert np.array_equal(record.applicant_rank, result.lists.applicant_rank)
    assert record.alternative is not None
    assert stages_to_npz(record) == data
