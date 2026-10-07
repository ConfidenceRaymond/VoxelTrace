"""Overlays drawn on rendered pixel planes. Outlines come ONLY from supplied masks."""

from __future__ import annotations

import numpy as np

CYAN = (0, 255, 255)
GREEN = (0, 255, 0)
MAGENTA = (255, 0, 255)
YELLOW = (255, 255, 0)


def contour(mask_px: np.ndarray) -> np.ndarray:
    """Inner boundary (4-neighbourhood) of a pixel-level mask."""
    m = mask_px.astype(bool)
    pad = np.pad(m, 1, constant_values=False)
    interior = pad[1:-1, 1:-1] & pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    return m & ~interior


def paint(rgb: np.ndarray, where: np.ndarray, color: tuple[int, int, int]) -> np.ndarray:
    out = rgb.copy()
    out[where] = color
    return out


def crosshair(shape: tuple[int, int], x: int, y: int, arm: int, gap: int = 2) -> np.ndarray:
    """Cross centred on (x, y) with a gap so the marked pixel itself stays visible."""
    m = np.zeros(shape, bool)
    h, w = shape
    for d in range(gap, arm + 1):
        for xx, yy in ((x - d, y), (x + d, y), (x, y - d), (x, y + d)):
            if 0 <= xx < w and 0 <= yy < h:
                m[yy, xx] = True
    return m


def circle(shape: tuple[int, int], x: float, y: float, r: float) -> np.ndarray:
    yy, xx = np.mgrid[0 : shape[0], 0 : shape[1]]
    d = np.hypot(xx - x, yy - y)
    return np.abs(d - r) <= 0.5


def rectangle(shape: tuple[int, int], box: list[int], pad: int = 1) -> np.ndarray:
    """Outline just OUTSIDE an inclusive pixel box (so the box content stays visible)."""
    m = np.zeros(shape, bool)
    h, w = shape
    x0, y0, x1, y1 = box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad
    xs0, xs1 = max(x0, 0), min(x1, w - 1)
    ys0, ys1 = max(y0, 0), min(y1, h - 1)
    if 0 <= y0 < h:
        m[y0, xs0 : xs1 + 1] = True
    if 0 <= y1 < h:
        m[y1, xs0 : xs1 + 1] = True
    if 0 <= x0 < w:
        m[ys0 : ys1 + 1, x0] = True
    if 0 <= x1 < w:
        m[ys0 : ys1 + 1, x1] = True
    return m
