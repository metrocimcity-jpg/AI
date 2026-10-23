"""Frame context shared by every pipeline stage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from app.ml.postprocess import Detection


@dataclass
class MotionResult:
    detected: bool
    score: float
    regions: list[tuple[float, float, float, float]] = field(default_factory=list)


@dataclass
class Track:
    id: int
    bbox: tuple[float, float, float, float]
    score: float
    speed: float = 0.0
    vertical_speed: float = 0.0
    downward_speed: float = 0.0
    missed: int = 0


@dataclass
class PostureState:
    state: str = "unknown"
    since: float = 0.0
    raw: str = "unknown"
    transition: str | None = None
    duration_s: float = 0.0
    fall: bool = False
    man_down: bool = False


@dataclass
class ZoneView:
    id: str
    name: str
    type: str
    polygon: list[list[float]]
    schedule: dict | None = None


@dataclass
class EventDraft:
    event_type: str
    severity: str
    message: str
    track_id: int | None = None
    zone_id: str | None = None
    worker_id: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class FrameContext:
    camera_id: str
    ts: float
    frame: np.ndarray
    frame_index: int = 0
    width: int = 0
    height: int = 0
    motion: MotionResult | None = None
    persons: list[Detection] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    poses: dict[int, np.ndarray] = field(default_factory=dict)
    postures: dict[int, PostureState] = field(default_factory=dict)
    ppe: dict[int, dict[str, str]] = field(default_factory=dict)
    objects: list[Detection] = field(default_factory=list)
    prior_objects: list[Detection] = field(default_factory=list)
    faces: dict[int, dict] = field(default_factory=dict)
    events: list[EventDraft] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)
    zones: list[ZoneView] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


class Stage(Protocol):
    name: str
    enabled: bool

    def process(self, ctx: FrameContext) -> FrameContext: ...
