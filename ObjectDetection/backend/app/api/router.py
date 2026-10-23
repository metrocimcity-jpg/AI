"""Aggregate API routers under /api."""

from __future__ import annotations

from fastapi import APIRouter

from app.api import auth, cameras, events, health, samples, settings, stats, workers, ws, zones

api = APIRouter(prefix="/api")
api.include_router(health.router)
api.include_router(auth.router)
api.include_router(cameras.router)
api.include_router(events.router)
api.include_router(zones.router)
api.include_router(workers.router)
api.include_router(stats.router)
api.include_router(settings.router)
api.include_router(samples.router)

ws_router = ws.router
