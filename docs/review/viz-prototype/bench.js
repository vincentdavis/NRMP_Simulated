const Sim = require("./sim.js");
// correctness: brute-force stability check on a small instance using the exported da()
function checkDA() {
  let bad = 0;
  for (let t = 0; t < 200; t++) {
    const n = 12, m = 4, cap = Int32Array.from({ length: m }, (_, j) => 1 + (Sim.mix(t, 5, j, 0) % 3));
    const rolA = [], progRank = [];
    for (let i = 0; i < n; i++) rolA.push([...Array(m).keys()].filter((j) => Sim.mix(t, 1, i, j) % 4 !== 0).sort((a, b) => Sim.mix(t, 2, i, a) - Sim.mix(t, 2, i, b)));
    for (let j = 0; j < m; j++) { const l = [...Array(n).keys()].filter((i) => Sim.mix(t, 3, i, j) % 5 !== 0).sort((a, b) => Sim.mix(t, 4, a, j) - Sim.mix(t, 4, b, j)); progRank.push(new Map(l.map((i, r) => [i, r]))); }
    const { matchedTo, held } = Sim.da(n, m, cap, rolA, progRank);
    for (let j = 0; j < m; j++) if (held[j].length > cap[j]) bad++;
    for (let i = 0; i < n; i++) for (const j of rolA[i]) {
      const mi = matchedTo[i];
      if (mi === j) break; // j is at/after match in i's list -> not preferred
      if (!progRank[j].has(i)) continue;
      const worst = held[j].length < cap[j] ? Infinity : Math.max(...held[j].map((k) => progRank[j].get(k)));
      if (progRank[j].get(i) < worst) bad++;
    }
  }
  return bad;
}
console.log("DA blocking pairs wrt submitted ROLs over 200 random instances (must be 0):", checkDA());
const sizes = [[120, 8, 6], [1000, 100, 20], [5000, 500, 30], [10000, 1000, 30]];
for (const [n, m, A] of sizes) {
  const r = Sim.run({ nStudents: n, nPrograms: m, applications: A });
  const t = r.timing;
  console.log(`n=${n} m=${m} A=${A}: total=${t.totalMs.toFixed(0)}ms pipeline=${t.pipelineMs.toFixed(0)} DA=${t.daMs.toFixed(1)} (rounds ${t.daRounds}) metrics(blocking O(nm))=${t.metricsMs.toFixed(0)} | match ${(100*r.matchRate).toFixed(1)}% fill ${(100*r.fillRate).toFixed(1)}% blocking pairs(true prefs)=${r.blockingPairs} students-in-BP=${r.studentsInBlocking} payload=${(JSON.stringify(r).length/1024).toFixed(0)}KB`);
}
// sweep: match rate vs applications per applicant, 5 seeds each (Monte-Carlo band) at 1000x100
const t0 = Date.now(); const rows = [];
for (const A of [3, 5, 8, 12, 20, 30, 45, 60]) {
  const vals = [1, 2, 3, 4, 5].map((seed) => Sim.run({ seed, applications: A, nStudents: 1000, nPrograms: 100 }).matchRate);
  vals.sort(); rows.push([A, vals[0], vals[2], vals[4]]);
}
console.log("sweep A (min/median/max match rate over 5 seeds) at 1000x100:", JSON.stringify(rows.map(r => r.map(x => +x.toFixed(3)))), `took ${Date.now() - t0}ms for 40 runs`);
// CRN demo: raising rating error with same seed
for (const s of [0, 0.25, 0.5, 1.0, 2.0]) { const r = Sim.run({ sigmaPreA: s, sigmaPreP: s, nStudents: 1000, nPrograms: 100 }); console.log(`sigmaPre=${s}: match ${(100*r.matchRate).toFixed(1)}% studentsInTrueBlockingPairs=${r.studentsInBlocking} rank1=${r.rankAchieved[0]}`); }
