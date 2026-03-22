/**
 * Stock Research tab — DOM, analysis flow, KPI colouring.
 */

import { API } from "./api.js";
import { renderPriceChart, renderPEChart } from "./charts.js";
import { loadFeed } from "./market.js";
import { configureMarked, showBriefSkeleton, streamBrief } from "./brief.js";
import { renderPeers } from "./peers.js";

const SECTOR_PE = {
  banking: { low: 10, high: 20 },
  technology: { low: 20, high: 40 },
  "oil & gas": { low: 10, high: 18 },
  retail: { low: 50, high: 130 },
  default: { low: 15, high: 35 },
};

let currentTicker = "";
let currentPeriod = "1yr";
let marketTabInitialized = false;
let analyseSeq = 0;

function readFlags() {
  const b = document.body;
  return {
    enableMarket: b.dataset.enableMarket === "true",
    enablePeHistory: b.dataset.enablePeHistory === "true",
    enableAnnouncements: b.dataset.enableAnnouncements === "true",
  };
}

function $(id) {
  return document.getElementById(id);
}

function setStatus(msg, isErr = false) {
  const el = $("status-bar");
  if (!el) return;
  el.textContent = msg || "";
  el.classList.toggle("status-bar--err", !!isErr);
}

function setBusy(busy) {
  const btn = $("analyse-btn");
  if (!btn) return;
  btn.disabled = busy;
  if (busy) {
    btn.innerHTML =
      '<span class="btn-spinner" aria-hidden="true"></span>Analysing…';
  } else {
    btn.textContent = "Analyse →";
  }
}

function showKpiSkeleton(show) {
  const sk = $("kpi-skeleton");
  const grid = $("metrics-grid");
  if (sk) sk.hidden = !show;
  if (grid) grid.hidden = show;
}

function getSectorPeBand(sector) {
  const s = (sector || "").toLowerCase();
  if (s.includes("bank")) return SECTOR_PE.banking;
  if (s.includes("software") || s.includes("technology") || s.includes("tech") || s.includes("it ")) {
    return SECTOR_PE.technology;
  }
  if (s.includes("oil") || s.includes("gas") || s.includes("petrol")) return SECTOR_PE["oil & gas"];
  if (s.includes("retail")) return SECTOR_PE.retail;
  return SECTOR_PE.default;
}

function fmtMoney(v, prefix = "₹", suffix = "") {
  if (v == null || v === "") return "N/A";
  const n = parseFloat(String(v).replace(/,/g, ""));
  if (Number.isNaN(n)) return "N/A";
  return `${prefix}${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}${suffix}`;
}

/** Market cap in Cr per API — ≥ 1,00,000 Cr → lakh-crore shorthand */
function fmtMarketCap(v) {
  if (v == null || v === "") return "N/A";
  const n = parseFloat(String(v).replace(/,/g, ""));
  if (Number.isNaN(n)) return "N/A";
  if (n >= 100000) {
    return `₹${(n / 100000).toFixed(1)} L Cr`;
  }
  return `₹${Math.round(n).toLocaleString("en-IN")} Cr`;
}

function colourPe(el, peNum, sector) {
  if (!el || peNum == null || Number.isNaN(peNum)) return;
  const band = getSectorPeBand(sector);
  const th = band.high;
  if (peNum < th * 0.7) el.style.color = "#16a34a";
  else if (peNum > th * 1.2) el.style.color = "#dc2626";
  else el.style.color = "";
}

function colourPb(el, pbNum) {
  if (!el || pbNum == null || Number.isNaN(pbNum)) return;
  if (pbNum < 1.5) el.style.color = "#16a34a";
  else if (pbNum > 4) el.style.color = "#dc2626";
  else el.style.color = "";
}

function populateCards(data) {
  const flags = readFlags();

  $("company-name").textContent = data.company_name || "—";
  $("company-sub").textContent = `${data.ticker || "—"} · ${data.sector || "—"}`;
  $("price-nse").textContent = data.price_nse ? `₹${data.price_nse}` : "—";
  $("data-date").textContent = data.data_date || "—";

  const chg = parseFloat(data.percent_change);
  const chgEl = $("price-change");
  if (!isNaN(chg) && chgEl) {
    chgEl.textContent = `${chg >= 0 ? "+" : ""}${chg}% today`;
    chgEl.className = "price-box__change " + (chg >= 0 ? "price-box__change--up" : "price-box__change--down");
  }

  const pr = parseFloat(String(data.price_nse || "").replace(/,/g, ""));
  const sector = data.sector || "";

  const peEl = $("m-pe");
  if (data.pe) {
    const peNum = parseFloat(data.pe);
    peEl.textContent = `${peNum.toFixed(1)}x`;
    colourPe(peEl, peNum, sector);
  } else {
    peEl.textContent = "N/A";
    peEl.style.color = "";
  }

  const pbEl = $("m-pb");
  if (data.pb) {
    const pbNum = parseFloat(data.pb);
    pbEl.textContent = `${pbNum.toFixed(2)}x`;
    colourPb(pbEl, pbNum);
  } else {
    pbEl.textContent = "N/A";
    pbEl.style.color = "";
  }

  $("m-eps").textContent = data.eps ? fmtMoney(data.eps, "₹", "") : "N/A";
  $("m-cap").textContent = fmtMarketCap(data.market_cap);

  const roeEl = $("m-roe");
  if (data.roe) {
    const rv = parseFloat(data.roe);
    roeEl.textContent = `${rv.toFixed(1)}%`;
    if (rv >= 15) roeEl.style.color = "#16a34a";
    else if (rv < 8) roeEl.style.color = "#dc2626";
    else roeEl.style.color = "";
  } else {
    roeEl.textContent = "N/A";
    roeEl.style.color = "";
  }

  $("m-div").textContent = data.div_yield ? `${parseFloat(data.div_yield).toFixed(2)}%` : "N/A";

  $("m-high").textContent = data.year_high ? `₹${parseFloat(data.year_high).toLocaleString("en-IN")}` : "N/A";
  $("m-low").textContent = data.year_low ? `₹${parseFloat(data.year_low).toLocaleString("en-IN")}` : "N/A";

  const trendEl = $("m-trend");
  const tv = (data.overall_trend || "").toLowerCase();
  trendEl.textContent = data.overall_trend || "N/A";
  if (tv.includes("buy") || tv.includes("bullish")) trendEl.style.color = "#16a34a";
  else if (tv.includes("sell") || tv.includes("bearish")) trendEl.style.color = "#dc2626";
  else trendEl.style.color = "";

  const riskEl = $("m-risk");
  const rl = (data.risk_level || "").toLowerCase();
  riskEl.textContent = data.risk_level || "N/A";
  if (rl.includes("low")) riskEl.style.color = "#16a34a";
  else if (rl.includes("high")) riskEl.style.color = "#dc2626";
  else riskEl.style.color = "";

  if (data.price_target != null && data.price_target !== "") {
    $("m-target").textContent = `₹${parseFloat(data.price_target).toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
  } else {
    $("m-target").textContent = "N/A";
  }

  const sma50El = $("m-sma50");
  if (data.sma50) {
    sma50El.textContent = fmtMoney(data.sma50);
    const s50 = parseFloat(data.sma50);
    if (!isNaN(pr) && !isNaN(s50)) sma50El.style.color = pr > s50 ? "#16a34a" : "#dc2626";
  } else {
    sma50El.textContent = "N/A";
    sma50El.style.color = "";
  }

  const sma200El = $("m-sma200");
  if (data.sma200) {
    sma200El.textContent = fmtMoney(data.sma200);
    const s200 = parseFloat(data.sma200);
    if (!isNaN(pr) && !isNaN(s200)) sma200El.style.color = pr > s200 ? "#16a34a" : "#dc2626";
  } else {
    sma200El.textContent = "N/A";
    sma200El.style.color = "";
  }

  $("m-rev").textContent = data.revenue ? fmtMarketCap(data.revenue) : "N/A";
  $("m-profit").textContent = data.net_profit ? fmtMarketCap(data.net_profit) : "N/A";

  renderPeers(data.peers, data.company_name, data.pe);

  if (data.recos_buy != null || data.recos_hold != null || data.recos_sell != null) {
    $("recos-lbl").textContent = `Analyst sentiment: ${data.recos_buy ?? "—"}% Buy · ${data.recos_hold ?? "—"}% Hold · ${data.recos_sell ?? "—"}% Sell`;
  } else {
    $("recos-lbl").textContent = "";
  }

  const av = data.analyst_view || {};
  const total =
    (av.strongBuy || 0) + (av.buy || 0) + (av.hold || 0) + (av.sell || 0) + (av.strongSell || 0) || 1;
  const pw = (v) => `${(((v || 0) / total) * 100).toFixed(1)}%`;
  $("ab-sb").style.width = pw(av.strongBuy);
  $("ab-b").style.width = pw(av.buy);
  $("ab-h").style.width = pw(av.hold);
  $("ab-s").style.width = pw(av.sell);
  $("ab-ss").style.width = pw(av.strongSell);
  $("analyst-lbl").textContent = `Strong Buy: ${av.strongBuy || 0} · Buy: ${av.buy || 0} · Hold: ${av.hold || 0} · Sell: ${av.sell || 0} · Strong Sell: ${av.strongSell || 0}`;

  const sp = pct(data.sh_promoters);
  const sf = pct(data.sh_fii);
  const sd = pct(data.sh_dii);
  const su = pct(data.sh_public);
  $("sh-promoter-bar").style.width = sp + "%";
  $("sh-fii-bar").style.width = sf + "%";
  $("sh-dii-bar").style.width = sd + "%";
  $("sh-public-bar").style.width = su + "%";
  $("sh-promoter-lbl").textContent = `Promoters ${data.sh_promoters || "—"}`;
  $("sh-fii-lbl").textContent = `FII ${data.sh_fii || "—"}`;
  $("sh-dii-lbl").textContent = `MF/DII ${data.sh_dii || "—"}`;
  $("sh-public-lbl").textContent = `Other ${data.sh_public || "—"}`;

  const df = data.data_flags || [];
  const fs = $("flags-section");
  if (df.length && fs) {
    fs.hidden = false;
    $("flag-count").textContent = String(df.length);
    $("flags-list").innerHTML = df.map((f) => `<li>${escapeHtml(String(f))}</li>`).join("");
  } else if (fs) {
    fs.hidden = true;
  }

  if (flags.enableAnnouncements) {
    const annSection = $("ann-section");
    const anns = data.announcements || [];
    if (annSection) {
      if (anns.length) {
        annSection.hidden = false;
        $("ann-list").innerHTML = anns
          .map((a) => {
            const subj = stripHtmlToText(a.subject || "(no subject)") || "(no subject)";
            return `<div class="ann-item"><span>${escapeHtml(subj)}</span><span class="ann-item__date">${escapeHtml(a.date || "")}</span></div>`;
          })
          .join("");
      } else {
        annSection.hidden = true;
      }
    }
  }

  const news = data.news || [];
  const nl = $("news-list");
  if (nl) {
    if (news.length) {
      nl.innerHTML = news
        .map((n) => {
          const rawTitle = n.title || "(no title)";
          const titlePlain = stripHtmlToText(rawTitle) || "(no title)";
          const date = n.date || "";
          const url = n.url || n.link;
          const head = url
            ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(titlePlain)}</a>`
            : escapeHtml(titlePlain);
          return `<div class="news-item"><div>${head}</div><div class="date">${escapeHtml(date)}</div></div>`;
        })
        .join("");
    } else {
      nl.innerHTML = '<p class="muted" style="font-size:0.85rem">No recent news available.</p>';
    }
  }
}

function pct(s) {
  const n = parseFloat(String(s ?? "").replace("%", ""));
  return Number.isNaN(n) ? 0 : Math.min(Math.max(n, 0), 100);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** News titles from API sometimes include HTML (e.g. webrupee spans) — show plain text safely */
function stripHtmlToText(html) {
  if (html == null) return "";
  return String(html)
    .replace(/<[^>]*>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

async function loadPriceChartOnly() {
  const canvas = $("price-chart");
  const statusEl = $("chart-status");
  if (!canvas || !currentTicker) return;
  if (statusEl) statusEl.textContent = "Loading chart…";
  try {
    const d = await API.fetchHistory(currentTicker, currentPeriod);
    if (d.error) {
      if (statusEl) statusEl.textContent = d.error;
      return;
    }
    if (!d.data || !d.data.length) {
      if (statusEl) statusEl.textContent = "No price data";
      return;
    }
    renderPriceChart(canvas, d.data, currentPeriod);
    if (statusEl) statusEl.textContent = `${d.data.length} points · ${currentPeriod}`;
  } catch (e) {
    if (statusEl) statusEl.textContent = "Chart unavailable";
  }
}

async function loadPEChartOnly() {
  const flags = readFlags();
  if (!flags.enablePeHistory) return;
  const canvas = $("pe-chart");
  const statusEl = $("pe-chart-status");
  if (!canvas || !currentTicker) return;
  try {
    const d = await API.fetchPEHistory(currentTicker, "3yr");
    if (d.error || !d.data || !d.data.length) {
      if (statusEl) statusEl.textContent = "No PE data";
      return;
    }
    renderPEChart(canvas, d.data);
    const vals = d.data.map((x) => Number(x.pe));
    const min = Math.min(...vals).toFixed(1);
    const max = Math.max(...vals).toFixed(1);
    const cur = vals[vals.length - 1].toFixed(1);
    if (statusEl) statusEl.textContent = `Current PE: ${cur}x · 3Y range: ${min}x – ${max}x`;
  } catch (e) {
    if (statusEl) statusEl.textContent = "PE chart unavailable";
  }
}

async function analyse() {
  const input = $("ticker-input");
  const ticker = (input?.value || "").trim().toUpperCase();
  if (!ticker) {
    setStatus("Please enter a ticker symbol.", true);
    return;
  }

  const seq = ++analyseSeq;
  setBusy(true);
  setStatus(`Fetching market data for ${ticker}…`);

  const out = $("output");
  if (out) out.hidden = false;
  showKpiSkeleton(true);

  try {
    const data = await API.fetchStockData(ticker);
    if (seq !== analyseSeq) return;

    currentTicker = ticker;
    setStatus("Data loaded. Running AI analysis…");
    showKpiSkeleton(false);
    populateCards(data);

    showBriefSkeleton();

    const chartP = loadPriceChartOnly();
    const peP = loadPEChartOnly();

    const promptKey = $("prompt-select")?.value || "A_structured";
    await streamBrief(ticker, promptKey);

    await Promise.allSettled([chartP, peP]);

    if (seq === analyseSeq) {
      setStatus(`Analysis complete · ${new Date().toLocaleTimeString()}`);
    }
  } catch (e) {
    if (seq === analyseSeq) {
      setStatus(`Failed: ${e.message || e}`, true);
      showKpiSkeleton(false);
    }
  } finally {
    if (seq === analyseSeq) setBusy(false);
  }
}

function quickPick(ticker) {
  const input = $("ticker-input");
  if (input) input.value = ticker;
  analyse();
}

function switchTab(tab) {
  const flags = readFlags();
  const stockPanel = $("tab-stock");
  const marketPanel = $("tab-market");
  const btnStock = $("tab-btn-stock");
  const btnMarket = $("tab-btn-market");

  if (tab === "stock") {
    stockPanel?.classList.add("active");
    marketPanel?.classList.remove("active");
    btnStock?.classList.add("active");
    btnStock?.setAttribute("aria-selected", "true");
    btnMarket?.classList.remove("active");
    btnMarket?.setAttribute("aria-selected", "false");
  } else if (tab === "market" && flags.enableMarket) {
    stockPanel?.classList.remove("active");
    marketPanel?.classList.add("active");
    btnStock?.classList.remove("active");
    btnStock?.setAttribute("aria-selected", "false");
    btnMarket?.classList.add("active");
    btnMarket?.setAttribute("aria-selected", "true");

    if (!marketTabInitialized) {
      marketTabInitialized = true;
      loadFeed("trending", (t) => {
        switchTab("stock");
        const inp = $("ticker-input");
        if (inp) inp.value = t;
        analyse();
      });
      document.querySelectorAll(".feed-pill").forEach((p) => {
        p.classList.toggle("active", p.getAttribute("data-feed") === "trending");
      });
    }
  }
}

function wireMarketPills() {
  document.querySelectorAll(".feed-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const feed = pill.getAttribute("data-feed");
      document.querySelectorAll(".feed-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      loadFeed(feed, (t) => {
        switchTab("stock");
        const inp = $("ticker-input");
        if (inp) inp.value = t;
        analyse();
      });
    });
  });
}

function wirePeriodButtons() {
  document.querySelectorAll(".period-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const p = btn.getAttribute("data-period");
      if (!p) return;
      currentPeriod = p;
      document.querySelectorAll(".period-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      loadPriceChartOnly();
    });
  });
}

async function checkHealth() {
  const dot = $("health-dot");
  const label = $("health-label");
  try {
    const h = await API.fetchHealth();
    const ok = h && h.status === "ok";
    if (dot) {
      dot.classList.remove("health-dot--unknown", "health-dot--ok", "health-dot--down");
      dot.classList.add(ok ? "health-dot--ok" : "health-dot--down");
    }
    if (label) label.textContent = ok ? "API connected" : "API issue";
  } catch {
    if (dot) {
      dot.classList.remove("health-dot--unknown", "health-dot--ok");
      dot.classList.add("health-dot--down");
    }
    if (label) label.textContent = "API unreachable";
  }
}

function init() {
  configureMarked();
  $("analyse-btn")?.addEventListener("click", () => analyse());
  $("ticker-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") analyse();
  });
  $("ticker-input")?.addEventListener("input", (e) => {
    const t = e.target;
    const start = t.selectionStart;
    const end = t.selectionEnd;
    t.value = t.value.toUpperCase();
    if (start != null && end != null) t.setSelectionRange(start, end);
  });

  document.querySelectorAll(".quick-pick").forEach((b) => {
    b.addEventListener("click", () => quickPick(b.getAttribute("data-ticker") || ""));
  });

  $("tab-btn-stock")?.addEventListener("click", () => switchTab("stock"));
  $("tab-btn-market")?.addEventListener("click", () => switchTab("market"));

  wirePeriodButtons();
  wireMarketPills();
  checkHealth();

  window.analyse = analyse;
  window.quickPick = quickPick;
  window.switchTab = switchTab;
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
