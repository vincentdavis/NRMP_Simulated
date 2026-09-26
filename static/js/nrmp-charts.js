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

  function register(kind, build, { engine = "echarts" } = {}) {
    builders[kind] = { build, engine };
  }

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
      entry.observer = new ResizeObserver(() => engine.resize(entry));
      entry.observer.observe(element);
      drawn.set(element, entry);
    }
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

  function renderAll(root = document) {
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

  // The funnel from applications to matches {applied, invited, not_invited, ...} as a Sankey diagram: the stages in
  // the blue ramp, the drop-offs in neutral grey. Below 560 px it runs top to bottom, so the labels fit.
  register("funnel", (p, t, element, option) => {
    const vertical = element.clientWidth < 560;
    const main = ["Applied", "Invited", "Interviewed", "Ranked", "Matched"];
    const drops = ["Not invited", "Declined", "Not ranked", "Not matched"];
    const counts = {
      Applied: p.applied,
      Invited: p.invited,
      "Not invited": p.not_invited,
      Interviewed: p.interviewed,
      Declined: p.declined,
      Ranked: p.ranked,
      "Not ranked": p.not_ranked,
      Matched: p.matched,
      "Not matched": p.not_matched,
    };
    const links = [];
    for (let k = 0; k < drops.length; k += 1) {
      links.push({ source: main[k], target: main[k + 1], value: counts[main[k + 1]] });
      links.push({ source: main[k], target: drops[k], value: counts[drops[k]] });
    }
    const node = (name, color) => ({
      name,
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
          orient: vertical ? "vertical" : "horizontal",
          left: 8,
          right: vertical ? 8 : 96,
          top: vertical ? 8 : 16,
          bottom: vertical ? 48 : 16,
          nodeGap: 14,
          nodeWidth: 14,
          nodeAlign: "left",
          draggable: false,
          emphasis: { focus: "adjacency" },
          data: [...main.map((name, k) => node(name, t.stages[k])), ...drops.map((name) => node(name, t.neutral))],
          links,
          lineStyle: { color: "gradient", opacity: 0.3, curveness: 0.5 },
        },
      ],
    };
  });

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
