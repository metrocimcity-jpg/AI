"""Event list, detail, acknowledge, and resolve."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.deps import AuthUser, DbSession, OfficerUser
from app.db.models import Event
from app.schemas.api import EventOut, ResolveIn
from app.services.event_service import event_payload

router = APIRouter(prefix="/events", tags=["events"])


def _to_out(row: Event) -> EventOut:
    return EventOut(**event_payload(row))


@router.get("")
def list_events(
    session: DbSession,
    _: AuthUser,
    camera_id: str | None = None,
    type: str | None = None,
    severity: str | None = None,
    status: str | None = None,
    worker_id: str | None = None,
    from_ts: datetime | None = None,
    to_ts: datetime | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> dict:
    limit = max(1, min(limit, 200))
    stmt = select(Event)
    if camera_id:
        stmt = stmt.where(Event.camera_id == camera_id)
    if type:
        stmt = stmt.where(Event.event_type == type)
    if severity:
        stmt = stmt.where(Event.severity == severity)
    if status:
        stmt = stmt.where(Event.status == status)
    if worker_id:
        stmt = stmt.where(Event.worker_id == worker_id)
    if from_ts:
        stmt = stmt.where(Event.ts >= from_ts)
    if to_ts:
        stmt = stmt.where(Event.ts <= to_ts)
    if cursor:
        current = session.get(Event, cursor)
        if current is not None:
            stmt = stmt.where(Event.ts < current.ts)
    rows = session.scalars(stmt.order_by(Event.ts.desc()).limit(limit)).all()
    next_cursor = rows[-1].id if len(rows) == limit else None
    return {"items": [_to_out(row).model_dump() for row in rows], "next_cursor": next_cursor}


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, session: DbSession, _: AuthUser) -> EventOut:
    row = session.get(Event, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    return _to_out(row)


@router.post("/{event_id}/ack", response_model=EventOut)
def ack_event(event_id: str, session: DbSession, user: OfficerUser) -> EventOut:
    row = session.get(Event, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    row.status = "ack"
    row.ack_by = user.id
    session.flush()
    return _to_out(row)


@router.post("/{event_id}/resolve", response_model=EventOut)
def resolve_event(event_id: str, body: ResolveIn, session: DbSession, user: OfficerUser) -> EventOut:
    row = session.get(Event, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail="event not found")
    row.status = "resolved"
    row.ack_by = row.ack_by or user.id
    row.resolved_note = body.note
    session.flush()
    return _to_out(row)
