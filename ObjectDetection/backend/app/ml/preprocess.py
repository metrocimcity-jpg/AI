"""Letterbox resize for square detector inputs."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class LetterboxMeta:
    scale: float
    pad_x: int
    pad_y: int
    orig_w: int
    orig_h: int
    size: int
    in_w: int = 0
    in_h: int = 0

    def __post_init__(self) -> None:
        if self.in_w <= 0:
            object.__setattr__(self, "in_w", self.size)
        if self.in_h <= 0:
            object.__setattr__(self, "in_h", self.size)


def letterbox(
    image: np.ndarray,
    new_size: int | tuple[int, int],
    color: tuple[int, int, int] = (114, 114, 114),
) -> tuple[np.ndarray, LetterboxMeta]:
    if isinstance(new_size, tuple):
        new_w, new_h = int(new_size[0]), int(new_size[1])
    else:
        new_w = new_h = int(new_size)
    height, width = image.shape[:2]
    scale = min(new_w / max(width, 1), new_h / max(height, 1))
    resized_w = max(1, int(round(width * scale)))
    resized_h = max(1, int(round(height * scale)))
    resized = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((new_h, new_w, 3), color, dtype=np.uint8)
    pad_x = (new_w - resized_w) // 2
    pad_y = (new_h - resized_h) // 2
    canvas[pad_y : pad_y + resized_h, pad_x : pad_x + resized_w] = resized
    meta = LetterboxMeta(
        scale, pad_x, pad_y, width, height, max(new_w, new_h), new_w, new_h
    )
    return canvas, meta


def to_nchw(image_bgr: np.ndarray) -> np.ndarray:
    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    blob = rgb.astype(np.float32) / 255.0
    return np.transpose(blob, (2, 0, 1))[None]


def unletterbox_xyxy(
    x1: float, y1: float, x2: float, y2: float, meta: LetterboxMeta
) -> tuple[float, float, float, float]:
    x1 = (x1 - meta.pad_x) / meta.scale
    y1 = (y1 - meta.pad_y) / meta.scale
    x2 = (x2 - meta.pad_x) / meta.scale
    y2 = (y2 - meta.pad_y) / meta.scale
    x1 = float(np.clip(x1, 0, meta.orig_w - 1))
    y1 = float(np.clip(y1, 0, meta.orig_h - 1))
    x2 = float(np.clip(x2, 0, meta.orig_w - 1))
    y2 = float(np.clip(y2, 0, meta.orig_h - 1))
    return x1, y1, x2, y2


def unletterbox_point(x: float, y: float, meta: LetterboxMeta) -> tuple[float, float]:
    px = float(np.clip((x - meta.pad_x) / meta.scale, 0, meta.orig_w - 1))
    py = float(np.clip((y - meta.pad_y) / meta.scale, 0, meta.orig_h - 1))
    return px, py
