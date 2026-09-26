"""Rank order lists (model_spec.md §8): who ranks whom after interviews, in which order."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.special import log_ndtr

from nrmps.params import SimulationParams

from .applications import Applications
from .interviews import Interviews
from .rng import Stream, pair_uniforms
from .signals import NO_SIGNAL, Signals

F64 = NDArray[np.float64]
I32 = NDArray[np.int32]
I64 = NDArray[np.int64]

MAX_LIST = 300  # the NRMP's limit on the length of an applicant's rank order list (programs have none)
COUNT_TOLERANCE = 1e-9  # ceil(n x (1 - q)) must not round up exact products such as 10 x 0.9


@dataclass(frozen=True, eq=False)
class RankLists:
    """The rank of every application on both sides' lists (0 = not on the list)."""

    applicant_rank: I32  # where the applicant ranks the program (1 = first choice)
    program_rank: I32  # where the program ranks the applicant
    certified: NDArray[np.bool_]  # per applicant: has a non-empty list


def _positions(order: I64, groups: I32) -> I64:
    """Return 1-based positions within each group for indices already sorted by group."""
    sorted_groups = groups[order]
    if sorted_groups.size == 0:
        return np.zeros(0, dtype=np.int64)
    new = np.empty(sorted_groups.size, dtype=np.bool_)
    new[0] = True
    new[1:] = sorted_groups[1:] != sorted_groups[:-1]
    starts = np.flatnonzero(new)
    result: I64 = np.arange(sorted_groups.size) - starts[np.cumsum(new) - 1] + 1
    return result


def _likelihood_penalty(competitiveness: F64, prestige: F64, band: float) -> F64:
    """Return ln Phi((c - p) / band), with the limits of a zero band."""
    gap = competitiveness - prestige
    if band > 0:
        result: F64 = log_ndtr(gap / band)
        return result
    return np.where(gap > 0, 0.0, np.where(gap < 0, -np.inf, np.log(0.5)))


def rank_lists(
    params: SimulationParams,
    applications: Applications,
    signals: Signals,
    interviews: Interviews,
    seed: int,
    replicate: int = 0,
) -> RankLists:
    """Build both sides' strict rank order lists from the post-interview views (§8)."""
    rol = params.rol
    n_pairs = applications.size
    i, j = applications.i, applications.j
    applicant_rank = np.zeros(n_pairs, dtype=np.int32)
    program_rank = np.zeros(n_pairs, dtype=np.int32)
    held = np.flatnonzero(~np.isnan(interviews.applicant_post))

    # Applicants.
    key = interviews.applicant_post.copy()
    if rol.applicant_policy == "likelihood_weighted":
        key[held] = key[held] + _likelihood_penalty(
            applications.competitiveness[i[held]], applications.prestige[j[held]], params.apps.target_band
        )
    candidates = held
    if rol.applicant_policy == "above_reservation":
        candidates = held[interviews.applicant_post[held] >= rol.reservation_utility]
    tie = pair_uniforms(seed, Stream.TIE_A, replicate, i[candidates], j[candidates])
    order = candidates[np.lexsort((tie, -key[candidates], i[candidates]))]
    position = _positions(np.arange(order.size), i[order])
    limit = MAX_LIST
    if rol.applicant_policy in ("top_k", "truncate_k"):
        limit = min(limit, rol.applicant_top_k)
    keep = position <= limit
    applicant_rank[order[keep]] = position[keep]

    # Programs.
    program_key = interviews.program_post.copy()
    if params.signals.use_in_ranking:
        seen = (signals.tier != NO_SIGNAL) & signals.program_uses[j]
        boosted = held[seen[held]]
        program_key[boosted] = program_key[boosted] + signals.boost_of(boosted, j[boosted])
    candidates = held
    if rol.program_policy == "dnr_threshold":
        candidates = held[interviews.program_post[held] >= rol.reservation_utility]
    tie = pair_uniforms(seed, Stream.TIE_P, replicate, i[candidates], j[candidates])
    order = candidates[np.lexsort((tie, -program_key[candidates], j[candidates]))]
    position = _positions(np.arange(order.size), j[order])
    keep = np.ones(order.size, dtype=np.bool_)  # program lists have no length limit
    if rol.program_policy == "dnr_quantile" and order.size:
        interviewed = np.bincount(j[order], minlength=int(j.max()) + 1)
        kept = np.maximum(1, np.ceil(interviewed * (1.0 - rol.program_dnr_quantile) - COUNT_TOLERANCE))
        keep = position <= kept[j[order]].astype(np.int64)
    program_rank[order[keep]] = position[keep]

    n = applications.count.shape[0]
    certified = np.bincount(i[applicant_rank > 0], minlength=n) > 0
    return RankLists(applicant_rank, program_rank, certified)
