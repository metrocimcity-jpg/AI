"""Camera registry, control, snapshots, and MJPEG."""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.deps import AdminUser, AuthUser, DbSession, OfficerUser
from app.db.models import AuditLog, Camera
from app.schemas.api import CameraIn, CameraOut, CameraPatch

router = APIRouter(prefix="/cameras", tags=["cameras"])


def _redact(source: str, role: str) -> str:
    if role == "viewer" and "@" in source and "://" in source:
        scheme, rest = source.split("://", 1)
        host = rest.split("@", 1)[1]
        return f"{scheme}://***@{host}"
    return source


def _out(row: Camera, request: Request, role: str) -> CameraOut:
    runtime = request.app.state.ctx.cameras.runtime(row.id)
    return CameraOut(
        id=row.id,
        name=row.name,
        source=_redact(row.source, role),
        enabled=row.enabled,
        status=runtime["status"],
        fps=runtime["fps"],
        latency_ms=runtime["latency_ms"],
        last_error=runtime["last_error"],
    )


@router.get("", response_model=list[CameraOut])
def list_cameras(request: Request, session: DbSession, user: AuthUser) -> list[CameraOut]:
    rows = session.scalars(select(Camera).order_by(Camera.created_at)).all()
    return [_out(row, request, user.role) for row in rows]


@router.post("", response_model=CameraOut)
def create_camera(
    body: CameraIn, request: Request, session: DbSession, user: AdminUser
) -> CameraOut:
    state = request.app.state.ctx
    count = len(session.scalars(select(Camera)).all())
    if count >= int(state.config.section("runtime").get("max_cameras", 8)):
        raise HTTPException(status_code=400, detail="camera limit reached")
    row = Camera(
        id=str(uuid.uuid4()),
        name=body.name,
        source=body.source,
        enabled=body.enabled,
        config_json=body.pipeline_overrides or {},
    )
    session.add(row)
    session.add(AuditLog(user_id=user.id, action="camera.create", target=row.id))
    session.commit()
    if row.enabled:
        state.cameras.start(row.id)
    return _out(row, request, user.role)


@router.patch("/{camera_id}", response_model=CameraOut)
def update_camera(
    camera_id: str, body: CameraPatch, request: Request, session: DbSession, user: AdminUser
) -> CameraOut:
    row = session.get(Camera, camera_id)
    if row is None:
        raise HTTPException(status_code=404, detail="camera not found")
    if body.name is not None:
        row.name = body.name
    if body.source is not None:
        row.source = body.source
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.pipeline_overrides is not None:
        row.config_json = body.pipeline_overrides
    session.add(AuditLog(user_id=user.id, action="camera.update", target=row.id))
    session.flush()
    return _out(row, request, user.role)


@router.delete("/{camera_id}")
def delete_camera(camera_id: str, request: Request, session: DbSession, user: AdminUser) -> dict:
    row = session.get(Camera, camera_id)
    if row is None:
        raise HTTPException(status_code=404, detail="camera not found")
    request.app.state.ctx.cameras.stop(camera_id)
    session.delete(row)
    session.add(AuditLog(user_id=user.id, action="camera.delete", target=camera_id))
    return {"deleted": camera_id}


@router.post("/{camera_id}/start", response_model=CameraOut)
def start_camera(camera_id: str, request: Request, session: DbSession, _: OfficerUser) -> CameraOut:
    row = session.get(Camera, camera_id)
    if row is None:
        raise HTTPException(status_code=404, detail="camera not found")
    row.enabled = True
    session.commit()
    request.app.state.ctx.cameras.start(camera_id)
    return _out(row, request, "admin")


@router.post("/{camera_id}/stop", response_model=CameraOut)
def stop_camera(camera_id: str, request: Request, session: DbSession, _: OfficerUser) -> CameraOut:
    row = session.get(Camera, camera_id)
    if row is None:
        raise HTTPException(status_code=404, detail="camera not found")
    row.enabled = False
    session.flush()
    request.app.state.ctx.cameras.stop(camera_id)
    return _out(row, request, "admin")


@router.get("/{camera_id}/snapshot.jpg")
def snapshot(camera_id: str, request: Request, _: AuthUser) -> Response:
    jpeg = request.app.state.ctx.cameras.latest_jpeg(camera_id)
    if not jpeg:
        raise HTTPException(status_code=404, detail="no frame yet")
    return Response(content=jpeg, media_type="image/jpeg")


@router.get("/{camera_id}/stream.mjpg")
async def stream(camera_id: str, request: Request, _: AuthUser) -> StreamingResponse:
    manager = request.app.state.ctx.cameras

    async def frames():
        while True:
            if await request.is_disconnected():
                break
            jpeg = manager.latest_jpeg(camera_id)
            if jpeg:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
            await asyncio.sleep(0.05)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")
