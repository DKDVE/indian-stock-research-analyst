/**
 * API layer — fetch/SSE only, no DOM.
 */

const API = {
  async fetchStockData(ticker) {
    const r = await fetch(`/api/data?ticker=${encodeURIComponent(ticker)}`);
    let data = {};
    try {
      data = await r.json();
    } catch {
      throw new Error(r.statusText || "Invalid response");
    }
    if (!r.ok || data.error) {
      const err = new Error(data.error || r.statusText || "Request failed");
      err.payload = data;
      throw err;
    }
    return data;
  },

  /**
   * SSE: chunks are `data: ...` lines; ⏎ → newline; ends with `data: [DONE]`.
   */
  streamBrief(ticker, prompt, onChunk, onDone, onError) {
    const url = `/api/brief?ticker=${encodeURIComponent(ticker)}&prompt=${encodeURIComponent(prompt)}`;
    fetch(url)
      .then(async (resp) => {
        if (!resp.ok) {
          onError(new Error(resp.statusText || "Brief request failed"));
          return;
        }
        const reader = resp.body.getReader();
        const dec = new TextDecoder();
        let buffer = "";
        let text = "";
        try {
          while (true) {
            const { done, value } = await reader.read();
            buffer += dec.decode(value || new Uint8Array(), { stream: !done });
            let idx;
            while ((idx = buffer.indexOf("\n")) >= 0) {
              const line = buffer.slice(0, idx).replace(/\r$/, "");
              buffer = buffer.slice(idx + 1);
              if (!line.startsWith("data: ")) continue;
              const payload = line.slice(6).trim();
              if (payload === "[DONE]") {
                onDone(text);
                return;
              }
              text += payload.replace(/⏎/g, "\n");
              onChunk(text);
            }
            if (done) break;
          }
          if (buffer.trim()) {
            const line = buffer.replace(/\r$/, "");
            if (line.startsWith("data: ")) {
              const payload = line.slice(6).trim();
              if (payload !== "[DONE]") {
                text += payload.replace(/⏎/g, "\n");
                onChunk(text);
              }
            }
          }
          onDone(text);
        } catch (e) {
          onError(e);
        }
      })
      .catch(onError);
  },

  async fetchHistory(ticker, period) {
    const r = await fetch(
      `/api/history?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}`
    );
    return r.json();
  },

  async fetchPEHistory(ticker, period) {
    const r = await fetch(
      `/api/pe_history?ticker=${encodeURIComponent(ticker)}&period=${encodeURIComponent(period)}`
    );
    return r.json();
  },

  async fetchMarket(feed) {
    const r = await fetch(`/api/market?feed=${encodeURIComponent(feed)}`);
    return r.json();
  },

  async fetchHealth() {
    const r = await fetch("/health");
    return r.json();
  },
};

export { API };
