"""Start, stop, and supervise one worker thread per camera."""

from __future__ import annotations

import threading
import time
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import AppConfig
from app.core.logging import get_logger
from app.db.models import Camera, FaceEmbedding, Worker, Zone
from app.ml.registry import ModelRegistry
from app.pipeline.base import EventDraft, ZoneView
from app.pipeline.worker import CameraWorker
from app.services.broadcaster import Broadcaster
from app.services.event_service import EventService

logger = get_logger("siteguard.cameras")


class CameraManager:
    def __init__(
        self,
        config: AppConfig,
        registry: ModelRegistry,
        factory: sessionmaker[Session],
        events: EventService,
        broadcaster: Broadcaster,
        decode_gallery,  # type: ignore[no-untyped-def]
    ) -> None:
        self.config = config
        self.registry = registry
        self.factory = factory
        self.events = events
        self.broadcaster = broadcaster
        self.decode_gallery = decode_gallery
        self._wanted: set[str] = set()
        self._workers: dict[str, CameraWorker] = {}
        self._latest: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._watchdog = threading.Thread(target=self._watch, name="camera-watchdog", daemon=True)
        self._sample_at: dict[tuple[str, int], float] = {}
        self._material_at: dict[str, float] = {}

    def start_enabled(self) -> None:
        if not self.config.autostart_cameras:
            self._watchdog.start()
            return
        session = self.factory()
        try:
            rows = session.scalars(select(Camera).where(Camera.enabled.is_(True))).all()
            ids = [row.id for row in rows]
        finally:
            session.close()
        for camera_id in ids:
            self.start(camera_id)
        self._watchdog.start()

    def stop_all(self) -> None:
        self._stop.set()
        with self._lock:
            workers = list(self._workers.values())
            self._workers.clear()
        for worker in workers:
            worker.stop()

    def start(self, camera_id: str) -> None:
        session = self.factory()
        try:
            row = session.get(Camera, camera_id)
            if row is None:
                return
            source = row.source
            name = row.name
            overrides = dict(row.config_json or {})
        finally:
            session.close()
        with self._lock:
            self._wanted.add(camera_id)
            current = self._workers.get(camera_id)
            if current and current.thread.is_alive():
                return
            worker = CameraWorker(
                camera_id=camera_id,
                name=name,
                source=source,
                config=self.config,
                registry=self.registry,
                on_result=lambda message, drafts, frame, cid=camera_id: self._on_result(
                    cid, message, drafts, frame
                ),
                zone_provider=lambda cid=camera_id: self._zones(cid),
                gallery_provider=self._gallery,
                overrides=overrides,
            )
            self._workers[camera_id] = worker
        worker.start()
        self.broadcaster.publish(
            {"type": "camera_status", "camera_id": camera_id, "status": "online"}
        )

    def stop(self, camera_id: str) -> None:
        with self._lock:
            self._wanted.discard(camera_id)
            worker = self._workers.pop(camera_id, None)
        if worker:
            worker.stop()
        self.broadcaster.publish(
            {"type": "camera_status", "camera_id": camera_id, "status": "offline"}
        )

    def runtime(self, camera_id: str) -> dict[str, Any]:
        with self._lock:
            worker = self._workers.get(camera_id)
        if worker is None:
            return {"status": "offline", "fps": 0.0, "latency_ms": 0.0, "last_error": None}
        return {
            "status": worker.status,
            "fps": round(worker.fps, 2),
            "latency_ms": round(worker.latency_ms, 1),
            "last_error": worker.last_error,
        }

    def latest_jpeg(self, camera_id: str) -> bytes | None:
        with self._lock:
            worker = self._workers.get(camera_id)
        if worker is None:
            return None
        return worker.latest_jpeg()

    def latest_frame(self, camera_id: str) -> dict[str, Any] | None:
        return self._latest.get(camera_id)

    def all_latest(self) -> list[dict[str, Any]]:
        return list(self._latest.values())

    def _on_result(
        self, camera_id: str, message: dict[str, Any], drafts: list[EventDraft], frame: np.ndarray
    ) -> None:
        self._latest[camera_id] = message
        self.broadcaster.publish(message)
        if drafts:
            self.events.record(camera_id, drafts, frame, message.get("ts"))
        self._maybe_sample(camera_id, message)

    def _maybe_sample(self, camera_id: str, message: dict[str, Any]) -> None:
        ts = float(message.get("ts") or time.time())
        for person in message.get("persons") or []:
            track_id = int(person["track_id"])
            key = (camera_id, track_id)
            if ts - self._sample_at.get(key, 0) < 1:
                continue
            self._sample_at[key] = ts
            self.events.sample_posture(camera_id, ts, track_id, str(person.get("posture") or "unknown"))
            ppe = person.get("ppe") or {}
            if ppe:
                self.events.sample_ppe(camera_id, ts, track_id, ppe)
            worker = person.get("worker") or {}
            if worker.get("id"):
                self.events.mark_attendance(str(worker["id"]), camera_id, ts)
        if ts - self._material_at.get(camera_id, 0) < 60:
            return
        self._material_at[camera_id] = ts
        counts: dict[str, int] = {}
        areas: dict[str, float] = {}
        width = max(1, int(message.get("w") or 1))
        height = max(1, int(message.get("h") or 1))
        frame_area = float(width * height)
        for obj in message.get("objects") or []:
            name = str(obj.get("class"))
            counts[name] = counts.get(name, 0) + 1
            box = obj.get("bbox") or [0, 0, 0, 0]
            areas[name] = areas.get(name, 0.0) + max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])
        for name, count in counts.items():
            self.events.upsert_material(camera_id, ts, name, count, areas[name] / frame_area)

    def _zones(self, camera_id: str) -> list[ZoneView]:
        session = self.factory()
        try:
            rows = session.scalars(select(Zone).where(Zone.camera_id == camera_id)).all()
            return [
                ZoneView(
                    id=row.id,
                    name=row.name,
                    type=row.type,
                    polygon=list(row.polygon_json or []),
                    schedule=row.schedule_json,
                )
                for row in rows
            ]
        finally:
            session.close()

    def _gallery(self) -> list[tuple[str, str, np.ndarray]]:
        if not self.config.face_recognition_enabled:
            return []
        session = self.factory()
        try:
            rows = session.scalars(select(FaceEmbedding)).all()
            people = {row.id: row for row in session.scalars(select(Worker)).all()}
            gallery = []
            for row in rows:
                worker = people.get(row.worker_id)
                if worker is None:
                    continue
                vec = self.decode_gallery(row.embedding_blob)
                gallery.append((worker.id, worker.name, vec))
            return gallery
        finally:
            session.close()

    def _watch(self) -> None:
        while not self._stop.wait(5):
            session = self.factory()
            try:
                enabled = {
                    row.id: row
                    for row in session.scalars(select(Camera).where(Camera.enabled.is_(True))).all()
                }
            finally:
                session.close()
            with self._lock:
                wanted = set(self._wanted)
                current = dict(self._workers)
            for camera_id in wanted:
                if camera_id not in enabled:
                    continue
                worker = current.get(camera_id)
                if worker is None or not worker.thread.is_alive():
                    logger.warning("restarting camera %s", camera_id)
                    self.start(camera_id)
                    self.broadcaster.publish(
                        {
                            "type": "camera_status",
                            "camera_id": camera_id,
                            "status": "reconnecting",
                        }
                    )
