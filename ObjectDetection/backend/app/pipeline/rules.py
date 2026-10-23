"""Safe rule expressions. Names, comparisons, and method calls only — no eval."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from app.pipeline.base import EventDraft, FrameContext, Track


class ExprError(ValueError):
    """The rule text is not a supported expression."""


_OPS = (">=", "<=", "==", "!=", ">", "<")


def _apply(op: str, left: Any, right: Any) -> bool:
    if op == "==":
        return bool(left == right)
    if op == "!=":
        return bool(left != right)
    if op == ">":
        return bool(left > right)
    if op == "<":
        return bool(left < right)
    if op == ">=":
        return bool(left >= right)
    if op == "<=":
        return bool(left <= right)
    raise ExprError(f"unsupported operator {op}")


class SafeExpr:
    def __init__(self, source: str) -> None:
        self.source = source
        self.s = source
        self.n = len(source)
        self.i = 0

    def eval(self, env: dict[str, Any]) -> bool:
        self.i = 0
        value = self._or(env)
        self._skip()
        if self.i != self.n:
            raise ExprError(f"unexpected trailing input: {self.s[self.i :]!r}")
        return bool(value)

    def _skip(self) -> None:
        while self.i < self.n and self.s[self.i].isspace():
            self.i += 1

    def _eat_word(self, word: str) -> bool:
        self._skip()
        end = self.i + len(word)
        if self.s[self.i : end] != word:
            return False
        if end < self.n and (self.s[end].isalnum() or self.s[end] == "_"):
            return False
        self.i = end
        return True

    def _or(self, env: dict[str, Any]) -> Any:
        left = self._and(env)
        while self._eat_word("or"):
            right = self._and(env)
            left = bool(left) or bool(right)
        return left

    def _and(self, env: dict[str, Any]) -> Any:
        left = self._unary(env)
        while self._eat_word("and"):
            right = self._unary(env)
            left = bool(left) and bool(right)
        return left

    def _unary(self, env: dict[str, Any]) -> Any:
        if self._eat_word("not"):
            return not bool(self._unary(env))
        return self._cmp(env)

    def _cmp(self, env: dict[str, Any]) -> Any:
        left = self._primary(env)
        self._skip()
        for op in _OPS:
            if self.s.startswith(op, self.i):
                self.i += len(op)
                right = self._primary(env)
                return _apply(op, left, right)
        if self._eat_word("in"):
            right = self._primary(env)
            try:
                return left in right
            except TypeError as exc:
                raise ExprError("'in' is not valid for these values") from exc
        return left

    def _primary(self, env: dict[str, Any]) -> Any:
        self._skip()
        if self.i >= self.n:
            raise ExprError("unexpected end of expression")
        ch = self.s[self.i]
        if ch == "(":
            self.i += 1
            value = self._or(env)
            self._skip()
            if self.i >= self.n or self.s[self.i] != ")":
                raise ExprError("missing )")
            self.i += 1
            return value
        if ch == "[":
            return self._list(env)
        if ch in "\"'":
            return self._string()
        if ch.isdigit() or (
            ch == "-" and self.i + 1 < self.n and self.s[self.i + 1].isdigit()
        ):
            return self._number()
        if self._eat_word("true"):
            return True
        if self._eat_word("false"):
            return False
        return self._chain(env)

    def _list(self, env: dict[str, Any]) -> list[Any]:
        self.i += 1
        items: list[Any] = []
        self._skip()
        if self.i < self.n and self.s[self.i] == "]":
            self.i += 1
            return items
        while True:
            items.append(self._or(env))
            self._skip()
            if self.i < self.n and self.s[self.i] == ",":
                self.i += 1
                continue
            if self.i < self.n and self.s[self.i] == "]":
                self.i += 1
                return items
            raise ExprError("bad list")

    def _string(self) -> str:
        quote = self.s[self.i]
        self.i += 1
        start = self.i
        while self.i < self.n and self.s[self.i] != quote:
            self.i += 1
        if self.i >= self.n:
            raise ExprError("unterminated string")
        value = self.s[start : self.i]
        self.i += 1
        return value

    def _number(self) -> int | float:
        start = self.i
        if self.s[self.i] == "-":
            self.i += 1
        while self.i < self.n and (self.s[self.i].isdigit() or self.s[self.i] == "."):
            self.i += 1
        raw = self.s[start : self.i]
        return float(raw) if "." in raw else int(raw)

    def _ident(self) -> str:
        self._skip()
        if self.i >= self.n or not (self.s[self.i].isalpha() or self.s[self.i] == "_"):
            raise ExprError(f"expected a name near {self.s[self.i :]!r}")
        start = self.i
        self.i += 1
        while self.i < self.n and (self.s[self.i].isalnum() or self.s[self.i] == "_"):
            self.i += 1
        return self.s[start : self.i]

    def _chain(self, env: dict[str, Any]) -> Any:
        name = self._ident()
        if name not in env:
            raise ExprError(f"unknown name {name}")
        current = env[name]
        while True:
            self._skip()
            if self.i < self.n and self.s[self.i] == ".":
                self.i += 1
                attr = self._ident()
                if attr.startswith("_"):
                    raise ExprError("private attribute access is not allowed")
                if isinstance(current, dict):
                    if attr not in current:
                        raise ExprError(f"missing field {attr}")
                    current = current[attr]
                else:
                    if not hasattr(current, attr):
                        raise ExprError(f"missing field {attr}")
                    current = getattr(current, attr)
                continue
            if self.i < self.n and self.s[self.i] == "(":
                if not callable(current):
                    raise ExprError("value is not callable")
                self.i += 1
                args: list[Any] = []
                self._skip()
                if not (self.i < self.n and self.s[self.i] == ")"):
                    while True:
                        args.append(self._or(env))
                        self._skip()
                        if self.i < self.n and self.s[self.i] == ",":
                            self.i += 1
                            continue
                        break
                self._skip()
                if self.i >= self.n or self.s[self.i] != ")":
                    raise ExprError("missing )")
                self.i += 1
                current = current(*args)
                continue
            break
        return current


def expression_kind(source: str) -> str:
    if "object." in source:
        return "object"
    if any(token in source for token in ("person.", "posture.", "face.", "worker.")):
        return "person"
    return "scene"


def _distance_to(track: Track, pattern: str, objects: list) -> float:
    import re

    names = set(filter(None, re.split(r"[|,]", pattern)))
    x1, y1, x2, y2 = track.bbox
    pcx, pcy = (x1 + x2) / 2, (y1 + y2) / 2
    ph = max(1.0, y2 - y1)
    best = 1e9
    for obj in objects:
        if obj.class_name not in names:
            continue
        ox1, oy1, ox2, oy2 = obj.bbox_xyxy
        ocx, ocy = (ox1 + ox2) / 2, (oy1 + oy2) / 2
        dist = ((pcx - ocx) ** 2 + (pcy - ocy) ** 2) ** 0.5 / ph
        best = min(best, dist)
    return best


class _Person:
    def __init__(self, ppe: Any, zone_names: set[str], distance) -> None:  # type: ignore[no-untyped-def]
        self.ppe = ppe
        self._zones = zone_names
        self._distance = distance

    def in_zone(self, name: str) -> bool:
        return name in self._zones

    def distance_to(self, pattern: str) -> float:
        return float(self._distance(pattern))


class _ObjectView:
    def __init__(self, class_name: str, zone_names: set[str]) -> None:
        setattr(self, "class", class_name)
        self._zones = zone_names

    def in_zone(self, name: str) -> bool:
        return name in self._zones


@dataclass
class RuleEngine:
    rules: list[dict[str, Any]]
    material_names: list[str]
    true_since: dict[tuple[Any, str], float] = field(default_factory=dict)
    cooldowns: dict[tuple[Any, str], float] = field(default_factory=dict)
    _compiled: dict[str, SafeExpr] = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: str, material_names: list[str]) -> RuleEngine:
        loaded = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        rules = loaded.get("rules") or []
        return cls(rules=list(rules), material_names=material_names)

    def compile_all(self) -> None:
        for rule in self.rules:
            source = str(rule.get("when", "false"))
            self._compiled[source] = SafeExpr(source)

    def _expr(self, source: str) -> SafeExpr:
        if source not in self._compiled:
            self._compiled[source] = SafeExpr(source)
        return self._compiled[source]

    def evaluate(self, ctx: FrameContext, closed: bool) -> list[EventDraft]:
        drafts: list[EventDraft] = []
        for rule in self.rules:
            if rule.get("enabled", True) is False:
                continue
            source = str(rule.get("when", "false"))
            kind = expression_kind(source)
            if kind == "object":
                for obj in ctx.objects:
                    drafts.extend(self._apply(rule, self._object_env(ctx, obj, closed), None, ctx.ts))
            elif kind == "person":
                if not ctx.tracks:
                    continue
                for track in ctx.tracks:
                    drafts.extend(
                        self._apply(rule, self._person_env(ctx, track, closed), track.id, ctx.ts)
                    )
            else:
                drafts.extend(self._apply(rule, self._scene_env(ctx, closed), None, ctx.ts))
        return drafts

    def _apply(
        self, rule: dict[str, Any], env: dict[str, Any], track_id: int | None, now: float
    ) -> list[EventDraft]:
        source = str(rule.get("when", "false"))
        ok = bool(self._expr(source).eval(env))
        key = (track_id, str(rule["id"]))
        if not ok:
            self.true_since.pop(key, None)
            return []
        self.true_since.setdefault(key, now)
        if now - self.true_since[key] < float(rule.get("min_duration_s") or 0):
            return []
        last = self.cooldowns.get(key, -1e12)
        cooldown = float(rule.get("cooldown_s") or 0)
        if now - last < cooldown:
            return []
        self.cooldowns[key] = now
        return [
            EventDraft(
                event_type=str(rule["id"]),
                severity=str(rule.get("severity", "info")),
                message=str(rule.get("message") or rule["id"]),
                track_id=track_id,
                meta={"rule": rule["id"]},
            )
        ]

    def _scene_env(self, ctx: FrameContext, closed: bool) -> dict[str, Any]:
        detected = bool(ctx.motion and ctx.motion.detected)
        score = float(ctx.motion.score) if ctx.motion else 0.0
        return {
            "motion": SimpleNamespace(detected=detected, score=score),
            "schedule": SimpleNamespace(is_closed=closed),
            "materials": self.material_names,
        }

    def _person_env(self, ctx: FrameContext, track: Track, closed: bool) -> dict[str, Any]:
        env = self._scene_env(ctx, closed)
        ppe = ctx.ppe.get(track.id, {})
        ppe_view = SimpleNamespace(
            helmet=ppe.get("helmet", "unknown"),
            vest=ppe.get("vest", "unknown"),
            gloves=ppe.get("gloves", "unknown"),
            boots=ppe.get("boots", "unknown"),
            goggles=ppe.get("goggles", "unknown"),
            harness=ppe.get("harness", "unknown"),
        )
        x1, y1, x2, y2 = track.bbox
        cx = ((x1 + x2) / 2) / max(ctx.width, 1)
        cy = ((y1 + y2) / 2) / max(ctx.height, 1)
        from app.pipeline.zones import zones_at

        hits = zones_at(cx, cy, ctx.zones) if ctx.width and ctx.height else []
        # Also test absolute pixels if polygons were drawn in pixel space (>1).
        if ctx.zones and max(abs(p) for z in ctx.zones for pt in z.polygon for p in pt[:2]) > 1.5:
            hits = zones_at((x1 + x2) / 2, (y1 + y2) / 2, ctx.zones)
        names = {zone.type for zone in hits} | {zone.name for zone in hits}
        posture = ctx.postures.get(track.id)
        face = ctx.faces.get(track.id, {})
        authorized = bool(face.get("authorized", False))
        env.update(
            {
                "person": _Person(
                    ppe_view,
                    names,
                    lambda pattern, t=track, c=ctx: _distance_to(t, pattern, c.objects),
                ),
                "posture": SimpleNamespace(
                    state=posture.state if posture else "unknown",
                    duration_s=posture.duration_s if posture else 0.0,
                    transition=(posture.transition or "") if posture else "",
                ),
                "worker": SimpleNamespace(authorized=authorized),
                "face": SimpleNamespace(
                    result=str(face.get("result", "unverified")),
                    quality=float(face.get("quality", 0.0)),
                ),
            }
        )
        return env

    def _object_env(self, ctx: FrameContext, obj: Any, closed: bool) -> dict[str, Any]:
        env = self._scene_env(ctx, closed)
        x1, y1, x2, y2 = obj.bbox_xyxy
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        from app.pipeline.zones import zones_at

        if ctx.width and ctx.height:
            norm_hits = zones_at(cx / ctx.width, cy / ctx.height, ctx.zones)
        else:
            norm_hits = []
        abs_hits = zones_at(cx, cy, ctx.zones)
        hits = norm_hits or abs_hits
        names = {zone.type for zone in hits} | {zone.name for zone in hits}
        env["object"] = _ObjectView(obj.class_name, names)
        return env
