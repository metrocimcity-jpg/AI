"""Fan out pipeline messages to WebSocket clients on the asyncio loop."""

from __future__ import annotations

import asyncio
import threading
from typing import Any


class Subscriber:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self.camera_ids: set[str] | None = None
        self.frames = True


class Broadcaster:
    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self._subs: set[Subscriber] = set()
        self._lock = threading.Lock()

    def subscribe(self) -> Subscriber:
        sub = Subscriber()
        with self._lock:
            self._subs.add(sub)
        return sub

    def unsubscribe(self, sub: Subscriber) -> None:
        with self._lock:
            self._subs.discard(sub)

    def publish(self, message: dict[str, Any]) -> None:
        loop = self.loop
        if loop is None or loop.is_closed():
            return
        loop.call_soon_threadsafe(self._fanout, message)

    def _fanout(self, message: dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subs)
        for sub in subs:
            if message.get("type") == "frame" and not sub.frames:
                continue
            camera_id = message.get("camera_id") or (message.get("event") or {}).get("camera_id")
            if sub.camera_ids is not None and camera_id not in sub.camera_ids:
                continue
            self._offer(sub, message)

    @staticmethod
    def _offer(sub: Subscriber, message: dict[str, Any]) -> None:
        try:
            sub.queue.put_nowait(message)
            return
        except asyncio.QueueFull:
            try:
                sub.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            sub.queue.put_nowait(message)
        except asyncio.QueueFull:
            return
