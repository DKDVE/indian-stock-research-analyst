"""
Indian Stock Market Research Analyst Agent
==========================================
Usage:
    python research_agent.py RELIANCE              # single stock, default prompt
    python research_agent.py RELIANCE --compare    # run all 3 prompt styles, compare
    python research_agent.py --batch               # run all 8 validation tickers
    python research_agent.py RELIANCE --save       # save output to /outputs folder

Validation tickers: RELIANCE, HDFCBANK, ZOMATO, TATAMOTORS, INFY, ADANIPORTS, IRCTC, DMART
"""

import sys
import os
import re
import json
import time
import argparse
import requests
from datetime import datetime, timedelta
from typing import Optional
import anthropic
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
#  CONFIG — fill these in before running
# ─────────────────────────────────────────────


INDIANAPI_KEY    = os.environ.get("INDIANAPI_KEY", "YOUR_INDIANAPI_KEY_HERE")
ANTHROPIC_KEY    = os.environ.get("ANTHROPIC_KEY", "YOUR_ANTHROPIC_KEY_HERE")
OPENROUTER_KEY   = os.environ.get("OPENROUTER_KEY", "YOUR_OPENROUTER_KEY_HERE")

# ── LLM provider selection ────────────────────────────────────────────────────
# Set LLM_PROVIDER to "anthropic" or "openrouter"
# For OpenRouter free models use: "openrouter"
# Best free models on OpenRouter (no cost, just need a free account):
#   "deepseek/deepseek-r1-0528:free"           — strong reasoning, good for analysis
#   "google/gemini-2.0-flash-exp:free"          — fast, capable, Google
#   "meta-llama/llama-3.3-70b-instruct:free"   — excellent instruction following
#   "qwen/qwen3-8b:free"                        — fast, multilingual, good quality
LLM_PROVIDER   = os.environ.get("LLM_PROVIDER",  "openrouter")
LLM_MODEL      = os.environ.get("LLM_MODEL",     "stepfun/step-3.5-flash:free")
LLM_MAX_TOKENS = 1800

INDIANAPI_BASE = "https://stock.indianapi.in"

VALIDATION_TICKERS = [
    "RELIANCE",    # large cap, conglomerate — data should be complete
    "HDFCBANK",    # banking sector, high liquidity
    "ZOMATO",      # new-age tech, recent listing, may have data gaps
    "TATAMOTORS",  # auto sector, global exposure
    "INFY",        # IT sector, well-covered
    "ADANIPORTS",  # infrastructure, complex group structure
    "IRCTC",       # PSU, unique monopoly business
    "DMART",       # retail, private promoter-heavy
]

SECTORS_PE_BENCHMARKS = {
    "Technology": {"low": 20, "fair": 30, "high": 40},
    "Software & Programming": {"low": 20, "fair": 30, "high": 40},
    "Banking": {"low": 10, "fair": 16, "high": 25},
    "Financial Services": {"low": 12, "fair": 20, "high": 35},
    "Consumer Defensive": {"low": 30, "fair": 50, "high": 70},
    "Conglomerate": {"low": 15, "fair": 25, "high": 40},
    "Auto & Truck Manufacturers": {"low": 8, "fair": 15, "high": 25},
    "Retail": {"low": 50, "fair": 90, "high": 130},
    "Infrastructure": {"low": 15, "fair": 25, "high": 40},
    "Energy": {"low": 8, "fair": 14, "high": 22},
    "Default": {"low": 15, "fair": 25, "high": 40},
}


# ─────────────────────────────────────────────
#  DATA FETCHING
# ─────────────────────────────────────────────

INDIANAPI_BASE = "https://stock.indianapi.in"

# Ticker → search names for indianapi.in (Livemint-style name search, not raw symbols).
TICKER_NAME_MAP: dict[str, list[str]] = {
    "ZOMATO":        ["Zomato", "Eternal"],
    "TATAMOTORS":    ["Tata Motors", "TATA MOTORS"],
    "TATASTEEL":     ["Tata Steel", "TATA STEEL"],
    "BAJFINANCE":    ["Bajaj Finance", "BAJAJ FINANCE"],
    "BAJAJFINSV":    ["Bajaj Finserv", "BAJAJ FINSERV"],
    "AXISBANK":      ["Axis Bank", "AXIS BANK"],
    "KOTAKBANK":     ["Kotak Mahindra Bank", "Kotak Bank"],
    "MARUTI":        ["Maruti Suzuki", "MARUTI SUZUKI"],
    "ASIANPAINT":    ["Asian Paints", "ASIAN PAINTS"],
    "HINDUNILVR":    ["Hindustan Unilever", "HUL"],
    "BHARTIARTL":    ["Bharti Airtel", "Airtel"],
    "ADANIPORTS":    ["Adani Ports", "ADANI PORTS"],
    "ADANIENT":      ["Adani Enterprises", "ADANI ENTERPRISES"],
    "ADANIGREEN":    ["Adani Green Energy", "ADANI GREEN"],
    "ADANIPOWER":    ["Adani Power", "ADANI POWER"],
    "WIPRO":         ["Wipro"],
    "LTIM":          ["LTIMindtree", "LTI Mindtree"],
    "HCLTECH":       ["HCL Technologies", "HCL Tech"],
    "TECHM":         ["Tech Mahindra", "TECH MAHINDRA"],
    "SUNPHARMA":     ["Sun Pharma", "SUN PHARMA"],
    "DRREDDY":       ["Dr Reddy", "Dr. Reddy's"],
    "CIPLA":         ["Cipla"],
    "POWERGRID":     ["Power Grid", "POWER GRID"],
    "NTPC":          ["NTPC"],
    "ONGC":          ["ONGC", "Oil & Natural Gas"],
    "BPCL":          ["BPCL", "Bharat Petroleum"],
    "IOC":           ["Indian Oil", "IndianOil"],
    "COALINDIA":     ["Coal India", "COAL INDIA"],
    "JSWSTEEL":      ["JSW Steel", "JSW STEEL"],
    "HINDALCO":      ["Hindalco", "HINDALCO"],
    "ULTRACEMCO":    ["UltraTech Cement", "Ultratech"],
    "NESTLEIND":     ["Nestle India", "NESTLE"],
    "TITAN":         ["Titan Company", "Titan"],
    "TATACONSUM":    ["Tata Consumer", "TATA CONSUMER"],
    "PIDILITIND":    ["Pidilite", "PIDILITE"],
    "HAVELLS":       ["Havells", "HAVELLS INDIA"],
    "DMART":         ["DMart", "Avenue Supermarts", "D-Mart"],
    "NYKAA":         ["Nykaa", "FSN E-Commerce"],
    "PAYTM":         ["Paytm", "One 97 Communications"],
    "POLICYBZR":     ["PB Fintech", "Policy Bazaar"],
    "IRCTC":         ["IRCTC", "Indian Railway Catering"],
    "HAL":           ["HAL", "Hindustan Aeronautics"],
    "BEL":           ["BEL", "Bharat Electronics"],
    "LICI":          ["LIC", "Life Insurance Corporation"],
}


def _missing_indianapi_key() -> bool:
    k = (INDIANAPI_KEY or "").strip()
    return not k or k == "YOUR_INDIANAPI_KEY_HERE"


def is_indianapi_configured() -> bool:
    return not _missing_indianapi_key()


def _ticker_search_names(ticker: str) -> list[str]:
    """Search names to try for this ticker (ticker first, then mapped names)."""
    names = TICKER_NAME_MAP.get(ticker.upper(), [])
    return [ticker] + [n for n in names if n != ticker]


def fetch_stock_data(ticker: str) -> tuple[Optional[dict], Optional[str]]:
    """
    Fetch from indianapi.in /stock endpoint.
    Returns (data, error_message). Never raises.
    Falls back to mock data when INDIANAPI_KEY is not set.
    Tries multiple search names when the first attempt fails.
    """
    if _missing_indianapi_key():
        print("\n⚠  INDIANAPI_KEY not set — using mock data.\n")
        return _mock_data(ticker), None

    search_names = _ticker_search_names(ticker)
    last_error = None

    for search_name in search_names:
        try:
            resp = requests.get(
                f"{INDIANAPI_BASE}/stock",
                params={"name": search_name},
                headers={"X-Api-Key": INDIANAPI_KEY},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data or (isinstance(data, dict) and "error" in data):
                last_error = f"No data for '{search_name}'"
                continue
            data["_searchedAs"] = search_name
            return data, None
        except requests.exceptions.Timeout:
            return None, "Request timed out (15s) — indianapi.in may be slow"
        except requests.exceptions.HTTPError as e:
            code = e.response.status_code
            if code == 401:
                return None, "API key rejected (401) — check INDIANAPI_KEY"
            if code == 429:
                return None, "Rate limit hit (429) — wait 60s and retry"
            last_error = f"HTTP {code}: {e.response.text[:150]}"
            continue
        except requests.exceptions.ConnectionError:
            return None, "Connection failed — check internet or indianapi.in status"
        except Exception as e:
            return None, f"Unexpected error: {type(e).__name__}: {e}"

    tried = ", ".join(f"'{n}'" for n in search_names)
    return None, last_error or f"Stock not found. Tried: {tried}. Check spelling or try the full company name."


def fetch_stock_target_price(stock_id: str) -> Optional[dict]:
    """
    Fetch analyst target price + recommendation data.
    Endpoint: GET /stock_target_price?stock_id=<id>
    stock_id is the tickerId returned by /stock (e.g. "RELIANCE").
    Returns None on any error — this endpoint is supplementary.
    """
    if _missing_indianapi_key():
        return None  # not available in mock mode

    try:
        resp = requests.get(
            f"{INDIANAPI_BASE}/stock_target_price",
            params={"stock_id": stock_id},
            headers={"X-Api-Key": INDIANAPI_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None  # silently skip — not critical


def _indianapi_get(endpoint: str, params: dict) -> Optional[dict]:
    """Generic helper — all supplementary fetches share error handling."""
    if _missing_indianapi_key():
        return None
    try:
        r = requests.get(
            f"{INDIANAPI_BASE}{endpoint}",
            params=params,
            headers={"X-Api-Key": INDIANAPI_KEY},
            timeout=12,
        )
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


def fetch_historical_data(stock_name: str, period: str = "1yr") -> Optional[list]:
    """
    GET /historical_data — price history for charting.
    period: 1m | 6m | 1yr | 3yr | 5yr | 10yr | max
    filter=price returns [{date, open, high, low, close, volume}]
    """
    data = _indianapi_get("/historical_data", {
        "stock_name": stock_name,
        "period": period,
        "filter": "price",
    })
    if data is None:
        return None
    # API may return list directly or wrapped in a key
    if isinstance(data, list):
        return data
    for key in ("data", "priceData", "history", "prices"):
        if key in data and isinstance(data[key], list):
            return data[key]
    return None


def filter_price_history_by_period(cleaned: list, period: str) -> list:
    """
    Keep rows in the trailing calendar window for the selected chart range.

    The upstream API may return a long series for every period request; the app
    previously sliced ``cleaned[-252:]``, which always capped the chart at ~1Y
    and made 1M/6M/3Y/5Y look identical apart from minor length differences.
    """
    if not cleaned:
        return cleaned
    p = (period or "1yr").strip().lower()
    calendar_days = {
        "1m": 45,
        "6m": 200,
        "1yr": 400,
        "3yr": 1200,
        "5yr": 2000,
        "10yr": 4000,
        "max": 365 * 30,
    }.get(p, 400)

    try:
        sorted_rows = sorted(
            cleaned,
            key=lambda r: (r.get("date") or "")[:10],
        )
        last_str = (sorted_rows[-1].get("date") or "")[:10]
        last_dt = datetime.strptime(last_str, "%Y-%m-%d")
        cutoff = last_dt - timedelta(days=calendar_days)
        out = []
        for r in sorted_rows:
            ds = (r.get("date") or "")[:10]
            try:
                dt = datetime.strptime(ds, "%Y-%m-%d")
                if dt >= cutoff:
                    out.append(r)
            except ValueError:
                continue
        if out:
            return out
    except (ValueError, IndexError, TypeError, OSError):
        pass

    sorted_rows = sorted(
        cleaned,
        key=lambda r: (r.get("date") or "")[:10],
    )
    limits = {"1m": 24, "6m": 128, "1yr": 252, "3yr": 756, "5yr": 1260, "10yr": 2520, "max": 5000}
    n = limits.get(p, 252)
    if len(sorted_rows) <= n:
        return sorted_rows
    return sorted_rows[-n:]


def fetch_statements(stock_name: str) -> Optional[dict]:
    """
    GET /statement — quarterly P&L + balance sheet.
    stats param left empty to get all available statements.
    """
    return _indianapi_get("/statement", {
        "stock_name": stock_name,
        "stats": "consolidated",
    })


def _first_nonempty_str(*vals: object) -> str:
    for v in vals:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return ""


def _looks_like_date_prefix(s: str) -> bool:
    """Short leading segment before ' - ' in combined announcement blobs (e.g. '18 Mar')."""
    s = s.strip()
    if not s or len(s) > 28:
        return False
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return True
    if re.match(r"^\d{1,2}\s+[A-Za-z]{3}\b", s):
        return True
    if re.match(r"^\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}$", s):
        return True
    return False


def normalize_announcement_item(raw: dict) -> dict:
    """
    Map a raw /recent_announcements row to {date, subject, description}.

    IndianAPI responses often omit `subject` or put 'DD Mon - body...' entirely in `date`.
    We merge alternate field names (Subject, title, body, etc.) so the UI never shows a
    blank title when text exists in another key.
    """
    if not isinstance(raw, dict):
        return {"date": "", "subject": "", "description": ""}

    subject = _first_nonempty_str(
        raw.get("subject"),
        raw.get("Subject"),
        raw.get("headline"),
        raw.get("Headline"),
        raw.get("title"),
        raw.get("Title"),
        raw.get("newsTitle"),
        raw.get("announcementType"),
        raw.get("category"),
        raw.get("type"),
    )
    desc = _first_nonempty_str(
        raw.get("description"),
        raw.get("Description"),
        raw.get("details"),
        raw.get("Details"),
        raw.get("text"),
        raw.get("content"),
        raw.get("message"),
        raw.get("remarks"),
        raw.get("body"),
        raw.get("announcement"),
        raw.get("announcementText"),
        raw.get("summary"),
    )
    date_val = _first_nonempty_str(
        raw.get("date"),
        raw.get("Date"),
        raw.get("announcementDate"),
        raw.get("time"),
        raw.get("filingDate"),
        raw.get("newsdate"),
    )

    # Combined field: "18 Mar - Customs redemption fine..." with no separate subject/description
    if date_val and " - " in date_val:
        left, right = date_val.split(" - ", 1)
        left, right = left.strip(), right.strip()
        if _looks_like_date_prefix(left) and len(right) > 3:
            date_val = left
            if not subject:
                subject = right
            if not desc:
                desc = right

    if not subject and desc:
        subject = desc
    if not desc and subject:
        desc = subject

    # Single long blob only in date (no recognised split)
    if not subject and date_val and not desc and len(date_val) > 50:
        subject = date_val[:220]
        date_val = ""

    return {"date": date_val, "subject": subject, "description": desc}


def fetch_announcements(stock_name: str) -> Optional[list]:
    """
    GET /recent_announcements — BSE/NSE exchange filings.
    Returns list of {date, subject, description} dicts (normalized).
    """
    data = _indianapi_get("/recent_announcements", {"stock_name": stock_name})
    if data is None:
        return None
    raw_list = None
    if isinstance(data, list):
        raw_list = data
    elif isinstance(data, dict):
        for key in ("announcements", "data", "results", "recentAnnouncements"):
            if key in data and isinstance(data[key], list):
                raw_list = data[key]
                break
    if not raw_list:
        return None
    out = [normalize_announcement_item(x) for x in raw_list if isinstance(x, dict)]
    out = [x for x in out if x.get("date") or x.get("subject") or x.get("description")]
    return out or None


def fetch_pe_history(stock_name: str, period: str = "3yr") -> Optional[list]:
    """
    GET /historical_data?filter=pe — PE ratio history for valuation context.
    Returns list of {date, pe} so we can show whether current PE is
    cheap or expensive relative to its own history.
    """
    data = _indianapi_get("/historical_data", {
        "stock_name": stock_name,
        "period":     period,
        "filter":     "pe",
    })
    if data is None:
        return None
    rows = data if isinstance(data, list) else data.get("data") or data.get("peData") or []
    cleaned = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        d   = row.get("date") or row.get("Date") or ""
        pe  = row.get("pe")   or row.get("PE")   or row.get("value") or 0
        try:
            pe = float(str(pe).replace(",", ""))
        except (ValueError, TypeError):
            continue
        if d and pe > 0:
            cleaned.append({"date": str(d).split("T")[0], "pe": round(pe, 2)})
    return cleaned or None


def fetch_eps_forecasts(stock_id: str) -> Optional[dict]:
    """
    GET /stock_forecasts — EPS estimates vs actuals.
    stock_id = tickerId from /stock response (e.g. "RELIANCE").
    Returns dict with actuals + estimates lists.
    """
    data = _indianapi_get("/stock_forecasts", {
        "stock_id":    stock_id,
        "measure_code": "EPS",
        "period_type":  "Annual",
        "data_type":    "Estimates",
        "age":          "Current",
    })
    return data


def fetch_market_feed(endpoint: str) -> Optional[list]:
    """
    Generic market-wide feed fetcher.
    endpoint: /trending | /NSE_most_active | /BSE_most_active |
              /price_shockers | /ipo | /fetch_52_week_high_low_data
    """
    data = _indianapi_get(endpoint, {})
    if data is None:
        return None
    # trending wraps data under "trending_stocks"
    if isinstance(data, dict):
        for key in ("trending_stocks", "top_gainers", "data", "results"):
            if key in data:
                inner = data[key]
                if isinstance(inner, list):
                    return inner
                if isinstance(inner, dict):
                    # trending_stocks = {"top_gainers": [...], "top_losers": [...]}
                    result = []
                    for v in inner.values():
                        if isinstance(v, list):
                            result.extend(v)
                    return result or None
        return None
    if isinstance(data, list):
        return data
    return None


def _mock_market_feed(feed_type: str) -> list:
    """Mock data for market-wide feeds during testing."""
    import random
    random.seed(hash(feed_type) % 500)
    stocks = ["RELIANCE", "TCS", "HDFCBANK", "INFY", "WIPRO",
              "TATAMOTORS", "SBIN", "ZOMATO", "ADANIPORTS", "ITC"]
    result = []
    for s in stocks[:6]:
        chg = random.uniform(-5, 5)
        price = random.uniform(500, 4000)
        result.append({
            "ticker_id":    s,
            "company_name": f"{s} Limited",
            "price":        round(price, 2),
            "percent_change": round(chg, 2),
            "volume":       random.randint(100000, 5000000),
            "year_high":    round(price * 1.2, 2),
            "year_low":     round(price * 0.8, 2),
        })
    return result


def _mock_historical(ticker: str) -> list:
    """Generate ~5y of mock daily price data so period buttons change the chart window."""
    import random
    random.seed(hash(ticker) % 1000)
    base = 1400.0
    rows = []
    d = datetime.now() - timedelta(days=2200)
    for i in range(1300):  # ~5y trading days; filtered per period in /api/history
        open_ = base * (1 + random.uniform(-0.012, 0.012))
        close = open_ * (1 + random.uniform(-0.015, 0.015))
        high  = max(open_, close) * (1 + random.uniform(0, 0.008))
        low   = min(open_, close) * (1 - random.uniform(0, 0.008))
        rows.append({
            "date":   d.strftime("%Y-%m-%d"),
            "open":   round(open_, 2),
            "high":   round(high, 2),
            "low":    round(low, 2),
            "close":  round(close, 2),
            "volume": random.randint(500000, 5000000),
        })
        base = close
        d += timedelta(days=1)
        # skip weekends
        while d.weekday() >= 5:
            d += timedelta(days=1)
    return rows


def _mock_data(ticker: str) -> dict:
    """
    Realistic mock matching actual indianapi.in /stock response schema,
    including all fields the real API returns.
    """
    return {
        "tickerId": ticker,
        "companyName": f"{ticker} Limited (MOCK)",
        "industry": "Technology",
        "companyProfile": {
            "description": f"{ticker} is a leading Indian company in its sector.",
            "founded": "1990",
            "headquarters": "Mumbai, India",
            "employees": "50,000+",
            "website": f"https://www.{ticker.lower()}.com",
        },
        "currentPrice": {"BSE": 3456.75, "NSE": 3458.20},
        "percentChange": 1.23,
        "yearHigh": 3987.00,
        "yearLow": 2750.50,
        "keyMetrics": {
            "pe": 28.4,
            "pb": 9.2,
            "eps": 121.7,
            "dividendYield": 1.8,
            "marketCap": "12,45,678",
            "debtToEquity": 0.12,
            "roe": 24.5,
            "roce": 31.2,
        },
        "financials": {
            "revenue": "2,34,567",
            "netProfit": "23,456",
            "operatingProfit": "45,678",
            "totalAssets": "3,45,678",
            "totalDebt": "45,678",
        },
        "stockTechnicalData": {
            "rsi": 58.3,
            "shortTermTrend": "Moderately Bullish",
            "longTermTrend": "Bullish",
            "overallRating": "Bullish",
            "sma50": 3280.0,
            "sma200": 3050.0,
        },
        "shareholding": {
            "promoters": "72.05%",
            "FII": "12.34%",
            "DII": "8.45%",
            "public": "7.16%",
        },
        "analystView": {
            "strongBuy": 8,
            "buy": 5,
            "hold": 3,
            "sell": 1,
            "strongSell": 0,
        },
        "recosBar": {
            "buy": 72,
            "hold": 18,
            "sell": 10,
        },
        "riskMeter": {"level": "Moderately High", "score": 3},
        # indianapi.in real field names for news items
        "recentNews": [
            {"newsHeadline": f"{ticker} Q3 results beat estimates, PAT up 18% YoY",
             "title": f"{ticker} Q3 results beat estimates, PAT up 18% YoY",
             "date": "2025-01-15"},
            {"newsHeadline": f"{ticker} announces expansion into new markets",
             "title": f"{ticker} announces expansion into new markets",
             "date": "2025-01-10"},
            {"newsHeadline": "Sector-wide FII buying continues",
             "title": "Sector-wide FII buying continues",
             "date": "2025-01-08"},
            {"newsHeadline": f"{ticker} board approves share buyback",
             "title": f"{ticker} board approves share buyback",
             "date": "2025-01-05"},
            {"newsHeadline": "Brokerage upgrades rating",
             "title": "Brokerage upgrades rating",
             "date": "2025-01-02"},
        ],
        "stockCorporateActionData": [
            {"action": "Dividend", "amount": "₹6 per share", "exDate": "2024-08-15"},
        ],
    }



# ─────────────────────────────────────────────
#  DATA STRUCTURING
# ─────────────────────────────────────────────

def _normalise(val):
    """
    Normalise any shape that indianapi.in might return for a data block.

    Handles:
      1. Single dict wrapped in list: [{"pe": 22}] → {"pe": 22}
      2. Multiple dicts in list (merge): [{"pe": 22}, {"pb": 2}] → {"pe": 22, "pb": 2}
      3. Label/value list: [{"label":"P/E","value":"22"}, ...] → {"P/E": "22", "pe": "22", ...}
         Also handles: {"name":..., "value":...} and {"key":..., "val":...} patterns
      4. Plain dict or scalar — returned as-is
    """
    if not isinstance(val, list):
        return val

    dicts = [v for v in val if isinstance(v, dict)]
    if not dicts:
        strs = [str(v) for v in val if v not in (None, "", "N/A")]
        return strs[0] if strs else None

    # Detect label/value format: list of {"label": X, "value": Y} objects
    # Also handles "name"/"value", "key"/"value", "metric"/"value" patterns
    label_keys = {"label", "name", "key", "metric", "title", "field"}
    value_keys = {"value", "val", "data", "amount", "figure"}

    first = dicts[0]
    has_label = any(k in first for k in label_keys)
    has_value = any(k in first for k in value_keys)

    if has_label and has_value:
        # Convert label/value list to a flat dict with multiple key aliases
        merged = {}
        for item in dicts:
            label_key = next((k for k in label_keys if k in item), None)
            value_key = next((k for k in value_keys if k in item), None)
            if label_key and value_key:
                raw_label = str(item[label_key]).strip()
                raw_value = item[value_key]
                # Store under original label AND cleaned variants
                merged[raw_label] = raw_value
                # Clean version: remove spaces, slashes, special chars
                clean = raw_label.replace(" ", "").replace("/", "").replace("-", "").lower()
                merged[clean] = raw_value
                # Also store common short forms
                label_lower = raw_label.lower()
                if "p/e" in label_lower or "price to earn" in label_lower or "pe ratio" in label_lower:
                    merged["pe"] = raw_value
                elif "p/b" in label_lower or "price to book" in label_lower or "pb ratio" in label_lower:
                    merged["pb"] = raw_value
                elif "eps" in label_lower:
                    merged["eps"] = raw_value
                elif "market cap" in label_lower or "mcap" in label_lower:
                    merged["marketCap"] = raw_value
                elif "roe" in label_lower or "return on equity" in label_lower:
                    merged["roe"] = raw_value
                elif "roce" in label_lower or "return on capital" in label_lower:
                    merged["roce"] = raw_value
                elif "debt" in label_lower and "equity" in label_lower:
                    merged["debtToEquity"] = raw_value
                elif "dividend" in label_lower and "yield" in label_lower:
                    merged["dividendYield"] = raw_value
                elif "rsi" in label_lower:
                    merged["rsi"] = raw_value
                elif "promoter" in label_lower:
                    merged["promoters"] = raw_value
                elif "fii" in label_lower or "foreign institutional" in label_lower:
                    merged["FII"] = raw_value
                elif "dii" in label_lower or "domestic institutional" in label_lower:
                    merged["DII"] = raw_value
                elif "public" in label_lower or "retail" in label_lower:
                    merged["public"] = raw_value
                elif "strong buy" in label_lower:
                    merged["strongBuy"] = raw_value
                elif "strong sell" in label_lower:
                    merged["strongSell"] = raw_value
                elif label_lower == "buy":
                    merged["buy"] = raw_value
                elif label_lower == "sell":
                    merged["sell"] = raw_value
                elif label_lower == "hold":
                    merged["hold"] = raw_value
        return merged if merged else None

    # Regular list of dicts — merge all
    merged = {}
    for d in dicts:
        merged.update(d)
    return merged


# ── Alias map: every known variation of a field name the API might use ────────
# indianapi.in docs show clean names but the live API uses different casing/naming
# We map our canonical names → all aliases the live API might return
_FIELD_ALIASES: dict[str, list[str]] = {
    # keyMetrics
    "pe":            ["pe", "PE", "peRatio", "ttmPe", "pe_ratio", "priceToEarnings",
                      "P/E", "pe_ttm", "trailing_pe", "trailingPE", "currentPE",
                      "priceTTMEarnings", "price_earnings"],
    "pb":            ["pb", "PB", "pbRatio", "priceToBook", "price_book",
                      "P/B", "ptb", "priceToBV", "pricebookvalue"],
    "eps":           ["eps", "EPS", "epsTtm", "eps_ttm", "earningsPerShare",
                      "basic_eps", "diluted_eps", "ttmEPS"],
    "marketCap":     ["marketCap", "MarketCap", "market_cap", "mktCap",
                      "marketCapFull", "mcap", "Mcap", "MCAP", "mcs",
                      "totalMarketCap", "market_capitalization"],
    "roe":           ["roe", "ROE", "returnOnEquity", "return_on_equity",
                      "roeTtm", "roe_ttm"],
    "roce":          ["roce", "ROCE", "returnOnCapitalEmployed",
                      "return_on_capital_employed"],
    "debtToEquity":  ["debtToEquity", "DebtToEquity", "debt_to_equity",
                      "d_e_ratio", "debtEquity", "de_ratio", "D/E"],
    "dividendYield": ["dividendYield", "DividendYield", "dividend_yield",
                      "divYield", "div_yield", "yield", "dividendYieldTtm"],
    # stockTechnicalData
    "rsi":              ["rsi", "RSI", "rsi14", "RSI14", "rsi_14"],
    "shortTermTrend":   ["shortTermTrend", "ShortTermTrend", "short_term_trend",
                         "shortTrend", "stTrend", "short_term"],
    "longTermTrend":    ["longTermTrend", "LongTermTrend", "long_term_trend",
                         "longTrend", "ltTrend", "long_term"],
    "overallRating":    ["overallRating", "OverallRating", "overall_rating",
                         "rating", "Rating", "trend", "Trend", "overallTrend",
                         "technicalRating", "technicalRating"],
    "sma50":            ["sma50", "SMA50", "sma_50", "ma50", "MA50",
                         "movingAvg50", "50dma"],
    "sma200":           ["sma200", "SMA200", "sma_200", "ma200", "MA200",
                         "movingAvg200", "200dma"],
    # shareholding
    "promoters":     ["promoters", "Promoters", "PROMOTERS", "promoter",
                      "promoterHolding", "promoter_holding", "promoterStake"],
    "FII":           ["FII", "fii", "Fii", "foreignInstitutional",
                      "foreign_institutional", "fiiHolding", "fii_holding",
                      "foreign_investors", "ForeignInstitutional"],
    "DII":           ["DII", "dii", "Dii", "domesticInstitutional",
                      "domestic_institutional", "diiHolding", "dii_holding"],
    "public":        ["public", "Public", "PUBLIC", "publicHolding",
                      "public_holding", "retail", "others", "Others",
                      "retailPublic"],
    # analystView
    "strongBuy":     ["strongBuy", "StrongBuy", "strong_buy", "strongbuy",
                      "STRONG_BUY", "buy1", "Strong Buy"],
    "buy":           ["buy", "Buy", "BUY", "outperform", "Outperform"],
    "hold":          ["hold", "Hold", "HOLD", "neutral", "Neutral"],
    "sell":          ["sell", "Sell", "SELL", "underperform", "Underperform"],
    "strongSell":    ["strongSell", "StrongSell", "strong_sell", "strongsell",
                      "STRONG_SELL", "sell1", "Strong Sell"],
}


def _km_get(keyMetrics: dict, *keys: str):
    """
    Extract value from the real indianapi.in keyMetrics structure:
    {sectionName: [{key: "someKey", value: "123", displayName: "..."}, ...]}
    Tries each key name in order, returns first non-null value found.
    """
    if not isinstance(keyMetrics, dict):
        return None
    for target_key in keys:
        for section_items in keyMetrics.values():
            if not isinstance(section_items, list):
                continue
            for item in section_items:
                if isinstance(item, dict) and item.get("key") == target_key:
                    v = item.get("value")
                    if v is not None and str(v).strip() not in ("", "None", "null", "N/A"):
                        return str(v).strip()
    return None


def _sh_get(shareholding: list, display_name: str):
    """
    Extract latest shareholding % for a category from the real API structure:
    [{displayName, categoryName, categories: [{holdingDate, percentage}, ...]}]
    """
    if not isinstance(shareholding, list):
        return None
    dn_lower = display_name.lower()
    for item in shareholding:
        if not isinstance(item, dict):
            continue
        name = str(item.get("displayName", "") or item.get("categoryName", "")).lower()
        if dn_lower in name or name in dn_lower:
            cats = item.get("categories", [])
            if cats and isinstance(cats, list):
                # get most recent (last entry)
                latest = cats[-1]
                if isinstance(latest, dict):
                    pct = latest.get("percentage")
                    if pct is not None:
                        return f"{pct}%"
    return None


def _av_get(analystView: list, rating_name: str):
    """
    Extract analyst count from the real API analystView structure:
    [{ratingName, numberOfAnalystsLatest, ...}]
    """
    if not isinstance(analystView, list):
        return "0"
    rn_lower = rating_name.lower().replace(" ", "")
    for item in analystView:
        if not isinstance(item, dict):
            continue
        name = str(item.get("ratingName", "")).lower().replace(" ", "")
        if name == rn_lower:
            v = item.get("numberOfAnalystsLatest", "0")
            return str(v) if v is not None else "0"
    return "0"


def _safe_int(val) -> int:
    """Coerce API values like '0.00' or 3.0 to int (indianapi sometimes returns floats as strings)."""
    try:
        s = str(val).replace(",", "").strip()
        if not s or s.lower() in ("none", "null", "n/a"):
            return 0
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _find_in_dict(d: dict, canonical_key: str):
    """
    Look up a value in dict d using canonical_key.
    Tries: exact match → alias list → case-insensitive scan → substring match.
    Returns the first non-None, non-empty value found.
    """
    if not isinstance(d, dict):
        return None

    # 1. exact match
    if canonical_key in d:
        v = d[canonical_key]
        if v not in (None, "", "N/A"):
            return v

    # 2. alias list
    for alias in _FIELD_ALIASES.get(canonical_key, []):
        if alias in d:
            v = d[alias]
            if v not in (None, "", "N/A"):
                return v

    # 3. case-insensitive full scan
    key_lower = canonical_key.lower()
    for dk, dv in d.items():
        if dk.lower() == key_lower and dv not in (None, "", "N/A"):
            return dv

    # 4. substring match (e.g. "pe" matches "peTtm") — last resort
    for dk, dv in d.items():
        if (key_lower in dk.lower() or dk.lower() in key_lower) and dv not in (None, "", "N/A"):
            if isinstance(dv, (int, float, str)) and not isinstance(dv, bool):
                return dv

    return None


def extract_field(data, *keys, default="N/A") -> str:
    """
    Safely traverse nested dict/list structure using alias-aware lookup.
    Handles any field naming convention indianapi.in might use.
    Falls back through: exact → alias list → case-insensitive → substring.
    """
    val = data
    for k in keys:
        val = _normalise(val)
        if not isinstance(val, dict):
            return default
        result = _find_in_dict(val, k)
        if result is None:
            return default
        val = result
    val = _normalise(val)
    if val is None or val == "" or val == "N/A":
        return default
    return str(val)


def assess_pe_context(pe_str: str, sector: str) -> str:
    """Return a human-readable PE assessment against Indian sector norms."""
    try:
        pe = float(str(pe_str).replace(",", ""))
    except (ValueError, TypeError):
        return "P/E not available — cannot assess valuation"

    bench = SECTORS_PE_BENCHMARKS.get(sector, SECTORS_PE_BENCHMARKS["Default"])
    if pe < bench["low"]:
        return f"{pe}x — BELOW sector norm (cheap or value-trap territory for {sector})"
    elif pe <= bench["fair"]:
        return f"{pe}x — within fair range for {sector} ({bench['low']}–{bench['fair']}x)"
    elif pe <= bench["high"]:
        return f"{pe}x — above fair but not extreme for {sector} (growth premium)"
    else:
        return f"{pe}x — ELEVATED vs Indian {sector} peers (>{bench['high']}x = priced for perfection)"



def flag_data_gaps(data: dict) -> list:
    """
    Detect missing fields using the real indianapi.in response structure.
    Uses _km_get, _sh_get, _av_get which understand the actual API schema.
    """
    flags = []

    # Check top-level block existence
    for field in ["currentPrice", "keyMetrics", "shareholding", "analystView"]:
        if not data.get(field):
            flags.append(f"MISSING: '{field}' block entirely absent")

    # Check key KPI values using real extractors
    km  = data.get("keyMetrics") or {}
    sh  = data.get("shareholding") or []
    av  = data.get("analystView") or []
    sdr = data.get("stockDetailsReusableData") or {}

    kpi_checks = {
        "PE ratio": (_km_get(km,
            "pPerEBasicExcludingExtraordinaryItemsTTM",
            "pPerEExcludingExtraordinaryItemsMostRecentFiscalYear") or
            str(sdr.get("pPerEBasicExcludingExtraordinaryItemsTTM") or "")),
        "P/B ratio": _km_get(km, "priceToBookMostRecentFiscalYear"),
        "Market Cap": (_km_get(km, "marketCap") or str(sdr.get("marketCap") or "")),
        "ROE": _km_get(km, "returnOnAverageEquity5YearAverage",
                           "returnOnAverageEquityTrailing12Month"),
        "Div Yield": _km_get(km, "currentDividendYieldCommonStockPrimaryIssueLTM"),
    }
    for label, val in kpi_checks.items():
        if not val or str(val).strip() in ("", "None", "null", "N/A"):
            flags.append(f"MISSING: {label}")

    # Shareholding
    if not _sh_get(sh, "Promoter"):
        flags.append("MISSING: shareholding promoter")
    if not _sh_get(sh, "FII"):
        flags.append("MISSING: shareholding FII")

    # Analyst view
    if not _av_get(av, "Strong Buy") and not _av_get(av, "Buy"):
        flags.append("MISSING: analystView data")

    # News
    news_raw = data.get("recentNews")
    if not news_raw:
        flags.append("MISSING: recentNews")
    elif isinstance(news_raw, list) and len(news_raw) < 3:
        flags.append(f"THIN: only {len(news_raw)} news articles")

    # Suspicious PE
    pe_str = (_km_get(km, "pPerEBasicExcludingExtraordinaryItemsTTM") or
              str(sdr.get("pPerEBasicExcludingExtraordinaryItemsTTM") or ""))
    if pe_str:
        try:
            pe_f = float(str(pe_str).replace(",", ""))
            if pe_f > 500:
                flags.append(f"SUSPICIOUS: P/E {pe_f:.0f}x — extreme value")
            elif pe_f < 0:
                flags.append(f"SUSPICIOUS: Negative P/E — company likely loss-making")
        except (ValueError, TypeError):
            pass

    # Suspicious daily change
    change = data.get("percentChange")
    if change:
        try:
            if abs(float(str(change).replace("%", ""))) > 20:
                flags.append(f"SUSPICIOUS: {change}% daily change — circuit breaker?")
        except (ValueError, TypeError):
            pass

    return flags
def _news_title(n: dict) -> str:
    """Get headline — real API uses 'headline' field (not 'newsHeadline')."""
    return (n.get("headline") or n.get("newsHeadline") or n.get("title") or
            n.get("heading") or n.get("summary", "")[:80] or "(no headline)")


def _news_date(n: dict) -> str:
    """Return date string, stripping ISO timestamp suffix if present."""
    raw = n.get("date") or n.get("publishedAt") or n.get("newsDate") or "N/A"
    return str(raw).split("T")[0] if "T" in str(raw) else str(raw)


def _financials_get(financials: list, key: str, period_type: str = "Annual") -> Optional[str]:
    """
    Extract a value from financials list:
    [{Type, FiscalYear, stockFinancialMap: {INC:[{key,value}], ...}}]
    """
    if not isinstance(financials, list):
        return None
    periods = sorted(
        [f for f in financials if isinstance(f, dict)
         and f.get("Type", "").lower() == period_type.lower()],
        key=lambda x: str(x.get("FiscalYear", "0")),
        reverse=True,
    )
    for period in periods:
        sfm = period.get("stockFinancialMap", {})
        for section_items in sfm.values():
            if not isinstance(section_items, list):
                continue
            for item in section_items:
                if isinstance(item, dict) and item.get("key") == key:
                    v = item.get("value")
                    if v is not None and str(v).strip() not in ("", "None", "null"):
                        return str(v).strip()
    return None


def _peers_extract(company_profile: dict) -> list[dict]:
    """Peer rows from companyProfile.peerCompanyList for API + UI."""
    if not isinstance(company_profile, dict):
        return []
    peers_raw = company_profile.get("peerCompanyList", [])
    if not isinstance(peers_raw, list):
        return []
    peers = []
    for p in peers_raw[:8]:
        if not isinstance(p, dict):
            continue
        mcap_raw = p.get("marketCap")
        try:
            mcap_cr = f"₹{float(mcap_raw):,.0f} Cr" if mcap_raw not in (None, "") else "N/A"
        except (ValueError, TypeError):
            mcap_cr = "N/A"
        peers.append({
            "name":    p.get("companyName", "?"),
            "pe":      p.get("priceToEarningsValueRatio"),
            "pb":      p.get("priceToBookValueRatio"),
            "roe":     p.get("returnOnAverageEquityTrailing12Month"),
            "mcap_cr": mcap_cr,
            "price":   p.get("price"),
            "change":  p.get("percentChange"),
            "rating":  p.get("overallRating"),
        })
    return peers


def build_structured_summary(data: dict, ticker: str) -> dict:
    """
    Parse API response into clean structured sections.
    Returns dict with separate sections so prompts can use what they need.
    Also returns data_flags for quality checking.
    """
    sector    = data.get("industry", "N/A")

    # ── price ────────────────────────────────────────────────────────────────
    cp = data.get("currentPrice", {})
    if isinstance(cp, dict):
        price_nse = str(cp.get("NSE") or cp.get("nse") or "N/A")
        price_bse = str(cp.get("BSE") or cp.get("bse") or "N/A")
    else:
        price_nse = price_bse = str(cp) if cp else "N/A"
    yr_high = str(data.get("yearHigh") or "N/A")
    yr_low  = str(data.get("yearLow")  or "N/A")
    pct_chg = str(data.get("percentChange") or "N/A")

    # ── keyMetrics — real structure: {section: [{key, value, displayName}]} ──
    km = data.get("keyMetrics") or {}
    sdr = data.get("stockDetailsReusableData") or {}  # flat dict with some KPIs
    financials_raw = data.get("financials") or data.get("stockFinancialData") or []

    pe = (_km_get(km,
            "pPerEBasicExcludingExtraordinaryItemsTTM",
            "pPerEExcludingExtraordinaryItemsMostRecentFiscalYear",
            "priceToEarningsRatio") or
          str(sdr.get("pPerEBasicExcludingExtraordinaryItemsTTM") or "") or "N/A")

    pb = (_km_get(km,
            "priceToBookMostRecentFiscalYear",
            "priceToBookValueMostRecentQuarter",
            "priceToBookRatio") or "N/A")

    eps = (
        _financials_get(financials_raw, "DilutedNormalizedEPS", "Annual") or
        _financials_get(financials_raw, "DilutedEPSExcludingExtraOrdItems", "Annual") or
        _km_get(km, "earningsPerShareTrailing12Months", "basicEPSTrailing12Month") or "N/A"
    )
    eps_val = _km_get(km,
                "earningsPerShareTrailing12Months",
                "basicEPSTrailing12Month",
                "dilutedEPSTrailing12Month")
    if eps in ("N/A", "", None) and eps_val:
        eps = eps_val

    revenue_fin = _financials_get(financials_raw, "TotalRevenue", "Annual")
    netincome_fin = _financials_get(financials_raw, "NetIncome", "Annual")

    mktcap = (_km_get(km, "marketCap") or
               str(sdr.get("marketCap") or "") or "N/A")

    roe = (_km_get(km,
            "returnOnAverageEquity5YearAverage",
            "returnOnAverageEquityTrailing12Month") or "N/A")

    roce = _km_get(km,
            "returnOnInvestmentMostRecentFiscalYear",
            "returnOnCapitalEmployedMostRecentFiscalYear") or "N/A"

    d_e = (_km_get(km,
             "totalDebtPerTotalEquityMostRecentQuarter",
             "ltDebtPerEquityMostRecentFiscalYear") or
            str(sdr.get("totalDebtPerTotalEquityMostRecentQuarter") or "") or "N/A")

    div_yield = (_km_get(km,
                   "currentDividendYieldCommonStockPrimaryIssueLTM",
                   "dividendYield") or "N/A")

    revenue   = _km_get(km,
                  "revenueTrailing12Month)",   # note: API has trailing ) in key
                  "revenueTrailing12Month",
                  "totalRevenueMostRecentFiscalYear") or "N/A"

    net_profit = _km_get(km,
                   "netIncomeAvailableToCommonTrailing12Months",
                   "netIncomeAvailableToCommonMostRecentFiscalYear") or "N/A"

    avg_rating = str(sdr.get("averageRating") or "N/A")
    sector_pe  = str(sdr.get("sectorPriceToEarningsValueRatio") or "N/A")

    # ── stockTechnicalData — real structure: [{days, nsePrice, bsePrice}] ────
    # NOT RSI/trends. It's moving averages keyed by number of days.
    tech_raw = data.get("stockTechnicalData") or []
    ma_map = {}
    if isinstance(tech_raw, list):
        for entry in tech_raw:
            if isinstance(entry, dict) and "days" in entry:
                ma_map[int(entry["days"])] = entry.get("nsePrice") or entry.get("bsePrice")
    sma50  = str(ma_map.get(50,  ma_map.get(20,  "N/A")))
    sma200 = str(ma_map.get(300, ma_map.get(100, "N/A")))
    # No RSI or trend labels in this block — use stockDetailsReusableData
    rsi     = "N/A"   # not available in /stock endpoint
    st_trend = "N/A"  # not available directly
    lt_trend = "N/A"
    rating  = avg_rating  # use analyst consensus as overall rating proxy

    # ── shareholding — real structure: [{displayName, categories:[{holdingDate, percentage}]}] ──
    sh_raw    = data.get("shareholding") or []
    promoters = _sh_get(sh_raw, "Promoter")  or "N/A"
    fii       = _sh_get(sh_raw, "FII")        or "N/A"
    dii       = _sh_get(sh_raw, "MF")         or _sh_get(sh_raw, "DII") or "N/A"  # API returns "MF" not "DII"
    public_hold = _sh_get(sh_raw, "Other")    or _sh_get(sh_raw, "Public") or "N/A"

    # ── analystView — real structure: [{ratingName, numberOfAnalystsLatest}] ──
    av_raw    = data.get("analystView") or []
    strong_buy  = _av_get(av_raw, "Strong Buy")
    buy         = _av_get(av_raw, "Buy")
    hold        = _av_get(av_raw, "Hold")
    sell        = _av_get(av_raw, "Sell")
    strong_sell = _av_get(av_raw, "Strong Sell")

    # ── riskMeter — real structure: {categoryName, stdDev} ──────────────────
    risk_raw   = data.get("riskMeter") or {}
    risk_level = str(risk_raw.get("categoryName") or "N/A")
    risk_score = str(risk_raw.get("stdDev") or "N/A")

    # ── recosBar — real structure: {stockAnalyst: [{ratingName, numberOfAnalysts}]} ──
    rb_raw = data.get("recosBar") or {}
    rb_analysts = rb_raw.get("stockAnalyst") or []
    rb_total = sum(_safe_int(a.get("numberOfAnalysts")) for a in rb_analysts if isinstance(a, dict))
    recos_buy  = "N/A"
    recos_hold = "N/A"
    recos_sell = "N/A"
    if rb_total > 0:
        rb_buys  = sum(_safe_int(a.get("numberOfAnalysts")) for a in rb_analysts
                       if isinstance(a, dict) and a.get("ratingValue") in (1, 2))
        rb_holds = sum(_safe_int(a.get("numberOfAnalysts")) for a in rb_analysts
                       if isinstance(a, dict) and a.get("ratingValue") == 3)
        rb_sells = sum(_safe_int(a.get("numberOfAnalysts")) for a in rb_analysts
                       if isinstance(a, dict) and a.get("ratingValue") in (4, 5))
        recos_buy  = f"{round(rb_buys/rb_total*100)}%"
        recos_hold = f"{round(rb_holds/rb_total*100)}%"
        recos_sell = f"{round(rb_sells/rb_total*100)}%"

    # recentNews — uses module-level _news_title / _news_date helpers
    news_raw = data.get("recentNews", [])
    news = [n for n in news_raw if isinstance(n, dict)] if isinstance(news_raw, list) else []
    news_lines = "\n".join(
        f"  [{_news_date(n)}] {_news_title(n)}"
        for n in news[:6]
    ) or "  No news available"

    # financials — prefer annual statements when present
    rev      = revenue_fin or revenue
    profit   = netincome_fin or net_profit
    op_prof  = _km_get(km, "eBITDATrailing12Month", "eBITDTrailing12Month",
                        "operatingIncomeTrailing12Month") or "N/A"
    t_assets = _km_get(km, "totalAssetsMostRecentFiscalYear") or "N/A"
    t_debt   = _km_get(km, "totalDebtMostRecentFiscalYear",
                        "longTermDebtMostRecentFiscalYear") or "N/A"

    # risk_level, risk_score, recos_buy/hold/sell already computed above

    # corporate actions
    corp_actions_raw = data.get("stockCorporateActionData", [])
    if isinstance(corp_actions_raw, list):
        corp_lines = "\n".join(
            f"  {ca.get('action','?')} — {ca.get('amount','N/A')} (ex-date: {ca.get('exDate','N/A')})"
            for ca in corp_actions_raw[:3] if isinstance(ca, dict)
        ) or "  No recent corporate actions"
    else:
        corp_lines = "  N/A"

    # company profile description (1-liner for LLM context)
    cp_prof = data.get("companyProfile") or {}
    co_desc = (
        (cp_prof.get("companyDescription") if isinstance(cp_prof, dict) else None)
        or extract_field(data, "companyProfile", "description")
    )

    pe_context = assess_pe_context(pe, sector)

    try:
        price_f = float(str(price_nse).replace(",", ""))
        high_f  = float(str(yr_high).replace(",", ""))
        low_f   = float(str(yr_low).replace(",", ""))
        pct_from_high = f"{((price_f - high_f) / high_f * 100):.1f}%"
        pct_from_low  = f"{((price_f - low_f)  / low_f  * 100):.1f}%"
    except (ValueError, TypeError):
        pct_from_high = "N/A"
        pct_from_low  = "N/A"

    data_flags = flag_data_gaps(data)

    # ── supplementary data (pre-fetched by caller, passed in via data dict) ──
    # The app fetches these in parallel and injects them under special keys
    announcements_raw = data.get("_announcements") or []
    ann_lines = "\n".join(
        f"  [{a.get('date', 'N/A')}] {a.get('subject') or a.get('headline') or a.get('description', '')[:80]}"
        for a in announcements_raw[:5] if isinstance(a, dict)
    ) or "  No recent announcements"

    statements_raw = data.get("_statements") or {}

    # EPS forecasts (analyst estimates)
    eps_data = data.get("_eps_forecasts")
    eps_text = "N/A"
    if isinstance(eps_data, dict):
        estimates = eps_data.get("estimates") or eps_data.get("data") or []
        if isinstance(estimates, list) and estimates:
            eps_lines = [
                f"  FY{e.get('period', '?')}: ₹{e.get('mean') or e.get('value', 'N/A')}"
                for e in estimates[:3] if isinstance(e, dict)
            ]
            eps_text = "\n".join(eps_lines) if eps_lines else "N/A"

    peers = _peers_extract(data.get("companyProfile") or {})
    peers_lines = ""
    if peers:
        col = "  {:<28} {:>6} {:>5} {:>6} {:<20}"
        header = col.format("Company", "PE", "PB", "ROE%", "Rating")
        divider = "  " + "-" * 70
        rows = []
        for p in peers:
            try:
                pe_s = f"{float(p['pe']):.1f}x" if p.get("pe") not in (None, "", "N/A") else "N/A"
            except (ValueError, TypeError, KeyError):
                pe_s = "N/A"
            try:
                pb_s = f"{float(p['pb']):.2f}x" if p.get("pb") not in (None, "", "N/A") else "N/A"
            except (ValueError, TypeError, KeyError):
                pb_s = "N/A"
            try:
                r = p.get("roe")
                roe_s = (
                    f"{float(r):.1f}%"
                    if r not in (None, "", "N/A") and float(r) > 0
                    else "N/A"
                )
            except (ValueError, TypeError):
                roe_s = "N/A"
            rows.append(col.format(str(p["name"])[:28], pe_s, pb_s, roe_s, p.get("rating") or "N/A"))
        peers_lines = header + "\n" + divider + "\n" + "\n".join(rows)

    sections = {
        "header": f"""STOCK: {data.get('companyName', ticker)} | TICKER: {ticker}
SECTOR: {sector}
DATE: {datetime.now().strftime('%d %b %Y, %H:%M IST')}""",

        "price": f"""PRICE ACTION
  NSE: ₹{price_nse} | BSE: ₹{price_bse}
  Today's Change: {pct_chg}%
  52W High: ₹{yr_high}  ({pct_from_high} from current)
  52W Low:  ₹{yr_low}   ({pct_from_low} from current)""",

        "valuation": f"""VALUATION
  P/E:  {pe_context}
  P/B:  {pb}x
  EPS:  ₹{eps}
  ROE:  {roe}% | ROCE: {roce}%
  D/E:  {d_e}
  Div Yield: {div_yield}%
  Market Cap: ₹{mktcap} Cr""",

        "technicals": f"""TECHNICALS (Moving Averages — indianapi.in provides MAs, not RSI/trend signals)
  Analyst consensus:  {rating}
  5-day MA:    ₹{ma_map.get(5,  'N/A')}
  20-day MA:   ₹{ma_map.get(20, 'N/A')}
  50-day MA:   ₹{ma_map.get(50, 'N/A')}
  100-day MA:  ₹{ma_map.get(100,'N/A')}
  300-day MA:  ₹{ma_map.get(300,'N/A')}
  Price vs 50d MA:  {'ABOVE' if price_nse != 'N/A' and sma50 != 'N/A' and float(str(price_nse).replace(',','')) > float(str(sma50).replace(',','')) else 'BELOW' if price_nse != 'N/A' and sma50 != 'N/A' else 'N/A'}
  Price vs 300d MA: {'ABOVE' if price_nse != 'N/A' and sma200 != 'N/A' and float(str(price_nse).replace(',','')) > float(str(sma200).replace(',','')) else 'BELOW' if price_nse != 'N/A' and sma200 != 'N/A' else 'N/A'}""",

        "shareholding": f"""SHAREHOLDING PATTERN
  Promoters: {promoters}
  FII:       {fii}
  DII:       {dii}
  Public:    {public_hold}""",

        "analyst": f"""ANALYST CONSENSUS
  Strong Buy: {strong_buy} | Buy: {buy} | Hold: {hold}
  Sell: {sell} | Strong Sell: {strong_sell}""",

        "news": f"""RECENT NEWS
{news_lines}""",

        "financials": f"""FINANCIALS (₹ Cr)
  Revenue:          ₹{rev} Cr
  Net Profit:       ₹{profit} Cr
  Operating Profit: ₹{op_prof} Cr
  Total Assets:     ₹{t_assets} Cr
  Total Debt:       ₹{t_debt} Cr""",

        "peers": f"""PEER COMPARISON
{peers_lines if peers_lines else "  No peer data available"}""",

        "risk": f"""RISK ASSESSMENT
  Risk Level: {risk_level}  (Score: {risk_score}/5)
  Analyst consensus: {recos_buy}% Buy | {recos_hold}% Hold | {recos_sell}% Sell""",

        "corporate_actions": f"""CORPORATE ACTIONS (recent)
{corp_lines}""",

        "announcements": f"""EXCHANGE ANNOUNCEMENTS (BSE/NSE filings)
{ann_lines}""",

        "eps_forecasts": f"""ANALYST EPS FORECASTS
{eps_text}""",

        "company_profile": co_desc,

        "data_flags": data_flags,
    }

    return sections


def format_full_summary(sections: dict) -> str:
    """Join all sections into the string sent to the LLM."""
    flags_text = ""
    if sections["data_flags"]:
        flags_text = "\nDATA QUALITY WARNINGS (pre-LLM detection)\n" + \
                     "\n".join(f"  ⚠  {f}" for f in sections["data_flags"])

    parts = [
        sections["header"],
        sections["price"],
        sections["valuation"],
        sections["financials"],
        sections["peers"],
        sections["technicals"],
        sections["shareholding"],
        sections["analyst"],
        sections["risk"],
        sections["corporate_actions"],
        sections["announcements"],
        sections["eps_forecasts"],
        sections["news"],
    ]
    if flags_text:
        parts.append(flags_text)

    return "\n\n".join(parts)


# ─────────────────────────────────────────────
#  PROMPTS  (3 styles for comparison)
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior research analyst at an Indian equity research firm.
You cover NSE/BSE-listed stocks and write briefs for fund managers and serious retail investors.

Your rules (non-negotiable):
1. NEVER give explicit BUY/SELL/HOLD recommendations
2. NEVER invent data not present in the input — if a field is N/A, say so
3. Always interpret valuation in the Indian market context, not US/global norms
4. Flag data anomalies you spot — be the analyst, not the cheerleader
5. Write for an investor who has 90 seconds — be crisp, not verbose
6. Use ₹ for prices, Cr for market cap
7. Your job is to organise facts and surface the right questions, not to predict
8. The API provides moving averages (5d/20d/50d/100d/300d), NOT RSI. Use price-vs-MA context for technical posture.
9. Market Cap from this API is in ₹ Cr already. Revenue/NetProfit figures are in raw units — note if they seem very large (banking sector shows values in ₹ lakhs)."""


PROMPT_A_STRUCTURED = """You are writing a research brief. Produce clean, readable markdown.

{summary}

Use EXACTLY this structure with proper markdown headings:

### Valuation snapshot
2-3 sentences. Is this cheap, fair, or expensive vs Indian sector peers?
Use the P/E context provided. Note ROE and D/E if available.

### Technical posture
2-3 sentences. Price vs 50d and 300d moving average signals.
Note distance from 52W high/low and what it implies.

### News pulse
- Key event 1 (one line)
- Key event 2 (one line)
- Key event 3 (one line, max)

### Shareholding signals
1-2 sentences. Promoter holding level, FII concentration, any notable pattern.

### Key questions for deeper research
1. [Specific question about this company's situation]
2. [Specific question about risks or valuation drivers]
3. [Specific question about near-term catalysts]

### Data quality
Note any missing or suspicious fields. If clean, say so in one line.

---
*Data as of {ticker} · All figures in ₹ unless noted*"""


PROMPT_B_CONVERSATIONAL = """You\'re briefing a sharp investor who has 90 seconds. Stock: **{ticker}**

Data:
{summary}

Write a tight conversational briefing in clean markdown — no section headers, just flowing paragraphs:

**First paragraph:** Where is this stock right now? Price vs 52W high/low, trend vs moving averages. One strong opening sentence.

**Second paragraph:** Is the valuation interesting or stretched? P/E vs Indian sector norms, what ROE/D/E tell us about quality.

**Third paragraph:** What does the news/announcements tell us? Any material event that changes the picture?

**One final line:** The single most important question to answer before taking a position.

Be direct. No fluff. Write like you\'re actually talking to them."""


PROMPT_C_RISK_FIRST = """Analyse this Indian stock with a RISK-FIRST lens. Stock: **{ticker}**

{summary}

### Red flags
List concrete concerns (valuation, technicals, news, debt, governance).
If none: *No major red flags in available data.*

### Bull case
One paragraph — best case interpretation of the available data.

### Bear case
One paragraph — worst case interpretation of the same data.

### Risk verdict
**One sentence** on risk/reward balance.

### Data reliability
Brief note on what key data is missing and how it limits confidence."""


PROMPTS = {
    "A_structured":     (PROMPT_A_STRUCTURED,     "Structured Brief"),
    "B_conversational": (PROMPT_B_CONVERSATIONAL,  "Conversational Briefing"),
    "C_risk_first":     (PROMPT_C_RISK_FIRST,      "Risk-First Analysis"),
}


# ─────────────────────────────────────────────
#  LLM CALL
# ─────────────────────────────────────────────

def run_llm(prompt_text: str, ticker: str) -> tuple[Optional[str], Optional[str]]:
    """Call Claude. Returns (output_text, error_message)."""
    if ANTHROPIC_KEY == "YOUR_ANTHROPIC_KEY_HERE":
        return (
            "[MOCK LLM OUTPUT]\n\nSet ANTHROPIC_KEY to get real analysis.\n"
            "The data summary above shows what the LLM would receive.",
            None,
        )

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
        message = client.messages.create(
            model=LLM_MODEL,
            max_tokens=LLM_MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt_text}],
        )
        return message.content[0].text, None

    except anthropic.AuthenticationError:
        return None, "Invalid Anthropic API key — check ANTHROPIC_KEY"
    except anthropic.RateLimitError:
        return None, "Rate limit hit — wait 60s and retry"
    except anthropic.APIConnectionError:
        return None, "Cannot reach Anthropic API — check connection"
    except Exception as e:
        return None, f"LLM call failed: {e}"


# ─────────────────────────────────────────────
#  OUTPUT HELPERS
# ─────────────────────────────────────────────

DIVIDER = "─" * 64

def print_header(text: str):
    print(f"\n{DIVIDER}")
    print(f"  {text}")
    print(DIVIDER)

def print_section(label: str, content: str):
    print(f"\n{'━'*20} {label} {'━'*20}")
    print(content)

def save_output(ticker: str, content: str, suffix: str = ""):
    os.makedirs("outputs", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"outputs/{ticker}_{ts}{suffix}.txt"
    with open(fname, "w") as f:
        f.write(content)
    print(f"\n  💾 Saved → {fname}")
    return fname


# ─────────────────────────────────────────────
#  MAIN MODES
# ─────────────────────────────────────────────

def run_single(ticker: str, prompt_key: str = "A_structured", save: bool = False):
    """Default mode — one ticker, one prompt, clean output."""
    ticker = ticker.upper().strip()

    print_header(f"Research Analyst Agent  ·  {ticker}  ·  {datetime.now().strftime('%d %b %Y')}")

    # 1. Fetch data
    print(f"\n  ⟳  Fetching market data for {ticker}...")
    data, err = fetch_stock_data(ticker)

    if err:
        print(f"\n  ✗  DATA FETCH FAILED: {err}")
        print("     → Try a different ticker name (e.g. 'Reliance' or 'RELIANCE')")
        print("     → Check indianapi.in status")
        return

    print(f"  ✓  Data received")

    # 2. Structure it
    sections = build_structured_summary(data, ticker)
    full_summary = format_full_summary(sections)

    # 3. Print the structured summary — the most important debugging tool
    print_section("STRUCTURED DATA SENT TO LLM", full_summary)

    if sections["data_flags"]:
        print(f"\n  ⚠  {len(sections['data_flags'])} data quality issue(s) detected (see above)")

    # 4. Run LLM
    prompt_template, prompt_label = PROMPTS[prompt_key]
    prompt_text = prompt_template.format(summary=full_summary, ticker=ticker)

    print(f"\n  ⟳  Running LLM ({LLM_MODEL}) with prompt style: {prompt_label}...")
    t0 = time.time()
    output, err = run_llm(prompt_text, ticker)
    elapsed = time.time() - t0

    if err:
        print(f"\n  ✗  LLM FAILED: {err}")
        return

    print(f"  ✓  Response in {elapsed:.1f}s")

    print_section(f"RESEARCH BRIEF  [{prompt_label}]", output)

    if save:
        content = f"TICKER: {ticker}\nPROMPT: {prompt_label}\n\n"
        content += "=== DATA SUMMARY ===\n" + full_summary + "\n\n"
        content += "=== LLM OUTPUT ===\n" + output
        save_output(ticker, content, f"_{prompt_key}")

    return output


def run_compare(ticker: str, save: bool = False):
    """Run all 3 prompt styles on the same ticker for comparison."""
    ticker = ticker.upper().strip()

    print_header(f"PROMPT COMPARISON  ·  {ticker}  ·  3 styles")

    # Fetch once, reuse
    print(f"\n  ⟳  Fetching data for {ticker}...")
    data, err = fetch_stock_data(ticker)

    if err:
        print(f"\n  ✗  {err}")
        return

    sections = build_structured_summary(data, ticker)
    full_summary = format_full_summary(sections)

    print_section("DATA SENT TO ALL PROMPTS", full_summary)

    outputs = {}
    all_content = f"TICKER: {ticker}\nCOMPARISON RUN: {datetime.now()}\n\n"
    all_content += "=== DATA SUMMARY ===\n" + full_summary + "\n\n"

    for key, (template, label) in PROMPTS.items():
        print(f"\n  ⟳  Running Prompt {key[-1]}: {label}...")
        t0 = time.time()
        prompt_text = template.format(summary=full_summary, ticker=ticker)
        output, err = run_llm(prompt_text, ticker)
        elapsed = time.time() - t0

        if err:
            print(f"  ✗  Failed: {err}")
            output = f"ERROR: {err}"
        else:
            print(f"  ✓  {elapsed:.1f}s")

        outputs[key] = output
        separator = "=" * 64
        print(f"\n{separator}")
        print(f"  PROMPT {key[-1].upper()}: {label.upper()}")
        print(separator)
        print(output)

        all_content += f"=== PROMPT {key}: {label} ===\n{output}\n\n"

        if key != list(PROMPTS.keys())[-1]:
            print("\n  ⏸  Pausing 3s between LLM calls...")
            time.sleep(3)

    # Scoring guide
    print(f"\n{DIVIDER}")
    print("  VALIDATION CHECKLIST — score each prompt (1-5):")
    print(DIVIDER)
    print("  For each output above, ask:")
    print("  □  Is the valuation assessment India-specific? (not US benchmarks)")
    print("  □  Does it catch the data gaps we flagged?")
    print("  □  Are the 'key questions' actually specific and useful?")
    print("  □  Would you trust this as a starting point for research?")
    print("  □  Is the length appropriate — or too verbose / too thin?")
    print()
    print("  Pick the prompt style that scores highest across 8 validation tickers.")
    print(DIVIDER)

    if save:
        save_output(ticker, all_content, "_comparison")


def run_batch(save: bool = False):
    """Run all 8 validation tickers with the default prompt."""
    print_header("BATCH VALIDATION  ·  8 tickers  ·  Prompt A (Structured)")
    print(f"\n  Tickers: {', '.join(VALIDATION_TICKERS)}")
    print("  This validates data coverage + LLM quality across sectors.\n")

    results = {}
    for i, ticker in enumerate(VALIDATION_TICKERS, 1):
        print(f"\n{'='*64}")
        print(f"  [{i}/8]  {ticker}")
        print('='*64)

        data, err = fetch_stock_data(ticker)
        if err:
            results[ticker] = {"status": "FETCH_ERROR", "error": err}
            print(f"  ✗  {err}")
            continue

        sections = build_structured_summary(data, ticker)
        full_summary = format_full_summary(sections)
        flags = sections["data_flags"]

        prompt_text = PROMPT_A_STRUCTURED.format(summary=full_summary, ticker=ticker)
        output, err = run_llm(prompt_text, ticker)

        if err:
            results[ticker] = {"status": "LLM_ERROR", "error": err, "data_flags": flags}
            print(f"  ✗  LLM error: {err}")
        else:
            results[ticker] = {
                "status": "OK",
                "data_flags": flags,
                "output_preview": output[:200] + "...",
            }
            print(f"\n{output}")

        if i < len(VALIDATION_TICKERS):
            print("\n  ⏸  5s pause between tickers...")
            time.sleep(5)

    # Summary table
    print(f"\n\n{DIVIDER}")
    print("  BATCH SUMMARY")
    print(DIVIDER)
    print(f"  {'Ticker':<14} {'Status':<12} {'Data Issues'}")
    print(f"  {'-'*14} {'-'*12} {'-'*30}")
    for ticker, result in results.items():
        status   = result["status"]
        flags    = result.get("data_flags", [])
        flag_str = f"{len(flags)} issue(s)" if flags else "Clean"
        print(f"  {ticker:<14} {status:<12} {flag_str}")

    if save:
        content = json.dumps(results, indent=2)
        save_output("BATCH", content, "_validation")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Indian Stock Market Research Analyst Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python research_agent.py RELIANCE
  python research_agent.py ZOMATO --compare
  python research_agent.py INFY --prompt B_conversational --save
  python research_agent.py --batch --save
        """
    )
    parser.add_argument("ticker", nargs="?", help="NSE ticker symbol (e.g. RELIANCE, HDFCBANK)")
    parser.add_argument("--compare",  action="store_true", help="Run all 3 prompt styles for comparison")
    parser.add_argument("--batch",    action="store_true", help="Run all 8 validation tickers")
    parser.add_argument("--save",     action="store_true", help="Save output to /outputs folder")
    parser.add_argument("--prompt",   default="A_structured",
                        choices=list(PROMPTS.keys()),
                        help="Which prompt style to use (default: A_structured)")

    args = parser.parse_args()

    if args.batch:
        run_batch(save=args.save)
    elif args.ticker and args.compare:
        run_compare(args.ticker, save=args.save)
    elif args.ticker:
        run_single(args.ticker, prompt_key=args.prompt, save=args.save)
    else:
        parser.print_help()
        print("\n  Quick start:")
        print("  python research_agent.py RELIANCE")
        print("  python research_agent.py RELIANCE --compare")
        print("  python research_agent.py --batch\n")


if __name__ == "__main__":
    main()
