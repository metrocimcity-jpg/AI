"""Delete snapshots, clips, and rows older than the retention window."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.logging import get_logger
from app.db.models import Event, MaterialCount, PostureSample, PPESample

logger = get_logger("siteguard.retention")


def purge(factory: sessionmaker[Session], data_dir: Path, days: int) -> dict[str, int]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    removed_files = 0
    session = factory()
    try:
        old_events = session.scalars(select(Event).where(Event.ts < cutoff)).all()
        for row in old_events:
            for rel in (row.snapshot_path, row.clip_path):
                if not rel:
                    continue
                path = data_dir / rel
                if path.is_file():
                    path.unlink()
                    removed_files += 1
        event_count = session.execute(delete(Event).where(Event.ts < cutoff)).rowcount or 0
        posture_count = session.execute(delete(PostureSample).where(PostureSample.ts < cutoff)).rowcount or 0
        ppe_count = session.execute(delete(PPESample).where(PPESample.ts < cutoff)).rowcount or 0
        material_count = session.execute(
            delete(MaterialCount).where(MaterialCount.ts_bucket < cutoff)
        ).rowcount or 0
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("retention failed")
        raise
    finally:
        session.close()
    logger.info(
        "retention removed events=%s files=%s posture=%s ppe=%s materials=%s",
        event_count,
        removed_files,
        posture_count,
        ppe_count,
        material_count,
    )
    return {
        "events": int(event_count),
        "files": removed_files,
        "posture_samples": int(posture_count),
        "ppe_samples": int(ppe_count),
        "material_counts": int(material_count),
    }


class RetentionJob:
    def __init__(self, factory: sessionmaker[Session], data_dir: Path, days: int) -> None:
        self.factory = factory
        self.data_dir = data_dir
        self.days = days
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="retention", daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.wait(24 * 3600):
            try:
                purge(self.factory, self.data_dir, self.days)
            except Exception:
                logger.exception("scheduled retention failed")
