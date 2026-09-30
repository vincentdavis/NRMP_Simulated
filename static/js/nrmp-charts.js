// Charts (plan steps 3.8 and 5.1): draws every [data-chart] element when it comes into view.
//
// <div data-chart="histogram" data-payload="chart-strength" data-series="applicant" role="img" aria-label="...">
// reads the JSON in the element with id "chart-strength" (written by Django's json_script) and draws it with the
// builder registered for its kind: ECharts for charts, sigma.js with graphology for networks. A builder gets the
// payload, the chart tokens and the element, and returns an ECharts option (or a graph with sigma settings).
//
// - Colours come from the chart tokens in styles.css (--viz-*, with separate dark values), so every chart follows
//   the theme; the display setting "Patterns as well as colours" adds ECharts decals.
// - Tooltips are built with tip(), which escapes every value: names come from uploaded files and must never become
//   markup (VIZ-12). Numbers are formatted with format.* (Intl.NumberFormat in the page's language).
// - Charts resize with their box, are redrawn when the theme or the patterns setting changes, and are disposed of
//   when HTMX removes them. The page gives each chart's numbers as text too, so nothing depends on the drawing.
// - A switch (<input type="checkbox" data-chart-switch="bands"> in the chart's figure) turns an option of its chart
//   on or off: data-bands="on" on the chart element, which its builder reads. The choice is kept in the browser for
//   every chart with the same switch.
(() => {
  "use strict";

  const builders = {}; // kind -> {build, engine}
  const drawn = new Map(); // element -> {engine, observer, chart | renderer}
  const lang = document.documentElement.lang || "en";
  const probe = document.createElement("canvas").getContext("2d", { willReadFrequently: true });

  // --- Colours, numbers and tooltips ----------------------------------------------------------------------------

  // ECharts cannot parse the oklch() colours daisyUI uses, so let the browser convert any CSS colour to rgba().
  function rgba(color, alpha = 1) {
    probe.clearRect(0, 0, 1, 1);
    probe.fillStyle = "#000";
    probe.fillStyle = color;
    probe.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = probe.getImageData(0, 0, 1, 1).data;
    return `rgba(${r}, ${g}, ${b}, ${((a / 255) * alpha).toFixed(3)})`;
  }

  // Patterns (decals) as well as colours: the display setting, or the system's "more contrast" preference.
  function patterns() {
    const choice = document.documentElement.dataset.chartPatterns;
    return choice === "on" || (choice !== "off" && window.matchMedia("(prefers-contrast: more)").matches);
  }

  function tokens() {
    const style = getComputedStyle(document.documentElement);
    const colour = (name, fallback, alpha = 1) => rgba(style.getPropertyValue(name).trim() || fallback, alpha);
    return {
      ink: colour("--viz-ink", "#1f2937"),
      muted: colour("--viz-ink", "#1f2937", 0.7),
      faint: colour("--viz-ink", "#1f2937", 0.35),
      grid: colour("--viz-ink", "#1f2937", 0.12),
      surface: colour("--viz-surface", "#ffffff"),
      applicant: colour("--viz-series-1", "#2a78d6"),
      program: colour("--viz-series-2", "#d95c1f"),
      matched: colour("--viz-series-3", "#148f63"),
      neutral: colour("--viz-neutral", "#8a8880"),
      series: [1, 2, 3].map((k) => colour(`--viz-series-${k}`, "#2a78d6")),
      stages: [1, 2, 3, 4, 5].map((k) => colour(`--viz-seq-${k}`, "#2a78d6")),
      diverging: [1, 2, 3, 4, 5].map((k) => colour(`--viz-div-${k}`, "#8a8880")),
      font: getComputedStyle(document.body).fontFamily,
      patterns: patterns(),
      alpha: rgba,
    };
  }

  // The colour of a one-sided chart: data-series="applicant" (the default) or "program".
  const sideColour = (t, element) => (element.dataset.series === "program" ? t.program : t.applicant);

  const formats = new Map();
  function numberFormat(options) {
    const key = JSON.stringify(options);
    if (!formats.has(key)) formats.set(key, new Intl.NumberFormat(lang, options));
    return formats.get(key);
  }
  const format = {
    count: (value) => numberFormat({ maximumFractionDigits: 0 }).format(value),
    fixed: (value, digits) =>
      numberFormat({ minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value),
    sig: (value) => numberFormat({ maximumSignificantDigits: 3 }).format(value),
    share: (value, digits = 1) =>
      numberFormat({ style: "percent", minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value),
  };

  const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const escape = (value) => String(value).replace(/[&<>"']/g, (character) => ESCAPES[character]);

  // Tooltip HTML from a title and rows ([label, value] pairs or plain text), every piece escaped. Builders never
  // write tooltip HTML themselves.
  function tip(title, rows = []) {
    const lines = title === undefined || title === null || title === "" ? [] : [`<strong>${escape(title)}</strong>`];
    for (const row of rows) lines.push(Array.isArray(row) ? `${escape(row[0])}: ${escape(row[1])}` : escape(row));
    return lines.join("<br>");
  }

  const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // --- The registry ------------------------------------------------------------------------------------------------

  // The base of every ECharts option: fonts, colours and tooltip style from the tokens, and patterns when asked for.
  // The page labels each chart itself (role="img", aria-label and a summary), so ECharts' own description is off.
  function base(t) {
    return {
      animation: !reducedMotion(),
      textStyle: { fontFamily: t.font, color: t.ink },
      grid: { left: 56, right: 16, top: 36, bottom: 48, containLabel: false },
      tooltip: {
        backgroundColor: t.surface,
        borderColor: t.grid,
        textStyle: { color: t.ink, fontFamily: t.font },
        confine: true,
      },
      legend: { top: 0, textStyle: { color: t.muted } },
      aria: { enabled: true, label: { enabled: false }, decal: { show: t.patterns } },
    };
  }

  function axis(t, name, extra = {}) {
    return {
      name,
      nameLocation: "middle",
      nameGap: 32,
      nameTextStyle: { color: t.muted },
      axisLine: { lineStyle: { color: t.faint } },
      axisLabel: { color: t.muted },
      splitLine: { lineStyle: { color: t.grid } },
      ...extra,
    };
  }

  // How each engine draws, resizes and disposes of a chart.
  const engines = {
    echarts: {
      ready: () => Boolean(window.echarts),
      draw(element, entry, option) {
        if (!entry.chart) entry.chart = window.echarts.init(element, null, { renderer: "canvas" });
        entry.chart.setOption(option, true);
      },
      resize: (entry) => entry.chart && entry.chart.resize(),
      dispose: (entry) => entry.chart && entry.chart.dispose(),
    },
    sigma: {
      ready: () => Boolean(window.Sigma && window.graphology),
      draw(element, entry, { graph, settings }) {
        if (entry.renderer) entry.renderer.kill();
        entry.renderer = new window.Sigma(graph, element, { allowInvalidContainer: true, ...settings });
      },
      resize(entry) {
        if (!entry.renderer) return;
        entry.renderer.resize();
        entry.renderer.refresh();
      },
      dispose: (entry) => entry.renderer && entry.renderer.kill(),
    },
  };

  // `widths`: the element widths (px) at which the builder changes layout (a Sankey turns vertical, labels wrap).
  // Resizing across one redraws the chart; within them the engine only resizes it.
  function register(kind, build, { engine = "echarts", widths = [] } = {}) {
    builders[kind] = { build, engine, widths };
  }

  const layoutOf = (kind, element) => kind.widths.filter((width) => element.clientWidth < width).length;

  function draw(element) {
    const kind = builders[element.dataset.chart];
    const engine = kind && engines[kind.engine];
    const source = document.getElementById(element.dataset.payload);
    if (!engine || !engine.ready() || !source) return;
    const payload = JSON.parse(source.textContent);
    if (payload === null) return;
    let entry = drawn.get(element);
    if (!entry) {
      entry = { engine };
      entry.observer = new ResizeObserver(() => {
        engine.resize(entry); // the canvas follows the box ...
        if (layoutOf(kind, element) !== entry.layout) draw(element); // ... and a new layout needs a new option
      });
      entry.observer.observe(element);
      drawn.set(element, entry);
    }
    entry.layout = layoutOf(kind, element);
    const t = tokens();
    try {
      engine.draw(element, entry, kind.build(payload, t, element, kind.engine === "echarts" ? base(t) : {}));
      delete element.dataset.chartFailed;
    } catch (error) {
      // One chart that cannot be drawn (no WebGL, say) leaves the others alone; its numbers are on the page.
      element.dataset.chartFailed = "true";
      console.error(`Chart ${element.dataset.chart} could not be drawn:`, error);
    }
  }

  function dispose(element) {
    if (onScreen) onScreen.unobserve(element);
    const entry = drawn.get(element);
    if (!entry) return;
    entry.observer.disconnect();
    entry.engine.dispose(entry);
    drawn.delete(element);
  }

  // Charts are drawn once they come near the screen, so a page with many charts only draws the ones looked at.
  const onScreen =
    "IntersectionObserver" in window
      ? new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (!entry.isIntersecting) continue;
              onScreen.unobserve(entry.target);
              draw(entry.target);
            }
          },
          { rootMargin: "200px 0px" },
        )
      : null;

  // --- Switches -----------------------------------------------------------------------------------------------------

  function remember(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (error) {
      // Storage unavailable (private mode): the switch still works on this page.
    }
  }

  function recalled(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (error) {
      return null;
    }
  }

  // Set the switch's option on its chart (and show the key that goes with it); return the chart element.
  function applySwitch(input) {
    const figure = input.closest("figure");
    const element = figure && figure.querySelector("[data-chart]");
    if (!element) return null;
    const on = input.checked && !input.disabled;
    element.dataset[input.dataset.chartSwitch] = on ? "on" : "off";
    figure.querySelectorAll(`[data-chart-switch-key="${input.dataset.chartSwitch}"]`).forEach((key) => {
      key.hidden = !on;
    });
    return element;
  }

  function restoreSwitches(root) {
    const inputs = root.querySelectorAll ? [...root.querySelectorAll("input[data-chart-switch]")] : [];
    for (const input of inputs) {
      const saved = recalled(`chart-switch-${input.dataset.chartSwitch}`);
      if (saved !== null && !input.disabled) input.checked = saved === "on";
      applySwitch(input);
    }
  }

  document.addEventListener("change", (event) => {
    const input = event.target;
    if (!(input instanceof HTMLInputElement) || !input.matches("[data-chart-switch]")) return;
    remember(`chart-switch-${input.dataset.chartSwitch}`, input.checked ? "on" : "off");
    const element = applySwitch(input);
    if (element && drawn.has(element)) draw(element);
  });

  function renderAll(root = document) {
    restoreSwitches(root);
    const elements = root instanceof Element && root.matches("[data-chart]") ? [root] : [];
    if (root.querySelectorAll) elements.push(...root.querySelectorAll("[data-chart]"));
    for (const element of elements) {
      if (drawn.has(element) || !onScreen) draw(element);
      else onScreen.observe(element);
    }
  }

  function redrawAll() {
    drawn.forEach((_entry, element) => draw(element));
  }

  // --- Chart kinds (ECharts) ------------------------------------------------------------------------------------------

  // A histogram {edges, counts, requested?}: the realised counts as bars in the side's colour, the requested counts
  // as a line.
  register("histogram", (p, t, element, option) => {
    // One more decimal than the bin width needs, so neighbouring bins get different labels (nrmps/charts.py digits).
    const width = (p.edges[p.edges.length - 1] - p.edges[0]) / Math.max(1, p.edges.length - 1);
    const places = width > 0 ? Math.max(0, Math.ceil(-Math.log10(width)) + 1) : 0;
    const labels = p.counts.map((_count, k) => format.fixed((p.edges[k] + p.edges[k + 1]) / 2, places));
    const ranges = p.counts.map(
      (_count, k) => `${format.fixed(p.edges[k], places)} to ${format.fixed(p.edges[k + 1], places)}`,
    );
    const series = [
      { name: "Realised", type: "bar", data: p.counts, barCategoryGap: "8%", itemStyle: { color: sideColour(t, element) } },
    ];
    if (p.requested) {
      series.push({
        name: "Requested",
        type: "line",
        data: p.requested,
        smooth: true,
        symbol: "none",
        lineStyle: { color: t.ink, width: 2 },
        itemStyle: { color: t.ink },
      });
    }
    return {
      ...option,
      legend: { ...option.legend, show: Boolean(p.requested) },
      tooltip: {
        ...option.tooltip,
        trigger: "axis",
        formatter: (items) =>
          tip(
            ranges[items[0].dataIndex],
            items.map((item) => [item.seriesName, item.seriesIndex ? format.fixed(item.value, 1) : format.count(item.value)]),
          ),
      },
      xAxis: axis(t, element.dataset.xLabel || "", { type: "category", data: labels, axisTick: { alignWithLabel: true } }),
      yAxis: axis(t, element.dataset.yLabel || "Count", { type: "value", nameGap: 44 }),
      series,
    };
  });

  // True against observed utility {pre: [x, y], post: [x, y] | null}, with the identity line.
  register("scatter", (p, t, element, option) => {
    const points = ([x, y]) => x.map((value, k) => [value, y[k]]);
    const all = [...p.pre[0], ...p.pre[1], ...(p.post ? [...p.post[0], ...p.post[1]] : [])];
    const low = Math.floor(Math.min(...all));
    const high = Math.ceil(Math.max(...all));
    const series = [
      {
        name: "Before interviews",
        type: "scatter",
        data: points(p.pre),
        symbolSize: 4,
        itemStyle: { color: t.series[0], opacity: 0.45 },
      },
    ];
    if (p.post) {
      series.push({
        name: "After interviews",
        type: "scatter",
        data: points(p.post),
        symbolSize: 4,
        itemStyle: { color: t.series[1], opacity: 0.45 },
      });
    }
    series.push({
      name: "Observed = true",
      type: "line",
      data: [
        [low, low],
        [high, high],
      ],
      symbol: "none",
      silent: true,
      lineStyle: { color: t.neutral, type: "dashed", width: 1 },
      itemStyle: { color: t.neutral },
    });
    return {
      ...option,
      tooltip: {
        ...option.tooltip,
        trigger: "item",
        formatter: (item) =>
          tip(item.seriesName, [
            ["True", format.fixed(item.value[0], 2)],
            ["Observed", format.fixed(item.value[1], 2)],
          ]),
      },
      xAxis: axis(t, element.dataset.xLabel || "True utility", { type: "value", min: low, max: high }),
      yAxis: axis(t, element.dataset.yLabel || "Observed", { type: "value", min: low, max: high, nameGap: 36 }),
      series,
    };
  });

  // First-choice demand per program {names, demand, positions}, most wanted first, with the positions as marks.
  register("demand", (p, t, element, option) => {
    const zoom = p.demand.length > 60;
    return {
      ...option,
      grid: { ...option.grid, bottom: zoom ? 72 : 48 },
      tooltip: {
        ...option.tooltip,
        trigger: "axis",
        formatter: (items) =>
          tip(
            p.names[items[0].dataIndex],
            items.map((item) => [item.seriesName, format.count(item.value)]),
          ),
      },
      xAxis: axis(t, "Programs, most wanted first", {
        type: "category",
        data: p.names,
        axisLabel: { show: false },
        axisTick: { show: false },
      }),
      yAxis: axis(t, "Applicants", { type: "value", nameGap: 44 }),
      dataZoom: zoom
        ? [
            { type: "inside", start: 0, end: Math.max(5, (60 / p.demand.length) * 100) },
            { type: "slider", height: 18, bottom: 8, textStyle: { color: t.muted } },
          ]
        : [],
      series: [
        {
          name: "Rank it first",
          type: "bar",
          data: p.demand,
          large: p.demand.length > 400,
          itemStyle: { color: t.program },
        },
        {
          name: "Positions",
          type: "scatter",
          data: p.positions,
          symbol: "rect",
          symbolSize: [10, 2],
          itemStyle: { color: t.ink },
        },
      ],
    };
  });

  // The Lorenz curve of first-choice demand {lorenz: [[share of programs, share of demand], ...], gini}.
  register("lorenz", (p, t, element, option) => ({
    ...option,
    legend: { ...option.legend, show: true },
    tooltip: {
      ...option.tooltip,
      trigger: "axis",
      formatter: (items) =>
        tip("", [
          `${format.share(items[0].value[0], 0)} of programs get ${format.share(items[0].value[1], 0)} of first choices`,
        ]),
    },
    xAxis: axis(t, "Share of programs (least wanted first)", { type: "value", min: 0, max: 1 }),
    yAxis: axis(t, "Share of first choices", { type: "value", min: 0, max: 1, nameGap: 40 }),
    series: [
      {
        name: "Demand",
        type: "line",
        data: p.lorenz,
        symbol: "none",
        areaStyle: { color: t.program, opacity: 0.15 },
        lineStyle: { color: t.program, width: 2 },
        itemStyle: { color: t.program },
      },
      {
        name: "Equal demand",
        type: "line",
        data: [
          [0, 0],
          [1, 1],
        ],
        symbol: "none",
        silent: true,
        lineStyle: { color: t.neutral, type: "dashed", width: 1 },
        itemStyle: { color: t.neutral },
      },
    ],
  }));

  // --- Colour by strength -------------------------------------------------------------------------------------------

  // The step of a scale for item k of `of` items, spread over the whole scale.
  const scaleStep = (scale, k, of) => scale[Math.round((k * (scale.length - 1)) / Math.max(1, of - 1))];

  // A Sankey diagram split by strength fifth (the "bands" switch), for the applicants' flow and a program's funnel:
  // {main: stage names, drops: drop-off names (drops[k] leaves main[k]), total and each group's counts: {name: count},
  // groups: [{label, low, high, counts}], unit ("applicants" or "applications"), notes: {name: [[label, count]]}}.
  // Each stage splits into the fifths in the diverging scale (red the bottom 20%, grey the middle, blue the top 20%;
  // strongest first, at the top, or at the left when vertical), links take their fifth's colour, and each drop-off is
  // one bar in the fifths' colours in proportion, set apart from its stage by a transparent spacer, with a small bar of
  // the same mix (`barWidth` px) in its label. Stage labels go above their column (in the left margin when vertical),
  // drop-off labels to the right of it (below it when vertical). Returns the series' {nodes, links} and its tooltip.
  function strengthSankey(t, spec) {
    const { main, drops, total, groups, unit, notes = {}, narrow = false, vertical = false, barWidth } = spec;
    const colourOf = (b) => scaleStep(t.diverging, b, groups.length);
    const SPACER = "spacer:";
    const stageOf = (node) => String(node).split("|")[0];
    const bandOf = (node) => (String(node).includes("|") ? Number(String(node).split("|")[1]) : null);
    const everyone = total[main[0]];
    // The space between a stage and its drop-off: a node with a value (3% of the whole) but no links.
    const spacer = (k) => ({
      name: `${SPACER}${k}`,
      depth: k,
      value: Math.max(1, Math.round(0.03 * everyone)),
      // A transparent pattern too: with patterns on, ECharts would hatch the gap (decal "none" throws in ECharts 6.1).
      itemStyle: { color: "transparent", borderWidth: 0, decal: { color: "transparent" } },
      label: { show: false },
      tooltip: { show: false },
      emphasis: { disabled: true },
    });
    // A drop-off: one bar in the fifths' colours, strongest first, which is the order in which ECharts stacks the
    // links arriving from the stage before (by their source's position), so each fifth's link lands on its colour.
    // The label's small bar shows the same mix, weakest on the left like the key.
    function dropNode(drop, k) {
      const count = total[drop];
      const words = narrow ? drop.replace(", ", ",\n") : drop;
      const rich = { t: { color: t.muted, lineHeight: 16 }, n: { color: t.muted, lineHeight: 16 } };
      const text = words.split("\n").map((line) => `{t|${line}}`).join("\n");
      const below = { position: ["0%", "100%"], align: "left", verticalAlign: "top", padding: [4, 0, 0, 0] };
      const place = vertical ? below : {};
      const node = { name: drop, depth: k, itemStyle: { color: t.neutral, borderWidth: 0 } };
      if (!count) return { ...node, label: { ...place, rich, formatter: () => `${text}\n{n|${format.count(0)}}` } };
      const colorStops = [];
      let done = 0;
      for (let b = groups.length - 1; b >= 0; b -= 1) {
        const part = groups[b].counts[drop];
        if (!part) continue;
        colorStops.push({ offset: done / count, color: colourOf(b) });
        done += part;
        colorStops.push({ offset: done / count, color: colourOf(b) });
      }
      let bar = "";
      let edge = 0;
      let sum = 0;
      groups.forEach((group, b) => {
        sum += group.counts[drop];
        const right = Math.round((barWidth * sum) / count);
        if (right > edge) {
          rich[`s${b}`] = { backgroundColor: colourOf(b), width: right - edge, height: 8 };
          bar += `{s${b}|}`;
        }
        edge = right;
      });
      const [x2, y2] = vertical ? [1, 0] : [0, 1];
      return {
        ...node,
        itemStyle: { color: { type: "linear", x: 0, y: 0, x2, y2, colorStops }, borderWidth: 0 },
        label: { ...place, rich, formatter: () => `${text}\n${bar}{n|  ${format.count(count)}}` },
      };
    }
    const stageLabel = (stage) =>
      vertical
        ? { position: "left", color: t.ink, formatter: () => `${stage}\n${format.count(total[stage])}` }
        : {
            // Above the column, from its left edge (never cut off at the chart's edge); two lines when narrow.
            position: [0, narrow ? -32 : -16],
            align: "left",
            color: t.ink,
            formatter: () => `${stage}${narrow ? "\n" : "  "}${format.count(total[stage])}`,
          };
    const nodes = [];
    main.forEach((stage, k) => {
      for (let b = groups.length - 1; b >= 0; b -= 1) {
        nodes.push({
          name: `${stage}|${b}`,
          depth: k,
          itemStyle: { color: colourOf(b), borderWidth: 0 },
          label: b === groups.length - 1 ? stageLabel(stage) : { show: false },
        });
      }
      if (k >= 1) nodes.push(spacer(k), dropNode(drops[k - 1], k));
    });
    const links = [];
    drops.forEach((drop, k) => {
      groups.forEach((group, b) => {
        // Empty flows are left out: ECharts would draw them as 1 px lines, which look like a few.
        const next = group.counts[main[k + 1]];
        const lost = group.counts[drop];
        if (next > 0) links.push({ source: `${main[k]}|${b}`, target: `${main[k + 1]}|${b}`, value: next });
        if (lost > 0) links.push({ source: `${main[k]}|${b}`, target: drop, value: lost });
      });
    });
    const share = (part, whole) => format.share(part / Math.max(1, whole));
    const ofGroup = (count, group) => `${share(count, group.counts[main[0]])} of the group`;
    const range = (group) => `${format.fixed(group.low, 2)} to ${format.fixed(group.high, 2)}`;
    const bandTitle = (group) => `${group.label} (strength ${range(group)})`;
    function describe(item) {
      if (String(item.name).startsWith(SPACER)) return "";
      if (item.dataType === "edge") {
        const group = groups[bandOf(item.data.source)];
        const from = stageOf(item.data.source);
        const count = `${format.count(item.value)} (${ofGroup(item.value, group)})`;
        const rows = [[`${from} → ${stageOf(item.data.target)}`, count]];
        if (from !== main[0]) rows.push([`Share of ${from.toLowerCase()}`, share(item.value, group.counts[from])]);
        return tip(bandTitle(group), rows);
      }
      const b = bandOf(item.name);
      const stage = stageOf(item.name);
      if (b !== null) {
        const group = groups[b];
        const count = group.counts[stage];
        return tip(bandTitle(group), [[stage, `${format.count(count)} (${ofGroup(count, group)})`]]);
      }
      // A drop-off: its total and its own breakdown (No interview: never invited, invited without one), then each
      // fifth: how many of the drop-off it makes up, and how much of the fifth that is.
      const rows = [[stage, `${format.count(total[stage])} (${share(total[stage], everyone)} of all ${unit})`]];
      (notes[stage] || []).forEach(([label, count]) => rows.push([label, format.count(count)]));
      groups.forEach((group) => {
        const count = group.counts[stage];
        const of = `${share(count, total[stage])} of the ${format.count(total[stage])}; ${ofGroup(count, group)}`;
        rows.push([group.label, `${format.count(count)} (${of})`]);
      });
      return tip(stage, rows);
    }
    return { nodes, links, describe };
  }

  // Whether a chart's "bands" switch is on and its payload has the fifths to split by.
  const bandsOn = (p, element) => element.dataset.bands === "on" && Array.isArray(p.bands) && p.bands.length > 1;

  // The series options of a Sankey split by strength fifth (strengthSankey).
  const strengthSeries = ({ nodes, links }) => ({
    type: "sankey",
    nodeGap: 3,
    nodeAlign: "left", // a drop-off stays in the column after its stage ("justify" pushes it to the end)
    layoutIterations: 0,
    draggable: false,
    emphasis: { focus: "trajectory" },
    data: nodes,
    links,
    lineStyle: { color: "source", opacity: 0.7, curveness: 0.5 },
  });

  // --- Chart kinds: flows (ECharts Sankey diagrams) -----------------------------------------------------------------

  // The funnel from applications to matches {applied, invited, not_invited, ...} as a Sankey diagram: the stages in
  // the blue ramp, the drop-offs in neutral grey. Below 560 px it runs top to bottom, so the labels fit. A program's
  // funnel has the applications of each strength fifth too (bands: [{label, low, high, counts}]), drawn with the
  // "bands" switch on by strengthSankey.
  register("funnel", (p, t, element, option) => {
    const vertical = element.clientWidth < 560;
    const main = ["Applied", "Invited", "Interviewed", "Ranked", "Matched"];
    const drops = ["Not invited", "Declined", "Not ranked", "Not matched"];
    const countsOf = (c) => ({
      Applied: c.applied,
      Invited: c.invited,
      "Not invited": c.not_invited,
      Interviewed: c.interviewed,
      Declined: c.declined,
      Ranked: c.ranked,
      "Not ranked": c.not_ranked,
      Matched: c.matched,
      "Not matched": c.not_matched,
    });
    const counts = countsOf(p);
    const orient = vertical ? "vertical" : "horizontal";
    if (bandsOn(p, element)) {
      const groups = p.bands.map((band) => ({ ...band, counts: countsOf(band.counts) }));
      const spec = { main, drops, total: counts, groups, unit: "applications", vertical, barWidth: 56 };
      const { nodes, links, describe } = strengthSankey(t, spec);
      return {
        ...option,
        legend: { show: false },
        tooltip: { ...option.tooltip, trigger: "item", formatter: describe },
        series: [
          {
            ...strengthSeries({ nodes, links }),
            orient,
            nodeWidth: 14,
            // Vertical: stage labels in the left margin, drop-off labels under their bar (the last one's at the foot).
            left: vertical ? 84 : 8,
            right: vertical ? 8 : 104,
            top: vertical ? 8 : 28,
            bottom: vertical ? 40 : 16,
          },
        ],
      };
    }
    const links = [];
    for (let k = 0; k < drops.length; k += 1) {
      // Empty flows are left out (ECharts draws a zero link as a 1 px line, which looks like a few).
      if (counts[main[k + 1]] > 0) links.push({ source: main[k], target: main[k + 1], value: counts[main[k + 1]] });
      if (counts[drops[k]] > 0) links.push({ source: main[k], target: drops[k], value: counts[drops[k]] });
    }
    const node = (name, color, depth) => ({
      name,
      depth, // pinned, so a stage or drop-off with no flow keeps its column
      itemStyle: { color, borderColor: color },
      label: { color: t.ink, formatter: () => `${name}\n${format.count(counts[name])}` },
    });
    return {
      ...option,
      legend: { show: false },
      tooltip: {
        ...option.tooltip,
        trigger: "item",
        formatter: (item) =>
          item.dataType === "edge"
            ? tip(`${item.data.source} → ${item.data.target}`, [
                ["Applications", format.count(item.value)],
                [`Share of ${item.data.source.toLowerCase()}`, format.share(item.value / Math.max(1, counts[item.data.source]))],
              ])
            : tip(item.name, [["Applications", format.count(counts[item.name])]]),
      },
      series: [
        {
          type: "sankey",
          orient,
          left: 8,
          right: vertical ? 8 : 96,
          top: vertical ? 8 : 16,
          bottom: vertical ? 48 : 16,
          nodeGap: 14,
          nodeWidth: 14,
          nodeAlign: "left",
          draggable: false,
          emphasis: { focus: "adjacency" },
          data: [
            ...main.map((name, k) => node(name, t.stages[k], k)),
            ...drops.map((name, k) => node(name, t.neutral, k + 1)),
          ],
          links,
          lineStyle: { color: "gradient", opacity: 0.3, curveness: 0.5 },
        },
      ],
    };
  }, { widths: [560] });

  // Every applicant once through the stages {stages, drops, counts, bands, notes}: drops[k] leaves stages[k]. The
  // stages in the blue ramp, the drop-offs in neutral grey; with the "bands" switch on, split by strength fifth
  // (strengthSankey). Hovering a stage or a band highlights its path through the stages.
  register("flow", (p, t, element, option) => {
    const narrow = element.clientWidth < 480;
    const frame = { left: 8, right: narrow ? 96 : 160, bottom: 16, nodeWidth: 16 };
    const tooltip = (formatter) => ({ ...option.tooltip, trigger: "item", formatter });
    if (bandsOn(p, element)) {
      const spec = { main: p.stages, drops: p.drops, total: p.counts, groups: p.bands, unit: "applicants" };
      const split = strengthSankey(t, { ...spec, notes: p.notes, narrow, barWidth: narrow ? 48 : 80 });
      return {
        ...option,
        legend: { show: false },
        tooltip: tooltip(split.describe),
        series: [{ ...strengthSeries(split), ...frame, top: narrow ? 44 : 28 }],
      };
    }
    const everyone = p.counts[p.stages[0]];
    const nodes = [];
    p.stages.forEach((stage, k) => {
      nodes.push({
        name: stage,
        depth: k,
        itemStyle: { color: scaleStep(t.stages, k, p.stages.length), borderWidth: 0 },
        label: { color: t.ink, formatter: () => `${stage}\n${format.count(p.counts[stage])}` },
      });
      if (k >= 1) {
        const drop = p.drops[k - 1];
        const words = narrow ? drop.replace(", ", ",\n") : drop;
        nodes.push({
          name: drop,
          depth: k,
          itemStyle: { color: t.neutral, borderWidth: 0 },
          label: { color: t.muted, formatter: () => `${words}\n${format.count(p.counts[drop])}` },
        });
      }
    });
    const links = [];
    p.drops.forEach((drop, k) => {
      // Empty flows are left out: ECharts would draw them as 1 px lines, which look like a few applicants.
      const next = p.counts[p.stages[k + 1]];
      const lost = p.counts[drop];
      if (next > 0) links.push({ source: p.stages[k], target: p.stages[k + 1], value: next });
      if (lost > 0) links.push({ source: p.stages[k], target: drop, value: lost });
    });
    const share = (part, whole) => format.share(part / Math.max(1, whole));
    function describe(item) {
      if (item.dataType === "edge") {
        const from = item.data.source;
        const count = `${format.count(item.value)} (${share(item.value, everyone)} of all applicants)`;
        const rows = [[`${from} → ${item.data.target}`, count]];
        if (from !== p.stages[0]) rows.push([`Share of ${from.toLowerCase()}`, share(item.value, p.counts[from])]);
        return tip("All applicants", rows);
      }
      const count = p.counts[item.name];
      const rows = [[item.name, `${format.count(count)} (${share(count, everyone)} of all applicants)`]];
      // The total's own breakdown (No interview: never invited, invited without one).
      ((p.notes || {})[item.name] || []).forEach(([label, count]) => rows.push([label, format.count(count)]));
      return tip(item.name, rows);
    }
    return {
      ...option,
      legend: { show: false },
      tooltip: tooltip(describe),
      series: [
        {
          type: "sankey",
          ...frame,
          top: 16,
          nodeGap: 14,
          nodeAlign: "left", // a drop-off stays in the column after its stage ("justify" pushes it to the end)
          layoutIterations: 0,
          draggable: false,
          emphasis: { focus: "trajectory" },
          data: nodes,
          links,
          lineStyle: { color: "gradient", opacity: 0.3, curveness: 0.5 },
        },
      ],
    };
  }, { widths: [480] });

  // --- Network kinds (sigma.js) -----------------------------------------------------------------------------------

  // A hover label in the theme's colours (sigma's own draws a white box, unreadable in the dark theme). Text is drawn
  // on the canvas, never inserted as HTML.
  function hoverLabel(t) {
    return (context, data, settings) => {
      const size = settings.labelSize;
      context.font = `${settings.labelWeight} ${size}px ${settings.labelFont}`;
      const label = typeof data.label === "string" ? data.label : "";
      const width = context.measureText(label).width;
      context.fillStyle = t.surface;
      context.strokeStyle = t.faint;
      context.beginPath();
      context.arc(data.x, data.y, data.size + 3, 0, Math.PI * 2);
      context.fill();
      context.stroke();
      if (!label) return;
      const x = data.x + data.size + 4;
      context.beginPath();
      context.rect(x - 3, data.y - size / 2 - 4, width + 6, size + 8);
      context.fill();
      context.stroke();
      context.fillStyle = t.ink;
      context.fillText(label, x, data.y + size / 3);
    };
  }

  // One agent's applications by how far each got {center, side, stages: [labels], nodes: [[name, stage], ...]}:
  // the agent in the middle, the other side on rings, the furthest stage (a match) nearest the middle. Colours:
  // neutral for applied only, the blue ramp for invited, interviewed and ranked, series 3 for the match.
  register(
    "ego",
    (p, t) => {
      const graph = new window.graphology.Graph();
      const last = p.stages.length - 1;
      const colours = p.stages.map((_label, stage) => {
        if (stage === 0) return t.neutral;
        return stage === last ? t.matched : t.stages[Math.min(stage, 4)];
      });
      graph.addNode("agent", {
        x: 0,
        y: 0,
        size: 12,
        label: p.center,
        color: p.side === "program" ? t.program : t.applicant,
        zIndex: 2,
      });
      const rings = p.stages.map(() => []);
      p.nodes.forEach(([_name, stage], k) => rings[stage].push(k));
      rings.forEach((members, stage) => {
        const radius = 1 + last - stage;
        // Applications that were never invited get no edge (the outer ring says enough), and a crowded ring's edges
        // fade, so a program with a thousand applications still shows its interviews and matches.
        const opacity = Math.min(0.5, Math.max(0.08, 15 / Math.max(1, members.length)));
        const shrink = Math.min(1, Math.sqrt(60 / Math.max(1, members.length))); // crowded rings get smaller dots
        members.forEach((k, position) => {
          const angle = (2 * Math.PI * position) / members.length + stage * 0.4;
          const key = `n${k}`;
          graph.addNode(key, {
            x: radius * Math.cos(angle),
            y: radius * Math.sin(angle),
            size: Math.max(2, (stage >= last - 1 ? 7 : 4) * shrink),
            label: p.nodes[k][0],
            color: colours[stage],
            zIndex: stage >= last - 1 ? 1 : 0,
          });
          if (stage > 0) {
            graph.addEdge("agent", key, { color: t.alpha(colours[stage], opacity), size: stage >= last - 1 ? 1.5 : 0.8 });
          }
        });
      });
      return {
        graph,
        settings: {
          labelColor: { color: t.ink },
          labelFont: t.font,
          labelSize: 12,
          labelRenderedSizeThreshold: 7,
          defaultDrawNodeHover: hoverLabel(t),
          zIndex: true,
          stagePadding: 24,
          // The layout is fixed: no zooming or panning, so scrolling the page over the chart scrolls the page.
          enableCameraZooming: false,
          enableCameraPanning: false,
          enableCameraRotation: false,
        },
      };
    },
    { engine: "sigma" },
  );

  // --- Life cycle -------------------------------------------------------------------------------------------------

  function start() {
    renderAll();
    new MutationObserver(redrawAll).observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme", "data-chart-patterns"],
    });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redrawAll);
    window.matchMedia("(prefers-contrast: more)").addEventListener("change", redrawAll);
  }

  document.addEventListener("htmx:afterSettle", (event) => renderAll(event.target));
  document.addEventListener("htmx:beforeCleanupElement", (event) => dispose(event.target));

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();

  window.NRMPCharts = { register, renderAll, escape, tip, format };
})();
