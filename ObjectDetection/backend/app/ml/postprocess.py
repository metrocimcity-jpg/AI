"""Decode YOLO-style ONNX outputs and run class-wise NMS."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from app.ml.preprocess import LetterboxMeta, unletterbox_point, unletterbox_xyxy


@dataclass
class Detection:
    bbox_xyxy: tuple[float, float, float, float]
    score: float
    class_id: int
    class_name: str
    keypoints: np.ndarray | None = None


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def non_max_suppression(detections: list[Detection], iou_threshold: float) -> list[Detection]:
    grouped: dict[int, list[Detection]] = {}
    for det in detections:
        grouped.setdefault(det.class_id, []).append(det)
    kept: list[Detection] = []
    for group in grouped.values():
        order = sorted(group, key=lambda item: item.score, reverse=True)
        while order:
            current = order.pop(0)
            kept.append(current)
            order = [
                item for item in order if _iou(current.bbox_xyxy, item.bbox_xyxy) < iou_threshold
            ]
    kept.sort(key=lambda item: item.score, reverse=True)
    return kept


def _as_rows(output: np.ndarray) -> np.ndarray:
    pred = np.squeeze(np.asarray(output))
    if pred.ndim == 1:
        pred = pred.reshape(1, -1)
    if pred.ndim != 2:
        raise ValueError(f"unexpected YOLO output shape {pred.shape}")
    # (C, N) with C small and N large -> (N, C)
    if pred.shape[0] < pred.shape[1] and pred.shape[0] <= 512:
        pred = pred.T
    return pred.astype(np.float32, copy=False)


def decode_yolo(
    output: np.ndarray,
    meta: LetterboxMeta,
    classes: list[str],
    conf: float,
    iou: float,
    conf_of: Callable[[str], float] | None = None,
) -> list[Detection]:
    rows = _as_rows(output)
    class_count = max(1, len(classes))
    detections: list[Detection] = []
    for row in rows:
        if row.shape[0] < 4 + class_count:
            continue
        scores = row[4 : 4 + class_count]
        class_id = int(np.argmax(scores))
        score = float(scores[class_id])
        class_name = classes[class_id] if class_id < len(classes) else f"class_{class_id}"
        threshold = conf_of(class_name) if conf_of else conf
        if score < threshold:
            continue
        cx, cy, bw, bh = (float(v) for v in row[:4])
        # Some exports are normalized 0-1.
        if max(cx, cy, bw, bh) <= 1.5:
            cx *= meta.in_w
            cy *= meta.in_h
            bw *= meta.in_w
            bh *= meta.in_h
        x1, y1, x2, y2 = unletterbox_xyxy(cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2, meta)
        keypoints = None
        kpt_start = 4 + class_count
        if row.shape[0] >= kpt_start + 51:
            raw = row[kpt_start : kpt_start + 51].reshape(17, 3).copy()
            if float(np.max(raw[:, :2])) <= 1.5:
                raw[:, 0] *= meta.in_w
                raw[:, 1] *= meta.in_h
            for index in range(17):
                px, py = unletterbox_point(float(raw[index, 0]), float(raw[index, 1]), meta)
                raw[index, 0] = px
                raw[index, 1] = py
            keypoints = raw
        detections.append(
            Detection((x1, y1, x2, y2), score, class_id, class_name, keypoints)
        )
    return non_max_suppression(detections, iou)
