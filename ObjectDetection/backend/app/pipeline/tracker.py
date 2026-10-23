"""ByteTrack-style association: high-score matches first, then low-score recovery."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.ml.postprocess import Detection
from app.pipeline.base import Track


def iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def _greedy_match(
    tracks: list[_Internal],
    detections: list[Detection],
    used_tracks: set[int],
    used_dets: set[int],
    threshold: float,
) -> list[tuple[int, int]]:
    pairs: list[tuple[float, int, int]] = []
    for ti, track in enumerate(tracks):
        if ti in used_tracks:
            continue
        for di, det in enumerate(detections):
            if di in used_dets:
                continue
            overlap = iou(track.bbox, det.bbox_xyxy)
            if overlap >= threshold:
                pairs.append((overlap, ti, di))
    pairs.sort(reverse=True)
    matches: list[tuple[int, int]] = []
    for _overlap, ti, di in pairs:
        if ti in used_tracks or di in used_dets:
            continue
        used_tracks.add(ti)
        used_dets.add(di)
        matches.append((ti, di))
    return matches


def _center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x1, y1, x2, y2 = box
    return (x1 + x2) / 2, (y1 + y2) / 2


def _height(box: tuple[float, float, float, float]) -> float:
    return max(1.0, box[3] - box[1])


@dataclass
class _Internal:
    id: int
    bbox: tuple[float, float, float, float]
    score: float
    missed: int = 0
    hits: int = 1
    prev_center: tuple[float, float] | None = None
    prev_ts: float | None = None
    speed: float = 0.0
    vertical_speed: float = 0.0
    downward_speed: float = 0.0
    history: list[tuple[float, float]] = field(default_factory=list)


class ByteTrack:
    def __init__(
        self,
        high_thresh: float = 0.5,
        low_thresh: float = 0.1,
        match_iou: float = 0.3,
        max_missed: int = 30,
    ) -> None:
        self.high_thresh = high_thresh
        self.low_thresh = low_thresh
        self.match_iou = match_iou
        self.max_missed = max_missed
        self._tracks: list[_Internal] = []
        self._next_id = 1

    def update(self, detections: list[Detection], ts: float) -> list[Track]:
        high = [det for det in detections if det.score >= self.high_thresh]
        low = [det for det in detections if self.low_thresh <= det.score < self.high_thresh]
        used_tracks: set[int] = set()
        used_high: set[int] = set()
        for ti, di in _greedy_match(self._tracks, high, used_tracks, used_high, self.match_iou):
            self._assign(self._tracks[ti], high[di], ts)
        used_low: set[int] = set()
        for ti, di in _greedy_match(self._tracks, low, used_tracks, used_low, self.match_iou):
            self._assign(self._tracks[ti], low[di], ts)
        for di, det in enumerate(high):
            if di in used_high:
                continue
            self._tracks.append(
                _Internal(
                    id=self._next_id,
                    bbox=det.bbox_xyxy,
                    score=det.score,
                    prev_center=_center(det.bbox_xyxy),
                    prev_ts=ts,
                )
            )
            self._next_id += 1
        seen = {self._tracks[ti].id for ti in used_tracks}
        fresh_ids = {track.id for track in self._tracks if track.hits == 1 and track.prev_ts == ts}
        for track in self._tracks:
            if track.id not in seen and track.id not in fresh_ids:
                track.missed += 1
        self._tracks = [track for track in self._tracks if track.missed <= self.max_missed]
        return [
            Track(
                id=track.id,
                bbox=track.bbox,
                score=track.score,
                speed=track.speed,
                vertical_speed=track.vertical_speed,
                downward_speed=track.downward_speed,
                missed=track.missed,
            )
            for track in self._tracks
            if track.missed == 0
        ]

    def _assign(self, track: _Internal, det: Detection, ts: float) -> None:
        cx, cy = _center(det.bbox_xyxy)
        height = _height(det.bbox_xyxy)
        if track.prev_center is not None and track.prev_ts is not None:
            dt = max(1e-3, ts - track.prev_ts)
            dx = cx - track.prev_center[0]
            dy = cy - track.prev_center[1]
            track.speed = (dx * dx + dy * dy) ** 0.5 / height / dt
            track.vertical_speed = (track.prev_center[1] - cy) / height / dt
            track.downward_speed = (cy - track.prev_center[1]) / height / dt
        track.prev_center = (cx, cy)
        track.prev_ts = ts
        track.bbox = det.bbox_xyxy
        track.score = det.score
        track.missed = 0
        track.hits += 1
