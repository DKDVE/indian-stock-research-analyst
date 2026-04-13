/**
 * Morning digest page — POST /api/digest and render cards.
 */

function $(id) {
  return document.getElementById(id);
}

function parseTickers(raw) {
  return raw
    .split(",")
    .map((t) => t.trim().toUpperCase())
    .filter(Boolean);
}

function stanceClass(stance) {
  const s = (stance || "neutral").toLowerCase();
  if (s === "bullish") return "stance-bullish";
  if (s === "bearish") return "stance-bearish";
  if (s === "caution") return "stance-caution";
  return "stance-neutral";
}

function renderCard(item) {
  const st = stanceClass(item.stance);
  const href = `/?ticker=${encodeURIComponent(item.ticker)}`;
  return `
    <a class="digest-card" href="${href}">
      <div class="digest-card__ticker">${escapeHtml(item.ticker)} <span class="${st}">· ${escapeHtml(item.stance || "neutral")}</span></div>
      <div class="digest-card__co">${escapeHtml(item.company || "")}</div>
      <div class="digest-card__verdict ${st}">${escapeHtml(item.verdict || "—")}</div>
      <p class="digest-card__why">${escapeHtml(item.one_liner || "")}</p>
      <p class="digest-card__why">${escapeHtml(item.why_today || "")}</p>
      <div class="digest-card__px">₹${escapeHtml(String(item.price || "—"))} · ${escapeHtml(String(item.change || "0"))}%</div>
      <span class="digest-card__link">Open full analysis →</span>
    </a>
  `;
}

function renderMuted(ticker) {
  return `
    <div class="digest-card digest-card--muted">
      <div class="digest-card__ticker">${escapeHtml(ticker)}</div>
      <div class="digest-card__co">Data unavailable</div>
      <p class="digest-card__why">Could not load this symbol. Check the ticker or try again later.</p>
    </div>
  `;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function loadDigest(tickers) {
  const grid = $("digest-grid");
  const sk = $("digest-skeleton");
  const errEl = $("digest-error");
  const failedEl = $("digest-failed");
  const sub = $("digest-subline");
  const updated = $("digest-updated");

  if (!grid) return;

  errEl.hidden = true;
  failedEl.hidden = true;
  grid.innerHTML = "";
  sk.hidden = false;

  try {
    const resp = await fetch("/api/digest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tickers }),
    });
    const data = await resp.json();
    if (!resp.ok) {
      throw new Error(data.error || resp.statusText);
    }

    sk.hidden = true;

    const list = data.digest || [];
    const failed = data.failed || [];
    grid.innerHTML = list.map(renderCard).join("");
    for (const t of failed) {
      grid.insertAdjacentHTML("beforeend", renderMuted(t));
    }

    const today = data.date || "";
    if (sub) {
      sub.textContent = `${today} · watchlist analysis (${list.length} loaded)`;
    }
    if (updated) {
      updated.textContent = `Last updated: ${today}`;
    }
    if (failed.length && failedEl) {
      failedEl.hidden = false;
      failedEl.textContent = `Unavailable: ${failed.join(", ")}`;
    }
  } catch (e) {
    sk.hidden = true;
    errEl.hidden = false;
    errEl.textContent = e.message || String(e);
  }
}

function init() {
  const inp = $("watchlist-input");
  const btn = $("refresh-digest");

  const run = () => {
    const tickers = parseTickers(inp?.value || "");
    if (!tickers.length) {
      const errEl = $("digest-error");
      if (errEl) {
        errEl.hidden = false;
        errEl.textContent = "Enter at least one ticker.";
      }
      return;
    }
    loadDigest(tickers);
  };

  btn?.addEventListener("click", run);
  run();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
