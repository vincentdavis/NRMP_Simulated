/* NRMP mini-simulation core (prototype for the VIZ review).
 * Runs the full pipeline in the browser or in node:
 *   population -> true utilities -> pre-interview observed -> applications (+signals)
 *   -> invitations -> interviews -> post-interview observed -> rank lists -> applicant-proposing DA
 *   -> outcome metrics (match rate, fill, rank achieved, deciles, true-preference blocking pairs).
 * All randomness is counter-based (hash of (seed, stream, i, j)), so changing a slider keeps
 * "common random numbers": only the parameter changes, not the noise draws.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.NrmpSim = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // --- counter-based RNG -------------------------------------------------
  function mix(a, b, c, d) {
    let h = (a ^ 0x9e3779b9) >>> 0;
    h = Math.imul(h ^ (b + 0x7f4a7c15), 0x85ebca6b) >>> 0;
    h = Math.imul(h ^ (h >>> 13) ^ (c + 0x165667b1), 0xc2b2ae35) >>> 0;
    h = Math.imul(h ^ (h >>> 16) ^ (d + 0x27d4eb2f), 0x85ebca6b) >>> 0;
    h ^= h >>> 15;
    return h >>> 0;
  }
  function unif(seed, stream, i, j) {
    return (mix(seed, stream, i, j) + 0.5) / 4294967296;
  }
  function gauss(seed, stream, i, j) {
    const u1 = unif(seed, stream, i, j);
    const u2 = unif(seed, stream + 101, i, j);
    return Math.sqrt(-2 * Math.log(u1)) * Math.cos(6.283185307179586 * u2);
  }
  const S = { SCORE: 1, PRESTIGE: 2, CAP: 3, EPS: 4, ETA: 5, PRE_A: 6, PRE_P: 7, POST_A: 8, POST_P: 9 };

  const DEFAULTS = {
    seed: 1,
    nStudents: 1000,
    nPrograms: 100,
    capMean: 9,
    capSd: 3,
    rhoApplicant: 0.6, // share of applicant utility that is common (program prestige); 1 = everyone agrees
    rhoProgram: 0.6, // share of program utility that is common (applicant score)
    sigmaPreA: 0.5, // applicant pre-interview rating error (sd, added to utility)
    sigmaPreP: 0.5,
    sigmaPostA: 0.15,
    sigmaPostP: 0.15,
    applications: 20, // applications per applicant
    signals: 0, // signals per applicant (sent to top-S applied programs)
    signalBoost: 0.5, // added to program's pre-interview view of a signaling applicant
    interviewsPerPosition: 10, // program interview slots per position
    applicantInterviewLimit: 12, // max interviews an applicant attends
  };

  function run(userParams) {
    const p = Object.assign({}, DEFAULTS, userParams || {});
    const n = p.nStudents | 0, m = p.nPrograms | 0, seed = p.seed | 0;
    const t0 = now();
    const sqA = Math.sqrt(p.rhoApplicant), sqA1 = Math.sqrt(1 - p.rhoApplicant);
    const sqP = Math.sqrt(p.rhoProgram), sqP1 = Math.sqrt(1 - p.rhoProgram);

    const score = new Float64Array(n), prestige = new Float64Array(m), cap = new Int32Array(m);
    for (let i = 0; i < n; i++) score[i] = gauss(seed, S.SCORE, i, 0);
    for (let j = 0; j < m; j++) {
      prestige[j] = gauss(seed, S.PRESTIGE, j, 0);
      cap[j] = Math.max(1, Math.round(p.capMean + p.capSd * gauss(seed, S.CAP, j, 0)));
    }
    const U = (i, j) => sqA * prestige[j] + sqA1 * gauss(seed, S.EPS, i, j); // true applicant utility
    const V = (i, j) => sqP * score[i] + sqP1 * gauss(seed, S.ETA, i, j); // true program utility

    // 1. applications: each applicant applies to top-A programs by pre-interview observed utility
    const A = Math.min(p.applications | 0, m);
    const appsOf = new Array(n); // program ids, best first
    const preU = new Float64Array(m), idx = new Int32Array(m);
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < m; j++) preU[j] = U(i, j) + p.sigmaPreA * gauss(seed, S.PRE_A, i, j);
      appsOf[i] = topK(preU, m, A);
    }
    // applicants per program, with signal flag
    const applicantsOf = Array.from({ length: m }, () => []);
    const nSig = Math.min(p.signals | 0, A);
    for (let i = 0; i < n; i++) {
      const apps = appsOf[i];
      for (let k = 0; k < apps.length; k++) applicantsOf[apps[k]].push(i * 2 + (k < nSig ? 1 : 0));
    }
    // 2. invitations: program invites top-K applicants by its pre-interview view (+ signal boost)
    const invitesOf = Array.from({ length: n }, () => []);
    let nInvited = 0;
    for (let j = 0; j < m; j++) {
      const K = Math.round(p.interviewsPerPosition * cap[j]);
      const list = applicantsOf[j].map((code) => {
        const i = code >> 1, sig = code & 1;
        return [i, V(i, j) + p.sigmaPreP * gauss(seed, S.PRE_P, i, j) + (sig ? p.signalBoost : 0)];
      });
      list.sort((a, b) => b[1] - a[1]);
      for (let k = 0; k < Math.min(K, list.length); k++) { invitesOf[list[k][0]].push(j); nInvited++; }
    }
    // 3. interviews: applicant attends up to L invitations, preferring higher pre-observed utility
    const L = p.applicantInterviewLimit | 0;
    const interviewedBy = Array.from({ length: m }, () => []);
    const rolA = new Array(n);
    let nInterviews = 0;
    for (let i = 0; i < n; i++) {
      const inv = invitesOf[i]
        .map((j) => [j, U(i, j) + p.sigmaPreA * gauss(seed, S.PRE_A, i, j)])
        .sort((a, b) => b[1] - a[1])
        .slice(0, L);
      // 4. post-interview observed utilities -> applicant rank-order list
      const post = inv.map(([j]) => [j, U(i, j) + p.sigmaPostA * gauss(seed, S.POST_A, i, j)]);
      post.sort((a, b) => b[1] - a[1]);
      rolA[i] = post.map((x) => x[0]);
      for (const [j] of inv) interviewedBy[j].push(i);
      nInterviews += inv.length;
    }
    // program rank-order lists (ranks every interviewee) as rank lookup maps
    const progRank = new Array(m);
    for (let j = 0; j < m; j++) {
      const lst = interviewedBy[j].map((i) => [i, V(i, j) + p.sigmaPostP * gauss(seed, S.POST_P, i, j)]);
      lst.sort((a, b) => b[1] - a[1]);
      const mp = new Map();
      lst.forEach(([i], r) => mp.set(i, r));
      progRank[j] = mp;
    }
    const tPre = now();
    // 5. applicant-proposing deferred acceptance (Gale-Shapley with capacities)
    const match = da(n, m, cap, rolA, progRank);
    const tDa = now();

    // 6. metrics
    const matchedTo = match.matchedTo; // -1 = unmatched
    const held = match.held; // per program: array of students
    let nMatched = 0;
    const rankAchieved = new Int32Array(Math.max(L, 1) + 1); // index L = unmatched
    for (let i = 0; i < n; i++) {
      if (matchedTo[i] >= 0) { nMatched++; rankAchieved[rolA[i].indexOf(matchedTo[i])]++; }
      else rankAchieved[rankAchieved.length - 1]++;
    }
    const seats = cap.reduce((a, b) => a + b, 0);
    // applicant score deciles
    const order = Array.from({ length: n }, (_, i) => i).sort((a, b) => score[a] - score[b]);
    const decileOf = new Int32Array(n);
    order.forEach((i, r) => (decileOf[i] = Math.min(9, Math.floor((10 * r) / n))));
    const decMatched = new Array(10).fill(0), decTotal = new Array(10).fill(0);
    for (let i = 0; i < n; i++) { decTotal[decileOf[i]]++; if (matchedTo[i] >= 0) decMatched[decileOf[i]]++; }
    // program prestige deciles, and student-decile x program-decile heat
    const pOrder = Array.from({ length: m }, (_, j) => j).sort((a, b) => prestige[b] - prestige[a]);
    const pDec = new Int32Array(m);
    pOrder.forEach((j, r) => (pDec[j] = Math.min(9, Math.floor((10 * r) / m))));
    const heat = [];
    const heatCount = new Map();
    for (let i = 0; i < n; i++) if (matchedTo[i] >= 0) {
      const key = decileOf[i] * 10 + pDec[matchedTo[i]];
      heatCount.set(key, (heatCount.get(key) || 0) + 1);
    }
    for (let a = 0; a < 10; a++) for (let b = 0; b < 10; b++) heat.push([b, a, heatCount.get(a * 10 + b) || 0]);
    // blocking pairs under TRUE preferences (information-friction instability), O(n*m)
    const worstHeld = new Float64Array(m).fill(-Infinity);
    const hasVacancy = new Uint8Array(m);
    for (let j = 0; j < m; j++) {
      if (held[j].length < cap[j]) hasVacancy[j] = 1;
      else { let w = Infinity; for (const i of held[j]) w = Math.min(w, V(i, j)); worstHeld[j] = w; }
    }
    let blockingPairs = 0, studentsInBlocking = 0;
    const trueRankOfMatch = [];
    for (let i = 0; i < n; i++) {
      const mi = matchedTo[i];
      const ui = mi >= 0 ? U(i, mi) : -Infinity;
      let any = false, better = 0;
      for (let j = 0; j < m; j++) {
        if (j === mi) continue;
        const uij = U(i, j);
        if (uij > ui) {
          better++;
          if (hasVacancy[j] || V(i, j) > worstHeld[j]) { blockingPairs++; any = true; }
        }
      }
      if (any) studentsInBlocking++;
      if (mi >= 0) trueRankOfMatch.push(better + 1);
    }
    const tEnd = now();
    // sampled true-vs-observed pairs (for the scatter), deterministic sample
    const scatter = [];
    const sampleN = Math.min(n, 400);
    for (let s = 0; s < sampleN; s++) {
      const i = Math.floor((s * n) / sampleN), j = mix(seed, 77, s, 0) % m;
      const u = U(i, j);
      scatter.push([u, u + p.sigmaPreA * gauss(seed, S.PRE_A, i, j), u + p.sigmaPostA * gauss(seed, S.POST_A, i, j)]);
    }
    return {
      params: p,
      timing: { pipelineMs: tPre - t0, daMs: tDa - tPre, metricsMs: tEnd - tDa, totalMs: tEnd - t0, daRounds: match.rounds },
      funnel: { applications: n * A, invitations: nInvited, interviews: nInterviews,
        ranked: rolA.reduce((a, r) => a + r.length, 0), matched: nMatched, seats },
      nMatched, matchRate: nMatched / n, fillRate: nMatched / seats, unfilled: seats - nMatched,
      rankAchieved: Array.from(rankAchieved),
      decileMatchRate: decMatched.map((x, k) => x / Math.max(1, decTotal[k])),
      programFill: pOrder.map((j) => ({ id: j, prestige: prestige[j], cap: cap[j], filled: held[j].length,
        interviews: interviewedBy[j].length, applicants: applicantsOf[j].length })),
      heat, blockingPairs, studentsInBlocking, trueRankOfMatch,
      scatter,
      // compact edge lists for the network (first 300 students)
      edges: sampleEdges(Math.min(n, 300), appsOf, invitesOf, rolA, matchedTo),
      score: Array.from(score), prestige: Array.from(prestige), cap: Array.from(cap),
    };
  }

  /** indices of the k largest values (best first) via a size-k min-heap: O(m log k) instead of O(m log m). */
  function topK(vals, m, k) {
    const heap = new Int32Array(k); let size = 0;
    const less = (a, b) => vals[a] < vals[b];
    for (let j = 0; j < m; j++) {
      if (size < k) { let c = size++; heap[c] = j; while (c > 0) { const pr = (c - 1) >> 1; if (less(heap[c], heap[pr])) { const t = heap[c]; heap[c] = heap[pr]; heap[pr] = t; c = pr; } else break; } }
      else if (vals[j] > vals[heap[0]]) { heap[0] = j; let c = 0; for (;;) { const l = 2 * c + 1, r = l + 1; let s = c; if (l < k && less(heap[l], heap[s])) s = l; if (r < k && less(heap[r], heap[s])) s = r; if (s === c) break; const t = heap[c]; heap[c] = heap[s]; heap[s] = t; c = s; } }
    }
    return Array.from(heap.subarray(0, size)).sort((a, b) => vals[b] - vals[a]);
  }

  function sampleEdges(k, appsOf, invitesOf, rolA, matchedTo) {
    const out = [];
    for (let i = 0; i < k; i++) {
      const inter = new Set(rolA[i]);
      const inv = new Set(invitesOf[i]);
      for (const j of appsOf[i]) {
        const stage = matchedTo[i] === j ? 4 : inter.has(j) ? 3 : inv.has(j) ? 2 : 1;
        out.push([i, j, stage]);
      }
    }
    return out;
  }

  /** Applicant-proposing deferred acceptance. rolA[i] = program ids best-first; progRank[j] = Map(student->rank). */
  function da(n, m, cap, rolA, progRank) {
    const next = new Int32Array(n); // next index into rolA[i] to propose to
    const matchedTo = new Int32Array(n).fill(-1);
    const held = Array.from({ length: m }, () => []);
    let free = [];
    for (let i = 0; i < n; i++) if (rolA[i].length) free.push(i);
    let rounds = 0;
    while (free.length) {
      rounds++;
      const nextFree = [];
      for (const i of free) {
        while (next[i] < rolA[i].length) {
          const j = rolA[i][next[i]++];
          const r = progRank[j].get(i);
          if (r === undefined) continue; // program did not rank i
          const h = held[j];
          if (h.length < cap[j]) { h.push(i); matchedTo[i] = j; break; }
          // find worst held
          let wk = 0, wr = -1;
          for (let k = 0; k < h.length; k++) { const rk = progRank[j].get(h[k]); if (rk > wr) { wr = rk; wk = k; } }
          if (r < wr) { const out = h[wk]; h[wk] = i; matchedTo[i] = j; matchedTo[out] = -1; nextFree.push(out); break; }
        }
      }
      free = nextFree.filter((i) => next[i] < rolA[i].length && matchedTo[i] === -1);
    }
    return { matchedTo, held, rounds };
  }

  function now() { return typeof performance !== "undefined" ? performance.now() : Date.now(); }

  return { run, da, DEFAULTS, gauss, mix };
});
