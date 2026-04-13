# OpenAlgo + Indian Stock Research (local setup)

Two services on **different ports**:

| Service | Port | Directory |
|--------|------|-----------|
| **Indian Stock Research** (this repo) | **5001** | `/mnt/e/fintech` |
| **OpenAlgo** | **5000** | `/mnt/e/openalgo` |

## 1. Start the research app (stock analyst)

```bash
cd /mnt/e/fintech
source venv/bin/activate
pip install -r requirements.txt
PORT=5001 python app.py
```

Open: **http://127.0.0.1:5001**

## 2. Start OpenAlgo

```bash
cd /mnt/e/openalgo
/mnt/e/fintech/venv/bin/uv run app.py
```

Open: **http://127.0.0.1:5000**

## 3. OpenAlgo `.env` (Fyers example)

Must **not** contain `<broker>` in `REDIRECT_URL` — use a real path, e.g.:

```ini
REDIRECT_URL = 'http://127.0.0.1:5000/fyers/callback'
HOST_SERVER = 'http://127.0.0.1:5000'
FLASK_PORT='5000'
```

Register the **same** redirect URL in [myapi.fyers.in](https://myapi.fyers.in) for your app.

**Iframe (research panel in order dialog):** allow the research origin in OpenAlgo CSP:

```ini
CSP_FRAME_SRC = "'self' http://127.0.0.1:5001 http://localhost:5001"
```

## 4. Fintech `.env` integration

```ini
PORT=5001
OPENALGO_HOST=http://localhost:5000
PANEL_ALLOWED_ORIGINS=http://localhost:5000,http://127.0.0.1:5000
```

## 5. Rebuild OpenAlgo frontend (after changing Vite env)

```bash
cd /mnt/e/openalgo/frontend
export VITE_API_URL=http://127.0.0.1:5000
export VITE_AI_RESEARCH_URL=http://127.0.0.1:5001
npm run build
```

`frontend/.env.production` should contain the same `VITE_*` values.

## 6. Morning digest

Research app: **http://127.0.0.1:5001/digest**
