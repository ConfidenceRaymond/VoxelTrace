"""CT rendering. For fusion, CT is resampled onto the PET grid FOR DISPLAY ONLY."""

from __future__ import annotations

import numpy as np
import SimpleITK as sitk

from voxeltrace.schemas import ImageGeometry
from voxeltrace.visualization.pet import axial_mapping, plane
from voxeltrace.visualization.render import (
    Convention,
    PlaneMapping,
    RenderError,
    RenderParams,
    colorize,
    require_standard_axial,
)

SOFT_TISSUE = (40.0, 400.0)  # window centre, width (HU)


def _sitk(vol: np.ndarray, g: ImageGeometry) -> sitk.Image:
    img = sitk.GetImageFromArray(vol)
    img.SetSpacing([float(v) for v in g.spacing_ijk])  # type: ignore[arg-type]
    img.SetOrigin(list(g.origin))
    img.SetDirection(list(g.direction))
    return img


def resample_ct_to_pet(
    ct: np.ndarray,
    ct_g: ImageGeometry,
    pet_g: ImageGeometry,
    ct_for: str | None,
    pet_for: str | None,
) -> np.ndarray:
    """Linear resampling of CT (HU) at PET voxel centres. Display only; same FoR required."""
    if not ct_for or ct_for != pet_for:
        raise RenderError("CT and PET FrameOfReferenceUID differ or are missing")
    if None in ct_g.spacing_ijk or None in pet_g.spacing_ijk:
        raise RenderError("non-uniform slice spacing")
    ref = _sitk(
        np.zeros((pet_g.shape_ijk[2], pet_g.shape_ijk[1], pet_g.shape_ijk[0]), np.float32), pet_g
    )
    out = sitk.Resample(
        _sitk(ct.astype(np.float32), ct_g),
        ref,
        sitk.Transform(),
        sitk.sitkLinear,
        -1024.0,
        sitk.sitkFloat32,
    )
    return sitk.GetArrayFromImage(out)


def ct_window_bounds(center: float, width: float) -> tuple[float, float]:
    return center - width / 2.0, center + width / 2.0


def ct_axial(
    ct_on_grid: np.ndarray,
    g: ImageGeometry,
    k: int,
    *,
    window=SOFT_TISSUE,
    scale: int = 2,
    convention: Convention = "radiological",
    crop: list[int] | None = None,
) -> tuple[np.ndarray, PlaneMapping, RenderParams]:
    require_standard_axial(g)
    m = axial_mapping(g, crop, scale, convention)
    lo, hi = ct_window_bounds(*window)
    rgb = colorize(plane(ct_on_grid, k, m), lo, hi, "gray")
    params = RenderParams(
        view="ct_axial",
        convention=convention,
        scale_x=scale,
        scale_y=scale,
        mm_per_px_x=g.spacing_ijk[0] / scale,
        mm_per_px_y=g.spacing_ijk[1] / scale,
        crop_voxels=crop,
        ct_window_center_width=list(window),
        resampling="CT linearly resampled onto PET grid (display only)",
    )
    return rgb, m, params
