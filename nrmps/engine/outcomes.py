"""Diagnostics of the stages from applications to the match (model_spec.md §10).

`outcome_metrics` returns JSON with these parts:

- `funnel`: applications, signals, invitations, interviews and list entries per applicant, interviews per position,
  declined invitations, and the applicants who got no interview.
- `match`: the algorithm, certified and matched applicants, match rate (matched / certified), fill rate, unfilled
  positions and programs, the share matched to their first and to a top-3 choice, the matched-rank distribution
  (1 to 10, then 11+), mean list length of matched and unmatched applicants, blocking pairs (always 0), and the
  comparison with the other proposing side when it ran.
- `signals`: interview rates of signalled and other applications, and the share of signals that ended in a match.
- `welfare`: over matched applicants, the realised-utility (u*) rank of the match among the programs they
  interviewed at, and the regret (best interviewed u* minus the match's); the correlation of realised and
  post-interview views (post-interview fidelity) for both sides.
- `by_group` and `by_strength_decile`: lists (in group order, or deciles 1 to 10) of the name, applicants,
  certified, match rate, mean matched rank and interviews. Lists rather than objects, because PostgreSQL's JSON
  storage does not keep the order of object keys.
- `checks`: the validation of the lists and the match (`validate.run_checks`): counts that must be 0, the rural
  hospitals and applicant-optimality flags (None without `match.compare_both`) and `passed`.
"""

from typing import Any

import numpy as np
from numpy.typing import NDArray

from .applications import Applications
from .interviews import Interviews
from .invitations import Invitations
from .match import UNMATCHED, Lists, MatchResult, comparison
from .numeric import correlation, quantiles
from .population import Population
from .rol import RankLists
from .signals import NO_SIGNAL, Signals
from .validate import run_checks

F64 = NDArray[np.float64]


def _share(part: float, whole: float) -> float | None:
    return float(part / whole) if whole else None


def _mean(values: NDArray[Any]) -> float | None:
    return float(values.mean()) if values.size else None


def _welfare(applications: Applications, interviews: Interviews, match: MatchResult) -> dict[str, float | None]:
    """Realised-utility rank of each match among the applicant's interviews, and the regret."""
    held = np.flatnonzero(~np.isnan(interviews.applicant_realised))
    i, j = applications.i[held], applications.j[held]
    realised = interviews.applicant_realised[held]
    matched_program = match.program[i]
    is_match = j == matched_program
    matched_value = np.full(match.program.shape[0], np.nan)
    matched_value[i[is_match]] = realised[is_match]
    better = np.bincount(i, weights=(realised > matched_value[i]).astype(np.float64), minlength=matched_value.size)
    best = np.full(matched_value.size, -np.inf)
    np.maximum.at(best, i, realised)
    matched = np.flatnonzero(~np.isnan(matched_value))
    return {
        "true_rank_mean": _mean(better[matched] + 1.0),
        "regret_mean": _mean(best[matched] - matched_value[matched]),
    }


def strength_decile(strength: F64) -> NDArray[np.int64]:
    """Return each applicant's strength decile, 0 (the weakest tenth) to 9, by rank (ties by index)."""
    return np.minimum((quantiles(strength) * 10).astype(np.int64), 9)


def _by(
    labels: NDArray[np.int64],
    names: list[str],
    match: MatchResult,
    certified: NDArray[np.bool_],
    interviews_per_applicant: F64,
) -> list[dict[str, Any]]:
    result = []
    for index, name in enumerate(names):
        members = labels == index
        count = int(members.sum())
        entered = members & certified
        matched = entered & (match.program != UNMATCHED)
        ranks = match.applicant_list_rank[matched]
        result.append(
            {
                "name": name,
                "applicants": count,
                "certified": int(entered.sum()),
                "match_rate": _share(int(matched.sum()), int(entered.sum())),
                "mean_matched_rank": _mean(ranks.astype(np.float64)),
                "interviews_mean": _mean(interviews_per_applicant[members]),
            }
        )
    return result


def outcome_metrics(
    population: Population,
    applications: Applications,
    signals: Signals,
    invitations: Invitations,
    interviews: Interviews,
    lists: RankLists,
    match_lists: Lists,
    match: MatchResult,
) -> dict[str, Any]:
    """Return the diagnostics of the applications-to-match stages."""
    n, m, positions = population.n_applicants, population.n_programs, population.n_positions
    i, j = applications.i, applications.j
    invited = invitations.wave > 0
    interviewed = invitations.accepted
    signalled = signals.tier != NO_SIGNAL
    list_length = np.bincount(i[lists.applicant_rank > 0], minlength=n)
    interviews_per_applicant = np.bincount(i[interviewed], minlength=n).astype(np.float64)
    certified = lists.certified
    matched = match.program != UNMATCHED
    ranks = match.applicant_list_rank[matched]
    distribution = {str(rank): int(np.count_nonzero(ranks == rank)) for rank in range(1, 11)}
    distribution["11+"] = int(np.count_nonzero(ranks > 10))
    matched_pair = interviewed & (match.program[i] == j)
    realised = ~np.isnan(interviews.applicant_realised)
    return {
        "funnel": {
            "applications_per_applicant": applications.size / n,
            "signals_per_applicant": int(signalled.sum()) / n,
            "invitations_per_applicant": int(invited.sum()) / n,
            "interviews_per_applicant": int(interviewed.sum()) / n,
            "interviews_per_position": int(interviewed.sum()) / positions,
            "list_entries_per_applicant": int((lists.applicant_rank > 0).sum()) / n,
            "declined_invitations": int((invited & ~interviewed).sum()),
            "applicants_without_interview": int(np.count_nonzero(interviews_per_applicant == 0)),
            "interview_slots": int(invitations.slots.sum()),
        },
        "match": {
            "algorithm": match.algorithm,
            "certified": int(certified.sum()),
            "matched": int(matched.sum()),
            "match_rate": _share(int(matched.sum()), int(certified.sum())),
            "fill_rate": _share(int(match.filled.sum()), positions),
            "unfilled_positions": int(positions - match.filled.sum()),
            "programs_unfilled": int(np.count_nonzero(match.filled < population.programs.capacity)),
            "first_choice_share": _share(int(np.count_nonzero(ranks == 1)), ranks.size),
            "top3_share": _share(int(np.count_nonzero(ranks <= 3)), ranks.size),
            "rank_distribution": distribution,
            "list_length_matched": _mean(list_length[matched].astype(np.float64)),
            "list_length_unmatched": _mean(list_length[certified & ~matched].astype(np.float64)),
            "blocking_pairs": match.blocking_pairs,
            "comparison": comparison(match_lists, match),
        },
        "signals": {
            "sent": int(signalled.sum()),
            "interview_rate_signalled": _share(int((signalled & interviewed).sum()), int(signalled.sum())),
            "interview_rate_other": _share(int((~signalled & interviewed).sum()), int((~signalled).sum())),
            "match_rate_signalled": _share(int((signalled & matched_pair).sum()), int(signalled.sum())),
            "programs_using_signals": int(signals.program_uses.sum()),
        },
        "welfare": _welfare(applications, interviews, match)
        | {
            "applicant_post_fidelity": correlation(
                interviews.applicant_realised[realised], interviews.applicant_post[realised]
            ),
            "program_post_fidelity": correlation(
                interviews.program_realised[realised], interviews.program_post[realised]
            ),
        },
        "by_group": _by(
            population.applicants.group.astype(np.int64),
            list(population.applicants.group_names),
            match,
            certified,
            interviews_per_applicant,
        ),
        "by_strength_decile": _by(
            strength_decile(population.applicants.strength),
            [str(d + 1) for d in range(10)],
            match,
            certified,
            interviews_per_applicant,
        ),
        "programs": {"n": m, "positions": positions},
        "checks": run_checks(applications, invitations, lists, match_lists, match),
    }
