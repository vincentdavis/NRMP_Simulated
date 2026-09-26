"""Screening, interview invitations and acceptance (model_spec.md §7.3)."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from nrmps.params import SimulationParams

from .applications import Applications
from .numeric import quantiles
from .population import Population
from .rng import Stream, pair_uniforms, replicate_for, stream_generator
from .signals import NO_SIGNAL, Signals
from .utility import MarketModel

F64 = NDArray[np.float64]
I32 = NDArray[np.int32]
I64 = NDArray[np.int64]

# Slots are ceil(interviews per position x capacity); this guards exact products against rounding up (10.1 x 10).
SLOT_TOLERANCE = 1e-9


@dataclass(frozen=True, eq=False)
class Invitations:
    """Screening, invitations and responses for every application."""

    program_view: F64  # the program's pre-interview view v_hat of each applicant
    screen: F64  # screening score
    eligible: NDArray[np.bool_]  # False when the hard screen excludes the applicant
    wave: NDArray[np.int8]  # 0 = not invited, else the invitation wave (1, 2, ...)
    accepted: NDArray[np.bool_]  # the applicant accepted the invitation (the interview takes place)
    slots: I32  # per program


def interview_slots(params: SimulationParams, population: Population) -> I32:
    """Return each program's interview slots, ceil(interviews per position x capacity)."""
    raw = params.invites.interviews_per_position * population.programs.capacity
    return np.ceil(raw - SLOT_TOLERANCE).astype(np.int32)


def _hard_screen(params: SimulationParams, population: Population, applicants: I32) -> NDArray[np.bool_]:
    """Return which applications pass the hard screen (all when the strategy or the attribute does not use one)."""
    invites = params.invites
    keys = population.applicants.keys
    if invites.strategy not in ("threshold_then_top", "threshold_then_random") or invites.screen_attribute not in keys:
        return np.ones(applicants.shape[0], dtype=np.bool_)
    column = population.applicants.attributes[:, keys.index(invites.screen_attribute)]
    passed: NDArray[np.bool_] = quantiles(column)[applicants] >= invites.screen_min_percentile
    return passed


def _program_order(
    params: SimulationParams,
    applications: Applications,
    invitations_screen: F64,
    signals: Signals,
    seed: int,
    replicate: int,
) -> I64:
    """Return the application indices sorted by program, then in the order that program invites them."""
    i, j = applications.i, applications.j
    strategy = params.invites.strategy
    if strategy == "threshold_then_random":
        key = pair_uniforms(seed, Stream.INVITES, replicate, i, j)
        order: I64 = np.lexsort((key, j))
        return order
    tie = pair_uniforms(seed, Stream.TIE_P, replicate, i, j)
    if strategy == "signal_first":
        seen = (signals.tier != NO_SIGNAL) & signals.program_uses[j]
        tier_key = np.where(seen, signals.tier, np.iinfo(np.int8).max)
        order = np.lexsort((tie, -invitations_screen, tier_key, j))
        return order
    order = np.lexsort((tie, -invitations_screen, j))
    return order


def invite(
    params: SimulationParams,
    population: Population,
    model: MarketModel,
    applications: Applications,
    signals: Signals,
    seed: int,
    replicate: int = 0,
) -> Invitations:
    """Screen the applications, run the invitation waves and the applicants' responses (§7.3)."""
    n_pairs = applications.size
    n, m = population.n_applicants, population.n_programs
    i64 = applications.i.astype(np.int64)
    j64 = applications.j.astype(np.int64)
    program_view = model.programs.pair_utilities(j64, i64) + model.program_view.pair_error(j64, i64)
    seen = (signals.tier != NO_SIGNAL) & signals.program_uses[applications.j]
    boost = signals.boost_of(np.arange(n_pairs), applications.j)
    gap = np.maximum(0.0, applications.standing[applications.i] - applications.prestige[applications.j])
    screen = np.where(seen, program_view + boost, program_view - params.invites.yield_protection * gap)
    eligible = _hard_screen(params, population, applications.i)
    slots = interview_slots(params, population)
    wave = np.zeros(n_pairs, dtype=np.int8)
    accepted = np.zeros(n_pairs, dtype=np.bool_)
    if n_pairs == 0:
        return Invitations(program_view, screen, eligible, wave, accepted, slots)

    order = _program_order(params, applications, screen, signals, seed, replicate)
    order = order[eligible[order]]
    ordered_programs = applications.j[order]
    starts = np.searchsorted(ordered_programs, np.arange(m), side="left")
    ends = np.searchsorted(ordered_programs, np.arange(m), side="right")
    pointer = starts.astype(np.int64)

    if params.interview.acceptance_order == "first_come":
        preference = pair_uniforms(seed, Stream.ACCEPT, replicate, applications.i, applications.j)
    else:
        preference = applications.pre_rank.astype(np.float64)
    resample = params.run.resample_population
    rng = stream_generator(seed, Stream.ACCEPT, replicate_for(Stream.ACCEPT, replicate, resample))
    waves = params.invites.rounds
    permutations = [rng.permutation(n) for _ in range(waves)]
    cap = params.interview.applicant_cap
    accepted_by_program = np.zeros(m, dtype=np.int64)
    accepted_by_applicant = np.zeros(n, dtype=np.int64)
    applicant_of = applications.i.tolist()
    program_of = applications.j.tolist()

    for number in range(1, waves + 1):
        numerator = 12 if number < waves else 10  # invite ceil(1.2 x open), or ceil(open) in the last wave
        batches = []
        for program in range(m):
            open_slots = int(slots[program] - accepted_by_program[program])
            if open_slots <= 0:
                continue
            take = (open_slots * numerator + 9) // 10
            first = int(pointer[program])
            last = min(first + take, int(ends[program]))
            if first < last:
                batches.append(order[first:last])
                pointer[program] = last
        if not batches:
            continue
        invited_now = np.concatenate(batches)
        wave[invited_now] = number
        position = np.empty(n, dtype=np.int64)
        position[permutations[number - 1]] = np.arange(n)
        responses = invited_now[np.lexsort((preference[invited_now], position[applications.i[invited_now]]))]
        taken_program = accepted_by_program.tolist()
        taken_applicant = accepted_by_applicant.tolist()
        slot_list = slots.tolist()
        yes = []
        for pair in responses.tolist():
            applicant, program = applicant_of[pair], program_of[pair]
            if taken_applicant[applicant] < cap and taken_program[program] < slot_list[program]:
                yes.append(pair)
                taken_applicant[applicant] += 1
                taken_program[program] += 1
        accepted[yes] = True
        accepted_by_program = np.array(taken_program, dtype=np.int64)
        accepted_by_applicant = np.array(taken_applicant, dtype=np.int64)
    return Invitations(program_view, screen, eligible, wave, accepted, slots)
