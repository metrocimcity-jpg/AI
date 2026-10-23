export type Role = "admin" | "officer" | "viewer";

export type Camera = {
  id: string;
  name: string;
  source: string;
  enabled: boolean;
  status: string;
  fps: number;
  latency_ms: number;
  last_error: string | null;
};

export type Zone = {
  id: string;
  camera_id: string;
  name: string;
  type: string;
  polygon: number[][];
  schedule?: { closed?: string[] } | null;
};

export type PpeMap = Record<string, string>;

export type PersonBox = {
  track_id: number;
  bbox: number[];
  posture: string;
  posture_since: number;
  ppe: PpeMap;
  worker: { id: string; name: string; score: number } | null;
  keypoints: number[][] | null;
};

export type FrameMsg = {
  type: "frame";
  camera_id: string;
  ts: number;
  w: number;
  h: number;
  persons: PersonBox[];
  objects: { class: string; bbox: number[]; score: number }[];
  motion: { detected: boolean; score: number; regions: number[][] } | null;
  metrics: { fps: number; latency_ms: number };
};

export type EventItem = {
  id: string;
  camera_id: string;
  event_type: string;
  severity: string;
  status: string;
  ts: string | null;
  track_id: number | null;
  worker_id: string | null;
  snapshot_url: string | null;
  message: string;
  meta: Record<string, unknown>;
  resolved_note?: string | null;
};

export type Overview = {
  people_now: number;
  active_alerts: number;
  ppe_compliance_pct: number | null;
  cameras_online: number;
  fps_avg: number;
  latency_ms_avg: number;
  posture_counts: Record<string, number>;
  material_counts: Record<string, number>;
  recent_events: EventItem[];
};

export type WorkerRow = {
  id: string;
  name: string;
  employee_id: string;
  role: string;
  authorized_zones: string[];
  face_count: number;
};

export type ModelRow = {
  name: string;
  path: string;
  task: string;
  license: string;
  imgsz: number;
  exists: boolean;
  sha256_pinned: boolean;
  loaded: boolean;
};
