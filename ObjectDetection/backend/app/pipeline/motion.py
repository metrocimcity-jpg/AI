"""MOG2 motion at reduced width, with an optional polygon mask."""

from __future__ import annotations

import cv2
import numpy as np

from app.pipeline.base import FrameContext, MotionResult
from app.pipeline.zones import point_in_polygon


class MotionStage:
    name = "motion"
    enabled = True

    def __init__(self, width: int = 320, history: int = 300, var_threshold: float = 25, min_area: int = 400) -> None:
        self.width = width
        self.min_area = min_area
        self._sub = cv2.createBackgroundSubtractorMOG2(
            history=history, varThreshold=var_threshold, detectShadows=True
        )

    def process(self, ctx: FrameContext) -> FrameContext:
        frame = ctx.frame
        h, w = frame.shape[:2]
        scale = self.width / max(w, 1)
        small_h = max(1, int(h * scale))
        small = cv2.resize(frame, (self.width, small_h))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        mask = self._sub.apply(gray)
        mask[mask < 255] = 0
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        rois = [zone for zone in ctx.zones if zone.type in {"restricted", "motion", "yard"}]
        if rois:
            allowed = np.zeros_like(mask)
            for zone in rois:
                pts = np.array(
                    [[int(p[0] * self.width), int(p[1] * small_h)] for p in zone.polygon],
                    dtype=np.int32,
                )
                if len(pts) >= 3:
                    cv2.fillPoly(allowed, [pts], 255)
            mask = cv2.bitwise_and(mask, allowed)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regions: list[tuple[float, float, float, float]] = []
        area_sum = 0
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.min_area * scale * scale:
                continue
            x, y, bw, bh = cv2.boundingRect(contour)
            regions.append(
                (x / scale, y / scale, (x + bw) / scale, (y + bh) / scale)
            )
            area_sum += int(area)
        score = min(1.0, area_sum / float(mask.size or 1))
        ctx.motion = MotionResult(detected=bool(regions), score=score, regions=regions)
        return ctx


def region_hits_polygon(
    region: tuple[float, float, float, float], polygon: list[list[float]], width: int, height: int
) -> bool:
    cx = ((region[0] + region[2]) / 2) / max(width, 1)
    cy = ((region[1] + region[3]) / 2) / max(height, 1)
    return point_in_polygon(cx, cy, polygon)
