"""Synthetic keypoints for every posture, plus fall and man-down timing."""

from __future__ import annotations

import numpy as np

from app.pipeline.posture import PostureSmoother, classify_posture


def skeleton(points: dict[int, tuple[float, float]]) -> np.ndarray:
    arr = np.zeros((17, 3), dtype=np.float64)
    for index, (x, y) in points.items():
        arr[index] = (x, y, 0.95)
    return arr


def upright(wrist_y: float = 120) -> dict[int, tuple[float, float]]:
    return {
        0: (40, 20),
        1: (35, 22),
        2: (45, 22),
        3: (30, 24),
        4: (50, 24),
        5: (25, 50),
        6: (55, 50),
        7: (22, 90),
        8: (58, 90),
        9: (20, wrist_y),
        10: (60, wrist_y),
        11: (30, 110),
        12: (50, 110),
        13: (30, 155),
        14: (50, 155),
        15: (30, 190),
        16: (50, 190),
    }


def test_standing_and_walking() -> None:
    bbox = (0, 0, 80, 200)
    assert classify_posture(skeleton(upright()), bbox, speed=0.0) == "standing"
    assert classify_posture(skeleton(upright()), bbox, speed=0.3) == "walking"


def test_sitting() -> None:
    points = {
        0: (70, 30),
        1: (64, 32),
        2: (76, 32),
        3: (58, 34),
        4: (82, 34),
        5: (50, 40),
        6: (90, 40),
        7: (45, 70),
        8: (95, 70),
        9: (40, 95),
        10: (100, 95),
        11: (40, 90),
        12: (80, 90),
        13: (110, 92),
        14: (130, 92),
        15: (100, 150),
        16: (120, 150),
    }
    assert classify_posture(skeleton(points), (0, 0, 140, 160), speed=0.0) == "sitting"


def test_crouching() -> None:
    points = upright()
    points[13] = (30, 145)
    points[14] = (70, 145)
    points[15] = (45, 120)
    points[16] = (75, 125)
    assert classify_posture(skeleton(points), (0, 0, 100, 180), speed=0.0) == "crouching"


def test_bending() -> None:
    points = {
        0: (40, 40),
        1: (36, 42),
        2: (44, 42),
        3: (32, 44),
        4: (48, 44),
        5: (30, 50),
        6: (50, 50),
        7: (28, 90),
        8: (52, 90),
        9: (26, 120),
        10: (54, 120),
        11: (100, 110),
        12: (120, 110),
        13: (100, 160),
        14: (120, 160),
        15: (100, 195),
        16: (120, 195),
    }
    assert classify_posture(skeleton(points), (0, 0, 160, 200), speed=0.0) == "bending"


def test_lying() -> None:
    points = {
        0: (30, 25),
        1: (28, 24),
        2: (34, 24),
        3: (24, 26),
        4: (38, 26),
        5: (40, 30),
        6: (50, 30),
        7: (70, 32),
        8: (80, 32),
        9: (90, 34),
        10: (100, 34),
        11: (160, 40),
        12: (170, 40),
        13: (180, 48),
        14: (190, 48),
        15: (200, 55),
        16: (210, 55),
    }
    assert classify_posture(skeleton(points), (0, 0, 220, 80), speed=0.0) == "lying"


def test_crawling() -> None:
    points = {
        0: (45, 20),
        1: (42, 18),
        2: (48, 18),
        3: (40, 22),
        4: (52, 22),
        5: (40, 28),
        6: (55, 28),
        7: (50, 50),
        8: (70, 50),
        9: (60, 70),
        10: (80, 70),
        11: (150, 50),
        12: (165, 50),
        13: (155, 72),
        14: (170, 72),
        15: (160, 78),
        16: (175, 78),
    }
    assert classify_posture(skeleton(points), (0, 0, 220, 90), speed=0.4) == "crawling"


def test_climbing() -> None:
    points = upright(wrist_y=30)
    points[7] = (22, 40)
    points[8] = (58, 40)
    label = classify_posture(
        skeleton(points),
        (0, 0, 80, 200),
        speed=0.02,
        vertical_speed=0.4,
        in_climb_zone=True,
    )
    assert label == "climbing"


def test_unknown_when_too_few_keypoints() -> None:
    kps = np.zeros((17, 3))
    kps[0] = (1, 1, 0.9)
    kps[5] = (1, 2, 0.9)
    assert classify_posture(kps, (0, 0, 10, 20)) == "unknown"


def test_fall_bypasses_dwell() -> None:
    smoother = PostureSmoother()
    ts = 0.0
    for _ in range(10):
        smoother.update("standing", ts)
        ts += 0.1
    assert smoother.state == "standing"
    saw_fall = False
    for _ in range(8):
        state = smoother.update("lying", ts, downward_speed=1.2)
        saw_fall = saw_fall or state.fall
        ts += 0.05
    assert saw_fall
    assert smoother.state == "lying"


def test_man_down_after_three_seconds() -> None:
    smoother = PostureSmoother()
    ts = 0.0
    for _ in range(10):
        smoother.update("standing", ts)
        ts += 0.1
    saw = False
    state = smoother.update("lying", ts, downward_speed=0.0)
    for _ in range(40):
        ts += 0.2
        state = smoother.update("lying", ts, downward_speed=0.0)
        saw = saw or state.man_down
    assert smoother.state == "lying"
    assert saw
