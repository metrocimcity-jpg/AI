"""Persist alerts, snapshots, and sampled analytics."""

from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.logging import get_logger
from app.db.models import Attendance, Event, MaterialCount, PostureSample, PPESample
from app.pipeline.base import EventDraft
from app.services.broadcaster import Broadcaster

logger = get_logger("siteguard.events")


class EventService:
    def __init__(
        self,
        factory: sessionmaker[Session],
        data_dir: Path,
        broadcaster: Broadcaster,
        cooldowns: dict[str, float] | None = None,
        save_clips: bool = False,
    ) -> None:
        self.factory = factory
        self.data_dir = data_dir
        self.broadcaster = broadcaster
        self.cooldowns = cooldowns or {}
        self.save_clips = save_clips
        self._last: dict[tuple[str, int | None, str], float] = {}
        self._lock = threading.Lock()
        (self.data_dir / "snapshots").mkdir(parents=True, exist_ok=True)
        (self.data_dir / "clips").mkdir(parents=True, exist_ok=True)

    def on_cooldown(self, camera_id: str, draft: EventDraft, now: float) -> bool:
        seconds = float(self.cooldowns.get(draft.event_type, 30))
        key = (camera_id, draft.track_id, draft.event_type)
        with self._lock:
            last = self._last.get(key, -1e12)
            if now - last < seconds:
                return True
            self._last[key] = now
        return False

    def record(
        self, camera_id: str, drafts: list[EventDraft], frame: np.ndarray, now: float | None = None
    ) -> list[dict]:
        moment = now if now is not None else time_now()
        saved: list[dict] = []
        session = self.factory()
        try:
            for draft in drafts:
                if self.on_cooldown(camera_id, draft, moment):
                    continue
                event_id = str(uuid.uuid4())
                rel = self._write_snapshot(camera_id, event_id, frame)
                meta = dict(draft.meta)
                meta.setdefault("message", draft.message)
                row = Event(
                    id=event_id,
                    camera_id=camera_id,
                    event_type=draft.event_type,
                    severity=draft.severity,
                    status="open",
                    ts=datetime.fromtimestamp(moment, timezone.utc),
                    track_id=draft.track_id,
                    worker_id=draft.worker_id,
                    zone_id=draft.zone_id,
                    snapshot_path=rel,
                    meta_json=meta,
                )
                session.add(row)
                payload = event_payload(row)
                saved.append(payload)
                self.broadcaster.publish({"type": "event", "event": payload})
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("failed to store events")
        finally:
            session.close()
        return saved

    def _write_snapshot(self, camera_id: str, event_id: str, frame: np.ndarray) -> str:
        rel = f"snapshots/{camera_id}/{event_id}.jpg"
        path = self.data_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), frame)
        return rel

    def sample_posture(self, camera_id: str, ts: float, track_id: int, state: str) -> None:
        self._add(
            PostureSample(
                camera_id=camera_id,
                ts=datetime.fromtimestamp(ts, timezone.utc),
                track_id=track_id,
                state=state,
            )
        )

    def sample_ppe(self, camera_id: str, ts: float, track_id: int, ppe: dict[str, str]) -> None:
        self._add(
            PPESample(
                camera_id=camera_id,
                ts=datetime.fromtimestamp(ts, timezone.utc),
                track_id=track_id,
                helmet=ppe.get("helmet", "unknown"),
                vest=ppe.get("vest", "unknown"),
                gloves=ppe.get("gloves", "unknown"),
                boots=ppe.get("boots", "unknown"),
                goggles=ppe.get("goggles", "unknown"),
                harness=ppe.get("harness", "unknown"),
            )
        )

    def upsert_material(
        self, camera_id: str, ts: float, class_name: str, count: int, area_ratio: float
    ) -> None:
        bucket = datetime.fromtimestamp(int(ts) // 60 * 60, timezone.utc)
        session = self.factory()
        try:
            row = session.scalar(
                select(MaterialCount).where(
                    MaterialCount.camera_id == camera_id,
                    MaterialCount.ts_bucket == bucket,
                    MaterialCount.class_name == class_name,
                )
            )
            if row is None:
                session.add(
                    MaterialCount(
                        camera_id=camera_id,
                        ts_bucket=bucket,
                        class_name=class_name,
                        count=count,
                        area_ratio=area_ratio,
                    )
                )
            else:
                row.count = count
                row.area_ratio = area_ratio
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("material count failed")
        finally:
            session.close()

    def mark_attendance(self, worker_id: str, camera_id: str, ts: float) -> None:
        moment = datetime.fromtimestamp(ts, timezone.utc)
        day = moment.date().isoformat()
        session = self.factory()
        try:
            row = session.scalar(
                select(Attendance).where(
                    Attendance.worker_id == worker_id,
                    Attendance.camera_id == camera_id,
                    Attendance.date == day,
                )
            )
            if row is None:
                session.add(
                    Attendance(
                        worker_id=worker_id,
                        camera_id=camera_id,
                        date=day,
                        first_seen=moment,
                        last_seen=moment,
                    )
                )
            else:
                row.last_seen = moment
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("attendance update failed")
        finally:
            session.close()

    def _add(self, row: object) -> None:
        session = self.factory()
        try:
            session.add(row)
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("sample write failed")
        finally:
            session.close()


def time_now() -> float:
    return datetime.now(timezone.utc).timestamp()


def event_payload(row: Event) -> dict:
    snapshot = f"/media/{row.snapshot_path}" if row.snapshot_path else None
    clip = f"/media/{row.clip_path}" if row.clip_path else None
    return {
        "id": row.id,
        "camera_id": row.camera_id,
        "event_type": row.event_type,
        "severity": row.severity,
        "status": row.status,
        "ts": row.ts.isoformat() if row.ts else None,
        "track_id": row.track_id,
        "worker_id": row.worker_id,
        "zone_id": row.zone_id,
        "snapshot_url": snapshot,
        "clip_url": clip,
        "message": (row.meta_json or {}).get("message") or row.event_type.replace("_", " "),
        "meta": row.meta_json or {},
        "ack_by": row.ack_by,
        "resolved_note": row.resolved_note,
    }
