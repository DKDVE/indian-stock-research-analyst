/**
 * Chart.js — price and PE charts.
 * Relies on global `Chart` from Chart.js UMD.
 */

let priceChartInstance = null;
let peChartInstance = null;

function getChart() {
  if (typeof Chart === "undefined") {
    throw new Error("Chart.js not loaded");
  }
  return Chart;
}

/** Readable axes on light backgrounds (avoids faint grey on dark canvas) */
function applyChartTheme() {
  const C = typeof Chart !== "undefined" ? Chart : null;
  if (!C || C.__fintechLightTheme) return;
  C.defaults.color = "#334155";
  C.defaults.borderColor = "rgba(148, 163, 184, 0.45)";
  C.defaults.font = { family: "system-ui, -apple-system, Segoe UI, Roboto, sans-serif", size: 11 };
  C.__fintechLightTheme = true;
}

function destroyPriceChart() {
  if (priceChartInstance) {
    priceChartInstance.destroy();
    priceChartInstance = null;
  }
}

function destroyPEChart() {
  if (peChartInstance) {
    peChartInstance.destroy();
    peChartInstance = null;
  }
}

/**
 * @param {HTMLCanvasElement} canvas
 * @param {Array<{date:string, close:number}>} rows
 * @param {string} period
 */
function renderPriceChart(canvas, rows, period) {
  destroyPriceChart();
  if (!canvas || !rows || !rows.length) return;

  applyChartTheme();
  const ChartCtor = getChart();
  const labels = rows.map((r) => r.date);
  const prices = rows.map((r) => r.close);
  const first = prices[0];
  const last = prices[prices.length - 1];
  const up = last >= first;
  const color = up ? "#16a34a" : "#dc2626";

  const ctx = canvas.getContext("2d");
  priceChartInstance = new ChartCtor(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          data: prices,
          borderColor: color,
          borderWidth: 1.5,
          pointRadius: 0,
          fill: true,
          backgroundColor: up ? "rgba(22,163,74,.07)" : "rgba(220,38,38,.07)",
          tension: 0.2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15, 23, 42, 0.92)",
          titleColor: "#f8fafc",
          bodyColor: "#f8fafc",
          borderColor: "#475569",
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: (c) =>
              `₹${c.parsed.y.toLocaleString("en-IN", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}`,
          },
        },
      },
      scales: {
        x: {
          ticks: {
            maxTicksLimit: 8,
            maxRotation: 0,
            font: { size: 11 },
            color: "#475569",
          },
          grid: { display: false },
        },
        y: {
          position: "right",
          ticks: {
            maxTicksLimit: 5,
            font: { size: 11 },
            color: "#475569",
            callback: (v) => "₹" + Number(v).toLocaleString("en-IN"),
          },
          grid: { color: "rgba(148, 163, 184, 0.35)" },
        },
      },
    },
  });
}

/**
 * Blue PE line, grey dashed 3Y average.
 * @param {HTMLCanvasElement} canvas
 * @param {Array<{date:string, pe:number}>} rows
 */
function renderPEChart(canvas, rows) {
  destroyPEChart();
  if (!canvas || !rows || !rows.length) return;

  applyChartTheme();
  const ChartCtor = getChart();
  const labels = rows.map((r) => r.date);
  const values = rows.map((r) => Number(r.pe));
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  const avgLine = values.map(() => Number(avg.toFixed(2)));

  const ctx = canvas.getContext("2d");
  peChartInstance = new ChartCtor(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          data: values,
          borderColor: "#3b82f6",
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          tension: 0.3,
        },
        {
          data: avgLine,
          borderColor: "rgba(128,128,128,.45)",
          borderWidth: 1,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "rgba(15, 23, 42, 0.92)",
          titleColor: "#f8fafc",
          bodyColor: "#f8fafc",
          borderColor: "#475569",
          borderWidth: 1,
          padding: 10,
          callbacks: {
            label: (c) => `${c.parsed.y.toFixed(1)}x`,
          },
        },
      },
      scales: {
        x: {
          ticks: { maxTicksLimit: 6, maxRotation: 0, font: { size: 11 }, color: "#475569" },
          grid: { display: false },
        },
        y: {
          position: "right",
          ticks: {
            maxTicksLimit: 4,
            font: { size: 11 },
            color: "#475569",
            callback: (v) => v + "x",
          },
          grid: { color: "rgba(148, 163, 184, 0.35)" },
        },
      },
    },
  });
}

export { renderPriceChart, renderPEChart, destroyPriceChart, destroyPEChart };
