#!/usr/bin/env sh
set -e
cd "$(dirname "$0")"
if [ ! -d backend/.venv ]; then
  python3 -m venv backend/.venv
  backend/.venv/bin/pip install -e "backend[dev]"
fi
if [ ! -d frontend/node_modules ]; then
  (cd frontend && npm install)
fi
PYTHONPATH=backend backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 &
cd frontend && npm run dev
