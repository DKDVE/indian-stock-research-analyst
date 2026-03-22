/**
 * Market Pulse — table rendering and feed loading.
 * Uses API only; DOM callbacks supplied by stock.js.
 */

import { API } from "./api.js";

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatVolume(v) {
  if (v == null || v === "") return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  if (n >= 1e7) return (n / 1e7).toFixed(1) + "Cr";
  if (n >= 1e5) return (n / 1e5).toFixed(1) + "L";
  return String(n);
}

/** Parse API percent change (handles strings, %, commas). */
function parsePctChange(raw) {
  if (raw == null || raw === "") return NaN;
  const n = parseFloat(String(raw).replace(/%/g, "").replace(/,/g, "").trim());
  return Number.isNaN(n) ? NaN : n;
}

/**
 * @param {Array} rows
 * @param {string} feed
 * @param {(ticker: string) => void} onRowPick
 */
function renderMarketTable(rows, feed, onRowPick) {
  const wrap = document.getElementById("market-table-wrap");
  if (!wrap) return;

  if (!rows || !rows.length) {
    wrap.innerHTML =
      '<p class="muted" style="font-size:0.85rem">No data available right now.</p>';
    return;
  }

  const isIPO = feed === "ipo";
  let html = '<table class="market-table"><thead><tr>';
  html += "<th>Ticker</th><th>Company</th><th>Price</th><th>Change %</th>";
  if (!isIPO) html += "<th>Volume</th>";
  html += "</tr></thead><tbody>";

  for (const row of rows) {
    const chg = parsePctChange(row.change);
    let chgClass = "market-chg--flat";
    if (!Number.isNaN(chg)) {
      if (chg > 0) chgClass = "market-chg--up";
      else if (chg < 0) chgClass = "market-chg--down";
    }
    const chgSign = Number.isNaN(chg) ? "" : chg > 0 ? "+" : "";
    const chgStr = Number.isNaN(chg)
      ? escapeHtml(String(row.change ?? "—"))
      : `${chg.toFixed(2)}%`;
    const priceStr = row.price
      ? Number(row.price).toLocaleString("en-IN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        })
      : "—";
    const volStr = !isIPO ? formatVolume(row.volume) : "";
    const t = escapeHtml(row.ticker || "");
    html += `<tr data-ticker="${t}">`;
    html += `<td class="ticker-cell">${escapeHtml(row.ticker || "—")}</td>`;
    html += `<td>${escapeHtml(row.company || "—")}</td>`;
    html += `<td>₹${priceStr}</td>`;
    html += `<td class="${chgClass}">${chgSign}${chgStr}</td>`;
    if (!isIPO) html += `<td class="muted">${volStr}</td>`;
    html += "</tr>";
  }
  html += "</tbody></table>";
  wrap.innerHTML = html;

  wrap.querySelectorAll("tr[data-ticker]").forEach((tr) => {
    tr.addEventListener("click", () => {
      const ticker = tr.getAttribute("data-ticker");
      if (ticker && onRowPick) onRowPick(ticker);
    });
  });
}

function showMarketSkeleton() {
  const wrap = document.getElementById("market-table-wrap");
  if (!wrap) return;
  let html = '<table class="market-table"><thead><tr>';
  html += "<th>Ticker</th><th>Company</th><th>Price</th><th>Change %</th><th>Volume</th>";
  html += "</tr></thead><tbody>";
  for (let i = 0; i < 3; i++) {
    html += '<tr class="market-skeleton-row">';
    for (let j = 0; j < 5; j++) {
      html += '<td><div class="skeleton market-skeleton-bar"></div></td>';
    }
    html += "</tr>";
  }
  html += "</tbody></table>";
  wrap.innerHTML = html;
}

/**
 * @param {string} feed
 * @param {(ticker: string) => void} onRowPick
 */
async function loadFeed(feed, onRowPick) {
  const statusEl = document.getElementById("market-status");
  const updatedEl = document.getElementById("market-updated");
  if (statusEl) statusEl.textContent = "Loading…";
  showMarketSkeleton();

  try {
    const d = await API.fetchMarket(feed);
    if (d.error) {
      if (statusEl) statusEl.textContent = d.error;
      const wrap = document.getElementById("market-table-wrap");
      if (wrap) wrap.innerHTML = "";
      return;
    }
    renderMarketTable(d.data, feed, onRowPick);
    if (statusEl) statusEl.textContent = `${d.data.length} stocks`;
    if (updatedEl) {
      updatedEl.textContent = `Last updated · ${new Date().toLocaleString()}`;
    }
  } catch (e) {
    if (statusEl) statusEl.textContent = "Feed unavailable";
    const wrap = document.getElementById("market-table-wrap");
    if (wrap) wrap.innerHTML = '<p class="muted">Could not load feed.</p>';
  }
}

export { loadFeed, renderMarketTable };
