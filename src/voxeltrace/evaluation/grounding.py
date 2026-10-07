"""Visual grounding metrics in rendered-image pixel coordinates (inclusive boxes)."""

from __future__ import annotations

import math

import numpy as np


def point_distance(a: list[float], b: list[float], mm_per_px: float | None = None) -> dict:
    d = math.hypot(a[0] - b[0], a[1] - b[1])
    return {"px": d, "mm": d * mm_per_px if mm_per_px else None}


def box_iou(a: list[int], b: list[int]) -> float:
    """IoU of inclusive pixel boxes [x0, y0, x1, y1]."""
    ix0, iy0 = max(a[0], b[0]), max(a[1], b[1])
    ix1, iy1 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix1 - ix0 + 1) * max(0, iy1 - iy0 + 1)
    area = lambda r: max(0, r[2] - r[0] + 1) * max(0, r[3] - r[1] + 1)  # noqa: E731
    union = area(a) + area(b) - inter
    return inter / union if union else 0.0


def mask_dice(a: np.ndarray, b: np.ndarray) -> float:
    a, b = a.astype(bool), b.astype(bool)
    s = a.sum() + b.sum()
    return float(2 * (a & b).sum() / s) if s else 1.0
