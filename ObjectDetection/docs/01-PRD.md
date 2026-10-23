# 01 — Product Requirements (PRD)

## 1. Problem
Construction sites need continuous monitoring of worker safety (PPE, falls, restricted areas) and inventory/material visibility, often with **no reliable internet**. Cloud AI is not acceptable (connectivity, privacy, latency).

## 2. Users
| Role | Needs |
|---|---|
| Safety officer | Live alerts, PPE compliance %, incident review with snapshots |
| Site manager | Overview dashboard, daily/weekly reports, material counts |
| Admin / IT | Camera setup, zones, worker enrollment, model management, system health |

## 3. Scope (MVP → v1)
### MVP
- Add cameras (RTSP URL, USB index, video file for demo)
- Live view with overlays (boxes, skeleton, labels, track IDs)
- Person detection + posture: standing, walking, sitting, crouching, bending, lying, crawling, climbing
- PPE: helmet, vest (+ missing helmet / missing vest)
- Event log with snapshots, filters, acknowledge/resolve
- Dashboard KPIs: people now, PPE compliance %, active alerts, FPS/latency
- 100% offline

### v1
- Materials & machinery detection + counts over time (rebar, gypsum, cement bags, bricks, pipes, plywood, steel beams, excavator, truck, forklift)
- Motion detection with polygon zones and schedules
- Face recognition (enroll workers, attendance log, unknown-face alert)
- Gloves, boots, goggles, harness
- Reports export (CSV/PDF), clip recording around events
- Multi-camera grid, role-based login (local users)

### Out of scope (for now)
Cloud sync, mobile app, 3D/BIM integration, audio analytics.

## 4. Functional requirements
- FR1 Process ≥ 4 camera streams at ≥ 10 FPS each on a mid GPU, ≥ 1 stream @ 8–10 FPS on a modern CPU (with small models).
- FR2 Alert latency (event occurs → dashboard) < 2 s.
- FR3 Alert rules configurable from UI (enable/disable, severity, cooldown, zones, schedule).
- FR4 Posture must be temporally stable (no flicker): min dwell 1 s before state change; `lying` for > 3 s (configurable) raises a "possible fall / man down" event.
- FR5 All data local (SQLite + files). Retention policy configurable (default 30 days).
- FR6 Admin can enroll a worker with 3–5 photos or a short webcam capture; delete on request.
- FR7 Models swappable by editing `models/manifest.json` (no code change).

## 5. Non-functional
- Offline-first: app boots and works with network cable unplugged.
- Privacy: face feature behind config flag + consent notice in UI; embeddings never exposed via API.
- Reliability: auto-reconnect cameras; watchdog restarts crashed workers.
- Security: local auth (argon2/bcrypt), JWT with short expiry, LAN-only binding by default.
- Observability: `/api/health`, per-stage latency metrics.

## 6. KPIs
- Person detection mAP50 ≥ 0.90 on site validation set
- Helmet/vest F1 ≥ 0.90; posture accuracy ≥ 0.85 (lying/crawling recall ≥ 0.85)
- Face recognition FAR ≤ 0.1 % at chosen threshold on local enrolled set
- False alert rate < 1 per camera per hour after tuning

## 7. Risks
| Risk | Mitigation |
|---|---|
| Materials classes have no good public dataset | Plan custom labeling + fine-tune (see 03-MODELS.md) |
| Occlusion / low light / dust | Per-camera calibration, confidence gates, IR cameras, augmentations |
| Licensing (AGPL / non-commercial weights) | Permissive model path documented |
| Posture ambiguity (crawling vs crouching) | Pose keypoints + temporal features, optional small LSTM/GRU later |
| Privacy/legal for face recognition | Opt-in flag, consent text, delete/export tools |
