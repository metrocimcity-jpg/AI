# 05 — API & Data Spec

Base URL: `http://<host>:8000`. All JSON, UTC ISO-8601 timestamps. Auth: `Authorization: Bearer <jwt>` (local users). Dashboard is served at `/`.

## 1. REST
### Auth
- `POST /api/auth/login` `{username,password}` → `{access_token, expires_in, role}`
- `GET /api/auth/me`

### Cameras
- `GET /api/cameras` → `[Camera]`
- `POST /api/cameras` `{name, source: "rtsp://…"|"0"|"file:///…", enabled, pipeline_overrides?}`
- `PATCH /api/cameras/{id}` · `DELETE /api/cameras/{id}`
- `POST /api/cameras/{id}/start|stop`
- `GET /api/cameras/{id}/stream.mjpg` (multipart MJPEG, `?overlay=0|1`)
- `GET /api/cameras/{id}/snapshot.jpg`

### Zones
- `GET/POST /api/cameras/{id}/zones` `{name, type: restricted|walkway|ladder|office|storage, polygon:[[x,y]…normalized 0-1], schedule?}`
- `PATCH/DELETE /api/zones/{zone_id}`

### Events
- `GET /api/events?camera_id&type&severity&status&from&to&worker_id&limit&cursor`
- `GET /api/events/{id}` (includes snapshot URL, clip URL, metadata)
- `POST /api/events/{id}/ack` · `POST /api/events/{id}/resolve` `{note}`

### Stats
- `GET /api/stats/overview` → people_now, active_alerts, ppe_compliance_pct, cameras_online, fps_avg
- `GET /api/stats/ppe?from&to&bucket=hour|day`
- `GET /api/stats/posture?from&to&bucket`
- `GET /api/stats/materials?from&to&bucket&class`
- `GET /api/stats/attendance?date`

### Workers & faces (admin only)
- `GET/POST /api/workers` `{name, employee_id, role, authorized_zones[]}`
- `POST /api/workers/{id}/faces` (multipart images) · `DELETE /api/workers/{id}/faces`
- `GET /api/workers/{id}/attendance`
- Embeddings are **never** returned.

### System
- `GET /api/health` → `{status, uptime, providers, models:[{name,loaded,license}], cameras:[{id,fps,latency_ms}]}`
- `GET/PUT /api/settings`, `GET/PUT /api/rules`
- `GET /api/models` · `POST /api/models/reload`
- `POST /api/reports/export` `{type: events|attendance|ppe, format: csv|pdf, from, to}`

## 2. WebSocket `/ws?token=…`
Server → client messages:
```jsonc
// every processed frame (throttled to ≤15 msg/s/camera)
{"type":"frame","camera_id":"cam1","ts":1730000000.12,"w":1280,"h":720,
 "persons":[{"track_id":7,"bbox":[x1,y1,x2,y2],"posture":"lying","posture_since":1730000000.0,
             "ppe":{"helmet":"ok","vest":"missing","gloves":"unknown"},
             "worker":{"id":"w12","name":"A. Karim","score":0.52}|null,
             "keypoints":[[x,y,c]…17]}],
 "objects":[{"class":"cement_bag","bbox":[…],"score":0.88}],
 "motion":{"detected":true,"score":0.31,"regions":[[x1,y1,x2,y2]]},
 "metrics":{"fps":12.4,"latency_ms":78}}

// event
{"type":"event","event":{"id":"evt_…","camera_id":"cam1","event_type":"no_helmet","severity":"critical",
 "ts":"…","track_id":7,"worker_id":null,"snapshot_url":"/media/snapshots/…jpg","message":"Worker without helmet (Zone A)"}}

// system
{"type":"camera_status","camera_id":"cam1","status":"online|offline|reconnecting"}
```
Client → server: `{"type":"subscribe","camera_ids":["cam1"],"frames":true}`.

## 3. SQLite schema (SQLAlchemy models)
```
users(id, username, password_hash, role[admin|officer|viewer], created_at)
cameras(id, name, source, enabled, config_json, created_at)
zones(id, camera_id→cameras, name, type, polygon_json, schedule_json)
workers(id, name, employee_id, role, authorized_zones_json, created_at)
face_embeddings(id, worker_id→workers, embedding_blob, model, created_at)   -- encrypted/L2-normalized
events(id, camera_id, event_type, severity, status[open|ack|resolved], ts, track_id, worker_id,
       zone_id, snapshot_path, clip_path, meta_json, ack_by, resolved_note)
posture_samples(id, camera_id, ts, track_id, state)                 -- sampled 1/s
ppe_samples(id, camera_id, ts, track_id, helmet, vest, gloves, boots, goggles, harness)
material_counts(id, camera_id, ts_bucket, class_name, count, area_ratio)
attendance(id, worker_id, camera_id, date, first_seen, last_seen)
audit_log(id, user_id, action, target, ts)
```
Indexes: `events(ts DESC)`, `events(camera_id, ts)`, `ppe_samples(ts)`, `material_counts(ts_bucket, class_name)`. SQLite in WAL mode, background writer queue, retention job daily.
