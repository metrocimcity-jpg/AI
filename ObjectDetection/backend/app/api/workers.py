"""Worker records and opt-in face enrollment. Embeddings are never returned."""

from __future__ import annotations

import uuid

import cv2
import numpy as np
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from sqlalchemy import select

from app.core.deps import AdminUser, AuthUser, DbSession
from app.core.security import fernet_from_secret
from app.db.models import Attendance, AuditLog, FaceEmbedding, Worker
from app.ml.registry import ModelError
from app.pipeline.face import FaceEngine
from app.schemas.api import WorkerIn, WorkerOut

router = APIRouter(prefix="/workers", tags=["workers"])


def _out(row: Worker) -> WorkerOut:
    return WorkerOut(
        id=row.id,
        name=row.name,
        employee_id=row.employee_id,
        role=row.role,
        authorized_zones=list(row.authorized_zones_json or []),
        face_count=len(row.embeddings or []),
    )


def _require_face(request: Request) -> None:
    if not request.app.state.ctx.config.face_recognition_enabled:
        raise HTTPException(status_code=403, detail="face recognition is disabled in config")


@router.get("", response_model=list[WorkerOut])
def list_workers(session: DbSession, _: AuthUser) -> list[WorkerOut]:
    rows = session.scalars(select(Worker).order_by(Worker.name)).all()
    return [_out(row) for row in rows]


@router.post("", response_model=WorkerOut)
def create_worker(body: WorkerIn, session: DbSession, actor: AdminUser) -> WorkerOut:
    row = Worker(
        id=str(uuid.uuid4()),
        name=body.name,
        employee_id=body.employee_id,
        role=body.role,
        authorized_zones_json=body.authorized_zones,
    )
    session.add(row)
    session.add(AuditLog(user_id=actor.id, action="worker.create", target=row.id))
    session.flush()
    return _out(row)


@router.delete("/faces")
def delete_all_faces(session: DbSession, actor: AdminUser) -> dict:
    rows = session.scalars(select(FaceEmbedding)).all()
    count = len(rows)
    for row in rows:
        session.delete(row)
    session.add(AuditLog(user_id=actor.id, action="faces.delete_all", target=str(count)))
    return {"deleted": count}


@router.delete("/{worker_id}")
def delete_worker(worker_id: str, session: DbSession, actor: AdminUser) -> dict:
    row = session.get(Worker, worker_id)
    if row is None:
        raise HTTPException(status_code=404, detail="worker not found")
    session.delete(row)
    session.add(AuditLog(user_id=actor.id, action="worker.delete", target=worker_id))
    return {"deleted": worker_id}


@router.post("/{worker_id}/faces")
async def enroll_faces(
    worker_id: str,
    request: Request,
    session: DbSession,
    actor: AdminUser,
    files: list[UploadFile] = File(...),
    consent: bool = False,
) -> dict:
    _require_face(request)
    if not consent:
        raise HTTPException(status_code=400, detail="consent is required before enrollment")
    row = session.get(Worker, worker_id)
    if row is None:
        raise HTTPException(status_code=404, detail="worker not found")
    if not 1 <= len(files) <= 5:
        raise HTTPException(status_code=400, detail="upload 1 to 5 photos")
    state = request.app.state.ctx
    face_cfg = state.config.section("face")
    try:
        engine = FaceEngine(
            state.registry,
            str(face_cfg.get("detector", "yunet")),
            str(face_cfg.get("recognizer", "sface")),
        )
    except ModelError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    fernet = fernet_from_secret(state.config.secret_key)
    stored = 0
    for upload in files:
        raw = await upload.read()
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            continue
        try:
            embedded = engine.embed(
                image,
                int(face_cfg.get("min_face_px", 80)),
                float(face_cfg.get("min_blur", 40)),
            )
        except cv2.error as exc:
            raise HTTPException(status_code=409, detail=f"face model failed: {exc}") from exc
        if embedded is None:
            continue
        vec, _quality = embedded
        blob = fernet.encrypt(np.asarray(vec, dtype=np.float32).tobytes())
        session.add(
            FaceEmbedding(
                id=str(uuid.uuid4()),
                worker_id=worker_id,
                embedding_blob=blob,
                model=str(face_cfg.get("recognizer", "sface")),
            )
        )
        stored += 1
    if stored == 0:
        raise HTTPException(status_code=422, detail="no photo passed the quality gate")
    session.add(AuditLog(user_id=actor.id, action="worker.enroll", target=worker_id))
    session.flush()
    return {"stored": stored}


@router.delete("/{worker_id}/faces")
def delete_faces(worker_id: str, session: DbSession, actor: AdminUser) -> dict:
    row = session.get(Worker, worker_id)
    if row is None:
        raise HTTPException(status_code=404, detail="worker not found")
    count = len(row.embeddings)
    row.embeddings.clear()
    session.add(AuditLog(user_id=actor.id, action="worker.faces.delete", target=worker_id))
    return {"deleted": count}


@router.get("/{worker_id}/attendance")
def attendance(worker_id: str, session: DbSession, _: AuthUser) -> list[dict]:
    rows = session.scalars(
        select(Attendance).where(Attendance.worker_id == worker_id).order_by(Attendance.date.desc())
    ).all()
    return [
        {
            "camera_id": row.camera_id,
            "date": row.date,
            "first_seen": row.first_seen.isoformat(),
            "last_seen": row.last_seen.isoformat(),
        }
        for row in rows
    ]
