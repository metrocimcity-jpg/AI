"""Opt-in face detection and embedding. Disabled unless face.enabled is true."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from app.core.logging import get_logger
from app.ml.registry import ModelError, ModelRegistry
from app.pipeline.base import FrameContext

logger = get_logger("siteguard.pipeline.face")


def _laplacian_var(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


class FaceEngine:
    def __init__(self, registry: ModelRegistry, det_name: str, rec_name: str) -> None:
        det = registry.get(det_name)
        rec = registry.get(rec_name)
        self.detector = cv2.FaceDetectorYN.create(str(det.path), "", (320, 320), 0.6, 0.3, 5000)
        self.recognizer = cv2.FaceRecognizerSF.create(str(rec.path), "")

    def embed(self, image: np.ndarray, min_px: int, min_blur: float) -> tuple[np.ndarray, float] | None:
        h, w = image.shape[:2]
        self.detector.setInputSize((w, h))
        _ok, faces = self.detector.detect(image)
        if faces is None or len(faces) == 0:
            return None
        faces = sorted(faces, key=lambda row: float(row[2] * row[3]), reverse=True)
        face = faces[0]
        if float(face[2]) < min_px or float(face[3]) < min_px:
            return None
        x, y, fw, fh = (int(face[0]), int(face[1]), int(face[2]), int(face[3]))
        crop = image[max(0, y) : y + fh, max(0, x) : x + fw]
        if crop.size == 0:
            return None
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        blur = _laplacian_var(gray)
        if blur < min_blur:
            return None
        aligned = self.recognizer.alignCrop(image, face)
        feat = self.recognizer.feature(aligned)
        vec = np.asarray(feat, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vec))
        if norm < 1e-6:
            return None
        vec = vec / norm
        quality = min(1.0, blur / 200.0)
        return vec, quality


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


def match_gallery(
    vec: np.ndarray,
    gallery: list[tuple[str, str, np.ndarray]],
    threshold: float,
    margin: float,
) -> dict[str, Any]:
    """gallery items are (worker_id, name, vector). Embeddings stay inside this process."""
    if not gallery:
        return {"result": "unknown", "worker_id": None, "name": None, "score": 0.0, "authorized": False}
    scored = sorted(((cosine(vec, item[2]), item) for item in gallery), key=lambda pair: pair[0], reverse=True)
    best_score, best = scored[0]
    second = scored[1][0] if len(scored) > 1 else -1.0
    if best_score >= threshold and (best_score - second) >= margin:
        return {
            "result": "known",
            "worker_id": best[0],
            "name": best[1],
            "score": best_score,
            "authorized": True,
        }
    return {
        "result": "unknown",
        "worker_id": None,
        "name": None,
        "score": best_score,
        "authorized": False,
    }


class FaceStage:
    name = "face"
    enabled = False

    def __init__(
        self,
        registry: ModelRegistry,
        enabled: bool,
        det_name: str,
        rec_name: str,
        min_px: int = 80,
        min_blur: float = 40,
        threshold: float = 0.36,
        margin: float = 0.05,
        every: int = 5,
        gallery_provider=None,  # type: ignore[no-untyped-def]
    ) -> None:
        self.registry = registry
        self.enabled = enabled
        self.det_name = det_name
        self.rec_name = rec_name
        self.min_px = min_px
        self.min_blur = min_blur
        self.threshold = threshold
        self.margin = margin
        self.every = max(1, every)
        self.gallery_provider = gallery_provider
        self._engine: FaceEngine | None = None
        self.failed = False
        self._cache: dict[int, dict] = {}
        self._seen: dict[int, int] = {}

    def process(self, ctx: FrameContext) -> FrameContext:
        if not self.enabled:
            return ctx
        if self.failed:
            return ctx
        try:
            if self._engine is None:
                self._engine = FaceEngine(self.registry, self.det_name, self.rec_name)
        except (ModelError, cv2.error, AttributeError) as exc:
            self.failed = True
            logger.error("face models are not ready: %s", exc)
            return ctx
        gallery = self.gallery_provider() if self.gallery_provider else []
        faces: dict[int, dict] = {}
        for track in ctx.tracks:
            self._seen[track.id] = self._seen.get(track.id, 0) + 1
            cached = self._cache.get(track.id)
            if cached and self._seen[track.id] % self.every != 0:
                faces[track.id] = cached
                continue
            x1, y1, x2, y2 = (int(v) for v in track.bbox)
            h, w = ctx.frame.shape[:2]
            crop = ctx.frame[max(0, y1) : min(h, y2), max(0, x1) : min(w, x2)]
            if crop.size == 0 or crop.shape[0] < self.min_px:
                faces[track.id] = {"result": "unverified", "quality": 0.0, "authorized": False}
                continue
            try:
                embedded = self._engine.embed(crop, self.min_px, self.min_blur)
            except cv2.error as exc:
                logger.warning("face embed failed: %s", exc)
                continue
            if embedded is None:
                faces[track.id] = {"result": "unverified", "quality": 0.0, "authorized": False}
                continue
            vec, quality = embedded
            match = match_gallery(vec, gallery, self.threshold, self.margin)
            match["quality"] = quality
            # The vector itself is intentionally not stored on the frame context.
            self._cache[track.id] = match
            faces[track.id] = match
        ctx.faces = faces
        return ctx
