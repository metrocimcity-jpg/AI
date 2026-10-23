"""Dashboard aggregates from live frames and stored samples."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Request
from sqlalchemy import func, select

from app.core.deps import AuthUser, DbSession
from app.db.models import Attendance, Event, MaterialCount, PostureSample, PPESample

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/overview")
def overview(request: Request, session: DbSession, _: AuthUser) -> dict:
    state = request.app.state.ctx
    frames = state.cameras.all_latest()
    people = 0
    compliant = 0
    considered = 0
    postures: Counter[str] = Counter()
    materials: Counter[str] = Counter()
    fps = []
    latency = []
    online = 0
    for frame in frames:
        persons = frame.get("persons") or []
        people += len(persons)
        metrics = frame.get("metrics") or {}
        if metrics.get("fps"):
            fps.append(float(metrics["fps"]))
        if metrics.get("latency_ms") is not None:
            latency.append(float(metrics["latency_ms"]))
        for person in persons:
            postures[str(person.get("posture") or "unknown")] += 1
            ppe = person.get("ppe") or {}
            helmet, vest = ppe.get("helmet"), ppe.get("vest")
            if helmet in {"ok", "missing"} or vest in {"ok", "missing"}:
                considered += 1
                if helmet != "missing" and vest != "missing":
                    compliant += 1
        for obj in frame.get("objects") or []:
            materials[str(obj.get("class"))] += 1
    for _camera_id, worker in list(state.cameras._workers.items()):
        if worker.status == "online":
            online += 1
    active = session.scalar(
        select(func.count()).select_from(Event).where(Event.status == "open")
    )
    recent = session.scalars(select(Event).order_by(Event.ts.desc()).limit(8)).all()
    from app.services.event_service import event_payload

    return {
        "people_now": people,
        "active_alerts": int(active or 0),
        "ppe_compliance_pct": round(100 * compliant / considered, 1) if considered else None,
        "cameras_online": online,
        "fps_avg": round(sum(fps) / len(fps), 2) if fps else 0.0,
        "latency_ms_avg": round(sum(latency) / len(latency), 1) if latency else 0.0,
        "posture_counts": dict(postures),
        "material_counts": dict(materials),
        "recent_events": [event_payload(row) for row in recent],
    }


def _range(hours: int = 24) -> datetime:
    return datetime.now(timezone.utc) - timedelta(hours=hours)


@router.get("/ppe")
def ppe_stats(session: DbSession, _: AuthUser, bucket: str = "hour") -> dict:
    rows = session.scalars(select(PPESample).where(PPESample.ts >= _range())).all()
    grouped: dict[str, list[PPESample]] = {}
    for row in rows:
        key = row.ts.strftime("%Y-%m-%d %H:00") if bucket == "hour" else row.ts.strftime("%Y-%m-%d")
        grouped.setdefault(key, []).append(row)
    series = []
    for key in sorted(grouped):
        items = grouped[key]
        known = [item for item in items if item.helmet in {"ok", "missing"}]
        pct = (
            round(100 * sum(1 for item in known if item.helmet == "ok") / len(known), 1)
            if known
            else None
        )
        series.append({"bucket": key, "samples": len(items), "helmet_ok_pct": pct})
    return {"series": series}


@router.get("/posture")
def posture_stats(session: DbSession, _: AuthUser) -> dict:
    rows = session.scalars(select(PostureSample).where(PostureSample.ts >= _range())).all()
    counts = Counter(row.state for row in rows)
    return {"counts": dict(counts)}


@router.get("/materials")
def material_stats(session: DbSession, _: AuthUser, class_name: str | None = None) -> dict:
    stmt = select(MaterialCount).where(MaterialCount.ts_bucket >= _range())
    if class_name:
        stmt = stmt.where(MaterialCount.class_name == class_name)
    rows = session.scalars(stmt.order_by(MaterialCount.ts_bucket)).all()
    return {
        "series": [
            {
                "bucket": row.ts_bucket.isoformat(),
                "camera_id": row.camera_id,
                "class_name": row.class_name,
                "count": row.count,
                "area_ratio": row.area_ratio,
            }
            for row in rows
        ]
    }


@router.get("/attendance")
def attendance(session: DbSession, _: AuthUser, date: str | None = None) -> dict:
    day = date or datetime.now(timezone.utc).date().isoformat()
    rows = session.scalars(select(Attendance).where(Attendance.date == day)).all()
    return {
        "date": day,
        "items": [
            {
                "worker_id": row.worker_id,
                "camera_id": row.camera_id,
                "first_seen": row.first_seen.isoformat(),
                "last_seen": row.last_seen.isoformat(),
            }
            for row in rows
        ],
    }
