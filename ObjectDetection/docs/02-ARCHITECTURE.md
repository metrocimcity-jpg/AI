# 02 — Architecture

## 1. High-level
```
 Cameras (RTSP/USB/file)
        │
 ┌──────▼───────┐   frames    ┌───────────────────────────── Inference worker (per camera) ───────────────────────────┐
 │ Capture thr. │────queue───▶│ Motion → Person det → Tracker → Pose → Posture → PPE/Materials det → Face → Rule engine │
 └──────────────┘ (drop old)  └───────────────┬───────────────────────────────────────────────────────────────────────┘
                                              │ FrameResult (detections, tracks, postures, events)
                          ┌───────────────────▼───────────────────┐
                          │ FastAPI app                             │
                          │  • MJPEG stream (annotated optional)    │
                          │  • WebSocket /ws (metadata + events)    │
                          │  • REST (cameras, zones, events, ...)   │
                          │  • SQLite + snapshots/clips on disk     │
                          └───────────────────┬───────────────────┘
                                              │ HTTP/WS (LAN)
                                   React dashboard (static build served by FastAPI)
```

## 2. Folder layout (create exactly this)
```
construction-vision/
├─ backend/
│  ├─ app/
│  │  ├─ main.py                 # FastAPI app factory, static mount, lifespan
│  │  ├─ core/        config.py, logging.py, security.py, deps.py
│  │  ├─ api/         cameras.py, events.py, zones.py, workers.py, stats.py, settings.py, auth.py, ws.py, health.py
│  │  ├─ db/          models.py, session.py, migrations/ (alembic)
│  │  ├─ schemas/     pydantic models (mirror 05-API-SPEC.md)
│  │  ├─ services/    camera_manager.py, event_service.py, report_service.py, retention.py
│  │  ├─ pipeline/
│  │  │   base.py, capture.py, worker.py
│  │  │   motion.py, detector.py, tracker.py, pose.py, posture.py
│  │  │   ppe.py, materials.py, face.py, rules.py, zones.py
│  │  └─ ml/          registry.py, onnx_session.py, preprocess.py, postprocess.py, providers.py
│  ├─ tests/
│  └─ pyproject.toml
├─ frontend/                     # Vite + React + TS (see 06-UI-SPEC.md)
├─ models/                       # manifest.json + *.onnx (git-lfs or manual copy)
├─ config/        settings.yaml, rules.yaml, classes.yaml
├─ data/          db.sqlite, snapshots/, clips/, faces/ (gitignored)
├─ scripts/       export_models.py, benchmark.py, enroll_cli.py, seed_demo.py, offline_bundle.sh
├─ training/      README.md, datasets.yaml, train_ppe.py, train_materials.py (offline fine-tuning)
├─ docker/        Dockerfile.backend, docker-compose.yml
└─ docs/
```

## 3. Pipeline stage contract
```python
@dataclass
class FrameContext:
    camera_id: str
    ts: float
    frame: np.ndarray            # BGR
    motion: MotionResult | None
    persons: list[Detection]
    tracks: list[Track]          # persistent IDs
    poses: dict[int, Keypoints]  # track_id -> 17 COCO keypoints
    postures: dict[int, PostureState]
    ppe: dict[int, PPEStatus]    # track_id -> {helmet: ok/missing/unknown, vest: ...}
    objects: list[Detection]     # materials + machinery
    faces: dict[int, FaceMatch]  # track_id -> (worker_id|unknown, score)
    events: list[Event]
    timings_ms: dict[str, float]

class Stage(Protocol):
    name: str
    enabled: bool
    def process(self, ctx: FrameContext) -> FrameContext: ...
```
Stage order is defined in `settings.yaml → pipeline.stages` and built by `worker.py`.

## 4. Latency / FPS budget (per frame, 1280×720 input, mid GPU / modern CPU)
| Stage | GPU target | CPU target | Notes |
|---|---|---|---|
| Motion (320 px) | 1 ms | 2 ms | skip heavy stages if no motion & no tracks |
| Person detect | 8 ms | 45 ms | YOLO11s/m @ 640 |
| Tracker | 1 ms | 2 ms | ByteTrack |
| Pose (crops or full) | 8 ms | 40 ms | run every 2nd frame, interpolate |
| PPE + materials det | 8 ms | 45 ms | can run every 2–3 frames |
| Face (per new/uncertain track) | 6 ms | 30 ms | throttled, cached |
| Rules/DB | 1 ms | 1 ms | async DB writes |

Adaptive strategy: **stride config per stage**, motion gating, frame dropping, and resolution scaling.

## 5. Concurrency
- 1 capture thread + 1 inference thread/process per camera; shared ONNX sessions per model via a lock or session-per-worker.
- Results published through an in-process `asyncio` broadcaster to WebSocket clients; DB writes via a background writer queue.
- Annotated MJPEG is optional; default = raw JPEG stream + client-side overlay from WS metadata.

## 6. Configuration (`config/settings.yaml` excerpt)
```yaml
runtime:
  provider_priority: [tensorrt, cuda, openvino, directml, cpu]
  max_cameras: 8
pipeline:
  stages: [motion, person, tracker, pose, posture, ppe, materials, face, rules]
  strides: {pose: 2, ppe: 2, materials: 3, face: 5}
  motion_gate: true
detector:
  person: {model: person_yolo, conf: 0.35, iou: 0.5}
  ppe:    {model: ppe_yolo,    conf: 0.40, iou: 0.5}
  materials: {model: materials_yolo, conf: 0.40, iou: 0.5}
face:
  enabled: false
  detector: yunet
  recognizer: sface
  match_threshold: 0.36     # cosine; calibrate locally
  min_face_px: 80
events:
  cooldown_seconds: {no_helmet: 60, lying: 30, intrusion: 20}
retention_days: 30
```
