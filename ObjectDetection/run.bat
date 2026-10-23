@echo off
setlocal
cd /d "%~dp0"
if not exist backend\.venv (
  python -m venv backend\.venv
  backend\.venv\Scripts\python -m pip install -e backend[dev]
)
if not exist frontend\node_modules (
  cd frontend && npm install && cd ..
)
start "siteguard-api" cmd /c "set PYTHONPATH=backend&& backend\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
cd frontend
npm run dev
