"""PET SUV axial rendering (display only; SUV array never modified)."""

from __future__ import annotations

import numpy as np

from voxeltrace.schemas import ImageGeometry
from voxeltrace.visualization.render import (
    Convention,
    PlaneMapping,
    RenderParams,
    colorize,
    require_standard_axial,
)

DEFAULT_SUV_WINDOW = (0.0, 8.0)


def axial_mapping(
    g: ImageGeometry, crop: list[int] | None, scale: int, convention: Convention
) -> PlaneMapping:
    ni, nj = g.shape_ijk[0], g.shape_ijk[1]
    i0, j0, i1, j1 = crop if crop else [0, 0, ni - 1, nj - 1]
    return PlaneMapping(
        a0=i0,
        b0=j0,
        n_a=i1 - i0 + 1,
        n_b=j1 - j0 + 1,
        sx=scale,
        sy=scale,
        flip_x=convention == "neurological",
    )


def plane(vol: np.ndarray, k: int, m: PlaneMapping) -> np.ndarray:
    """Cropped [j, i] plane of slice k, expanded to pixels."""
    return m.expand(vol[k, m.b0 : m.b0 + m.n_b, m.a0 : m.a0 + m.n_a])


def pet_axial(
    suv: np.ndarray,
    g: ImageGeometry,
    k: int,
    *,
    window=DEFAULT_SUV_WINDOW,
    cmap: str = "gray_inverted",
    scale: int = 2,
    convention: Convention = "radiological",
    crop: list[int] | None = None,
) -> tuple[np.ndarray, PlaneMapping, RenderParams]:
    require_standard_axial(g)
    m = axial_mapping(g, crop, scale, convention)
    rgb = colorize(plane(suv, k, m), window[0], window[1], cmap)
    params = RenderParams(
        view="pet_axial",
        convention=convention,
        scale_x=scale,
        scale_y=scale,
        mm_per_px_x=g.spacing_ijk[0] / scale,
        mm_per_px_y=g.spacing_ijk[1] / scale,
        crop_voxels=crop,
        pet_window=list(window),
        pet_colormap=cmap,
    )
    return rgb, m, params
