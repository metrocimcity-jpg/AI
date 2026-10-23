# 03 — Model Selection (all run offline)

All weights are copied into `models/` once (on a connected machine), then the app never touches the internet. Export to **ONNX** (and optionally OpenVINO/TensorRT engines) and register in `models/manifest.json`.

## 1. Recommended stack

| Task | Primary (best accuracy/speed) | Permissive-license alternative | Notes |
|---|---|---|---|
| Person detection | **YOLO11s/m** (Ultralytics, COCO `person`) | **RT-DETR-R18/R50** (Apache-2.0), **RF-DETR** (Apache-2.0), **YOLOX-s/m** (Apache-2.0) | Pretrained COCO is enough for MVP |
| Tracking | **ByteTrack** (or BoT-SORT with ReID in crowded scenes) | same (algorithms are permissive) | Use `supervision`'s ByteTrack or own implementation to avoid Ultralytics runtime dep |
| Pose / keypoints | **YOLO11-pose (n/s/m)** | **RTMPose-s/m (MMPose, Apache-2.0)** via ONNX, MoveNet/Lightning | 17 COCO keypoints; RTMPose is excellent and permissive |
| PPE detection | **Fine-tuned YOLO11s** | Fine-tuned RT-DETR / YOLOX-s | Classes in `04-CLASSES-AND-RULES.md` |
| Materials & machinery | **Fine-tuned YOLO11m** (small objects, many instances) | RT-DETR / YOLOX-m | Needs custom dataset; use tiling (SAHI-style) for small items |
| Face detect | **SCRFD (InsightFace)** | **YuNet (OpenCV Zoo, MIT/Apache)** | YuNet is tiny, CPU-fast |
| Face recognition | **ArcFace (InsightFace buffalo_l / buffalo_s)** | **SFace (OpenCV Zoo, Apache-2.0)**, AdaFace | InsightFace pretrained weights are **non-commercial** |
| Motion | **OpenCV MOG2 / frame differencing** (no ML) | — | + optional ML gate: only run heavy models when motion or tracks exist |
| Posture classifier | Rule-based on keypoints + temporal smoothing | Optional tiny GRU/TCN trained on keypoint sequences | See rules doc |

## 2. Why this split
- **Two detectors** (person/PPE vs. materials/machinery) let you retrain and tune thresholds independently; materials need different resolution/tiling.
- **Pose-based posture** is far more robust than "standing/lying" detector classes: it works with any camera angle after calibration and gives crawling/sitting/bending distinctions.
- Alternatives worth benchmarking on *your* footage: YOLO11 vs RT-DETR vs RF-DETR (RF-DETR is strong for small objects). Keep the detector wrapper model-agnostic so swapping is a manifest change.

## 3. Sizes (starting point)
| Model | Input | Approx. ONNX size | Use |
|---|---|---|---|
| yolo11n/s/m | 640 | 10 / 38 / 78 MB | CPU → n/s, GPU → m |
| yolo11s-pose | 640 | ~40 MB | Pose |
| YuNet | 320 | < 1 MB | Face det |
| SFace | 112 | ~37 MB | Face embed |
| ArcFace buffalo_l | 112 | ~280 MB bundle | Higher accuracy |

## 4. Datasets for fine-tuning (download once, train offline)
- **PPE**: Construction Site Safety (Roboflow Universe), **SH17** (17 PPE classes), CHV (colored helmets/vests), SHWD (helmet/head). Check each dataset's license.
- **Posture / falls**: COCO keypoints (pretrained already), optionally UR Fall, Le2i, NTU RGB+D for sequence classifier validation. Best data is **your own site video** (label 300–1000 clips of lying/crawling/sitting).
- **Materials/machinery**: very few public sets — plan **custom labeling** (CVAT / Label Studio / Roboflow offline-export). Target ≥ 500 images/class, varied lighting, stacked/partial occlusion. Use auto-labeling with a general detector (e.g. Grounding DINO / YOLO-World) on a connected machine to bootstrap, then human-review.
- Augmentations: mosaic, HSV jitter, motion blur, dust/haze, low light, random crop; negative images (empty site) to cut false positives.

## 5. Export & registry
```bash
# on a connected machine
yolo export model=ppe_best.pt format=onnx imgsz=640 opset=17 simplify=True dynamic=False
# optional: format=openvino  |  format=engine (TensorRT, built on the target GPU)
```
`models/manifest.json`:
```json
{
  "person_yolo":    {"path": "yolo11s.onnx",        "sha256": "...", "task": "detect", "imgsz": 640, "classes": ["person"], "license": "AGPL-3.0"},
  "pose_yolo":      {"path": "yolo11s-pose.onnx",   "sha256": "...", "task": "pose",   "imgsz": 640, "license": "AGPL-3.0"},
  "ppe_yolo":       {"path": "ppe_yolo11s.onnx",    "sha256": "...", "task": "detect", "imgsz": 640, "classes_file": "config/classes.yaml#ppe"},
  "materials_yolo": {"path": "materials_yolo11m.onnx","sha256": "...", "task": "detect", "imgsz": 960, "classes_file": "config/classes.yaml#materials"},
  "yunet":          {"path": "face_detection_yunet_2023mar.onnx", "sha256": "...", "task": "face_det"},
  "sface":          {"path": "face_recognition_sface_2021dec.onnx","sha256": "...", "task": "face_embed", "dim": 128}
}
```

## 6. Licensing cheat-sheet
- **Ultralytics YOLO (v5/v8/11)**: AGPL-3.0 → open-source your whole app or buy an Enterprise license.
- **YOLOX, RT-DETR, RF-DETR, RTMPose, YuNet, SFace, OpenCV, ONNX Runtime**: permissive (Apache/MIT/BSD).
- **InsightFace pretrained models**: non-commercial research use unless licensed.
- Always record each model's license in `manifest.json` and show it on the "Models" settings page.

## 7. Hardware → model tier
| Hardware | Suggested |
|---|---|
| Intel/AMD CPU only | yolo11n/s + OpenVINO, pose every 3rd frame, 1–2 cams |
| NVIDIA GTX/RTX 3050–4060 | yolo11s/m + TensorRT FP16, 4–6 cams |
| Jetson Orin Nano/NX | TensorRT FP16/INT8, 2–4 cams |
| Apple Silicon | ONNX Runtime CoreML EP, 2–3 cams |
