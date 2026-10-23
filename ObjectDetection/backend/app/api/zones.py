"""Polygon zones stored with normalized coordinates."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.deps import AdminUser, AuthUser, DbSession
from app.db.models import Camera, Zone
from app.schemas.api import ZoneIn, ZoneOut

router = APIRouter(tags=["zones"])


def _out(row: Zone) -> ZoneOut:
    return ZoneOut(
        id=row.id,
        camera_id=row.camera_id,
        name=row.name,
        type=row.type,  # type: ignore[arg-type]
        polygon=list(row.polygon_json or []),
        schedule=row.schedule_json,
    )


@router.get("/cameras/{camera_id}/zones", response_model=list[ZoneOut])
def list_zones(camera_id: str, session: DbSession, _: AuthUser) -> list[ZoneOut]:
    rows = session.scalars(select(Zone).where(Zone.camera_id == camera_id)).all()
    return [_out(row) for row in rows]


@router.post("/cameras/{camera_id}/zones", response_model=ZoneOut)
def create_zone(camera_id: str, body: ZoneIn, session: DbSession, _: AdminUser) -> ZoneOut:
    if session.get(Camera, camera_id) is None:
        raise HTTPException(status_code=404, detail="camera not found")
    if len(body.polygon) < 3:
        raise HTTPException(status_code=400, detail="polygon needs at least 3 points")
    row = Zone(
        id=str(uuid.uuid4()),
        camera_id=camera_id,
        name=body.name,
        type=body.type,
        polygon_json=body.polygon,
        schedule_json=body.schedule,
    )
    session.add(row)
    session.flush()
    return _out(row)


@router.patch("/zones/{zone_id}", response_model=ZoneOut)
def update_zone(zone_id: str, body: ZoneIn, session: DbSession, _: AdminUser) -> ZoneOut:
    row = session.get(Zone, zone_id)
    if row is None:
        raise HTTPException(status_code=404, detail="zone not found")
    row.name = body.name
    row.type = body.type
    row.polygon_json = body.polygon
    row.schedule_json = body.schedule
    session.flush()
    return _out(row)


@router.delete("/zones/{zone_id}")
def delete_zone(zone_id: str, session: DbSession, _: AdminUser) -> dict:
    row = session.get(Zone, zone_id)
    if row is None:
        raise HTTPException(status_code=404, detail="zone not found")
    session.delete(row)
    return {"deleted": zone_id}
