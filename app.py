<<<<<<< HEAD
PLACEHOLDER_APP
=======
"""
Indian Stock Research Analyst — Web App
========================================
Run:  python app.py
Open: http://localhost:5000

The non-tech user only needs to open the browser link.
You (the technical person) run this once on your machine / server.
"""

import os
import sys
import json
import threading
from dotenv import load_dotenv
from flask import Flask, request, jsonify, Response, stream_with_context, render_template
from datetime import datetime

load_dotenv()

# ── pull in all logic from the research_agent script ──────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from research_agent import (
    fetch_stock_data,
    fetch_historical_data,
    fetch_pe_history,
    fetch_statements,
    fetch_announcements,
    fetch_eps_forecasts,
    fetch_stock_target_price,
    fetch_market_feed,
    build_structured_summary,
    format_full_summary,
    run_llm,
    PROMPTS,
    SYSTEM_PROMPT,
    VALIDATION_TICKERS,
    LLM_MODEL,
    LLM_PROVIDER,
    ANTHROPIC_KEY,
    OPENROUTER_KEY,
    _news_title,
    _news_date,
    _mock_historical,
    _mock_market_feed,
    _safe_int,
    _financials_get,
    _peers_extract,
    is_indianapi_configured,
)

app = Flask(__name__)


@app.context_processor
def inject_flags():
    return {
        "ENABLE_MARKET_DASHBOARD": os.environ.get("ENABLE_MARKET_DASHBOARD", "true") == "true",
        "ENABLE_PE_HISTORY": os.environ.get("ENABLE_PE_HISTORY", "true") == "true",
        "ENABLE_ANNOUNCEMENTS": os.environ.get("ENABLE_ANNOUNCEMENTS", "true") == "true",
    }


# ── in-memory cache (one slot — good enough for validation) ───────────────────
_cache = {}
_cache_lock = threading.Lock()


# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    """
    Fetch primary stock data + kick off parallel supplementary calls.
    Supplementary data (history, announcements, target price) is fetched
    concurrently via threads to keep total latency low.
    """
    ticker = request.args.get("ticker", "").upper().strip()
    if not ticker:
        return jsonify({"error": "ticker is required"}), 400

    # ── step 1: primary fetch (blocking) ────────────────────────────────────
    raw, err = fetch_stock_data(ticker)
    if err:
        return jsonify({"error": err}), 502

    # ── step 2: parallel supplementary fetches ───────────────────────────────
    import concurrent.futures as _cf
    supp = {"announcements": None, "statements": None, "target": None}

    def _fetch_ann():
        return fetch_announcements(raw.get("companyName", ticker) or ticker)

    def _fetch_stmt():
        return fetch_statements(raw.get("companyName", ticker) or ticker)

    def _fetch_target():
        return fetch_stock_target_price(raw.get("tickerId", ticker) or ticker)

    def _fetch_eps():
        return fetch_eps_forecasts(raw.get("tickerId", ticker) or ticker)

    with _cf.ThreadPoolExecutor(max_workers=4) as ex:
        fut_ann    = ex.submit(_fetch_ann)
        fut_stmt   = ex.submit(_fetch_stmt)
        fut_target = ex.submit(_fetch_target)
        fut_eps    = ex.submit(_fetch_eps)
        for key, fut in [("announcements", fut_ann), ("statements", fut_stmt),
                          ("target", fut_target), ("eps", fut_eps)]:
            try:
                supp[key] = fut.result(timeout=10)
            except Exception:
                pass

    # inject supplementary data into raw so build_structured_summary can use it
    if supp.get("announcements"):
        raw["_announcements"] = supp["announcements"]
    if supp.get("statements"):
        raw["_statements"] = supp["statements"]
    if supp.get("eps"):
        raw["_eps_forecasts"] = supp["eps"]

    # ── step 3: build structured summary for LLM ────────────────────────────
    sections = build_structured_summary(raw, ticker)
    with _cache_lock:
        _cache[ticker] = format_full_summary(sections)

    # ── step 4: build JSON payload for the frontend cards ────────────────────
    from research_agent import (_km_get, _sh_get, _av_get, _news_title, _news_date,
                                  _normalise as _n)

    km  = raw.get("keyMetrics") or {}
    fin_raw = raw.get("financials") or raw.get("stockFinancialData") or []
    sdr = raw.get("stockDetailsReusableData") or {}
    sh_raw = raw.get("shareholding") or []
    av_raw = raw.get("analystView") or []
    rb_raw = raw.get("recosBar") or {}
    rb_analysts = rb_raw.get("stockAnalyst") or []
    news_raw = raw.get("recentNews") or []
    if not isinstance(news_raw, list): news_raw = []

    # currentPrice
    cp = raw.get("currentPrice", {})
    if isinstance(cp, dict):
        price_nse = cp.get("NSE") or cp.get("nse")
        price_bse = cp.get("BSE") or cp.get("bse")
    else:
        price_nse = price_bse = cp

    # PE, PB, MarketCap, ROE, DivYield from keyMetrics sections
    pe  = (_km_get(km,
                "pPerEBasicExcludingExtraordinaryItemsTTM",
                "pPerEExcludingExtraordinaryItemsMostRecentFiscalYear") or
           str(sdr.get("pPerEBasicExcludingExtraordinaryItemsTTM") or ""))
    pb  = _km_get(km, "priceToBookMostRecentFiscalYear",
                       "priceToBookValueMostRecentQuarter")
    eps = (
        _financials_get(fin_raw, "DilutedNormalizedEPS", "Annual") or
        _financials_get(fin_raw, "DilutedEPSExcludingExtraOrdItems", "Annual") or
        _km_get(km, "earningsPerShareTrailing12Months",
                "basicEPSTrailing12Month", "dilutedEPSTrailing12Month")
    )
    mcap = (_km_get(km, "marketCap") or
             str(sdr.get("marketCap") or ""))
    roe = _km_get(km, "returnOnAverageEquity5YearAverage",
                       "returnOnAverageEquityTrailing12Month")
    div = _km_get(km, "currentDividendYieldCommonStockPrimaryIssueLTM")

    # moving averages (stockTechnicalData = [{days, nsePrice}])
    tech_raw = raw.get("stockTechnicalData") or []
    ma_map = {}
    if isinstance(tech_raw, list):
        for entry in tech_raw:
            if isinstance(entry, dict) and "days" in entry:
                ma_map[int(entry["days"])] = entry.get("nsePrice") or entry.get("bsePrice")
    sma50_val  = ma_map.get(50,  ma_map.get(20))
    sma200_val = ma_map.get(300, ma_map.get(100))
    overall_trend = str(sdr.get("averageRating") or "N/A")

    # shareholding — latest % per category
    sh_promoters = _sh_get(sh_raw, "Promoter")
    sh_fii       = _sh_get(sh_raw, "FII")
    sh_dii       = _sh_get(sh_raw, "MF") or _sh_get(sh_raw, "DII")
    sh_public    = _sh_get(sh_raw, "Other") or _sh_get(sh_raw, "Public")

    # analystView — count per rating (API may return "0.00" strings)
    analyst_view = {
        "strongBuy":  _safe_int(_av_get(av_raw, "Strong Buy")),
        "buy":        _safe_int(_av_get(av_raw, "Buy")),
        "hold":       _safe_int(_av_get(av_raw, "Hold")),
        "sell":       _safe_int(_av_get(av_raw, "Sell")),
        "strongSell": _safe_int(_av_get(av_raw, "Strong Sell")),
    }

    # recosBar %
    rb_total = sum(_safe_int(a.get("numberOfAnalysts")) for a in rb_analysts if isinstance(a, dict))
    recos_buy = recos_hold = recos_sell = None
    if rb_total > 0:
        rb_b = sum(_safe_int(a.get("numberOfAnalysts")) for a in rb_analysts
                   if isinstance(a, dict) and a.get("ratingValue") in (1,2))
        rb_h = sum(_safe_int(a.get("numberOfAnalysts")) for a in rb_analysts
                   if isinstance(a, dict) and a.get("ratingValue") == 3)
        rb_s = sum(_safe_int(a.get("numberOfAnalysts")) for a in rb_analysts
                   if isinstance(a, dict) and a.get("ratingValue") in (4,5))
        recos_buy  = round(rb_b/rb_total*100)
        recos_hold = round(rb_h/rb_total*100)
        recos_sell = round(rb_s/rb_total*100)

    # riskMeter
    rm_raw = raw.get("riskMeter") or {}
    risk_level = rm_raw.get("categoryName")
    risk_score = rm_raw.get("stdDev")

    # target price
    target_data = supp.get("target") or {}
    price_target = None
    if isinstance(target_data, dict):
        pt = target_data.get("priceTarget") or {}
        if isinstance(pt, dict):
            price_target = pt.get("Mean") or pt.get("UnverifiedMean")

    # announcements
    anns = supp.get("announcements") or []
    ann_list = [
        {
            "date":    a.get("date", ""),
            "subject": (a.get("subject") or a.get("headline") or
                        a.get("description", ""))[:100],
        }
        for a in (anns if isinstance(anns, list) else [])[:5]
        if isinstance(a, dict)
    ]

    # company profile desc
    cp_block = raw.get("companyProfile") or {}
    company_desc = cp_block.get("companyDescription") if isinstance(cp_block, dict) else None

    payload = {
        "ticker":         ticker,
        "company_name":   raw.get("companyName") or f"{ticker}",
        "sector":         raw.get("industry") or "—",
        "price_nse":      price_nse,
        "price_bse":      price_bse,
        "percent_change": raw.get("percentChange"),
        "year_high":      raw.get("yearHigh"),
        "year_low":       raw.get("yearLow"),
        "data_date":      datetime.now().strftime("%d %b %Y"),
        "pe":             pe  or None,
        "pb":             pb  or None,
        "eps":            eps or None,
        "market_cap":     mcap or None,
        "roe":            roe or None,
        "div_yield":      div or None,
        "rsi":            None,   # not in /stock endpoint
        "overall_trend":  overall_trend,
        "sma50":          sma50_val,
        "sma200":         sma200_val,
        "sh_promoters":   sh_promoters,
        "sh_fii":         sh_fii,
        "sh_dii":         sh_dii,
        "sh_public":      sh_public,
        "analyst_view":   analyst_view,
        "data_flags":     sections["data_flags"],
        "news": [
            {"title": _news_title(n), "date": _news_date(n)}
            for n in news_raw[:6] if isinstance(n, dict)
        ],
        "risk_level":     risk_level,
        "risk_score":     risk_score,
        "recos_buy":      recos_buy,
        "recos_hold":     recos_hold,
        "recos_sell":     recos_sell,
        "revenue":        (
            _financials_get(fin_raw, "TotalRevenue", "Annual") or
            _km_get(km, "revenueTrailing12Month)", "revenueTrailing12Month")
        ),
        "net_profit":     (
            _financials_get(fin_raw, "NetIncome", "Annual") or
            _km_get(km, "netIncomeAvailableToCommonTrailing12Months")
        ),
        "company_desc":   company_desc,
        "price_target":   price_target,
        "announcements":  ann_list,
        "peers":          _peers_extract(raw.get("companyProfile") or {}),
    }
    return jsonify(payload)


@app.route("/api/history")
def api_history():
    """
    Return price history for Chart.js.
    Falls back to mock data when no API key or real data unavailable.
    """
    ticker = request.args.get("ticker", "").upper().strip()
    period = request.args.get("period", "1yr")
    if not ticker:
        return jsonify({"error": "ticker required"}), 400

    if not is_indianapi_configured():
        rows = _mock_historical(ticker)
    else:
        rows = fetch_historical_data(ticker, period)
        if not rows:
            rows = _mock_historical(ticker)

    # normalise field names — API may use different casing
    cleaned = []
    for row in (rows or []):
        if not isinstance(row, dict):
            continue
        d = (row.get("date") or row.get("Date") or row.get("timestamp") or "")
        c = (row.get("close") or row.get("Close") or
             row.get("price") or row.get("Price") or 0)
        try:
            c = float(str(c).replace(",", ""))
        except (ValueError, TypeError):
            c = 0
        if d and c:
            cleaned.append({"date": str(d).split("T")[0], "close": round(c, 2)})

    return jsonify({"ticker": ticker, "period": period, "data": cleaned[-252:]})


@app.route("/api/brief")
def api_brief():
    """Stream the LLM brief using the cached structured summary."""
    ticker = request.args.get("ticker", "").upper().strip()
    prompt_key = request.args.get("prompt", "A_structured")

    if prompt_key not in PROMPTS:
        prompt_key = "A_structured"

    with _cache_lock:
        summary = _cache.get(ticker)

    if not summary:
        # fallback: re-fetch if cache miss (e.g. page reload)
        raw, err = fetch_stock_data(ticker)
        if err:
            def err_stream():
                yield "data: Error fetching data.\n\ndata: [DONE]\n\n"
            return Response(stream_with_context(err_stream()), mimetype="text/event-stream")
        sections = build_structured_summary(raw, ticker)
        summary = format_full_summary(sections)

    prompt_template, _ = PROMPTS[prompt_key]
    prompt_text = prompt_template.format(summary=summary, ticker=ticker)

    def generate():
        # ── route to the right LLM provider ──────────────────────────────────
        if LLM_PROVIDER == "openrouter":
            yield from _stream_openrouter(prompt_text)
        else:
            yield from _stream_anthropic(prompt_text)

    def _stream_openrouter(prompt_text):
        """Stream via OpenRouter — supports 200+ models including free ones."""
        if OPENROUTER_KEY == "YOUR_OPENROUTER_KEY_HERE":
            msg = (
                "⚠ OPENROUTER_KEY not set.⏎⏎"
                "Get a free key at openrouter.ai — no credit card needed.⏎"
                "Then: export OPENROUTER_KEY=\'sk-or-...\' and restart."
            )
            yield f"data: {msg}\n\ndata: [DONE]\n\n"
            return

        import requests as _req, json as _json
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt_text},
        ]
        try:
            resp = _req.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type":  "application/json",
                    "HTTP-Referer":  "http://localhost:5000",
                    "X-Title":       "Indian Stock Research Analyst",
                },
                json={
                    "model":  LLM_MODEL,
                    "messages": messages,
                    "stream": True,
                    "max_tokens": 1800,
                },
                stream=True,
                timeout=60,
            )
            if resp.status_code != 200:
                body = resp.text[:300]
                msg = f"⚠ OpenRouter error {resp.status_code}: {body}"
                yield f"data: {msg}\n\ndata: [DONE]\n\n"
                return

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data: "):
                    continue
                payload = line[6:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = _json.loads(payload)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    text  = delta.get("content", "")
                    if text:
                        safe = text.replace("\n", "⏎")
                        yield f"data: {safe}\n\n"
                except (_json.JSONDecodeError, IndexError, KeyError):
                    continue

        except _req.exceptions.Timeout:
            yield f"data: ⚠ OpenRouter request timed out. Try again.\n\ndata: [DONE]\n\n"
            return
        except Exception as e:
            yield f"data: ⚠ OpenRouter error: {type(e).__name__}: {str(e)[:200]}\n\ndata: [DONE]\n\n"
            return

        yield "data: [DONE]\n\n"

    def _stream_anthropic(prompt_text):
        """Stream via Anthropic SDK."""
        if ANTHROPIC_KEY == "YOUR_ANTHROPIC_KEY_HERE":
            msg = "⚠ ANTHROPIC_KEY not set. Set LLM_PROVIDER=openrouter to use free models."
            yield f"data: {msg}\n\ndata: [DONE]\n\n"
            return
        import anthropic as _anthropic
        client = _anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        try:
            with client.messages.stream(
                model=LLM_MODEL,
                max_tokens=1800,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt_text}],
            ) as stream:
                for text_chunk in stream.text_stream:
                    safe = text_chunk.replace("\n", "⏎")
                    yield f"data: {safe}\n\n"
        except _anthropic.BadRequestError as e:
            err_str = str(e)
            if "credit balance" in err_str.lower() or "too low" in err_str.lower():
                msg = ("⚠ Anthropic credits too low.⏎⏎"
                       "Switch to free OpenRouter:⏎"
                       "  export LLM_PROVIDER=openrouter⏎"
                       "  export OPENROUTER_KEY=sk-or-...⏎"
                       "  python3 app.py⏎⏎"
                       "Get free key at openrouter.ai")
            else:
                msg = f"⚠ Anthropic error: {err_str[:200]}"
            yield f"data: {msg}\n\ndata: [DONE]\n\n"
            return
        except Exception as e:
            yield f"data: ⚠ {type(e).__name__}: {str(e)[:200]}\n\ndata: [DONE]\n\n"
            return
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@app.route("/api/pe_history")
def api_pe_history():
    """PE ratio history for valuation context chart."""
    ticker = request.args.get("ticker", "").upper().strip()
    period = request.args.get("period", "3yr")
    if not ticker:
        return jsonify({"error": "ticker required"}), 400

    rows = fetch_pe_history(ticker, period)
    if not rows:
        # mock PE history around a typical value for the ticker
        import random, math
        random.seed(hash(ticker) % 999)
        from datetime import datetime as _dt, timedelta as _td
        base_pe = random.uniform(15, 45)
        mock_rows = []
        d = _dt.now() - _td(days=3*365)
        for i in range(156):  # ~3 years weekly
            pe = base_pe + math.sin(i / 12) * 4 + random.uniform(-2, 2)
            mock_rows.append({"date": d.strftime("%Y-%m-%d"), "pe": round(max(pe, 5), 1)})
            d += _td(days=7)
        rows = mock_rows

    return jsonify({"ticker": ticker, "period": period, "data": rows})


@app.route("/api/market")
def api_market():
    """
    Market-wide feeds for the dashboard tab.
    feed: trending | most_active | price_shockers | ipo
    """
    feed = request.args.get("feed", "trending")
    endpoint_map = {
        "trending":      "/trending",
        "most_active":   "/NSE_most_active",
        "shockers":      "/price_shockers",
        "ipo":           "/ipo",
        "52w":           "/fetch_52_week_high_low_data",
    }
    endpoint = endpoint_map.get(feed, "/trending")
    data = fetch_market_feed(endpoint)
    if not data:
        data = _mock_market_feed(feed)

    # normalise to consistent shape for the frontend
    normalised = []
    for item in (data or [])[:15]:
        if not isinstance(item, dict):
            continue
        # handle both "ticker" and "ticker_id" field names
        ticker_val = (item.get("ticker") or item.get("ticker_id") or
                      item.get("ric") or "")
        price_val  = item.get("price") or item.get("lastPrice") or 0
        chg_val    = item.get("percent_change") or item.get("percentChange") or 0
        try:
            price_val = float(str(price_val).replace(",", ""))
            chg_val   = float(str(chg_val).replace(",", "").replace("%", ""))
        except (ValueError, TypeError):
            price_val = chg_val = 0
        normalised.append({
            "ticker":  str(ticker_val).replace(".NS", "").replace(".BO", ""),
            "company": item.get("company_name") or item.get("company") or ticker_val,
            "price":   round(price_val, 2),
            "change":  round(chg_val, 2),
            "volume":  item.get("volume") or 0,
            "high":    item.get("year_high") or item.get("high") or 0,
            "low":     item.get("year_low")  or item.get("low")  or 0,
        })
    return jsonify({"feed": feed, "data": normalised})


@app.route("/api/debug_fields")
def debug_fields():
    """
    Shows EXACT field names and sample values from the live indianapi.in response.
    Use this to diagnose N/A issues.
    Visit: http://localhost:5000/api/debug_fields?ticker=RELIANCE
    """
    ticker = request.args.get("ticker", "RELIANCE").upper().strip()
    raw, err = fetch_stock_data(ticker)
    if err:
        return jsonify({"error": err}), 502

    def describe_block(block, depth=0):
        if isinstance(block, list):
            if block and isinstance(block[0], dict):
                return {"_type": f"list[{len(block)}]", "_first": describe_block(block[0], depth)}
            return {"_type": f"list[{len(block)}]", "_sample": str(block[:2])[:200]}
        if isinstance(block, dict):
            return {
                k: (str(v)[:80] if not isinstance(v, (dict, list))
                    else describe_block(v, depth+1))
                for k, v in block.items()
            } if depth < 3 else f"{{...{len(block)} keys}}"
        return str(block)[:80] if block is not None else None

    # Show the key blocks that are currently N/A
    blocks_of_interest = [
        "keyMetrics", "stockTechnicalData", "shareholding",
        "analystView", "financials", "recosBar", "riskMeter",
        "currentPrice", "companyProfile",
    ]
    result = {"ticker": ticker, "blocks": {}}
    for block in blocks_of_interest:
        val = raw.get(block)
        if val is None:
            result["blocks"][block] = "MISSING — key not in response"
        else:
            result["blocks"][block] = describe_block(val)

    result["all_top_level_keys"] = list(raw.keys())
    return jsonify(result)


@app.route("/health")
def health():
    return jsonify({
        "status":             "ok",
        "llm_provider":       LLM_PROVIDER,
        "llm_model":          LLM_MODEL,
        "indianapi_key_set":  is_indianapi_configured(),
        "openrouter_key_set": OPENROUTER_KEY   != "YOUR_OPENROUTER_KEY_HERE",
    })

@app.route("/api/debug_raw")
def debug_raw():
    """Return the raw indianapi.in response — helps diagnose field name issues."""
    ticker = request.args.get("ticker", "RELIANCE").upper().strip()
    raw, err = fetch_stock_data(ticker)
    if err:
        return jsonify({"error": err}), 502
    # show top-level structure with types
    structure = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            structure[k] = {sk: type(sv).__name__ for sk, sv in v.items()}
        elif isinstance(v, list) and v:
            first = v[0]
            if isinstance(first, dict):
                structure[k] = f"[list of {len(v)} dicts, keys: {list(first.keys())}]"
            else:
                structure[k] = f"[list of {len(v)} {type(first).__name__}]"
        else:
            structure[k] = f"{type(v).__name__}: {str(v)[:80]}"
    return jsonify({"ticker": ticker, "raw_structure": structure, "raw": raw})


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"""
╔══════════════════════════════════════════════════════╗
║     Indian Stock Research Analyst — Web App          ║
╠══════════════════════════════════════════════════════╣
║  Open in browser → http://localhost:{port}            ║
║  Health check    → http://localhost:{port}/health     ║
║                                                      ║
║  indianapi.in key : {'SET ✓' if is_indianapi_configured() else 'NOT SET — mock data mode'}
║  LLM provider     : {LLM_PROVIDER} / {LLM_MODEL}
║  Anthropic key    : {'SET ✓' if ANTHROPIC_KEY != 'YOUR_ANTHROPIC_KEY_HERE' else 'not set'}
║  OpenRouter key   : {'SET ✓' if OPENROUTER_KEY != 'YOUR_OPENROUTER_KEY_HERE' else 'not set'}
╚══════════════════════════════════════════════════════╝
""")
    app.run(debug=False, host="0.0.0.0", port=port, threaded=True)
>>>>>>> 3313016 (Add Flask Indian stock research app for Render deployment)
