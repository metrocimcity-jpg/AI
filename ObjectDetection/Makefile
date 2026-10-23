.PHONY: dev build test lint

dev:
	cd backend && ../.venv/Scripts/python -m uvicorn app.main:app --app-dir . --host 127.0.0.1 --port 8000 --reload

build:
	cd frontend && npm install && npm run build

test:
	cd backend && ../backend/.venv/Scripts/python -m pytest

lint:
	cd backend && ../backend/.venv/Scripts/python -m ruff check app tests
