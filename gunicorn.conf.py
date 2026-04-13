"""Gunicorn settings — used by Render and any host that runs:
    gunicorn -c gunicorn.conf.py app:app
Keeps long-lived SSE streams for /api/brief from hitting the default 30s worker timeout.
"""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"
workers = 1
worker_class = "gthread"
threads = 4
timeout = 300
graceful_timeout = 60
