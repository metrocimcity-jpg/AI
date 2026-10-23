import type { Camera, EventItem, FrameMsg, Overview, WorkerRow, Zone } from "../api/types";

export const mockCameras: Camera[] = [
  { id: "cam-gate", name: "Gate A", source: "file:///samples/demo.avi", enabled: true, status: "online", fps: 12.4, latency_ms: 78, last_error: null },
  { id: "cam-yard", name: "Yard", source: "0", enabled: true, status: "online", fps: 11.1, latency_ms: 84, last_error: null },
  { id: "cam-deck", name: "Deck 2", source: "rtsp://***@10.0.0.14/stream", enabled: false, status: "offline", fps: 0, latency_ms: 0, last_error: null },
];

const person = (id: number, box: number[], posture: string, helmet: string, vest: string): FrameMsg["persons"][number] => ({
  track_id: id,
  bbox: box,
  posture,
  posture_since: Date.now() / 1000 - 12,
  ppe: { helmet, vest, gloves: "unknown", boots: "ok", goggles: "unknown", harness: "unknown" },
  worker: id === 7 ? { id: "w1", name: "A. Karim", score: 0.62 } : null,
  keypoints: null,
});

export const mockFrame = (cameraId: string): FrameMsg => ({
  type: "frame",
  camera_id: cameraId,
  ts: Date.now() / 1000,
  w: 1280,
  h: 720,
  persons: [
    person(7, [180, 120, 340, 620], "standing", "ok", "ok"),
    person(8, [520, 180, 760, 640], "bending", "missing", "ok"),
    person(9, [860, 360, 1180, 560], "lying", "ok", "missing"),
  ],
  objects: [
    { class: "cement_bag", bbox: [400, 500, 520, 640], score: 0.88 },
    { class: "excavator", bbox: [900, 80, 1240, 420], score: 0.81 },
  ],
  motion: { detected: true, score: 0.31, regions: [[160, 100, 360, 640]] },
  metrics: { fps: 12.4, latency_ms: 78 },
});

export const mockEvents: EventItem[] = [
  { id: "e1", camera_id: "cam-gate", event_type: "no_helmet", severity: "critical", status: "open", ts: new Date().toISOString(), track_id: 8, worker_id: null, snapshot_url: null, message: "Worker without helmet", meta: {} },
  { id: "e2", camera_id: "cam-yard", event_type: "man_down", severity: "critical", status: "open", ts: new Date(Date.now() - 60000).toISOString(), track_id: 9, worker_id: null, snapshot_url: null, message: "Person lying down", meta: {} },
  { id: "e3", camera_id: "cam-gate", event_type: "no_vest", severity: "warning", status: "ack", ts: new Date(Date.now() - 120000).toISOString(), track_id: 4, worker_id: null, snapshot_url: null, message: "Worker without hi-vis vest", meta: {} },
];

export const mockOverview: Overview = {
  people_now: 6,
  active_alerts: 2,
  ppe_compliance_pct: 82.5,
  cameras_online: 2,
  fps_avg: 11.8,
  latency_ms_avg: 81,
  posture_counts: { standing: 3, walking: 1, bending: 1, lying: 1 },
  material_counts: { cement_bag: 14, rebar_bundle: 6, gypsum_board: 9, brick_pallet: 4 },
  recent_events: mockEvents,
};

export const mockZones: Zone[] = [
  { id: "z1", camera_id: "cam-gate", name: "Restricted", type: "restricted", polygon: [[0.1, 0.2], [0.4, 0.2], [0.38, 0.8], [0.08, 0.75]], schedule: { closed: ["18:00-06:00"] } },
  { id: "z2", camera_id: "cam-gate", name: "Walkway", type: "walkway", polygon: [[0.45, 0.55], [0.9, 0.55], [0.92, 0.95], [0.42, 0.95]] },
];

export const mockWorkers: WorkerRow[] = [
  { id: "w1", name: "A. Karim", employee_id: "SG-014", role: "rigger", authorized_zones: ["yard"], face_count: 0 },
];

export const ppeTrend = [
  { hour: "08", pct: 91 },
  { hour: "10", pct: 88 },
  { hour: "12", pct: 84 },
  { hour: "14", pct: 86 },
  { hour: "16", pct: 82 },
];

export const alertBars = [
  { type: "helmet", count: 4 },
  { type: "vest", count: 2 },
  { type: "man down", count: 1 },
  { type: "zone", count: 1 },
];

export const mockModels = [
  { name: "person_yolo", path: "yolo11s.onnx", task: "detect", license: "AGPL-3.0", imgsz: 640, exists: false, sha256_pinned: false, loaded: false },
  { name: "pose_yolo", path: "yolo11s-pose.onnx", task: "pose", license: "AGPL-3.0", imgsz: 640, exists: false, sha256_pinned: false, loaded: false },
  { name: "ppe_yolo", path: "ppe_yolo11s.onnx", task: "detect", license: "AGPL-3.0", imgsz: 640, exists: false, sha256_pinned: false, loaded: false },
  { name: "materials_yolo", path: "materials_yolo11m.onnx", task: "detect", license: "AGPL-3.0", imgsz: 960, exists: false, sha256_pinned: false, loaded: false },
  { name: "yunet", path: "face_detection_yunet_2023mar.onnx", task: "face_det", license: "MIT", imgsz: 320, exists: false, sha256_pinned: false, loaded: false },
  { name: "sface", path: "face_recognition_sface_2021dec.onnx", task: "face_embed", license: "Apache-2.0", imgsz: 112, exists: false, sha256_pinned: false, loaded: false },
];
