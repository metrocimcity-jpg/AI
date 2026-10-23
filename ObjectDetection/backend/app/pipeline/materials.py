"""Tiled materials/machinery detection with cross-tile NMS."""

from __future__ import annotations

import numpy as np

from app.core.logging import get_logger
from app.ml.postprocess import Detection, non_max_suppression
from app.ml.registry import ModelError, ModelRegistry
from app.ml.yolo import YoloDetector
from app.pipeline.base import FrameContext

logger = get_logger("siteguard.pipeline.materials")


def iter_tiles(frame: np.ndarray, tile: int, overlap: float):
    height, width = frame.shape[:2]
    step = max(1, int(tile * (1 - overlap)))
    if height <= tile and width <= tile:
        yield 0, 0, frame
        return
    y = 0
    while y < height:
        x = 0
        y2 = min(height, y + tile)
        y1 = max(0, y2 - tile)
        while x < width:
            x2 = min(width, x + tile)
            x1 = max(0, x2 - tile)
            yield x1, y1, frame[y1:y2, x1:x2]
            if x2 >= width:
                break
            x += step
        if y2 >= height:
            break
        y += step


class MaterialsStage:
    name = "materials"
    enabled = True

    def __init__(
        self,
        registry: ModelRegistry,
        model_name: str,
        conf: float,
        iou: float,
        priority: list[str],
        tile: int = 640,
        overlap: float = 0.2,
        enabled: bool = True,
        class_conf: dict[str, float] | None = None,
    ) -> None:
        self.registry = registry
        self.model_name = model_name
        self.conf = conf
        self.iou = iou
        self.priority = priority
        self.tile = tile
        self.overlap = overlap
        self.enabled = enabled
        self.class_conf = class_conf or {}
        self._model: YoloDetector | None = None
        self.failed = False

    def process(self, ctx: FrameContext) -> FrameContext:
        if not self.enabled or self.failed:
            return ctx
        try:
            if self._model is None:
                self._model = YoloDetector(
                    self.registry,
                    self.model_name,
                    self.conf,
                    self.iou,
                    self.priority,
                    self.class_conf,
                )
        except ModelError as exc:
            self.failed = True
            logger.error("%s", exc)
            return ctx
        found: list[Detection] = []
        for origin_x, origin_y, crop in iter_tiles(ctx.frame, self.tile, self.overlap):
            for det in self._model.detect(crop):
                x1, y1, x2, y2 = det.bbox_xyxy
                found.append(
                    Detection(
                        (x1 + origin_x, y1 + origin_y, x2 + origin_x, y2 + origin_y),
                        det.score,
                        det.class_id,
                        det.class_name,
                    )
                )
        ctx.objects = non_max_suppression(found, self.iou)
        return ctx
