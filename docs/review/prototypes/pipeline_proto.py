"""Reference prototype of the full singles stage pipeline (from the project review, 2026-09-24).

Pipeline: utilities -> applications -> signals -> screening/invites -> accept/decline under caps -> interviews
(post-interview update) -> ROLs -> applicant-proposing DA -> stability check -> SOAP -> statistics.
Not part of the app. The normative model is docs/review/A-model-spec.md; this uses a simpler utility model.
Run: uv run python docs/review/prototypes/pipeline_proto.py
"""
from __future__ import annotations

import heapq
import time
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class Cfg:
    n_app: int = 2000
    n_prog: int = 200
    cap_mean: float = 8.0
    cap_sd: float = 4.0
    n_attr: int = 3
    w_common: float = 0.6        # weight on common (prestige) component vs idiosyncratic fit
    fit_sd: float = 0.15         # idiosyncratic pair fit
    pre_noise_sd: float = 0.10   # pre-interview observation error (additive)
    post_noise_sd: float = 0.03  # post-interview residual error
    interview_shock_sd: float = 0.05  # new info revealed at interview (true utility shift)
    apps_per_applicant: int = 40
    safety_share: float = 0.3
    n_gold: int = 3
    n_silver: int = 12
    signal_boost_gold: float = 0.25
    signal_boost_silver: float = 0.12
    interviews_per_position: float = 10.0
    applicant_interview_cap: int = 15
    invite_waves: int = 3
    rank_all_interviewed_app: bool = True
    prog_rank_min_score_pct: float = 0.1   # programs don't rank bottom 10% of interviewees
    soap_apps: int = 45
    soap_rounds: int = 4
    seed: int = 1


def run(cfg: Cfg, verbose=True):
    rng = np.random.default_rng(cfg.seed)
    A, P = cfg.n_app, cfg.n_prog
    t0 = time.time()
    # --- Stage 1: population ---
    cap = np.maximum(1, np.round(rng.normal(cfg.cap_mean, cfg.cap_sd, P))).astype(int)
    app_quality = rng.beta(5, 3, A)
    prog_quality = rng.beta(3, 3, P)
    app_attr = np.clip(app_quality[:, None] + rng.normal(0, 0.1, (A, cfg.n_attr)), 0, 1)
    prog_attr = np.clip(prog_quality[:, None] + rng.normal(0, 0.1, (P, cfg.n_attr)), 0, 1)
    app_w = rng.dirichlet(np.ones(cfg.n_attr), A)   # applicant weights over program attrs
    prog_w = rng.dirichlet(np.ones(cfg.n_attr), P)  # program weights over applicant attrs
    # --- Stage 2: true utilities (A x P) ---
    U_app = cfg.w_common * (app_w @ prog_attr.T) + rng.normal(0, cfg.fit_sd, (A, P))   # applicant's utility of program
    U_prog = cfg.w_common * (app_attr @ prog_w.T) + rng.normal(0, cfg.fit_sd, (A, P))  # program's utility of applicant
    # --- Stage 3: pre-interview observed (additive noise) ---
    O_app = U_app + rng.normal(0, cfg.pre_noise_sd, (A, P))
    O_prog = U_prog + rng.normal(0, cfg.pre_noise_sd, (A, P))
    # --- Stage 4: applications (portfolio: reach/target/safety by self-assessed competitiveness) ---
    applied = np.zeros((A, P), bool)
    k = min(cfg.apps_per_applicant, P)
    prestige_rank = np.argsort(-prog_quality)  # common knowledge
    for i in range(A):
        n_safe = int(round(k * cfg.safety_share))
        top = np.argsort(-O_app[i])[: k - n_safe]
        applied[i, top] = True
        # safety: programs whose prestige is below the applicant's own percentile
        pct = (app_quality[i] > app_quality).mean()
        lower = prestige_rank[int(pct * (P - 1)):] if pct < 1 else prestige_rank[-1:]
        cand = [j for j in lower if not applied[i, j]]
        if cand:
            pick = rng.choice(cand, size=min(n_safe, len(cand)), replace=False)
            applied[i, pick] = True
    # --- Stage 5: signals (gold/silver to top observed among applied) ---
    signal = np.zeros((A, P), np.int8)  # 0 none, 1 silver, 2 gold
    for i in range(A):
        js = np.flatnonzero(applied[i])
        order = js[np.argsort(-O_app[i, js])]
        signal[i, order[: cfg.n_gold]] = 2
        signal[i, order[cfg.n_gold: cfg.n_gold + cfg.n_silver]] = 1
    # --- Stage 6: program screening score ---
    boost = np.where(signal == 2, cfg.signal_boost_gold, np.where(signal == 1, cfg.signal_boost_silver, 0.0))
    screen = np.where(applied, O_prog + boost, -np.inf)
    # --- Stage 7: invitations in waves; applicants accept up to cap, best-first ---
    slots = np.ceil(cap * cfg.interviews_per_position).astype(int)
    invited = np.zeros((A, P), bool)
    accepted = np.zeros((A, P), bool)
    n_acc = np.zeros(A, int)
    filled = np.zeros(P, int)
    for w in range(cfg.invite_waves):
        # each program invites enough to fill remaining slots (over-invites by 20% in early waves)
        wave_new = []
        for j in range(P):
            remaining = slots[j] - filled[j]
            if remaining <= 0:
                continue
            over = 1.2 if w < cfg.invite_waves - 1 else 1.0
            cand = np.flatnonzero(np.isfinite(screen[:, j]) & ~invited[:, j])
            if cand.size == 0:
                continue
            best = cand[np.argsort(-screen[cand, j])][: int(np.ceil(remaining * over))]
            invited[best, j] = True
            wave_new.append((j, best))
        # applicants respond: accept best invites (by observed utility) up to cap; programs honor slot limits FCFS by applicant score
        new_inv = np.zeros((A, P), bool)
        for j, best in wave_new:
            new_inv[best, j] = True
        for i in np.flatnonzero(new_inv.any(1)):
            room = cfg.applicant_interview_cap - n_acc[i]
            js = np.flatnonzero(new_inv[i])
            js = js[np.argsort(-O_app[i, js])]
            for j in js:
                if room <= 0:
                    break
                if filled[j] < slots[j]:
                    accepted[i, j] = True
                    filled[j] += 1
                    n_acc[i] += 1
                    room -= 1
    # --- Stage 8: interview -> post-interview observed ---
    shock_a = rng.normal(0, cfg.interview_shock_sd, (A, P))
    shock_p = rng.normal(0, cfg.interview_shock_sd, (A, P))
    Post_app = np.where(accepted, U_app + shock_a + rng.normal(0, cfg.post_noise_sd, (A, P)), np.nan)
    Post_prog = np.where(accepted, U_prog + shock_p + rng.normal(0, cfg.post_noise_sd, (A, P)), np.nan)
    U_app_final = U_app + np.where(accepted, shock_a, 0)   # the realized "true" utility incl. revealed fit
    U_prog_final = U_prog + np.where(accepted, shock_p, 0)
    # --- Stage 9: ROLs (only interviewed pairs; strict order; tie-break by id) ---
    app_rol = []
    for i in range(A):
        js = np.flatnonzero(accepted[i])
        app_rol.append(list(js[np.lexsort((js, -Post_app[i, js]))]))
    prog_rank = []
    for j in range(P):
        iis = np.flatnonzero(accepted[:, j])
        if iis.size:
            order = iis[np.lexsort((iis, -Post_prog[iis, j]))]
            keep = order[: max(1, int(np.ceil(len(order) * (1 - cfg.prog_rank_min_score_pct))))]
        else:
            keep = np.array([], int)
        prog_rank.append({int(a): r for r, a in enumerate(keep, 1)})
    t_pre = time.time() - t0
    # --- Stage 10: match ---
    t1 = time.time()
    match_of, held = deferred_acceptance(app_rol, prog_rank, cap)
    t_match = time.time() - t1
    bp = blocking_pairs(app_rol, prog_rank, cap, match_of, held)
    # --- Stage 11: SOAP ---
    soap = run_soap(cfg, rng, match_of, cap, held, O_app, O_prog, U_app)
    stats = match_stats(app_rol, prog_rank, cap, match_of, held, accepted, applied, signal, soap)
    stats.update(t_pre_s=round(t_pre, 2), t_match_s=round(t_match, 3), blocking_pairs=len(bp))
    if verbose:
        for k_, v in stats.items():
            print(f"  {k_}: {v}")
    return dict(app_rol=app_rol, prog_rank=prog_rank, cap=cap, match_of=match_of, held=held, stats=stats)


def deferred_acceptance(app_rol, prog_rank, cap):
    """Applicant-proposing DA with capacities (the core of Roth-Peranson for singles)."""
    A, P = len(app_rol), len(cap)
    nxt = [0] * A
    match_of = [None] * A
    held = [[] for _ in range(P)]  # max-heap of (-rank, applicant): worst held applicant on top
    free = deque(range(A))
    while free:
        i = free.popleft()
        rol = app_rol[i]
        while nxt[i] < len(rol):
            j = rol[nxt[i]]
            nxt[i] += 1
            r = prog_rank[j].get(i)
            if r is None or cap[j] == 0:
                continue  # program did not rank applicant -> rejected
            if len(held[j]) < cap[j]:
                heapq.heappush(held[j], (-r, i))
                match_of[i] = j
                break
            worst_negr, worst_i = held[j][0]
            if r < -worst_negr:
                heapq.heapreplace(held[j], (-r, i))
                match_of[i] = j
                match_of[worst_i] = None
                free.append(worst_i)
                break
    return match_of, [sorted(a for _, a in h) for h in held]


def blocking_pairs(app_rol, prog_rank, cap, match_of, held):
    """Return list of (applicant, program) pairs that block the matching (ROL-restricted stability)."""
    worst = []
    for j, members in enumerate(held):
        worst.append(max((prog_rank[j][a] for a in members), default=None))
    out = []
    for i, rol in enumerate(app_rol):
        for j in rol:
            if match_of[i] == j:
                break  # everything after is worse than current match
            r = prog_rank[j].get(i)
            if r is None:
                continue
            if len(held[j]) < cap[j] or (worst[j] is not None and r < worst[j]):
                out.append((i, j))
    return out


def run_soap(cfg, rng, match_of, cap, held, O_app, O_prog, U_app):
    """SOAP: unmatched applicants apply to <=45 unfilled programs; 4 offer rounds; acceptance binding."""
    unfilled = {j: cap[j] - len(held[j]) for j in range(len(cap)) if cap[j] - len(held[j]) > 0}
    unmatched = [i for i, m in enumerate(match_of) if m is None]
    if not unfilled or not unmatched:
        return dict(soap_filled=0, soap_positions=sum(unfilled.values()), soap_unmatched_after=len(unmatched))
    progs = np.array(sorted(unfilled))
    apps = {}
    for i in unmatched:
        order = progs[np.argsort(-O_app[i, progs])][: cfg.soap_apps]
        apps[i] = set(order.tolist())
    pool = {j: sorted([i for i in unmatched if j in apps[i]], key=lambda i: -O_prog[i, j]) for j in progs.tolist()}
    offered = {j: 0 for j in pool}
    placed = {}
    for _ in range(cfg.soap_rounds):
        offers = {}
        for j, lst in pool.items():
            need = unfilled[j]
            cand = [i for i in lst[offered[j]:] if i not in placed][:need]
            offered[j] += len(cand)  # approximates "offer then move down list"
            for i in cand:
                offers.setdefault(i, []).append(j)
        for i, js in offers.items():
            best = max(js, key=lambda j: O_app[i, j])  # accept best offer (binding); reject others
            placed[i] = best
            unfilled[best] -= 1
        if all(v <= 0 for v in unfilled.values()):
            break
    return dict(soap_filled=len(placed), soap_positions=int(sum(cap[j] - len(held[j]) for j in progs)),
                soap_unmatched_after=len(unmatched) - len(placed))


def match_stats(app_rol, prog_rank, cap, match_of, held, accepted, applied, signal, soap):
    A = len(app_rol)
    matched = [i for i in range(A) if match_of[i] is not None]
    ranks = [app_rol[i].index(match_of[i]) + 1 for i in matched]
    rol_len = np.array([len(r) for r in app_rol])
    pos = int(sum(cap))
    filled = sum(len(h) for h in held)
    sig_matched = sum(1 for i in matched if signal[i, match_of[i]] > 0)
    return {
        "applicants": A, "positions": pos, "programs": len(cap),
        "match_rate": round(len(matched) / A, 3),
        "fill_rate": round(filled / pos, 3),
        "unfilled_positions": pos - filled,
        "programs_unfilled": sum(1 for j in range(len(cap)) if len(held[j]) < cap[j]),
        "pct_first_choice": round(sum(r == 1 for r in ranks) / max(1, len(ranks)), 3),
        "pct_top3": round(sum(r <= 3 for r in ranks) / max(1, len(ranks)), 3),
        "mean_rol_len_matched": round(float(rol_len[matched].mean()), 2) if matched else None,
        "mean_rol_len_unmatched": round(float(rol_len[[i for i in range(A) if match_of[i] is None]].mean()), 2)
        if len(matched) < A else None,
        "zero_interview_applicants": int((accepted.sum(1) == 0).sum()),
        "mean_apps": round(float(applied.sum(1).mean()), 1),
        "mean_interviews": round(float(accepted.sum(1).mean()), 2),
        "pct_matched_to_signaled": round(sig_matched / max(1, len(matched)), 3),
        **soap,
    }


if __name__ == "__main__":
    for n_app, n_prog in [(2000, 200), (5000, 500)]:
        print(f"== {n_app} applicants x {n_prog} programs")
        run(Cfg(n_app=n_app, n_prog=n_prog))
