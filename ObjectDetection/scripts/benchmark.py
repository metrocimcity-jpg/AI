"""Per-stage latency on a local video. Never downloads weights."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import load_config  # noqa: E402
from app.ml.registry import ModelError, ModelRegistry  # noqa: E402
from app.ml.yolo import YoloDetector, YoloPose  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Benchmark local ONNX models on a video file")
    parser.add_argument("--video", required=True)
    parser.add_argument("--frames", type=int, default=30)
    args = parser.parse_args(argv)
    video = Path(args.video)
    if not video.is_file():
        print(f"Video not found: {video}")
        return 1
    config = load_config(ROOT)
    registry = ModelRegistry(ROOT)
    priority = list((config.raw.get("runtime") or {}).get("provider_priority") or ["cpu"])
    try:
        person = YoloDetector(registry, "person_yolo", 0.35, 0.5, priority)
        pose = YoloPose(registry, "pose_yolo", 0.35, 0.5, priority)
    except ModelError as exc:
        print(exc)
        return 1
    import cv2

    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        print(f"Cannot open video: {video}")
        return 1
    frames = 0
    person_ms = 0.0
    pose_ms = 0.0
    while frames < args.frames:
        ok, frame = cap.read()
        if not ok:
            break
        t0 = time.perf_counter()
        person.detect(frame)
        t1 = time.perf_counter()
        pose.detect(frame)
        t2 = time.perf_counter()
        person_ms += (t1 - t0) * 1000
        pose_ms += (t2 - t1) * 1000
        frames += 1
    cap.release()
    if frames == 0:
        print("No frames decoded")
        return 1
    total = person_ms + pose_ms
    fps = 1000 / (total / frames) if total else 0
    print(f"frames={frames}")
    print(f"person_ms={person_ms / frames:.1f}")
    print(f"pose_ms={pose_ms / frames:.1f}")
    print(f"fps={fps:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
