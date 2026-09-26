/* Web Worker: runs the simulation off the main thread so sliders stay responsive. */
importScripts("sim.js");
let latest = 0;
self.onmessage = (e) => {
  const { id, kind, params } = e.data;
  latest = id;
  if (kind === "run") {
    const res = NrmpSim.run(params);
    if (id === latest) self.postMessage({ id, kind, res });
  } else if (kind === "sweep") {
    // Monte-Carlo parameter sweep: match rate vs applications per applicant, R seeds each.
    const t0 = performance.now();
    const xs = params.sweepValues, R = params.reps, out = [];
    for (const A of xs) {
      const v = [];
      for (let r = 1; r <= R; r++) v.push(NrmpSim.run(Object.assign({}, params, { applications: A, seed: r })).matchRate);
      v.sort((a, b) => a - b);
      const q = (p) => v[Math.min(v.length - 1, Math.floor(p * (v.length - 1) + 0.5))];
      out.push({ A, lo: q(0.1), med: q(0.5), hi: q(0.9) });
    }
    self.postMessage({ id, kind, res: { points: out, ms: performance.now() - t0 } });
  }
};
