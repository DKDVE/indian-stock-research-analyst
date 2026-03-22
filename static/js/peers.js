/**
 * Peer comparison table — data from /api/data `peers`.
 */

function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function ratingClass(rating) {
  if (!rating) return "rating-neutral";
  const r = String(rating).toLowerCase();
  if (r.includes("bullish") || r.includes("buy")) return "rating-bullish";
  if (r.includes("bearish") || r.includes("sell")) return "rating-bearish";
  return "rating-neutral";
}

/**
 * @param {Array} peers — [{ name, pe, pb, roe, mcap_cr, price, change, rating }]
 * @param {string|number} subjectPE — current stock P/E for relative colouring
 */
export function renderPeers(peers, _subjectName, subjectPE) {
  const section = document.getElementById("peers-section");
  const body = document.getElementById("peers-body");
  const count = document.getElementById("peers-count");

  if (!section || !body) return;

  if (!peers || !peers.length) {
    section.hidden = true;
    return;
  }

  section.hidden = false;
  if (count) count.textContent = `${peers.length} peers`;

  const subPE = parseFloat(subjectPE);

  body.innerHTML = peers
    .map((p) => {
      const pe = p.pe != null ? parseFloat(p.pe) : NaN;
      const pb = p.pb != null ? parseFloat(p.pb) : NaN;
      const roe = p.roe != null ? parseFloat(p.roe) : NaN;
      const chg = p.change != null ? parseFloat(p.change) : NaN;

      let peColour = "";
      if (!Number.isNaN(pe) && !Number.isNaN(subPE)) {
        if (pe < subPE) peColour = "peers-up";
        else if (pe > subPE) peColour = "peers-down";
      }

      const chgStr = !Number.isNaN(chg)
        ? `<span class="${chg >= 0 ? "peers-up" : "peers-down"}">${chg >= 0 ? "+" : ""}${chg.toFixed(2)}%</span>`
        : "—";
      const peStr = !Number.isNaN(pe)
        ? `<span class="${peColour}">${pe.toFixed(1)}x</span>`
        : '<span class="muted">N/A</span>';
      const pbStr = !Number.isNaN(pb) ? `${pb.toFixed(2)}x` : '<span class="muted">N/A</span>';
      const roeStr =
        !Number.isNaN(roe) && roe > 0 ? `${roe.toFixed(1)}%` : '<span class="muted">N/A</span>';
      const mcapStr = p.mcap_cr || "—";
      const priceStr =
        p.price != null && p.price !== ""
          ? `₹${parseFloat(p.price).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`
          : "—";
      const rc = ratingClass(p.rating);
      const ratingHtml = p.rating
        ? `<span class="rating-pill ${rc}">${escHtml(p.rating)}</span>`
        : "—";

      return `<tr>
        <td>${escHtml(p.name || "?")}</td>
        <td class="num">${peStr}</td>
        <td class="num">${pbStr}</td>
        <td class="num">${roeStr}</td>
        <td class="num muted">${escHtml(mcapStr)}</td>
        <td class="num">${priceStr}</td>
        <td class="num">${chgStr}</td>
        <td>${ratingHtml}</td>
      </tr>`;
    })
    .join("");
}
