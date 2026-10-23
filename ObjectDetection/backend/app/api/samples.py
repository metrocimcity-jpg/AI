"""Local sample clips used by the Test tab."""

from __future__ import annotations

import uuid
from pathlib import Path

import cv2
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.core.deps import AdminUser, DbSession
from app.db.models import AuditLog, Camera

router = APIRouter(prefix="/samples", tags=["samples"])

CLIPS: dict[str, dict[str, str]] = {
    "zone": {
        "file": "site-test.mp4",
        "fallback": "worker-zone-detection.mp4",
        "preview": "worker-zone-detection.mp4",
        "title": "Workers in a zone",
        "detail": "Intel IoT worker-zone clip, repeated to five minutes. People move through a marked work area.",
    },
    "ppe": {
        "file": "ppe-violations.mp4",
        "title": "Helmet and vest check",
        "detail": "CC BY 4.0 photos labeled no-helmet and no-vest. Each photo is held for three seconds.",
    },
    "materials": {
        "file": "materials-full.mp4",
        "fallback": "materials-conveyor.mp4",
        "min_bytes": "18000000",
        "title": "Material counting",
        "detail": "Brick, concrete, steel reinforcement, and timber on a moving conveyor. CC BY 4.0, Zenodo 17447590.",
    },
    "cement": {
        "file": "cement-bags.mp4",
        "fallback": "cement-bags.webm",
        "min_bytes": "83000000",
        "title": "Cement bags",
        "detail": "1930 public-domain site film. Workers empty cement sacks into the mixer.",
    },
    "gypsum": {
        "file": "gypsum-board.mp4",
        "min_bytes": "130000000",
        "title": "Gypsum board",
        "detail": "U.S. Marine Corps public-domain footage of drywall work in a barracks.",
    },
    "steel": {
        "file": "steel-beams.mp4",
        "min_bytes": "80000000",
        "title": "Steel beams",
        "detail": "1930 public-domain film. Cranes set the Empire State Building steel frame.",
    },
}


def root_preview(path: Path) -> Path | None:
    if path.is_file() and path.stat().st_size > 1000:
        return path
    return None


def _path_for(root: Path, spec: dict[str, str]) -> Path | None:
    folder = root / "samples"
    for key in ("file", "fallback"):
        name = spec.get(key)
        if not name:
            continue
        path = folder / name
        minimum = int(spec.get("min_bytes", "1000"))
        if path.is_file() and path.stat().st_size >= minimum:
            return path
    return None


def _seconds(path: Path) -> float | None:
    capture = cv2.VideoCapture(str(path))
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    capture.release()
    if fps <= 0 or frames <= 0:
        return None
    return round(frames / fps, 1)


def _describe(clip_id: str, spec: dict[str, str], path: Path | None) -> dict:
    body = {
        "id": clip_id,
        "title": spec["title"],
        "detail": spec["detail"],
        "file": spec["file"],
        "ready": path is not None,
    }
    if path is None:
        return body
    preview = path
    preview_name = spec.get("preview")
    if preview_name:
        candidate = root_preview(path.parent / preview_name)
        if candidate is not None:
            preview = candidate
    body.update(
        {
            "file": path.name,
            "url": f"/sample/{preview.name}",
            "source": str(path),
            "seconds": _seconds(path),
        }
    )
    return body


@router.get("")
def list_clips(request: Request) -> dict:
    root = request.app.state.ctx.config.root
    items = [_describe(clip_id, spec, _path_for(root, spec)) for clip_id, spec in CLIPS.items()]
    return {"items": items}


@router.post("/{clip_id}/camera")
def start_clip_camera(clip_id: str, request: Request, session: DbSession, user: AdminUser) -> dict:
    spec = CLIPS.get(clip_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="unknown sample")
    path = _path_for(request.app.state.ctx.config.root, spec)
    if path is None:
        raise HTTPException(status_code=404, detail="sample clip is not in samples/")
    source = str(path)
    row = session.scalar(select(Camera).where(Camera.source == source))
    state = request.app.state.ctx
    if row is None:
        count = len(session.scalars(select(Camera)).all())
        if count >= int(state.config.section("runtime").get("max_cameras", 8)):
            raise HTTPException(status_code=400, detail="camera limit reached")
        row = Camera(
            id=str(uuid.uuid4()),
            name=spec["title"],
            source=source,
            enabled=True,
            config_json={},
        )
        session.add(row)
        session.add(AuditLog(user_id=user.id, action="camera.create", target=row.id))
        session.commit()
    state.cameras.start(row.id)
    return {"id": row.id, "name": row.name, "source": source}
