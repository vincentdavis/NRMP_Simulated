"""Checks of the rank order lists and the match against matching theory (model_spec.md §8 and §9).

`run_checks` runs on every run and is stored with the metrics: every count must be 0 and every flag true (or None
when the other proposing side did not run). `nrmps.validation` repeats the checks over many random markets, together
with two that are too slow for every run: agreement with an independent solver (`oracle_match`, which needs the
`matching` package, a development dependency) and that no applicant gains by submitting a different list under
applicant-proposing deferred acceptance (`profitable_misreports`).
"""

import itertools
import math
import warnings
from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray

from .applications import Applications
from .invitations import Invitations
from .match import UNMATCHED, Lists, MatchResult, applicant_proposing, comparison
from .rol import MAX_LIST, RankLists

I32 = NDArray[np.int32]

# Counts that must be 0, and flags that must not be False, with their descriptions.
COUNT_CHECKS = {
    "blocking_pairs": "Blocking pairs: an applicant and a program that rank each other above their match",
    "over_capacity": "Programs matched to more applicants than they have positions",
    "unranked_matches": "Matches that are not on both rank order lists",
    "ranked_without_interview": "List entries without an interview",
    "lists_not_strict": "Rank order lists whose ranks are not exactly 1, 2, ..., k",
    "lists_too_long": "Applicant list entries beyond rank 300 (the NRMP limit)",
}
FLAG_CHECKS = {
    "rural_hospitals": "Both proposing sides match the same applicants and fill each program equally (rural hospitals)",
    "applicant_optimal": "No applicant prefers the program-proposing result (applicant optimality)",
}


def _not_strict(owner: I32, rank: I32) -> int:
    """Return how many agents' list ranks are not exactly 1..k, k being the length of the list."""
    ranked = rank > 0
    owners, ranks = owner[ranked].astype(np.int64), rank[ranked].astype(np.int64)
    if owners.size == 0:
        return 0
    size = np.bincount(owners)
    highest = np.zeros(size.shape[0], dtype=np.int64)
    np.maximum.at(highest, owners, ranks)
    order = np.lexsort((ranks, owners))
    owners, ranks = owners[order], ranks[order]
    repeated = np.zeros(size.shape[0], dtype=np.bool_)
    repeated[owners[1:][(owners[1:] == owners[:-1]) & (ranks[1:] == ranks[:-1])]] = True
    return int(np.count_nonzero((size > 0) & ((highest != size) | repeated)))


def list_checks(applications: Applications, invitations: Invitations, lists: RankLists) -> dict[str, int]:
    """Return the rank-list entries that break the rules of §8 (all 0 for a correct engine)."""
    ranked = (lists.applicant_rank > 0) | (lists.program_rank > 0)
    return {
        "ranked_without_interview": int(np.count_nonzero(ranked & ~invitations.accepted)),
        "lists_not_strict": _not_strict(applications.i, lists.applicant_rank)
        + _not_strict(applications.j, lists.program_rank),
        "lists_too_long": int(np.count_nonzero(lists.applicant_rank > MAX_LIST)),
    }


def match_checks(lists: Lists, result: MatchResult) -> dict[str, Any]:
    """Return the match's checks: blocking pairs, capacity, both-list membership and the proposing-side comparison."""
    unranked = sum(
        1
        for applicant, program in enumerate(result.program.tolist())
        if program != UNMATCHED
        and (program not in lists.applicant_rank[applicant] or applicant not in lists.program_rank[program])
    )
    compared = comparison(lists, result)
    return {
        "blocking_pairs": result.blocking_pairs,
        "over_capacity": int(np.count_nonzero(result.filled > np.array(lists.capacity, dtype=np.int64))),
        "unranked_matches": unranked,
        "rural_hospitals": None
        if compared is None
        else bool(compared["same_matched_applicants"] and compared["same_fill_per_program"]),
        "applicant_optimal": None
        if compared is None
        else compared["applicants_worse_off_when_applicants_propose"] == 0,
    }


def passed(checks: dict[str, Any]) -> bool:
    """Return True if every count is 0 and no flag is False."""
    return all(checks.get(key, 0) == 0 for key in COUNT_CHECKS) and all(
        checks.get(key) is not False for key in FLAG_CHECKS
    )


def run_checks(
    applications: Applications, invitations: Invitations, lists: RankLists, match_lists: Lists, result: MatchResult
) -> dict[str, Any]:
    """Return every check of a run, with `passed`."""
    checks = list_checks(applications, invitations, lists) | match_checks(match_lists, result)
    checks["passed"] = passed(checks)
    return checks


def oracle_match(lists: Lists, optimal: str = "resident") -> list[int] | None:
    """Solve the lists with the `matching` package; None if it is not installed.

    `optimal` is "resident" (applicant-optimal) or "hospital" (program-optimal). `clean=True` drops one-sided list
    entries, which deferred acceptance rejects anyway.
    """
    try:
        from matching.games import HospitalResident
    except ImportError:
        return None
    residents = {f"a{a}": [f"p{p}" for p in choices] for a, choices in enumerate(lists.applicant_lists)}
    hospitals = {f"p{p}": [f"a{a}" for a in choices] for p, choices in enumerate(lists.program_lists)}
    capacities = {f"p{p}": capacity for p, capacity in enumerate(lists.capacity)}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # the package warns about every entry it drops
        game = HospitalResident.create_from_dictionaries(residents, hospitals, capacities, clean=True)
        solution = game.solve(optimal=optimal)
    match = [UNMATCHED] * len(lists.applicant_lists)
    for hospital, matched in solution.items():
        for resident in matched:
            match[int(str(resident)[1:])] = int(str(hospital)[1:])
    return match


def _with_list(lists: Lists, applicant: int, choices: tuple[int, ...]) -> Lists:
    """Return the lists with one applicant's list replaced."""
    applicant_lists = list(lists.applicant_lists)
    applicant_rank = list(lists.applicant_rank)
    applicant_lists[applicant] = list(choices)
    applicant_rank[applicant] = {program: rank for rank, program in enumerate(choices, 1)}
    return Lists(applicant_lists, applicant_rank, lists.program_lists, lists.program_rank, lists.capacity)


def alternative_lists(truth: list[int], limit: int, rng: np.random.Generator) -> list[tuple[int, ...]]:
    """Return the lists an applicant with the list `truth` could submit instead.

    Every ordered subset of `truth` when there are at most `limit`; otherwise every truncation, every swap of two
    neighbours and random ordered subsets up to `limit` lists.
    """
    length = len(truth)
    if length <= 6 and sum(math.perm(length, k) for k in range(length + 1)) <= limit:
        return [
            choices for k in range(length + 1) for choices in itertools.permutations(truth, k) if list(choices) != truth
        ]
    found = {tuple(truth[:k]) for k in range(length)}
    for k in range(length - 1):
        swapped = list(truth)
        swapped[k], swapped[k + 1] = swapped[k + 1], swapped[k]
        found.add(tuple(swapped))
    while len(found) < limit:
        size = int(rng.integers(0, length + 1))
        choices = tuple(int(program) for program in rng.permutation(truth)[:size])
        if list(choices) != truth:
            found.add(choices)
    return sorted(found)


def profitable_misreports(
    lists: Lists,
    applicant: int,
    *,
    limit: int = 400,
    rng: np.random.Generator | None = None,
    mechanism: Callable[[Lists], list[int]] = applicant_proposing,
) -> int:
    """Return how many other lists would get `applicant` a program they rank higher under `mechanism`.

    The submitted list is taken as the applicant's true preference (unlisted programs are unacceptable). Deferred
    acceptance is strategy-proof for the proposing side, so with applicants proposing the answer is always 0; with
    programs proposing, applicants can sometimes gain by leaving programs off their list.
    """
    truth = lists.applicant_lists[applicant]
    worst = len(truth) + 1

    def value(program: int) -> int:
        return lists.applicant_rank[applicant].get(program, worst) if program != UNMATCHED else worst

    honest = value(mechanism(lists)[applicant])
    if honest == 1:
        return 0
    generator = rng if rng is not None else np.random.default_rng(applicant)
    return sum(
        1
        for choices in alternative_lists(truth, limit, generator)
        if value(mechanism(_with_list(lists, applicant, choices))[applicant]) < honest
    )
