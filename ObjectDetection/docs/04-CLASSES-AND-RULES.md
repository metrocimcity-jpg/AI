# 04 — Classes, Posture Logic, Alert Rules

## 1. Class taxonomy (`config/classes.yaml`)
```yaml
person: [person]

ppe:            # detector "ppe_yolo"
  - helmet            # hard hat worn
  - no_helmet         # bare head
  - vest              # hi-vis vest worn
  - no_vest
  - gloves
  - no_gloves
  - safety_boots
  - goggles
  - harness
  - ear_protection
  - face_mask

materials:      # detector "materials_yolo"
  - rebar_bundle        # steel bars
  - gypsum_board        # gypsum / drywall sheets
  - gypsum_packet       # bagged gypsum / plaster powder
  - cement_bag
  - brick_pallet
  - concrete_block
  - steel_beam
  - pipe_bundle
  - plywood_stack
  - scaffolding
  - sand_pile
  - wheelbarrow
  - paint_bucket

machinery:
  - excavator
  - dump_truck
  - concrete_mixer
  - forklift
  - crane
  - loader

hazards:        # optional v1
  - fire
  - smoke
  - spill
```
Counting: materials are counted per camera per time bucket (tile + NMS across tiles), stored in `material_counts` (see API spec). "Count" = visible instances; for bundles/stacks, store `count` and `bbox_area_ratio` as a rough volume proxy.

## 2. Posture states
`standing | walking | sitting | crouching | bending | lying | crawling | climbing | unknown`

### Inputs per track
- COCO 17 keypoints with confidences (`nose, eyes, ears, shoulders, elbows, wrists, hips, knees, ankles`)
- person bbox (w, h, aspect = h/w), bbox center history (speed in px/s, normalized by bbox height)
- optional camera calibration: ground-plane horizon/tilt (config `camera.tilt_deg`)

### Features
```
torso_vec      = mid_shoulder → mid_hip
torso_angle    = angle(torso_vec, vertical)     # 0° upright, 90° horizontal
thigh_angle    = angle(hip→knee, vertical)      # per leg, take mean of visible
knee_angle     = angle(hip-knee-ankle)          # 180° straight
hip_knee_dy    = (knee_y - hip_y) / bbox_h      # ~0 when seated, ~0.25 when standing
head_below_hip = nose_y > mid_hip_y
aspect         = bbox_h / bbox_w
speed          = |Δcenter| / bbox_h / Δt
vert_extent    = (max_kp_y - min_kp_y) / bbox_h
```

### Decision rules (first match wins; thresholds in `config/settings.yaml → posture`)
| State | Rule (all visible-keypoint confidence ≥ 0.3) |
|---|---|
| **lying** | torso_angle > 65° **and** aspect < 0.9 **and** speed < 0.15 (not crawling); OR head_below_hip with torso horizontal |
| **crawling** | torso_angle between 50°–90° (roughly horizontal) **and** wrists & knees both low in bbox (y > 0.6·bbox_h) **and** speed > 0.05 ; sustained ≥ 1 s |
| **sitting** | |hip_knee_dy| < 0.12 **and** knee_angle 60°–130° **and** torso_angle < 35° **and** speed < 0.1 |
| **crouching** | knee_angle < 100° **and** hip_y close to ankle_y (hip-ankle dy < 0.35·bbox_h) **and** torso_angle < 50° |
| **bending** | torso_angle 35°–65° **and** knee_angle > 140° |
| **climbing** | wrists above shoulders alternately + vertical speed > 0.05 inside a `ladder`/`scaffold` zone or near `scaffolding` detection |
| **walking** | torso_angle < 25° **and** speed ≥ 0.12 |
| **standing** | torso_angle < 25° **and** knee_angle > 150° **and** speed < 0.12 |
| **unknown** | too few visible keypoints (< 8) or confidence low |

### Temporal smoothing (mandatory)
1. Per-track ring buffer of the last 10 frame-level predictions → majority vote.
2. Change state only if the new state is stable for `min_dwell_ms` (default 800 ms; `lying`/`crawling` 1500 ms).
3. Maintain `state_since` timestamp for duration-based rules.
4. **Fall detection**: transition `standing|walking|climbing → lying` within ≤ 1.0 s with high downward center velocity → emit `fall_detected` (critical) immediately; otherwise `lying` > `lying_alert_seconds` (default 3 s) → `man_down`.

### Optional upgrade
Train a small GRU/TCN on 30-frame normalized keypoint sequences (`training/train_posture.py`) and fuse with rule output. Keep rule engine as fallback.

## 3. PPE association & status
For each tracked person:
1. Define regions from keypoints (fallback to bbox fractions): **head** = nose/eyes/ears ± 0.6·shoulder-width, expanded upward; **torso** = shoulders→hips; **hands** = wrist ± 0.25·arm length; **feet** = ankles ± 0.3·shin length.
2. Match PPE detections by **containment ratio** (area(det ∩ region) / area(det)) ≥ 0.5.
3. Status per item: `ok` (positive class found), `missing` (negative class found, or region visible and no positive class for ≥ N frames), `unknown` (region occluded / low keypoint confidence).
4. Temporal vote over 15 frames before raising `missing`.

## 4. Alert rules (`config/rules.yaml`)
```yaml
rules:
  - id: no_helmet
    severity: critical
    when: person.ppe.helmet == "missing" and not person.in_zone("office")
    min_duration_s: 2
    cooldown_s: 60
  - id: no_vest
    severity: warning
    when: person.ppe.vest == "missing"
    min_duration_s: 3
    cooldown_s: 120
  - id: fall_detected
    severity: critical
    when: posture.transition in ["standing->lying","walking->lying","climbing->lying"]
    cooldown_s: 30
  - id: man_down
    severity: critical
    when: posture.state == "lying" and posture.duration_s > 3
    cooldown_s: 30
  - id: crawling_in_restricted
    severity: warning
    when: posture.state == "crawling" and person.in_zone("restricted")
  - id: restricted_zone_intrusion
    severity: critical
    when: person.in_zone("restricted") and not worker.authorized
  - id: unknown_face
    severity: warning
    when: face.result == "unknown" and face.quality >= 0.6
    cooldown_s: 300
  - id: motion_after_hours
    severity: warning
    when: motion.detected and schedule.is_closed
  - id: person_near_machinery
    severity: critical
    when: person.distance_to("excavator|dump_truck|loader|crane") < 3.0   # meters if calibrated, else bbox-heights
  - id: material_blocking_exit
    severity: info
    when: object.class in materials and object.in_zone("walkway")
```

## 5. Face recognition behavior
- Enrollment: 3–5 photos → detect (YuNet/SCRFD) → align → embedding (SFace/ArcFace) → store L2-normalized vectors in SQLite BLOB (encrypted with a local key from `.env`).
- Matching: cosine similarity vs. all enrolled; accept if best ≥ `match_threshold` **and** margin to second-best ≥ 0.05. Cache result per `track_id`; re-verify every 30 frames or when confidence is low.
- Quality gates: face ≥ 80 px, blur (Laplacian var) ≥ threshold, yaw < 45°. Otherwise result = `unverified`.
- Attendance: first/last seen per worker per camera/day.
- Calibrate threshold on a local validation set (script: `scripts/calibrate_face.py`).

## 6. Motion detection
- Convert to gray, resize to 320 px width, `cv2.createBackgroundSubtractorMOG2(history=300, varThreshold=25, detectShadows=True)`, morphological open/close, contours with area ≥ `min_area`.
- Polygon ROI masks per camera; schedules (e.g., 18:00–06:00 closed).
- Output `MotionResult(detected, score, regions[])`; used both as an alert source and as a gate for heavy stages.
