"""PPE association, the safe rule language, and point-in-polygon."""

from __future__ import annotations

from datetime import datetime

import numpy as np

from app.ml.postprocess import Detection
from app.pipeline.base import FrameContext, Track
from app.pipeline.ppe import associate_ppe, head_region
from app.pipeline.rules import ExprError, RuleEngine, SafeExpr
from app.pipeline.zones import point_in_polygon, schedule_is_closed


def _person() -> tuple[np.ndarray, tuple[float, float, float, float]]:
    kps = np.zeros((17, 3))
    pairs = {
        0: (50, 20),
        5: (30, 40),
        6: (70, 40),
        7: (28, 70),
        8: (72, 70),
        9: (26, 100),
        10: (74, 100),
        11: (36, 110),
        12: (64, 110),
        13: (36, 150),
        14: (64, 150),
        15: (36, 190),
        16: (64, 190),
    }
    for index, (x, y) in pairs.items():
        kps[index] = (x, y, 0.95)
    return kps, (10, 0, 90, 200)


def test_helmet_association() -> None:
    kps, bbox = _person()
    region, visible = head_region(kps, bbox)
    assert visible
    helmet = Detection(
        (region[0] + 1, region[1] + 1, region[2] - 1, region[3] - 1),
        0.9,
        0,
        "helmet",
    )
    bare = Detection(
        (region[0] + 1, region[1] + 1, region[2] - 1, region[3] - 1),
        0.9,
        1,
        "no_helmet",
    )
    far = Detection((400, 400, 420, 420), 0.9, 0, "helmet")
    ok, vis = associate_ppe(kps, bbox, [helmet])
    missing, _ = associate_ppe(kps, bbox, [bare])
    absent, _ = associate_ppe(kps, bbox, [far])
    assert ok["helmet"] == "ok"
    assert vis["helmet"] is True
    assert missing["helmet"] == "missing"
    assert absent["helmet"] == "absent"


def test_hidden_face_still_counts_helmet() -> None:
    kps = np.zeros((17, 3))
    bbox = (10, 0, 90, 200)
    region, visible = head_region(kps, bbox)
    assert visible is False
    helmet = Detection((region[0] + 4, region[1] + 4, region[2] - 4, 30), 0.9, 0, "helmet")
    status, seen = associate_ppe(kps, bbox, [helmet])
    assert status["helmet"] == "ok"
    assert seen["helmet"] is True
    hidden, _ = associate_ppe(kps, bbox, [])
    assert hidden["helmet"] == "unknown"


def test_cropped_worker_counts_helmet_and_vest() -> None:
    kps = np.zeros((17, 3))
    bbox = (808, 525, 1198, 1069)
    vest = Detection((837, 741, 1197, 1079), 0.89, 7, "vest")
    helmet = Detection((895, 527, 1098, 696), 0.86, 0, "helmet")
    status, _seen = associate_ppe(kps, bbox, [vest, helmet])
    assert status["helmet"] == "ok"
    assert status["vest"] == "ok"


def test_occluded_head_is_unknown() -> None:
    kps, bbox = _person()
    kps[0, 2] = 0
    status, visible = associate_ppe(kps, bbox, [])
    assert visible["helmet"] is False
    assert status["helmet"] == "unknown"


def test_safe_expr_rejects_private_access() -> None:
    try:
        SafeExpr("person.__class__").eval({"person": object()})
    except ExprError:
        return
    raise AssertionError("private access should fail")


def test_rule_table() -> None:
    root = __import__("app.core.config", fromlist=["project_root"]).project_root()
    engine = RuleEngine.from_yaml(str(root / "config" / "rules.yaml"), ["cement_bag"])
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    ctx = FrameContext("cam", 10.0, frame, width=100, height=100)
    ctx.motion = type("M", (), {"detected": True, "score": 0.4, "regions": []})()
    # Closed schedule is injected by the caller. Motion-after-hours is a scene rule.
    drafts = engine.evaluate(ctx, closed=True)
    assert any(item.event_type == "motion_after_hours" for item in drafts)
    again = engine.evaluate(ctx, closed=True)
    assert not any(item.event_type == "motion_after_hours" for item in again)


def test_polygon_and_overnight_schedule() -> None:
    square = [[0, 0], [1, 0], [1, 1], [0, 1]]
    assert point_in_polygon(0.5, 0.5, square)
    assert not point_in_polygon(1.5, 0.5, square)
    noon = datetime(2026, 6, 1, 12, 0)
    night = datetime(2026, 6, 1, 22, 0)
    early = datetime(2026, 6, 1, 5, 0)
    schedule = {"closed": ["18:00-06:00"]}
    assert not schedule_is_closed(schedule, noon)
    assert schedule_is_closed(schedule, night)
    assert schedule_is_closed(schedule, early)


def test_person_rule_min_duration(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    engine = RuleEngine(
        rules=[
            {
                "id": "no_helmet",
                "severity": "critical",
                "when": 'person.ppe.helmet == "missing"',
                "min_duration_s": 2,
                "cooldown_s": 60,
                "message": "Worker without helmet",
            }
        ],
        material_names=[],
    )
    frame = np.zeros((50, 50, 3), dtype=np.uint8)
    ctx = FrameContext("cam", 0.0, frame, width=50, height=50)
    ctx.tracks = [Track(id=7, bbox=(10, 10, 40, 40), score=0.9)]
    ctx.ppe = {7: {"helmet": "missing", "vest": "ok"}}
    assert engine.evaluate(ctx, closed=False) == []
    ctx.ts = 3
    found = engine.evaluate(ctx, closed=False)
    assert found and found[0].event_type == "no_helmet"
    assert found[0].track_id == 7
