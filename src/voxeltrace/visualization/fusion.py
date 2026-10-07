"""PET/CT fusion: CT greyscale + PET colour weighted by normalised SUV (display only)."""

from __future__ import annotations

import numpy as np

from voxeltrace.schemas import ImageGeometry
from voxeltrace.visualization.ct import SOFT_TISSUE, ct_window_bounds
from voxeltrace.visualization.pet import DEFAULT_SUV_WINDOW, axial_mapping, plane
from voxeltrace.visualization.render import (
    Convention,
    PlaneMapping,
    RenderParams,
    _lut,
    colorize,
    require_standard_axial,
    window_index,
)


def fused_axial(
    suv: np.ndarray,
    ct_on_grid: np.ndarray,
    g: ImageGeometry,
    k: int,
    *,
    pet_window=DEFAULT_SUV_WINDOW,
    ct_window=SOFT_TISSUE,
    alpha: float = 0.7,
    scale: int = 2,
    convention: Convention = "radiological",
    crop: list[int] | None = None,
) -> tuple[np.ndarray, PlaneMapping, RenderParams]:
    require_standard_axial(g)
    m = axial_mapping(g, crop, scale, convention)
    lo, hi = ct_window_bounds(*ct_window)
    ct_rgb = colorize(plane(ct_on_grid, k, m), lo, hi, "gray").astype(np.float64)
    idx = window_index(plane(suv, k, m), *pet_window)
    pet_rgb = _lut("hot")[idx].astype(np.float64)
    w = (idx.astype(np.float64) / 255.0 * alpha)[..., None]
    rgb = np.floor(ct_rgb * (1 - w) + pet_rgb * w + 0.5).astype(np.uint8)
    params = RenderParams(
        view="fused_axial",
        convention=convention,
        scale_x=scale,
        scale_y=scale,
        mm_per_px_x=g.spacing_ijk[0] / scale,
        mm_per_px_y=g.spacing_ijk[1] / scale,
        crop_voxels=crop,
        pet_window=list(pet_window),
        pet_colormap="hot",
        ct_window_center_width=list(ct_window),
        pet_alpha=alpha,
        resampling="CT linearly resampled onto PET grid (display only)",
    )
    return rgb, m, params
