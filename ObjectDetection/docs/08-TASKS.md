# 08 — Build Plan for Cursor (run phases in order)

> For each phase: open a **new Agent/Composer chat**, attach `@.cursor/rules` (auto) + the listed docs, paste the prompt, then verify the acceptance checks before moving on.

---
## Phase 0 — Scaffold
**Attach:** `@docs/02-ARCHITECTURE.md`
```
Create the project skeleton exactly as in docs/02-ARCHITECTURE.md: backend (FastAPI app factory, config loader for config/settings.yaml + .env, logging, /api/health), frontend (Vite React TS + Tailwind + shadcn/ui, sidebar layout shell with empty pages), config/ files with defaults, scripts/ stubs, .gitignore, .env.example, run.sh and run.bat. FastAPI must serve frontend/dist in production. Add Makefile targets: dev, build, test, lint.
```
**Accept:** `make dev` starts both; `/api/health` returns OK; shell UI renders with fonts bundled locally.

---
## Phase 1 — Model layer (offline)
**Attach:** `@docs/03-MODELS.md`
```
Implement backend/app/ml: ModelRegistry reading models/manifest.json (sha256 verify, license field), ONNX Runtime session factory with provider priority + CPU fallback, YOLO-style detector wrapper (letterbox, decode, NMS, per-class thresholds) and YOLO-pose wrapper. Never download anything. Add scripts/export_models.py (runs on a connected machine only), scripts/benchmark.py (per-stage latency on a sample video), and unit tests with a tiny fixture.
```
**Accept:** `python scripts/benchmark.py --video samples/demo.mp4` prints FPS/latency for person+pose; missing model gives a clean error.

---
## Phase 2 — Capture + pipeline + tracking
**Attach:** `@docs/02-ARCHITECTURE.md`
```
Implement pipeline/capture.py (RTSP/USB/file with auto-reconnect and frame dropping), pipeline/base.py (FrameContext, Stage protocol), worker.py (per-camera thread, stage list from settings, stride support), detector.py (person), tracker.py (ByteTrack), and camera_manager service. Expose GET /api/cameras, POST start/stop, snapshot.jpg and stream.mjpg. Add WebSocket /ws broadcasting "frame" messages (persons, bboxes, track ids, metrics).
```
**Accept:** demo video plays in a minimal test page with boxes and stable track IDs; FPS shown.

---
## Phase 3 — Posture
**Attach:** `@docs/04-CLASSES-AND-RULES.md`
```
Implement pipeline/pose.py and pipeline/posture.py exactly per section 2 of docs/04: features, rule table, majority-vote smoothing, min dwell, state_since, fall transition detection. Thresholds come from settings.yaml. Write pytest tests with synthetic keypoint fixtures for each posture (standing, walking, sitting, crouching, bending, lying, crawling, climbing) and for the fall transition. Add a debug overlay option drawing skeleton + posture label.
```
**Accept:** tests pass; on demo footage posture labels don't flicker; lying > 3 s yields a `man_down` event object.

---
## Phase 4 — PPE
**Attach:** `@docs/04-CLASSES-AND-RULES.md` (section 3)
```
Implement pipeline/ppe.py: run the ppe detector (stride from settings), associate detections to tracked persons via keypoint-derived head/torso/hand/foot regions with containment ratio, compute ok/missing/unknown with temporal voting. Add training/README.md describing how to fine-tune YOLO on SH17/Construction-Site-Safety style datasets, with train_ppe.py and datasets.yaml.
```
**Accept:** WS frame messages include per-person `ppe` map; unit tests for association logic.

---
## Phase 5 — Events, rules, DB
**Attach:** `@docs/05-API-SPEC.md`, `@docs/04-CLASSES-AND-RULES.md`
```
Implement SQLAlchemy models + alembic for the schema in docs/05, rules.py rule engine reading config/rules.yaml (when-expressions evaluated safely — no eval; use a small parser or simpleeval), zones.py (point-in-polygon, schedules), event_service (cooldowns, snapshot saving, optional 10 s clip ring buffer), REST: events (list/get/ack/resolve), zones CRUD, stats endpoints. Broadcast "event" over WS.
```
**Accept:** no_helmet / man_down events appear in DB and WS with snapshots; cooldown prevents spam.

---
## Phase 6 — Dashboard UI (core)
**Attach:** `@docs/06-UI-SPEC.md`, `@docs/05-API-SPEC.md`
```
Build Dashboard, Live, and Events pages per docs/06-UI-SPEC.md: design tokens, KPI cards, PPE ring, posture donut, alert feed with toasts + bundled alert sound, CameraTile and VideoOverlayCanvas (boxes, skeleton, posture badges, PPE icons), PersonTable, filters, EventDrawer. WS client with reconnect + Zustand store; TanStack Query for REST. Use mock data fallback via ?mock=1 for UI dev.
```
**Accept:** UI looks modern in dark/light; overlays toggle; no external network requests (check DevTools Network tab).

---
## Phase 7 — Materials & machinery
**Attach:** `@docs/04-CLASSES-AND-RULES.md` (section 1), `@docs/03-MODELS.md`
```
Implement pipeline/materials.py: tiled inference (configurable tiles with overlap) + cross-tile NMS for small objects, class list from config/classes.yaml, per-bucket counts into material_counts, zone attribution, person_near_machinery rule. Build Materials page (inventory table, cards, trend charts, walkway-obstruction flags). Add training/train_materials.py + labeling guide (CVAT, class definitions, min images per class).
```
**Accept:** counts update in UI; tiling toggle in camera settings; benchmark shows added latency.

---
## Phase 8 — Motion + Zones editor
```
Implement pipeline/motion.py (MOG2, ROI polygons, schedules, gating of heavy stages) and the Zones page with a canvas polygon editor over a camera snapshot (normalized coordinates), schedule editor and live preview. Add rules motion_after_hours and restricted_zone_intrusion.
```
**Accept:** motion regions drawn in Live; heavy stages skipped when idle (verify FPS/CPU drop); intrusion event fires.

---
## Phase 9 — Face recognition (opt-in)
**Attach:** `@docs/04-CLASSES-AND-RULES.md` (section 5)
```
Implement pipeline/face.py with YuNet detect + SFace embed via ONNX (pluggable for SCRFD/ArcFace), quality gates, per-track caching, enrollment API + Workers page wizard with consent checkbox, encrypted embedding storage, attendance, unknown_face rule, delete-all-biometrics, scripts/calibrate_face.py. Feature must be disabled unless face.enabled=true.
```
**Accept:** enrolled person recognized with name on overlay; unknown triggers event; API never returns embeddings.

---
## Phase 10 — Analytics, reports, settings
```
Build Analytics and Settings pages (models list w/ licenses, provider selection, rules editor, retention, users/roles, backup). Implement report export (CSV/PDF) and retention job. Add local auth with roles (admin/officer/viewer) and protect routes + WS.
```
**Accept:** reports download; roles enforced; retention purges old files.

---
## Phase 11 — Hardening & offline packaging
**Attach:** `@docs/07-OFFLINE-DEPLOYMENT.md`
```
Add watchdog/auto-restart for workers, graceful camera failure states, structured logs, scripts/offline_bundle.sh, Dockerfile + compose, scripts/check_no_external_urls.sh, and the offline verification checklist as an automated smoke test (pytest + shell). Write docs/OPERATIONS.md (install, update, backup, troubleshooting).
```
**Accept:** every item in the offline checklist passes with the network disabled.

---
## Prompt tips for Cursor
- Keep one phase per chat; if the context gets long, start a new chat and re-attach the docs.
- Ask Cursor to **run tests and fix failures** before finishing each phase.
- When changing thresholds or classes, edit `config/*.yaml` and the docs together so the rules stay the source of truth.
