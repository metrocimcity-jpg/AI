"""Letterbox, NMS, registry errors, and tracker identity."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.ml.postprocess import Detection, decode_yolo, non_max_suppression
from app.ml.preprocess import LetterboxMeta, letterbox
from app.ml.providers import select_providers
from app.ml.registry import ModelHashError, ModelMissingError, ModelRegistry
from app.pipeline.tracker import ByteTrack


def test_letterbox_is_square() -> None:
    image = np.zeros((180, 320, 3), dtype=np.uint8)
    canvas, meta = letterbox(image, 64)
    assert canvas.shape == (64, 64, 3)
    assert meta.scale > 0


def test_decode_and_nms() -> None:
    meta = LetterboxMeta(scale=1, pad_x=0, pad_y=0, orig_w=640, orig_h=640, size=640)
    pred = np.zeros((1, 5, 8), dtype=np.float32)
    pred[0, :, 0] = (100, 100, 40, 80, 0.9)
    pred[0, :, 1] = (102, 100, 40, 80, 0.2)
    found = decode_yolo(pred, meta, ["person"], 0.35, 0.5)
    assert len(found) == 1
    assert found[0].class_name == "person"
    dup = [
        Detection((0, 0, 10, 10), 0.9, 0, "person"),
        Detection((1, 1, 11, 11), 0.4, 0, "person"),
        Detection((50, 50, 70, 70), 0.8, 1, "helmet"),
    ]
    kept = non_max_suppression(dup, 0.5)
    assert len(kept) == 2


def test_provider_order_falls_back_to_cpu() -> None:
    chosen = select_providers(["tensorrt", "cuda", "cpu"], ["CPUExecutionProvider"])
    assert chosen == ["CPUExecutionProvider"]


def test_registry_missing_and_hash(tmp_path: Path) -> None:
    models = tmp_path / "models"
    models.mkdir()
    weights = models / "tiny.onnx"
    weights.write_bytes(b"not-a-real-model")
    manifest = {
        "person_yolo": {
            "path": "tiny.onnx",
            "sha256": "0" * 64,
            "task": "detect",
            "imgsz": 32,
            "classes": ["person"],
            "license": "test",
        }
    }
    (models / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    registry = ModelRegistry(tmp_path, models / "manifest.json")
    with pytest.raises(ModelHashError):
        registry.get("person_yolo")
    manifest["person_yolo"]["path"] = "missing.onnx"
    manifest["person_yolo"]["sha256"] = ""
    (models / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    registry.reload()
    with pytest.raises(ModelMissingError) as caught:
        registry.get("person_yolo")
    assert "never downloads" in str(caught.value)


def test_track_ids_stay_stable() -> None:
    tracker = ByteTrack()
    first = tracker.update([Detection((0, 0, 20, 80), 0.9, 0, "person")], 0.0)
    second = tracker.update([Detection((2, 1, 22, 81), 0.91, 0, "person")], 0.1)
    assert first[0].id == second[0].id
    assert second[0].speed >= 0
