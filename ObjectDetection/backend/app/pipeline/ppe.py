"""Associate PPE boxes with a person using keypoint regions."""

from __future__ import annotations

from collections import defaultdict, deque

import numpy as np

from app.ml.postprocess import Detection

ITEMS = ("helmet", "vest", "gloves", "boots", "goggles", "harness")

_POSITIVE = {
    "helmet": {"helmet"},
    "vest": {"vest"},
    "gloves": {"gloves"},
    "boots": {"safety_boots"},
    "goggles": {"goggles"},
    "harness": {"harness"},
}
_NEGATIVE = {
    "helmet": {"no_helmet"},
    "vest": {"no_vest"},
    "gloves": {"no_gloves"},
    "boots": set(),
    "goggles": set(),
    "harness": set(),
}


def _area(box: tuple[float, float, float, float]) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def containment(det: tuple[float, float, float, float], region: tuple[float, float, float, float]) -> float:
    ix1, iy1 = max(det[0], region[0]), max(det[1], region[1])
    ix2, iy2 = min(det[2], region[2]), min(det[3], region[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    denom = _area(det)
    return inter / denom if denom > 0 else 0.0


def _visible_points(kps: np.ndarray, indexes: tuple[int, ...], conf: float) -> np.ndarray:
    pts = [kps[i, :2] for i in indexes if kps[i, 2] >= conf]
    if not pts:
        return np.zeros((0, 2))
    return np.stack(pts)


def _box_around(points: np.ndarray, pad: float) -> tuple[float, float, float, float] | None:
    if len(points) == 0:
        return None
    x1, y1 = points.min(axis=0)
    x2, y2 = points.max(axis=0)
    w = max(8.0, float(x2 - x1))
    h = max(8.0, float(y2 - y1))
    return (float(x1 - pad * w), float(y1 - pad * h), float(x2 + pad * w), float(y2 + pad * h))


def head_region(
    kps: np.ndarray, bbox: tuple[float, float, float, float], conf: float = 0.3
) -> tuple[tuple[float, float, float, float], bool]:
    pts = _visible_points(kps, (0, 1, 2, 3, 4), conf)
    if len(pts) == 0:
        x1, y1, x2, y2 = bbox
        height = y2 - y1
        # Face keypoints are hidden from behind. The hat still sits in the top of the box.
        return (x1, y1, x2, y1 + 0.42 * height), False
    shoulders = _visible_points(kps, (5, 6), conf)
    if len(shoulders) >= 2:
        span = abs(float(shoulders[0, 0] - shoulders[1, 0]))
    else:
        span = (bbox[2] - bbox[0]) * 0.4
    span = max(span, 8.0)
    cx, cy = float(pts[:, 0].mean()), float(pts[:, 1].mean())
    radius = 0.6 * span
    return (cx - radius, cy - 1.4 * radius, cx + radius, cy + 0.8 * radius), True


def torso_region(
    kps: np.ndarray, bbox: tuple[float, float, float, float], conf: float = 0.3
) -> tuple[tuple[float, float, float, float], bool]:
    pts = _visible_points(kps, (5, 6, 11, 12), conf)
    box = _box_around(pts, 0.15)
    if box is None:
        x1, y1, x2, y2 = bbox
        h = y2 - y1
        return (x1, y1 + 0.18 * h, x2, y1 + 0.62 * h), False
    return box, True


def _limb_regions(
    kps: np.ndarray,
    pairs: tuple[tuple[int, int], ...],
    conf: float,
    scale: float,
) -> tuple[list[tuple[float, float, float, float]], bool]:
    regions = []
    visible = False
    for joint, outer in pairs:
        if kps[joint, 2] < conf:
            continue
        visible = True
        length = 20.0
        if kps[outer, 2] >= conf:
            length = float(np.linalg.norm(kps[joint, :2] - kps[outer, :2]))
        length = max(12.0, length * scale)
        x, y = float(kps[joint, 0]), float(kps[joint, 1])
        regions.append((x - length, y - length, x + length, y + length))
    return regions, visible


def hand_regions(
    kps: np.ndarray, conf: float = 0.3
) -> tuple[list[tuple[float, float, float, float]], bool]:
    return _limb_regions(kps, ((9, 7), (10, 8)), conf, 0.25)


def foot_regions(
    kps: np.ndarray, conf: float = 0.3
) -> tuple[list[tuple[float, float, float, float]], bool]:
    return _limb_regions(kps, ((15, 13), (16, 14)), conf, 0.3)


def _center_in(det: Detection, region: tuple[float, float, float, float]) -> bool:
    x1, y1, x2, y2 = det.bbox_xyxy
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    return region[0] <= cx <= region[2] and region[1] <= cy <= region[3]


def _matches(det: Detection, regions: list[tuple[float, float, float, float]], threshold: float) -> bool:
    return any(
        containment(det.bbox_xyxy, region) >= threshold or _center_in(det, region) for region in regions
    )


def associate_ppe(
    keypoints: np.ndarray,
    bbox: tuple[float, float, float, float],
    detections: list[Detection],
    containment_threshold: float = 0.5,
    conf: float = 0.3,
) -> tuple[dict[str, str], dict[str, bool]]:
    """Return instant status and whether each body region is visible.

    Status is ok, missing (negative class), absent (region visible, no box), or unknown.
    """
    kps = np.asarray(keypoints, dtype=np.float64)
    head, head_ok = head_region(kps, bbox, conf)
    torso, torso_ok = torso_region(kps, bbox, conf)
    hands, hands_ok = hand_regions(kps, conf)
    feet, feet_ok = foot_regions(kps, conf)
    regions = {
        "head": ([head], head_ok),
        "torso": ([torso], torso_ok),
        "hands": (hands, hands_ok),
        "feet": (feet, feet_ok),
    }
    x1, y1, x2, y2 = bbox
    height = max(1.0, y2 - y1)
    # Keep a geometric head and body band so a back-view hat and vest still attach.
    regions["head"][0].append((x1, y1, x2, y1 + 0.45 * height))
    regions["torso"][0].append((x1, y1 + 0.15 * height, x2, y2))
    part = {
        "helmet": "head",
        "goggles": "head",
        "vest": "torso",
        "harness": "torso",
        "gloves": "hands",
        "boots": "feet",
    }
    status: dict[str, str] = {}
    visible: dict[str, bool] = {}
    for item in ITEMS:
        boxes, is_visible = regions[part[item]]
        visible[item] = is_visible
        positive = False
        negative = False
        for det in detections:
            if not _matches(det, boxes, containment_threshold):
                continue
            if det.class_name in _POSITIVE[item]:
                positive = True
            elif det.class_name in _NEGATIVE[item]:
                negative = True
        if positive:
            # A seen helmet or vest counts even when the face keypoints are hidden.
            status[item] = "ok"
            visible[item] = True
        elif not is_visible:
            status[item] = "unknown"
        elif negative:
            status[item] = "missing"
        else:
            status[item] = "absent"
    return status, visible


class PPEVoter:
    """Raise `missing` only after the vote window agrees."""

    def __init__(self, window: int = 15) -> None:
        self.window = window
        self._hist: dict[tuple[int, str], deque[str]] = defaultdict(lambda: deque(maxlen=window))

    def update(
        self, track_id: int, instant: dict[str, str], visible: dict[str, bool]
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        for item, value in instant.items():
            votes = self._hist[(track_id, item)]
            votes.append(value)
            ok_count = votes.count("ok")
            missing_count = votes.count("missing")
            if ok_count >= 1 and ok_count >= missing_count:
                # A seen helmet or vest stays until a missing vote overtakes it.
                if ok_count >= min(3, self.window) or value == "ok":
                    result[item] = "ok"
                    continue
            full = len(votes) >= self.window
            no_positive = ok_count == 0
            if visible.get(item) and no_positive and full and (
                missing_count > 0 or votes.count("absent") >= self.window
            ):
                result[item] = "missing"
            elif value == "unknown":
                result[item] = "unknown"
            else:
                result[item] = "unknown" if not full else value if value != "absent" else "unknown"
        return result

    def drop(self, track_id: int) -> None:
        stale = [key for key in self._hist if key[0] == track_id]
        for key in stale:
            del self._hist[key]
