# Indian Stock Research Analyst — Web App

A lightweight browser UI for the research analyst agent.
Built with Python Flask + Oat UI (~8KB, zero JS framework).

---

## Files

```
research_app/
├── app.py               ← Flask server + entire HTML frontend
├── research_agent.py    ← All data/LLM logic (copied from Phase 1)
├── requirements.txt
└── README.md
```

---

## Setup (one time, 3 minutes)

```bash
# 1. Create + activate virtual environment
python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your API keys
export INDIANAPI_KEY="your_key_from_indianapi.in"
export ANTHROPIC_KEY="your_key_from_console.anthropic.com"

# 4. Run the server
python app.py
```

Then open **http://localhost:5000** in any browser.

---

## Sharing with a non-technical user

**Same network (office / home WiFi):**
```bash
# Find your machine's local IP
# Mac/Linux:
ifconfig | grep "inet "
# Windows:
ipconfig | findstr IPv4

# Then tell the user to open:
http://192.168.x.x:5000
```

**Over the internet (temporary demo):**
```bash
pip install cloudflared      # or download from cloudflare.com/products/tunnel
cloudflared tunnel --url http://localhost:5000
# Cloudflare prints a public URL like: https://xxxx.trycloudflare.com
# Share that URL — valid until you stop the tunnel
```

---

## What the user sees

1. Enter any NSE ticker (or click a quick-pick button)
2. Choose analysis style: Structured / Conversational / Risk-First
3. Press Analyse
4. Data cards populate instantly (price, P/E, shareholding, news)
5. AI brief streams in word-by-word below

---

## Changing API keys without restarting

Edit the CONFIG section at the top of `research_agent.py` and restart `app.py`.
Or use environment variables — they take priority.

---

## Health check

```
http://localhost:5000/health
```

Returns JSON showing whether both API keys are configured.

---

## No keys? Mock mode

If keys aren't set, the app still works:
- Data cards show realistic mock data for any ticker
- AI brief shows a placeholder message
Good for demonstrating the UI before API access is ready.
