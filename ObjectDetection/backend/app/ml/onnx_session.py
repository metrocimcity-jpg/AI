"""ONNX Runtime session factory with CPU fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.ml.providers import select_providers
from app.ml.registry import ModelError

logger = get_logger("siteguard.ml.session")


class InferenceError(ModelError):
    """The ONNX file exists but Runtime could not execute it."""


def available_providers() -> list[str]:
    import onnxruntime as ort

    providers = ort.get_available_providers()
    return [str(item) for item in providers]


def create_session(path: Path, priority: list[str]) -> tuple[Any, list[str]]:
    import onnxruntime as ort

    available = available_providers()
    chosen = select_providers(priority, available)
    try:
        session = ort.InferenceSession(str(path), providers=chosen)
    except Exception as exc:
        if chosen == ["CPUExecutionProvider"]:
            raise InferenceError(f"Could not load ONNX model {path.name}: {exc}") from exc
        logger.warning(
            "providers %s failed for %s (%s); falling back to CPU",
            chosen,
            path.name,
            exc,
        )
        try:
            session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        except Exception as cpu_exc:
            raise InferenceError(f"Could not load ONNX model {path.name}: {cpu_exc}") from cpu_exc
    active = [str(item) for item in session.get_providers()]
    if active and active[0] == "CPUExecutionProvider" and chosen[0] != "CPUExecutionProvider":
        logger.warning("model %s is running on CPU; requested %s", path.name, chosen)
    return session, active
