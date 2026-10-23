"""Posture from COCO-17 keypoints, with majority vote and dwell time."""

from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field

import numpy as np

from app.pipeline.base import PostureState

NOSE = 0
L_SHOULDER, R_SHOULDER = 5, 6
L_ELBOW, R_ELBOW = 7, 8
L_WRIST, R_WRIST = 9, 10
L_HIP, R_HIP = 11, 12
L_KNEE, R_KNEE = 13, 14
L_ANKLE, R_ANKLE = 15, 16

DEFAULTS: dict = {
    "min_visible_keypoints": 8,
    "keypoint_conf": 0.3,
    "lying": {"torso_angle_gt": 65, "aspect_lt": 0.9, "speed_lt": 0.15},
    "crawling": {
        "torso_angle_min": 50,
        "torso_angle_max": 90,
        "limb_y_gt": 0.6,
        "speed_gt": 0.05,
    },
    "sitting": {
        "hip_knee_dy_lt": 0.12,
        "knee_angle_min": 60,
        "knee_angle_max": 130,
        "torso_angle_lt": 35,
        "speed_lt": 0.1,
    },
    "crouching": {"knee_angle_lt": 100, "hip_ankle_dy_lt": 0.35, "torso_angle_lt": 50},
    "bending": {"torso_angle_min": 35, "torso_angle_max": 65, "knee_angle_gt": 140},
    "climbing": {"vertical_speed_gt": 0.05},
    "walking": {"torso_angle_lt": 25, "speed_gte": 0.12},
    "standing": {"torso_angle_lt": 25, "knee_angle_gt": 150, "speed_lt": 0.12},
    "smoothing": {
        "window": 10,
        "min_dwell_ms": 800,
        "lying_dwell_ms": 1500,
        "crawling_dwell_ms": 1500,
        "fall_window_s": 1.0,
        "fall_downward_speed": 0.35,
        "lying_alert_seconds": 3.0,
    },
}

SKELETON = (
    (5, 6),
    (5, 7),
    (7, 9),
    (6, 8),
    (8, 10),
    (5, 11),
    (6, 12),
    (11, 12),
    (11, 13),
    (13, 15),
    (12, 14),
    (14, 16),
    (0, 1),
    (0, 2),
    (1, 3),
    (2, 4),
    (0, 5),
    (0, 6),
)


def merge_posture_cfg(cfg: dict | None) -> dict:
    merged = {key: (dict(value) if isinstance(value, dict) else value) for key, value in DEFAULTS.items()}
    for key, value in (cfg or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **value}
        else:
            merged[key] = value
    return merged


def _angle_with_vertical(vec: np.ndarray) -> float:
    norm = float(np.linalg.norm(vec))
    if norm < 1e-6:
        return 0.0
    cosine = float(np.clip(vec[1] / norm, -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def _joint_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    ba = a - b
    bc = c - b
    na = float(np.linalg.norm(ba))
    nc = float(np.linalg.norm(bc))
    if na < 1e-6 or nc < 1e-6:
        return 180.0
    cosine = float(np.clip(np.dot(ba, bc) / (na * nc), -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def _mid(kps: np.ndarray, i: int, j: int, visible: np.ndarray) -> np.ndarray | None:
    points = []
    if visible[i]:
        points.append(kps[i, :2])
    if visible[j]:
        points.append(kps[j, :2])
    if not points:
        return None
    return np.mean(np.stack(points), axis=0)


def _mean_knee(kps: np.ndarray, visible: np.ndarray) -> float | None:
    angles = []
    for hip, knee, ankle in ((L_HIP, L_KNEE, L_ANKLE), (R_HIP, R_KNEE, R_ANKLE)):
        if visible[hip] and visible[knee] and visible[ankle]:
            angles.append(_joint_angle(kps[hip, :2], kps[knee, :2], kps[ankle, :2]))
    if not angles:
        return None
    return float(np.mean(angles))


def _wrists_above(kps: np.ndarray, visible: np.ndarray) -> bool:
    for shoulder, wrist in ((L_SHOULDER, L_WRIST), (R_SHOULDER, R_WRIST)):
        if visible[shoulder] and visible[wrist] and kps[wrist, 1] < kps[shoulder, 1] - 2:
            return True
    return False


def classify_posture(
    keypoints: np.ndarray,
    bbox: tuple[float, float, float, float],
    speed: float = 0.0,
    vertical_speed: float = 0.0,
    in_climb_zone: bool = False,
    near_scaffold: bool = False,
    cfg: dict | None = None,
) -> str:
    options = merge_posture_cfg(cfg)
    conf = float(options["keypoint_conf"])
    kps = np.asarray(keypoints, dtype=np.float64)
    if kps.shape != (17, 3):
        return "unknown"
    visible = kps[:, 2] >= conf
    if int(visible.sum()) < int(options["min_visible_keypoints"]):
        return "unknown"
    x1, y1, x2, y2 = bbox
    width = max(1.0, x2 - x1)
    height = max(1.0, y2 - y1)
    aspect = height / width
    shoulders = _mid(kps, L_SHOULDER, R_SHOULDER, visible)
    hips = _mid(kps, L_HIP, R_HIP, visible)
    if shoulders is None or hips is None:
        return "unknown"
    torso_angle = _angle_with_vertical(hips - shoulders)
    knee_angle = _mean_knee(kps, visible)
    knee_ys = [float(kps[i, 1]) for i in (L_KNEE, R_KNEE) if visible[i]]
    hip_y = float(hips[1])
    hip_knee_dy = ((float(np.mean(knee_ys)) - hip_y) / height) if knee_ys else 1.0
    ankle_ys = [float(kps[i, 1]) for i in (L_ANKLE, R_ANKLE) if visible[i]]
    hip_ankle_dy = (abs(float(np.mean(ankle_ys)) - hip_y) / height) if ankle_ys else 1.0
    head_below_hip = bool(visible[NOSE] and kps[NOSE, 1] > hip_y)

    lying = options["lying"]
    horizontal = torso_angle > lying["torso_angle_gt"]
    if (horizontal and aspect < lying["aspect_lt"] and speed < lying["speed_lt"]) or (
        head_below_hip and horizontal
    ):
        return "lying"

    crawl = options["crawling"]
    wrist_ys = [float(kps[i, 1]) for i in (L_WRIST, R_WRIST) if visible[i]]
    knees_low = bool(knee_ys) and min(knee_ys) > y1 + crawl["limb_y_gt"] * height
    wrists_low = bool(wrist_ys) and min(wrist_ys) > y1 + crawl["limb_y_gt"] * height
    if (
        crawl["torso_angle_min"] <= torso_angle <= crawl["torso_angle_max"]
        and wrists_low
        and knees_low
        and speed > crawl["speed_gt"]
    ):
        return "crawling"

    sit = options["sitting"]
    if (
        knee_angle is not None
        and abs(hip_knee_dy) < sit["hip_knee_dy_lt"]
        and sit["knee_angle_min"] <= knee_angle <= sit["knee_angle_max"]
        and torso_angle < sit["torso_angle_lt"]
        and speed < sit["speed_lt"]
    ):
        return "sitting"

    crouch = options["crouching"]
    if (
        knee_angle is not None
        and knee_angle < crouch["knee_angle_lt"]
        and hip_ankle_dy < crouch["hip_ankle_dy_lt"]
        and torso_angle < crouch["torso_angle_lt"]
    ):
        return "crouching"

    bend = options["bending"]
    if (
        knee_angle is not None
        and bend["torso_angle_min"] <= torso_angle <= bend["torso_angle_max"]
        and knee_angle > bend["knee_angle_gt"]
    ):
        return "bending"

    if (
        torso_angle < options["walking"]["torso_angle_lt"]
        and _wrists_above(kps, visible)
        and vertical_speed > options["climbing"]["vertical_speed_gt"]
        and (in_climb_zone or near_scaffold)
    ):
        return "climbing"

    walk = options["walking"]
    if torso_angle < walk["torso_angle_lt"] and speed >= walk["speed_gte"]:
        return "walking"

    stand = options["standing"]
    if (
        knee_angle is not None
        and torso_angle < stand["torso_angle_lt"]
        and knee_angle > stand["knee_angle_gt"]
        and speed < stand["speed_lt"]
    ):
        return "standing"
    return "unknown"


def _majority(window: deque[str]) -> str:
    counts = Counter(window)
    best = max(counts.values())
    for label in reversed(window):
        if counts[label] == best:
            return label
    return window[-1]


@dataclass
class PostureSmoother:
    cfg: dict = field(default_factory=dict)
    state: str = "unknown"
    state_since: float = 0.0
    pending: str | None = None
    pending_since: float = 0.0
    fall_sent: bool = False
    man_down_sent: bool = False
    started: bool = False
    window: deque[str] = field(init=False)

    def __post_init__(self) -> None:
        size = int(merge_posture_cfg(self.cfg)["smoothing"]["window"])
        self.window = deque(maxlen=size)

    def update(self, raw: str, ts: float, downward_speed: float = 0.0) -> PostureState:
        smoothing = merge_posture_cfg(self.cfg)["smoothing"]
        self.window.append(raw)
        voted = _majority(self.window)
        transition: str | None = None
        fall = False
        man_down = False
        if not self.started:
            self.state_since = ts
            self.started = True
        if voted != self.state:
            if self.pending != voted:
                self.pending = voted
                self.pending_since = ts
            elapsed = ts - self.pending_since
            dwell_ms = float(smoothing["min_dwell_ms"])
            if voted == "lying":
                dwell_ms = float(smoothing["lying_dwell_ms"])
            elif voted == "crawling":
                dwell_ms = float(smoothing["crawling_dwell_ms"])
            fast_fall = (
                self.state in {"standing", "walking", "climbing"}
                and voted == "lying"
                and downward_speed >= float(smoothing["fall_downward_speed"])
                and elapsed <= float(smoothing["fall_window_s"])
            )
            if fast_fall or elapsed * 1000 >= dwell_ms:
                transition = f"{self.state}->{voted}"
                if fast_fall:
                    fall = True
                    self.fall_sent = True
                self.state = voted
                self.state_since = ts
                self.pending = None
                if voted != "lying":
                    self.fall_sent = False
                    self.man_down_sent = False
        else:
            self.pending = None
        duration = max(0.0, ts - self.state_since)
        if (
            self.state == "lying"
            and not self.fall_sent
            and not self.man_down_sent
            and duration > float(smoothing["lying_alert_seconds"])
        ):
            man_down = True
            self.man_down_sent = True
        return PostureState(
            state=self.state,
            since=self.state_since,
            raw=raw,
            transition=transition,
            duration_s=duration,
            fall=fall,
            man_down=man_down,
        )


def posture_event_types(state: PostureState) -> list[str]:
    names: list[str] = []
    if state.fall:
        names.append("fall_detected")
    if state.man_down:
        names.append("man_down")
    return names
