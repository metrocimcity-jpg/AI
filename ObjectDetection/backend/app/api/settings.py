"""Settings, rules, model inventory, reports, and retention."""

from __future__ import annotations

import yaml
from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.deps import AdminUser, AuthUser, DbSession
from app.db.models import AuditLog
from app.schemas.api import ReportIn
from app.services.report_service import export_report
from app.services.retention import purge

router = APIRouter(tags=["settings"])


def _public_settings(raw: dict) -> dict:
    return {
        "runtime": raw.get("runtime", {}),
        "site": raw.get("site", {}),
        "pipeline": raw.get("pipeline", {}),
        "detector": raw.get("detector", {}),
        "face": {"enabled": bool((raw.get("face") or {}).get("enabled", False))},
        "retention_days": raw.get("retention_days", 30),
        "events": raw.get("events", {}),
    }


@router.get("/settings")
def get_settings(request: Request, _: AuthUser) -> dict:
    return _public_settings(request.app.state.ctx.config.raw)


@router.put("/settings")
def put_settings(body: dict, request: Request, actor: AdminUser) -> dict:
    state = request.app.state.ctx
    for key in ("runtime", "site", "pipeline", "detector", "face", "events"):
        if key in body and isinstance(body[key], dict):
            current = dict(state.config.raw.get(key) or {})
            current.update(body[key])
            state.config.raw[key] = current
    if "retention_days" in body:
        state.config.raw["retention_days"] = int(body["retention_days"])
        state.config.retention_days = int(body["retention_days"])
    path = state.config.root / "config" / "settings.yaml"
    path.write_text(yaml.safe_dump(state.config.raw, sort_keys=False), encoding="utf-8")
    if "face" in body and "enabled" in body["face"]:
        state.config.face_recognition_enabled = bool(body["face"]["enabled"])
    return _public_settings(state.config.raw)


@router.get("/rules")
def get_rules(request: Request, _: AuthUser) -> dict:
    path = request.app.state.ctx.config.root / "config" / "rules.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@router.put("/rules")
def put_rules(body: dict, request: Request, session: DbSession, actor: AdminUser) -> dict:
    state = request.app.state.ctx
    path = state.config.root / "config" / "rules.yaml"
    path.write_text(yaml.safe_dump(body, sort_keys=False), encoding="utf-8")
    from app.pipeline.rules import RuleEngine

    names = []
    classes = state.config.root / "config" / "classes.yaml"
    if classes.is_file():
        loaded = yaml.safe_load(classes.read_text(encoding="utf-8")) or {}
        names = list(loaded.get("materials") or [])
    engine = RuleEngine.from_yaml(str(path), [str(item) for item in names])
    for worker in state.cameras._workers.values():
        worker.rules = engine
    session.add(AuditLog(user_id=actor.id, action="rules.update", target="rules.yaml"))
    return body


@router.get("/models")
def list_models(request: Request, _: AuthUser) -> dict:
    return {"models": request.app.state.ctx.registry.status()}


@router.post("/models/reload")
def reload_models(request: Request, _: AdminUser) -> dict:
    state = request.app.state.ctx
    state.registry.reload()
    for worker in state.cameras._workers.values():
        for stage in (worker.person, worker.pose, worker.materials):
            stage.failed = False
            stage._model = None
        worker._ppe_detector.failed = False
        worker._ppe_detector._model = None
        worker.face.failed = False
        worker.face._engine = None
    return {"models": state.registry.status()}


@router.post("/reports/export")
def export(body: ReportIn, session: DbSession, _: AuthUser) -> Response:
    payload, media, filename = export_report(session, body.type, body.format, body.from_ts, body.to)
    return Response(
        content=payload,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/retention/run")
def run_retention(request: Request, session: DbSession, actor: AdminUser) -> dict:
    state = request.app.state.ctx
    result = purge(state.sessions, state.config.data_dir, state.config.retention_days)
    session.add(AuditLog(user_id=actor.id, action="retention.run", target=str(result)))
    return result
