# gunicorn.conf.py – sourced by Dockerfile CMD
# Extracted from hardcoded Dockerfile flags so tuning doesn't require a rebuild.
#
# Worker sizing:
#   WEB_CONCURRENCY env var (set in Railway dashboard or .env) controls workers.
#   Defaults to 1 to stay within Railway free/starter tier RAM limits.
#   The ML model + DuckDB stack uses ~300-500MB per worker; 1 worker + 4 threads
#   handles concurrent requests via async I/O without duplicating RAM usage.
#   Upgrade path: set WEB_CONCURRENCY=2 on a 1GB+ instance.

import os

workers = int(os.environ.get("WEB_CONCURRENCY", 1))
threads = 4
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
accesslog = "-"
errorlog = "-"
loglevel = "info"
