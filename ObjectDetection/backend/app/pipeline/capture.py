"""RTSP, USB, and file capture with reconnect and a bounded queue."""

from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np

from app.core.logging import get_logger

logger = get_logger("siteguard.capture")


def parse_source(source: str) -> int | str:
    text = source.strip()
    if text.isdigit():
        return int(text)
    if text.startswith("file://"):
        raw = text[7:]
        if raw.startswith("/") and len(raw) > 3 and raw[2] == ":":
            raw = raw.lstrip("/")
        return str(Path(raw))
    return text


def open_capture(source: str) -> cv2.VideoCapture:
    target = parse_source(source)
    cap = cv2.VideoCapture(target)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cap


def put_latest(q: queue.Queue, item: tuple[float, np.ndarray]) -> None:
    try:
        q.put_nowait(item)
        return
    except queue.Full:
        try:
            q.get_nowait()
        except queue.Empty:
            pass
        try:
            q.put_nowait(item)
        except queue.Full:
            return


class CaptureLoop:
    def __init__(
        self,
        source: str,
        stop: threading.Event,
        on_jpeg: Callable[[bytes], None],
        loop_files: bool = True,
    ) -> None:
        self.source = source
        self.stop = stop
        self.on_jpeg = on_jpeg
        self.loop_files = loop_files
        self.status = "offline"
        self.last_error: str | None = None

    def run(self, frame_queue: queue.Queue) -> None:
        is_file = not self.source.strip().isdigit() and not self.source.startswith("rtsp")
        while not self.stop.is_set():
            cap = open_capture(self.source)
            if not cap.isOpened():
                self.status = "reconnecting"
                self.last_error = f"cannot open source {self.source}"
                logger.warning(self.last_error)
                cap.release()
                if self.stop.wait(2):
                    break
                continue
            self.status = "online"
            self.last_error = None
            while not self.stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    if is_file and self.loop_files:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok, frame = cap.read()
                    if not ok or frame is None:
                        self.status = "reconnecting"
                        break
                ts = time.time()
                encoded, buf = cv2.imencode(
                    ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80]
                )
                if encoded:
                    self.on_jpeg(buf.tobytes())
                put_latest(frame_queue, (ts, frame))
                if is_file:
                    time.sleep(0.03)
            cap.release()
            if self.stop.is_set():
                break
            self.stop.wait(1)
        self.status = "offline"
