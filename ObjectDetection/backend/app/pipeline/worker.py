"""One inference thread per camera. Capture never blocks on the model."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from time import perf_counter

import numpy as np

from app.core.config import AppConfig
from app.core.logging import get_logger
from app.ml.postprocess import Detection
from app.ml.registry import ModelRegistry
from app.pipeline.base import EventDraft, FrameContext, PostureState, Track, ZoneView
from app.pipeline.capture import CaptureLoop
from app.pipeline.detector import PersonStage
from app.pipeline.face import FaceStage
from app.pipeline.materials import MaterialsStage
from app.pipeline.motion import MotionStage
from app.pipeline.pose import PoseStage
from app.pipeline.posture import PostureSmoother, classify_posture
from app.pipeline.ppe import PPEVoter, associate_ppe
from app.pipeline.rules import RuleEngine
from app.pipeline.tracker import ByteTrack, iou
from app.pipeline.zones import zones_at

logger = get_logger("siteguard.worker")

HEAVY = {"person", "pose", "ppe", "materials", "face"}
_PPE_FROM_SCENE = {"helmet", "no_helmet", "vest", "no_vest", "gloves", "goggles", "safety_boots", "harness"}


def _det(model: str, cfg: dict) -> dict:
    value = cfg.get(model, {})
    return value if isinstance(value, dict) else {}


class CameraWorker:
    def __init__(
        self,
        camera_id: str,
        name: str,
        source: str,
        config: AppConfig,
        registry: ModelRegistry,
        on_result: Callable[[dict, list[EventDraft], np.ndarray], None],
        zone_provider: Callable[[], list[ZoneView]],
        gallery_provider: Callable[[], list] | None = None,
        overrides: dict | None = None,
    ) -> None:
        self.camera_id = camera_id
        self.name = name
        self.source = source
        self.config = config
        self.registry = registry
        self.on_result = on_result
        self.zone_provider = zone_provider
        self.overrides = overrides or {}
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, name=f"cam-{camera_id[:8]}", daemon=True)
        self.jpeg_lock = threading.Lock()
        self.jpeg: bytes | None = None
        self.status = "offline"
        self.fps = 0.0
        self.latency_ms = 0.0
        self.last_error: str | None = None
        self._fps_times: list[float] = []
        self._last_pub = 0.0
        self._zones: list[ZoneView] = []
        self._zones_at = 0.0
        self._posture: dict[int, PostureSmoother] = {}
        self._ppe = PPEVoter(int(config.section("ppe").get("vote_window", 15)))
        self._tracker = ByteTrack()
        self._hold_poses: dict[int, np.ndarray] = {}
        self._hold_ppe: dict[int, dict[str, str]] = {}
        self._prior_objects: list[Detection] = []
        self._ppe_boxes: list[Detection] = []
        self._frame_i = 0
        raw = config.raw
        priority = list((raw.get("runtime") or {}).get("provider_priority") or ["cpu"])
        det = raw.get("detector") or {}
        person = _det("person", det)
        pose = _det("pose", det)
        ppe = _det("ppe", det)
        materials = _det("materials", det)
        motion = config.section("motion")
        face_cfg = config.section("face")
        self.motion_gate = bool((raw.get("pipeline") or {}).get("motion_gate", True))
        self.strides = dict((raw.get("pipeline") or {}).get("strides") or {})
        self.strides.update((self.overrides.get("strides") or {}))
        self.loop_files = bool((raw.get("pipeline") or {}).get("loop_files", True))
        disabled = {
            name
            for name, on in (self.overrides.get("stages") or {}).items()
            if on is False
        }
        self.stage_names = [
            name
            for name in (raw.get("pipeline") or {}).get(
                "stages",
                ["motion", "person", "tracker", "pose", "posture", "materials", "ppe", "face", "rules"],
            )
            if name not in disabled
        ]
        mat_names = _material_names(config.root)
        self.rules = RuleEngine.from_yaml(str(config.root / "config" / "rules.yaml"), mat_names)
        self.person = PersonStage(
            registry,
            str(person.get("model", "person_yolo")),
            float(person.get("conf", 0.35)),
            float(person.get("iou", 0.5)),
            priority,
        )
        self.pose = PoseStage(
            registry,
            str(pose.get("model", "pose_yolo")),
            float(pose.get("conf", 0.35)),
            float(pose.get("iou", 0.5)),
            priority,
        )
        ppe_conf = float(ppe.get("conf", 0.25))
        self.materials = MaterialsStage(
            registry,
            str(materials.get("model", "materials_yolo")),
            float(materials.get("conf", 0.4)),
            float(materials.get("iou", 0.5)),
            priority,
            tile=int(materials.get("tile", 640)),
            overlap=float(materials.get("overlap", 0.2)),
            enabled="materials" in self.stage_names,
            class_conf={name: ppe_conf for name in _PPE_FROM_SCENE},
        )
        self._ppe_detector = _LazyDetector(
            registry,
            str(ppe.get("model", "ppe_yolo")),
            float(ppe.get("conf", 0.4)),
            float(ppe.get("iou", 0.5)),
            priority,
        )
        self.motion = MotionStage(
            width=int(motion.get("width", 320)),
            history=int(motion.get("history", 300)),
            var_threshold=float(motion.get("var_threshold", 25)),
            min_area=int(motion.get("min_area", 400)),
        )
        self.face = FaceStage(
            registry,
            enabled=bool(config.face_recognition_enabled),
            det_name=str(face_cfg.get("detector", "yunet")),
            rec_name=str(face_cfg.get("recognizer", "sface")),
            min_px=int(face_cfg.get("min_face_px", 80)),
            min_blur=float(face_cfg.get("min_blur", 40)),
            threshold=float(face_cfg.get("match_threshold", 0.36)),
            margin=float(face_cfg.get("margin", 0.05)),
            every=int(self.strides.get("face", face_cfg.get("reverify_frames", 5))),
            gallery_provider=gallery_provider,
        )
        self.posture_cfg = config.section("posture")
        self.ppe_cfg = config.section("ppe")

    def start(self) -> None:
        if not self.thread.is_alive():
            self.thread = threading.Thread(target=self.run, name=f"cam-{self.camera_id[:8]}", daemon=True)
            self.stop_event.clear()
            self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        self.thread.join(timeout=2)

    def set_jpeg(self, payload: bytes) -> None:
        with self.jpeg_lock:
            self.jpeg = payload

    def latest_jpeg(self) -> bytes | None:
        with self.jpeg_lock:
            return self.jpeg

    def run(self) -> None:
        backoff = 1.0
        while not self.stop_event.is_set():
            try:
                self._loop()
                backoff = 1.0
            except Exception as exc:
                self.status = "reconnecting"
                self.last_error = str(exc)
                logger.exception("camera %s failed", self.camera_id)
                if self.stop_event.wait(backoff):
                    break
                backoff = min(backoff * 2, 30)
        self.status = "offline"

    def _loop(self) -> None:
        frames: queue.Queue = queue.Queue(maxsize=2)
        capture = CaptureLoop(self.source, self.stop_event, self.set_jpeg, self.loop_files)
        threading.Thread(target=capture.run, args=(frames,), daemon=True).start()
        self.status = "online"
        while not self.stop_event.is_set():
            try:
                ts, frame = frames.get(timeout=0.5)
            except queue.Empty:
                self.status = capture.status
                self.last_error = capture.last_error
                continue
            self.status = "online"
            ctx = self._process(ts, frame)
            self._publish(ctx)

    def _process(self, ts: float, frame: np.ndarray) -> FrameContext:
        height, width = frame.shape[:2]
        now = time.time()
        if now - self._zones_at > 2:
            try:
                self._zones = self.zone_provider()
            except Exception:
                logger.exception("zone refresh failed")
            self._zones_at = now
        ctx = FrameContext(
            camera_id=self.camera_id,
            ts=ts,
            frame=frame,
            frame_index=self._frame_i,
            width=width,
            height=height,
            zones=self._zones,
            prior_objects=list(self._prior_objects),
            poses=dict(self._hold_poses),
            ppe=dict(self._hold_ppe),
        )
        active_ids = {track.id for track in self._tracker._tracks}
        idle = self.motion_gate and not active_ids
        for name in self.stage_names:
            stride = int(self.strides.get(name, 1) or 1)
            if stride > 1 and ctx.frame_index % stride != 0 and name in {"pose", "materials"}:
                if name == "materials":
                    ctx.objects = list(self._prior_objects)
                continue
            if idle and name in HEAVY and name != "person":
                continue
            started = perf_counter()
            ctx = self._run_stage(name, ctx)
            ctx.timings_ms[name] = (perf_counter() - started) * 1000
            if name == "motion" and self.motion_gate:
                moving = bool(ctx.motion and ctx.motion.detected)
                idle = not moving and not ctx.tracks and not active_ids
        self._hold_poses = dict(ctx.poses)
        self._hold_ppe = dict(ctx.ppe)
        self._prior_objects = list(ctx.objects)
        self._frame_i += 1
        return ctx

    def _run_stage(self, name: str, ctx: FrameContext) -> FrameContext:
        if name == "motion":
            return self.motion.process(ctx)
        if name == "person":
            if self.motion_gate and ctx.motion and not ctx.motion.detected and not self._tracker._tracks:
                ctx.persons = []
                return ctx
            return self.person.process(ctx)
        if name == "tracker":
            ctx.tracks = self._tracker.update(ctx.persons, ctx.ts)
            return ctx
        if name == "pose":
            return self.pose.process(ctx)
        if name == "posture":
            return self._posture_stage(ctx)
        if name == "ppe":
            return self._ppe_stage(ctx)
        if name == "materials":
            return self.materials.process(ctx)
        if name == "face":
            return self.face.process(ctx)
        if name == "rules":
            return self._rules_stage(ctx)
        return ctx

    def _posture_stage(self, ctx: FrameContext) -> FrameContext:
        states: dict[int, PostureState] = {}
        alive = {track.id for track in ctx.tracks}
        for track_id in list(self._posture):
            if track_id not in alive:
                del self._posture[track_id]
        for track in ctx.tracks:
            kps = ctx.poses.get(track.id)
            if kps is None:
                raw = "unknown"
            else:
                cx = ((track.bbox[0] + track.bbox[2]) / 2) / max(ctx.width, 1)
                cy = ((track.bbox[1] + track.bbox[3]) / 2) / max(ctx.height, 1)
                hits = zones_at(cx, cy, ctx.zones)
                in_climb = any(z.type in {"ladder", "scaffold"} or "scaffold" in z.name.lower() for z in hits)
                near = _near_scaffold(track, ctx.prior_objects)
                raw = classify_posture(
                    kps,
                    track.bbox,
                    speed=track.speed,
                    vertical_speed=track.vertical_speed,
                    in_climb_zone=in_climb,
                    near_scaffold=near,
                    cfg=self.posture_cfg,
                )
            smoother = self._posture.setdefault(track.id, PostureSmoother(cfg=self.posture_cfg))
            state = smoother.update(raw, ctx.ts, track.downward_speed)
            states[track.id] = state
            if state.fall:
                ctx.events.append(
                    EventDraft("fall_detected", "critical", "Possible fall", track_id=track.id)
                )
            if state.man_down:
                ctx.events.append(
                    EventDraft("man_down", "critical", "Person lying down", track_id=track.id)
                )
        ctx.postures = states
        return ctx

    def _ppe_stage(self, ctx: FrameContext) -> FrameContext:
        detections: list[Detection] = []
        # The construction model already found helmet and vest. Do not run it again.
        if self._ppe_detector.model_name != self.materials.model_name:
            try:
                detections = list(self._ppe_detector.detect(ctx.frame))
            except Exception as exc:
                self._ppe_detector.fail(exc)
        scene = [det for det in ctx.objects if det.class_name in _PPE_FROM_SCENE]
        if scene:
            self._ppe_boxes = scene
        detections.extend(self._ppe_boxes)
        threshold = float(self.ppe_cfg.get("containment", 0.5))
        conf = float(self.ppe_cfg.get("keypoint_conf", 0.3))
        out: dict[int, dict[str, str]] = {}
        alive = {track.id for track in ctx.tracks}
        blank = np.zeros((17, 3), dtype=np.float64)
        for track in ctx.tracks:
            kps = ctx.poses.get(track.id)
            instant, visible = associate_ppe(
                blank if kps is None else kps,
                track.bbox,
                detections,
                threshold,
                conf,
            )
            out[track.id] = self._ppe.update(track.id, instant, visible)
        for track_id in list(self._ppe._hist):
            if track_id[0] not in alive:
                self._ppe.drop(track_id[0])
        ctx.ppe = out
        return ctx

    def _rules_stage(self, ctx: FrameContext) -> FrameContext:
        from datetime import datetime, timezone

        from app.pipeline.zones import closed_hours_active

        windows = list((self.config.section("site").get("closed_hours") or []))
        closed = closed_hours_active(windows, datetime.now(timezone.utc).astimezone())
        try:
            ctx.events.extend(self.rules.evaluate(ctx, closed))
        except Exception:
            logger.exception("rule engine failed")
        return ctx

    def _publish(self, ctx: FrameContext) -> None:
        now = time.time()
        self._fps_times.append(now)
        self._fps_times = [t for t in self._fps_times if now - t < 2]
        self.fps = (len(self._fps_times) - 1) / 2 if len(self._fps_times) > 1 else 0.0
        self.latency_ms = max(0.0, (now - ctx.ts) * 1000)
        ctx.metrics = {"fps": round(self.fps, 2), "latency_ms": round(self.latency_ms, 1)}
        if now - self._last_pub < (1 / 15):
            if ctx.events:
                self.on_result(_frame_message(ctx), ctx.events, ctx.frame)
            return
        self._last_pub = now
        self.on_result(_frame_message(ctx), ctx.events, ctx.frame)


class _LazyDetector:
    def __init__(self, registry, model_name: str, conf: float, iou: float, priority: list[str]) -> None:
        self.registry = registry
        self.model_name = model_name
        self.conf = conf
        self.iou = iou
        self.priority = priority
        self._model = None
        self.failed = False

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if self.failed:
            return []
        if self._model is None:
            from app.ml.yolo import YoloDetector

            self._model = YoloDetector(self.registry, self.model_name, self.conf, self.iou, self.priority)
        return self._model.detect(frame)

    def fail(self, exc: Exception) -> None:
        if not self.failed:
            logger.error("%s", exc)
        self.failed = True


def _material_names(root) -> list[str]:
    import yaml

    path = root / "config" / "classes.yaml"
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    names = list(data.get("materials") or [])
    return [str(item) for item in names]


def _near_scaffold(track: Track, objects: list[Detection]) -> bool:
    for obj in objects:
        if obj.class_name != "scaffolding":
            continue
        if iou(track.bbox, obj.bbox_xyxy) > 0 or _center_dist(track.bbox, obj.bbox_xyxy) < 1.5:
            return True
    return False


def _center_dist(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    acx, acy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bcx, bcy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    height = max(1.0, a[3] - a[1])
    return ((acx - bcx) ** 2 + (acy - bcy) ** 2) ** 0.5 / height


def _frame_message(ctx: FrameContext) -> dict:
    persons = []
    for track in ctx.tracks:
        posture = ctx.postures.get(track.id)
        kps = ctx.poses.get(track.id)
        keypoints = None
        if kps is not None:
            keypoints = [[round(float(p[0]), 1), round(float(p[1]), 1), round(float(p[2]), 2)] for p in kps]
        face = ctx.faces.get(track.id)
        worker = None
        if face and face.get("result") == "known":
            worker = {
                "id": face.get("worker_id"),
                "name": face.get("name"),
                "score": round(float(face.get("score", 0)), 3),
            }
        persons.append(
            {
                "track_id": track.id,
                "bbox": [round(float(v), 1) for v in track.bbox],
                "posture": posture.state if posture else "unknown",
                "posture_since": posture.since if posture else ctx.ts,
                "ppe": ctx.ppe.get(track.id, {}),
                "worker": worker,
                "keypoints": keypoints,
            }
        )
    motion = None
    if ctx.motion is not None:
        motion = {
            "detected": ctx.motion.detected,
            "score": round(ctx.motion.score, 3),
            "regions": [[round(float(v), 1) for v in box] for box in ctx.motion.regions],
        }
    return {
        "type": "frame",
        "camera_id": ctx.camera_id,
        "ts": ctx.ts,
        "w": ctx.width,
        "h": ctx.height,
        "persons": persons,
        "objects": [
            {
                "class": det.class_name,
                "bbox": [round(float(v), 1) for v in det.bbox_xyxy],
                "score": round(float(det.score), 3),
            }
            for det in ctx.objects
        ],
        "motion": motion,
        "metrics": ctx.metrics,
        "timings_ms": {key: round(value, 2) for key, value in ctx.timings_ms.items()},
    }
