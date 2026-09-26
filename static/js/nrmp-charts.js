// Diagnostic charts (plan step 3.8): draws every [data-chart] element with ECharts.
//
// <div data-chart="histogram" data-payload="chart-strength" role="img" aria-label="..."></div> reads the JSON from
// the element with id "chart-strength" (written by Django's json_script) and draws it with the builder registered
// for its kind. Colours come from the daisyUI theme and follow the light/dark toggle; charts resize with their box
// and are disposed of when HTMX removes them. Tooltip text is escaped. The page gives every chart's numbers in text
// too, so nothing depends on the drawing.
(() => {
  "use strict";

  const builders = {};
  const charts = new Map(); // element -> {chart, observer}
  const probe = document.createElement("canvas").getContext("2d", { willReadFrequently: true });

  // ECharts cannot parse the oklch() colours daisyUI uses, so let the browser convert them to rgba().
  function rgba(color, alpha = 1) {
    probe.clearRect(0, 0, 1, 1);
    probe.fillStyle = "#000";
    probe.fillStyle = color;
    probe.fillRect(0, 0, 1, 1);
    const [r, g, b, a] = probe.getImageData(0, 0, 1, 1).data;
    return `rgba(${r}, ${g}, ${b}, ${((a / 255) * alpha).toFixed(3)})`;
  }

  function tokens() {
    const style = getComputedStyle(document.documentElement);
    const read = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
    const text = read("--color-base-content", "#1f2937");
    return {
      text: rgba(text),
      muted: rgba(text, 0.7),
      faint: rgba(text, 0.35),
      grid: rgba(text, 0.12),
      background: rgba(read("--color-base-100", "#ffffff")),
      primary: rgba(read("--color-primary", "#4f46e5")),
      secondary: rgba(read("--color-secondary", "#db2777")),
      accent: rgba(read("--color-accent", "#0d9488")),
      font: getComputedStyle(document.body).fontFamily,
    };
  }

  const escape = (value) => window.echarts.format.encodeHTML(String(value));
  const number = (value, digits = 0) =>
    Number(value).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });

  function base(t) {
    return {
      animation: !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
      textStyle: { fontFamily: t.font, color: t.text },
      grid: { left: 56, right: 16, top: 36, bottom: 48, containLabel: false },
      tooltip: {
        backgroundColor: t.background,
        borderColor: t.grid,
        textStyle: { color: t.text, fontFamily: t.font },
        confine: true,
      },
      legend: { top: 0, textStyle: { color: t.muted } },
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

  function register(kind, builder) {
    builders[kind] = builder;
  }

  function render(element) {
    const builder = builders[element.dataset.chart];
    const source = document.getElementById(element.dataset.payload);
    if (!builder || !source || !window.echarts) return;
    const payload = JSON.parse(source.textContent);
    if (payload === null) return;
    let entry = charts.get(element);
    if (!entry) {
      const chart = window.echarts.init(element, null, { renderer: "canvas" });
      const observer = new ResizeObserver(() => chart.resize());
      observer.observe(element);
      entry = { chart, observer };
      charts.set(element, entry);
    }
    const t = tokens();
    entry.chart.setOption(builder(payload, t, element, base(t)), true);
  }

  function dispose(element) {
    const entry = charts.get(element);
    if (!entry) return;
    entry.observer.disconnect();
    entry.chart.dispose();
    charts.delete(element);
  }

  function renderAll(root = document) {
    root.querySelectorAll("[data-chart]").forEach(render);
  }

  function redrawAll() {
    charts.forEach((_chart, element) => render(element));
  }

  // --- Chart kinds ------------------------------------------------------------------------------------------------

  // A histogram {edges, counts, requested?}: the realised counts as bars, the requested counts as a line.
  register("histogram", (p, t, element, option) => {
    // One more decimal than the bin width needs, so neighbouring bins get different labels (nrmps/charts.py digits).
    const width = (p.edges[p.edges.length - 1] - p.edges[0]) / Math.max(1, p.edges.length - 1);
    const places = width > 0 ? Math.max(0, Math.ceil(-Math.log10(width)) + 1) : 0;
    const labels = p.counts.map((_count, k) => number((p.edges[k] + p.edges[k + 1]) / 2, places));
    const ranges = p.counts.map((_count, k) => `${number(p.edges[k], places)} to ${number(p.edges[k + 1], places)}`);
    const series = [
      { name: "Realised", type: "bar", data: p.counts, barCategoryGap: "8%", itemStyle: { color: t.primary } },
    ];
    if (p.requested) {
      series.push({
        name: "Requested",
        type: "line",
        data: p.requested,
        smooth: true,
        symbol: "none",
        lineStyle: { color: t.secondary, width: 2 },
        itemStyle: { color: t.secondary },
      });
    }
    return {
      ...option,
      legend: { ...option.legend, show: Boolean(p.requested) },
      tooltip: {
        ...option.tooltip,
        trigger: "axis",
        formatter: (items) =>
          [escape(ranges[items[0].dataIndex])]
            .concat(items.map((item) => `${escape(item.seriesName)}: ${number(item.value, item.seriesIndex ? 1 : 0)}`))
            .join("<br>"),
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
        itemStyle: { color: t.primary, opacity: 0.45 },
      },
    ];
    if (p.post) {
      series.push({
        name: "After interviews",
        type: "scatter",
        data: points(p.post),
        symbolSize: 4,
        itemStyle: { color: t.secondary, opacity: 0.45 },
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
      lineStyle: { color: t.muted, type: "dashed", width: 1 },
      itemStyle: { color: t.muted },
    });
    return {
      ...option,
      tooltip: {
        ...option.tooltip,
        trigger: "item",
        formatter: (item) =>
          `${escape(item.seriesName)}<br>true ${number(item.value[0], 2)}, observed ${number(item.value[1], 2)}`,
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
          [escape(p.names[items[0].dataIndex])]
            .concat(items.map((item) => `${escape(item.seriesName)}: ${number(item.value)}`))
            .join("<br>"),
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
          itemStyle: { color: t.primary },
        },
        {
          name: "Positions",
          type: "scatter",
          data: p.positions,
          symbol: "rect",
          symbolSize: [10, 2],
          itemStyle: { color: t.secondary },
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
        `${number(items[0].value[0] * 100)}% of programs get ${number(items[0].value[1] * 100)}% of first choices`,
    },
    xAxis: axis(t, "Share of programs (least wanted first)", { type: "value", min: 0, max: 1 }),
    yAxis: axis(t, "Share of first choices", { type: "value", min: 0, max: 1, nameGap: 40 }),
    series: [
      {
        name: "Demand",
        type: "line",
        data: p.lorenz,
        symbol: "none",
        areaStyle: { color: t.primary, opacity: 0.15 },
        lineStyle: { color: t.primary, width: 2 },
        itemStyle: { color: t.primary },
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
        lineStyle: { color: t.muted, type: "dashed", width: 1 },
        itemStyle: { color: t.muted },
      },
    ],
  }));

  // The funnel from applications to matches {applied, invited, not_invited, ...} as a Sankey diagram.
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
      label: { color: t.text, formatter: () => `${name}\n${number(counts[name])}` },
    });
    return {
      ...option,
      legend: { show: false },
      tooltip: {
        ...option.tooltip,
        trigger: "item",
        formatter: (item) =>
          item.dataType === "edge"
            ? `${escape(item.data.source)} → ${escape(item.data.target)}: ${number(item.value)} (${number(
                (100 * item.value) / Math.max(1, counts[item.data.source]),
                1,
              )}%)`
            : `${escape(item.name)}: ${number(counts[item.name])}`,
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
          data: [...main.map((name) => node(name, t.primary)), ...drops.map((name) => node(name, t.faint))],
          links,
          lineStyle: { color: "gradient", opacity: 0.3, curveness: 0.5 },
        },
      ],
    };
  });

  // --- Life cycle ---------------------------------------------------------------------------------------------------

  function start() {
    renderAll();
    new MutationObserver(redrawAll).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redrawAll);
  }

  document.addEventListener("htmx:afterSettle", (event) => renderAll(event.target));
  document.addEventListener("htmx:beforeCleanupElement", (event) => dispose(event.target));

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();

  window.NRMPCharts = { register, renderAll, escape };
})();
