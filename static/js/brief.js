/**
 * AI Research Brief — marked options, skeleton, streaming via api.js.
 */
import { API } from "./api.js";

export function configureMarked() {
  if (typeof marked !== "undefined" && marked.setOptions) {
    marked.setOptions({
      breaks: true,
      gfm: true,
      mangle: false,
      headerIds: false,
    });
  }
}

export function normalizeMarkdown(raw) {
  let t = String(raw).replace(/\r\n/g, "\n");
  t = t.replace(/^(#{1,6})([^\s#])/gm, "$1 $2");
  t = t.replace(/([^\n])(#{1,6}\s)/g, "$1\n\n$2");
  t = t.replace(/([^\n])(\*\*[^*]+\*\*)/g, "$1 $2");
  return t;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function toHtml(text) {
  const normalized = normalizeMarkdown(text);
  if (typeof marked !== "undefined" && typeof marked.parse === "function") {
    try {
      return marked.parse(normalized, { breaks: true, gfm: true });
    } catch {
      return `<p>${escapeHtml(normalized).replace(/\n/g, "<br>")}</p>`;
    }
  }
  return `<p>${escapeHtml(normalized).replace(/\n/g, "<br>")}</p>`;
}

const DISCLAIMER_HTML = `
  <p class="brief-disclaimer muted">
    For informational purposes only. Not investment advice.
    Data from indianapi.in · AI analysis may contain errors.
  </p>`;

export function showBriefSkeleton() {
  const box = document.getElementById("brief-box");
  if (!box) return;
  box.innerHTML = `
    <div class="brief-skeleton">
      <div class="sk-line sk-heading"></div>
      <div class="sk-line w-full"></div>
      <div class="sk-line w-3q"></div>
      <div class="sk-line w-full"></div>
      <div style="height:12px"></div>
      <div class="sk-line sk-heading"></div>
      <div class="sk-line w-full"></div>
      <div class="sk-line w-half"></div>
      <div style="height:12px"></div>
      <div class="sk-line sk-heading"></div>
      <div class="sk-line w-full"></div>
      <div class="sk-line w-3q"></div>
      <div class="sk-line w-2q"></div>
    </div>`;
}

/**
 * Stream AI brief into #brief-box. Resolves with final text when the stream completes.
 */
export function streamBrief(ticker, promptKey) {
  return new Promise((resolve, reject) => {
    const box = document.getElementById("brief-box");
    if (!box) {
      resolve("");
      return;
    }
    box.innerHTML = "";
    const cursor = document.createElement("span");
    cursor.id = "cursor-brief";
    cursor.setAttribute("aria-hidden", "true");
    box.appendChild(cursor);

    API.streamBrief(
      ticker,
      promptKey,
      (text) => {
        box.innerHTML = toHtml(text);
        box.appendChild(cursor);
      },
      (text) => {
        cursor.remove();
        box.innerHTML = toHtml(text) + DISCLAIMER_HTML;
        box.style.animation = "none";
        void box.offsetWidth;
        box.style.animation = "";
        resolve(text);
      },
      (err) => {
        cursor.remove();
        box.innerHTML = `<p class="muted">${escapeHtml(err.message || String(err))}</p>`;
        reject(err);
      }
    );
  });
}
