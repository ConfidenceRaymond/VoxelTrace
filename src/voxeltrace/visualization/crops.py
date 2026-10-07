"""Lesion-centred crop windows (fixed physical size, shifted inside the image, no padding)."""

from __future__ import annotations

import math

from voxeltrace.schemas import ImageGeometry


def crop_box(center_ji: tuple[int, int], g: ImageGeometry, size_mm: float = 80.0) -> list[int]:
    """Inclusive [i0, j0, i1, j1] window of ~size_mm centred on (j, i), kept inside the image."""
    ni, nj = g.shape_ijk[0], g.shape_ijk[1]
    out = []
    for c, n, sp in ((center_ji[1], ni, g.spacing_ijk[0]), (center_ji[0], nj, g.spacing_ijk[1])):
        width = min(n, max(1, int(math.ceil(size_mm / float(sp)))))
        lo = c - width // 2
        lo = min(max(lo, 0), n - width)
        out.append((lo, lo + width - 1))
    (i0, i1), (j0, j1) = out
    return [i0, j0, i1, j1]
