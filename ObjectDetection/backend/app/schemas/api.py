"""Request and response models. Field names follow docs/05-API-SPEC.md."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    expires_in: int
    role: str


class UserIn(BaseModel):
    username: str = Field(min_length=2, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["admin", "officer", "viewer"] = "viewer"


class UserOut(BaseModel):
    id: str
    username: str
    role: str


class CameraIn(BaseModel):
    name: str
    source: str
    enabled: bool = True
    pipeline_overrides: dict[str, Any] | None = None


class CameraPatch(BaseModel):
    name: str | None = None
    source: str | None = None
    enabled: bool | None = None
    pipeline_overrides: dict[str, Any] | None = None


class CameraOut(BaseModel):
    id: str
    name: str
    source: str
    enabled: bool
    status: str
    fps: float
    latency_ms: float
    last_error: str | None = None


class ZoneIn(BaseModel):
    name: str
    type: Literal["restricted", "walkway", "ladder", "office", "storage", "scaffold", "motion", "yard"]
    polygon: list[list[float]]
    schedule: dict[str, Any] | None = None


class ZoneOut(ZoneIn):
    id: str
    camera_id: str


class EventOut(BaseModel):
    id: str
    camera_id: str
    event_type: str
    severity: str
    status: str
    ts: str | None
    track_id: int | None = None
    worker_id: str | None = None
    zone_id: str | None = None
    snapshot_url: str | None = None
    clip_url: str | None = None
    message: str
    meta: dict[str, Any] = Field(default_factory=dict)
    ack_by: str | None = None
    resolved_note: str | None = None


class ResolveIn(BaseModel):
    note: str = ""


class WorkerIn(BaseModel):
    name: str
    employee_id: str = ""
    role: str = ""
    authorized_zones: list[str] = Field(default_factory=list)
    consent: bool = False


class WorkerOut(BaseModel):
    id: str
    name: str
    employee_id: str
    role: str
    authorized_zones: list[str]
    face_count: int


class ReportIn(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["events", "attendance", "ppe"]
    format: Literal["csv", "pdf"]
    from_ts: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
