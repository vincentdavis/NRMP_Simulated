"""The match (model_spec.md §8): deferred acceptance with capacities, and its validation.

Both proposing sides are implemented with plain Python lists and heaps: the work is proportional to the total length
of the rank order lists (times log capacity), which stays small because lists only hold interviewed pairs.
"""

import heapq
from collections import deque
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .applications import Applications
from .rol import RankLists

I32 = NDArray[np.int32]
UNMATCHED = -1


@dataclass(frozen=True)
class Lists:
    """Both sides' lists as Python structures: ordered choices and rank lookups."""

    applicant_lists: list[list[int]]  # per applicant: programs, best first
    applicant_rank: list[dict[int, int]]  # per applicant: program -> rank
    program_lists: list[list[int]]  # per program: applicants, best first
    program_rank: list[dict[int, int]]  # per program: applicant -> rank
    capacity: list[int]


def build_lists(applications: Applications, lists: RankLists, capacity: I32) -> Lists:
    """Turn the list ranks of the applications into ordered lists and rank lookups."""
    n, m = applications.count.shape[0], capacity.shape[0]
    applicant_lists: list[list[int]] = [[] for _ in range(n)]
    applicant_rank: list[dict[int, int]] = [{} for _ in range(n)]
    program_lists: list[list[int]] = [[] for _ in range(m)]
    program_rank: list[dict[int, int]] = [{} for _ in range(m)]
    i, j = applications.i, applications.j
    ranked = np.flatnonzero(lists.applicant_rank > 0)
    for pair in ranked[np.lexsort((lists.applicant_rank[ranked], i[ranked]))].tolist():
        applicant, program = int(i[pair]), int(j[pair])
        applicant_lists[applicant].append(program)
        applicant_rank[applicant][program] = int(lists.applicant_rank[pair])
    ranked = np.flatnonzero(lists.program_rank > 0)
    for pair in ranked[np.lexsort((lists.program_rank[ranked], j[ranked]))].tolist():
        applicant, program = int(i[pair]), int(j[pair])
        program_lists[program].append(applicant)
        program_rank[program][applicant] = int(lists.program_rank[pair])
    return Lists(applicant_lists, applicant_rank, program_lists, program_rank, [int(c) for c in capacity])


def applicant_proposing(lists: Lists) -> list[int]:
    """Return each applicant's program (or UNMATCHED) from applicant-proposing deferred acceptance."""
    n = len(lists.applicant_lists)
    match = [UNMATCHED] * n
    next_choice = [0] * n
    held: list[list[tuple[int, int]]] = [[] for _ in lists.capacity]  # max-heap on rank: (-rank, applicant)
    free = deque(range(n))
    while free:
        applicant = free.popleft()
        choices = lists.applicant_lists[applicant]
        while next_choice[applicant] < len(choices):
            program = choices[next_choice[applicant]]
            next_choice[applicant] += 1
            rank = lists.program_rank[program].get(applicant)
            capacity = lists.capacity[program]
            if rank is None or capacity == 0:
                continue
            heap = held[program]
            if len(heap) < capacity:
                heapq.heappush(heap, (-rank, applicant))
                match[applicant] = program
                break
            worst_rank, worst = -heap[0][0], heap[0][1]
            if rank < worst_rank:
                heapq.heapreplace(heap, (-rank, applicant))
                match[applicant] = program
                match[worst] = UNMATCHED
                free.append(worst)
                break
    return match


def program_proposing(lists: Lists) -> list[int]:
    """Return each applicant's program (or UNMATCHED) from program-proposing deferred acceptance."""
    n, m = len(lists.applicant_lists), len(lists.capacity)
    match = [UNMATCHED] * n
    holding = [0] * m
    next_choice = [0] * m
    queue = deque(program for program in range(m) if lists.capacity[program] > 0)
    while queue:
        program = queue.popleft()
        choices = lists.program_lists[program]
        while holding[program] < lists.capacity[program] and next_choice[program] < len(choices):
            applicant = choices[next_choice[program]]
            next_choice[program] += 1
            rank = lists.applicant_rank[applicant].get(program)
            if rank is None:
                continue
            current = match[applicant]
            if current == UNMATCHED:
                match[applicant] = program
                holding[program] += 1
            elif rank < lists.applicant_rank[applicant][current]:
                match[applicant] = program
                holding[program] += 1
                holding[current] -= 1
                queue.append(current)
    return match


def blocking_pairs(lists: Lists, match: list[int]) -> list[tuple[int, int]]:
    """Return the (applicant, program) pairs that block the matching against the submitted lists."""
    filled = [0] * len(lists.capacity)
    worst = [0] * len(lists.capacity)
    for applicant, program in enumerate(match):
        if program != UNMATCHED:
            filled[program] += 1
            worst[program] = max(worst[program], lists.program_rank[program][applicant])
    found = []
    for applicant, choices in enumerate(lists.applicant_lists):
        for program in choices:
            if program == match[applicant]:
                break
            rank = lists.program_rank[program].get(applicant)
            if rank is None:
                continue
            if filled[program] < lists.capacity[program] or rank < worst[program]:
                found.append((applicant, program))
    return found


@dataclass(frozen=True, eq=False)
class MatchResult:
    """The match: each applicant's program, the ranks of the match on both lists, and its validation."""

    algorithm: str
    program: I32  # per applicant: the matched program, or UNMATCHED
    applicant_list_rank: I32  # per applicant: rank of the match on their list (0 = unmatched)
    program_list_rank: I32  # per applicant: the program's rank of them (0 = unmatched)
    filled: I32  # per program
    blocking_pairs: int
    alternative: I32 | None  # the other proposing side's result, with compare_both


def run_match(algorithm: str, lists: Lists, compare_both: bool = False) -> MatchResult:
    """Run the chosen mechanism (and the other one with `compare_both`) and validate the result."""
    first, second = (
        (applicant_proposing, program_proposing)
        if algorithm == "applicant_proposing"
        else (program_proposing, applicant_proposing)
    )
    match = first(lists)
    alternative = np.array(second(lists), dtype=np.int32) if compare_both else None
    n, m = len(match), len(lists.capacity)
    program = np.array(match, dtype=np.int32)
    applicant_list_rank = np.zeros(n, dtype=np.int32)
    program_list_rank = np.zeros(n, dtype=np.int32)
    for applicant, matched in enumerate(match):
        if matched != UNMATCHED:
            applicant_list_rank[applicant] = lists.applicant_rank[applicant][matched]
            program_list_rank[applicant] = lists.program_rank[matched][applicant]
    matched_programs = program[program != UNMATCHED]
    filled = np.bincount(matched_programs, minlength=m).astype(np.int32)
    return MatchResult(
        algorithm=algorithm,
        program=program,
        applicant_list_rank=applicant_list_rank,
        program_list_rank=program_list_rank,
        filled=filled,
        blocking_pairs=len(blocking_pairs(lists, match)),
        alternative=alternative,
    )


def comparison(lists: Lists, result: MatchResult) -> dict[str, int | bool] | None:
    """Compare the two proposing sides (rural hospitals theorem and applicant optimality), if both ran."""
    if result.alternative is None:
        return None
    applicant_side = result.program if result.algorithm == "applicant_proposing" else result.alternative
    program_side = result.alternative if result.algorithm == "applicant_proposing" else result.program
    n, m = applicant_side.shape[0], len(lists.capacity)
    same_matched = bool(np.array_equal(applicant_side == UNMATCHED, program_side == UNMATCHED))
    fill_a = np.bincount(applicant_side[applicant_side != UNMATCHED], minlength=m)
    fill_p = np.bincount(program_side[program_side != UNMATCHED], minlength=m)
    worse_for_applicant = 0
    for applicant in range(n):
        a, p = int(applicant_side[applicant]), int(program_side[applicant])
        if a == p:
            continue
        rank_a = lists.applicant_rank[applicant].get(a, len(lists.applicant_lists[applicant]) + 1)
        rank_p = lists.applicant_rank[applicant].get(p, len(lists.applicant_lists[applicant]) + 1)
        if rank_a > rank_p:
            worse_for_applicant += 1
    return {
        "differing_applicants": int(np.count_nonzero(applicant_side != program_side)),
        "same_matched_applicants": same_matched,
        "same_fill_per_program": bool(np.array_equal(fill_a, fill_p)),
        "applicants_worse_off_when_applicants_propose": worse_for_applicant,
    }
