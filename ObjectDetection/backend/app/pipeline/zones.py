"""Point-in-polygon tests and closed-hour schedules."""

from __future__ import annotations

from datetime import datetime

from app.pipeline.base import ZoneView


def point_in_polygon(x: float, y: float, polygon: list[list[float]]) -> bool:
    if len(polygon) < 3:
        return False
    inside = False
    j = len(polygon) - 1
    for i, point in enumerate(polygon):
        xi, yi = float(point[0]), float(point[1])
        xj, yj = float(polygon[j][0]), float(polygon[j][1])
        intersects = (yi > y) != (yj > y) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) + 1e-12) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def zones_at(x: float, y: float, zones: list[ZoneView]) -> list[ZoneView]:
    return [zone for zone in zones if point_in_polygon(x, y, zone.polygon)]


def schedule_is_closed(schedule: dict | None, now: datetime) -> bool:
    if not schedule:
        return False
    days = schedule.get("days")
    if isinstance(days, list) and days and now.weekday() not in days:
        return False
    windows = schedule.get("closed") or schedule.get("closed_hours") or []
    minutes = now.hour * 60 + now.minute
    for window in windows:
        if not isinstance(window, str) or "-" not in window:
            continue
        start, end = window.split("-", 1)
        sh, sm = (int(part) for part in start.split(":", 1))
        eh, em = (int(part) for part in end.split(":", 1))
        begin = sh * 60 + sm
        finish = eh * 60 + em
        if begin <= finish:
            if begin <= minutes < finish:
                return True
        elif minutes >= begin or minutes < finish:
            return True
    return False


def closed_hours_active(windows: list[str], now: datetime) -> bool:
    return schedule_is_closed({"closed": windows}, now)
