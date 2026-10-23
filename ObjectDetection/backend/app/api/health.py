"""Liveness and model inventory. Public so a local probe can run before login."""

from __future__ import annotations

import time

from fastapi import APIRouter, Request

from app.ml.onnx_session import available_providers

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request) -> dict:
    state = request.app.state.ctx
    cameras = []
    for camera_id, worker in list(state.cameras._workers.items()):
        cameras.append(
            {
                "id": camera_id,
                "fps": round(worker.fps, 2),
                "latency_ms": round(worker.latency_ms, 1),
                "status": worker.status,
            }
        )
    try:
        providers = available_providers()
    except Exception:
        providers = []
    return {
        "status": "ok",
        "uptime": round(time.time() - state.started, 1),
        "providers": providers,
        "models": state.registry.status(),
        "cameras": cameras,
        "face_enabled": bool(state.config.face_recognition_enabled),
    }
