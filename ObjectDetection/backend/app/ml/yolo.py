"""YOLO-style detect and pose wrappers. Callers pass frames; NMS stays here."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from app.ml.onnx_session import create_session
from app.ml.postprocess import Detection, decode_yolo
from app.ml.preprocess import letterbox, to_nchw
from app.ml.registry import ModelRegistry, ModelSpec


class YoloOnnx:
    def __init__(
        self,
        registry: ModelRegistry,
        model_name: str,
        conf: float,
        iou: float,
        priority: list[str],
        class_conf: dict[str, float] | None = None,
    ) -> None:
        self.spec: ModelSpec = registry.get(model_name)
        self.conf = conf
        self.iou = iou
        self.class_conf = class_conf or {}
        self.session: Any
        self.providers: list[str]
        self.session, self.providers = create_session(self.spec.path, priority)
        self.input_name = str(self.session.get_inputs()[0].name)

    def _threshold(self, class_name: str) -> float:
        return float(self.class_conf.get(class_name, self.conf))

    def _input_wh(self) -> tuple[int, int]:
        shape = self.session.get_inputs()[0].shape
        height = shape[2] if len(shape) >= 3 and isinstance(shape[2], int) else self.spec.imgsz
        width = shape[3] if len(shape) >= 4 and isinstance(shape[3], int) else self.spec.imgsz
        return int(width), int(height)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        canvas, meta = letterbox(frame, self._input_wh())
        blob = to_nchw(canvas)
        outputs = self.session.run(None, {self.input_name: blob})
        conf_of: Callable[[str], float] = self._threshold
        return decode_yolo(
            outputs[0],
            meta,
            self.spec.classes or ["person"],
            self.conf,
            self.iou,
            conf_of,
        )


class YoloDetector(YoloOnnx):
    """Object detector. `detect(frame) -> list[Detection]`."""


class YoloPose(YoloOnnx):
    """Pose model. Detections include (17, 3) COCO keypoints when the export has them."""
