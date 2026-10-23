"""Person detector stage. A missing ONNX file disables the stage with a clear log."""

from __future__ import annotations

from app.core.logging import get_logger
from app.ml.registry import ModelError, ModelRegistry
from app.ml.yolo import YoloDetector
from app.pipeline.base import FrameContext

logger = get_logger("siteguard.pipeline.person")


class PersonStage:
    name = "person"
    enabled = True

    def __init__(
        self,
        registry: ModelRegistry,
        model_name: str,
        conf: float,
        iou: float,
        priority: list[str],
    ) -> None:
        self.registry = registry
        self.model_name = model_name
        self.conf = conf
        self.iou = iou
        self.priority = priority
        self._model: YoloDetector | None = None
        self.failed = False

    def process(self, ctx: FrameContext) -> FrameContext:
        if self.failed:
            return ctx
        try:
            if self._model is None:
                self._model = YoloDetector(
                    self.registry, self.model_name, self.conf, self.iou, self.priority
                )
                logger.info(
                    "person model %s on %s", self.model_name, ",".join(self._model.providers)
                )
            found = self._model.detect(ctx.frame)
            classes = set(self._model.spec.classes)
            if "person" in classes:
                ctx.persons = [det for det in found if det.class_name == "person"]
            else:
                ctx.persons = found
        except ModelError as exc:
            self.failed = True
            logger.error("%s", exc)
        return ctx
