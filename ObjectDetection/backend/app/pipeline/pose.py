"""Pose stage. Keypoints are matched to tracks by box IoU."""

from __future__ import annotations

from app.core.logging import get_logger
from app.ml.registry import ModelError, ModelRegistry
from app.ml.yolo import YoloPose
from app.pipeline.base import FrameContext
from app.pipeline.tracker import iou

logger = get_logger("siteguard.pipeline.pose")


class PoseStage:
    name = "pose"
    enabled = True

    def __init__(
        self,
        registry: ModelRegistry,
        model_name: str,
        conf: float,
        iou_thr: float,
        priority: list[str],
    ) -> None:
        self.registry = registry
        self.model_name = model_name
        self.conf = conf
        self.iou_thr = iou_thr
        self.priority = priority
        self._model: YoloPose | None = None
        self.failed = False

    def process(self, ctx: FrameContext) -> FrameContext:
        if self.failed or not ctx.tracks:
            return ctx
        try:
            if self._model is None:
                self._model = YoloPose(
                    self.registry, self.model_name, self.conf, self.iou_thr, self.priority
                )
            found = self._model.detect(ctx.frame)
        except ModelError as exc:
            self.failed = True
            logger.error("%s", exc)
            return ctx
        poses: dict[int, object] = {}
        for track in ctx.tracks:
            best = None
            best_iou = 0.3
            for det in found:
                if det.keypoints is None:
                    continue
                overlap = iou(track.bbox, det.bbox_xyxy)
                if overlap > best_iou:
                    best_iou = overlap
                    best = det.keypoints
            if best is not None:
                poses[track.id] = best
        ctx.poses = poses  # type: ignore[assignment]
        return ctx
