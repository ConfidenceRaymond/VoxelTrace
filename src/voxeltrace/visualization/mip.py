"""PET coronal maximum-intensity projection (along the anterior-posterior axis, j)."""

from __future__ import annotations

import numpy as np

from voxeltrace.schemas import ImageGeometry
from voxeltrace.visualization.pet import DEFAULT_SUV_WINDOW
from voxeltrace.visualization.render import (
    Convention,
    PlaneMapping,
    RenderParams,
    colorize,
    require_standard_axial,
)


def pet_coronal_mip(
    suv: np.ndarray,
    g: ImageGeometry,
    *,
    window=DEFAULT_SUV_WINDOW,
    cmap: str = "gray_inverted",
    scale: int = 1,
    convention: Convention = "radiological",
) -> tuple[np.ndarray, PlaneMapping, RenderParams]:
    """Anterior view: image x = i (patient right on image left), image y = k with superior
    at the top (k increases inferior->superior in LPS-sorted volumes, so y is flipped)."""
    require_standard_axial(g)
    sx, _, sz = g.spacing_ijk
    scale_z = max(1, int(round(scale * float(sz) / float(sx))))
    mip = suv.max(axis=1)  # [k, i]
    nk, ni = mip.shape
    m = PlaneMapping(
        a0=0,
        b0=0,
        n_a=ni,
        n_b=nk,
        sx=scale,
        sy=scale_z,
        flip_x=convention == "neurological",
        flip_y=True,
    )
    rgb = colorize(m.expand(mip), window[0], window[1], cmap)
    params = RenderParams(
        view="pet_coronal_mip",
        convention=convention,
        scale_x=scale,
        scale_y=scale_z,
        mm_per_px_x=float(sx) / scale,
        mm_per_px_y=float(sz) / scale_z,
        pet_window=list(window),
        pet_colormap=cmap,
        notes=[
            "maximum over the anterior-posterior (j) axis",
            "superior at top; anisotropic px aspect recorded",
        ],
    )
    return rgb, m, params
