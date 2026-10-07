"""Reference-region measurement (liver / blood pool) on a supplied region. No AI, no guessing.

Automatic anatomical placement is NOT implemented: without a validated deterministic organ
localiser the engine returns MANUAL_OR_REFERENCE_MASK_REQUIRED instead of inventing a region.
Supported inputs:
  - SUPPLIED_MASK: a boolean mask on the PET grid (e.g. reviewed segmentation);
  - SPHERE_AT_SUPPLIED_CENTRE: a sphere of given diameter at a supplied (reviewed) patient-LPS
    centre; voxels whose centres lie within the radius (same rule as SUVpeak).
QC (all recorded): inside image, no overlap with lesion masks, no SUV==0 voxels (masked PET),
minimum voxel count, coefficient of variation reported (no standard threshold is applied
unless a rule supplies one).
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from pydantic import BaseModel, Field

from voxeltrace.schemas import ImageGeometry, QCWarning

Region = Literal["LIVER", "BLOOD_POOL"]
Method = Literal["SUPPLIED_MASK", "SPHERE_AT_SUPPLIED_CENTRE"]
MIN_VOXELS = 10


class ReferenceRegionSpec(BaseModel):
    region: Region
    method: Method
    centre_patient_mm: tuple[float, float, float] | None = None
    diameter_mm: float | None = None
    provenance: str = Field(description="who/what supplied the region (e.g. 'reviewer X')")


class ReferenceRegionResult(BaseModel):
    status: Literal["COMPUTED", "MANUAL_OR_REFERENCE_MASK_REQUIRED", "REFUSED"]
    region: Region
    method: Method | None = None
    provenance: str | None = None
    centre_patient_mm: tuple[float, float, float] | None = None
    diameter_mm: float | None = None
    bbox_kji: list[list[int]] | None = None
    voxel_count: int = 0
    volume_ml: float = 0.0
    suv_mean: float | None = None
    suv_sd: float | None = None
    cov: float | None = None
    sul_mean: float | None = None
    sul_sd: float | None = None
    qc_warnings: list[QCWarning] = Field(default_factory=list)
    refusal: str | None = None


def sphere_mask(
    g: ImageGeometry, centre_mm: tuple[float, float, float], diameter_mm: float
) -> np.ndarray | None:
    """Voxel-centre sphere on the grid; None if any part of the sphere leaves the image."""
    nk, nj, ni = g.shape_ijk[2], g.shape_ijk[1], g.shape_ijk[0]
    aff = np.asarray(g.affine)
    r = diameter_mm / 2.0
    ijk_c = np.linalg.solve(aff, [*centre_mm, 1.0])[:3]
    sp = np.asarray([v for v in g.spacing_ijk], dtype=float)
    lo = np.floor(ijk_c - r / sp).astype(int)
    hi = np.ceil(ijk_c + r / sp).astype(int)
    if (lo < 0).any() or hi[0] >= ni or hi[1] >= nj or hi[2] >= nk:
        return None
    kk, jj, ii = np.mgrid[0:nk, 0:nj, 0:ni]
    pts = np.stack([ii, jj, kk, np.ones_like(ii)], axis=-1) @ aff.T
    d2 = ((pts[..., :3] - np.asarray(centre_mm)) ** 2).sum(-1)
    return d2 <= r * r * (1 + 1e-12)


def measure_reference_region(
    suv: np.ndarray,
    g: ImageGeometry,
    spec: ReferenceRegionSpec | None,
    *,
    region: Region = "LIVER",
    mask: np.ndarray | None = None,
    lesion_masks: list[np.ndarray] | None = None,
    sul: np.ndarray | None = None,
) -> ReferenceRegionResult:
    if spec is None:
        return ReferenceRegionResult(
            status="MANUAL_OR_REFERENCE_MASK_REQUIRED",
            region=region,
            refusal="no supplied reference mask or reviewed centre; automatic placement is not "
            "implemented",
        )
    res = ReferenceRegionResult(
        status="REFUSED",
        region=spec.region,
        method=spec.method,
        provenance=spec.provenance,
        centre_patient_mm=spec.centre_patient_mm,
        diameter_mm=spec.diameter_mm,
    )
    if spec.method == "SUPPLIED_MASK":
        if mask is None or mask.shape != suv.shape or mask.dtype != bool:
            res.refusal = "supplied mask missing or not a boolean mask on the PET grid"
            return res
        m = mask
    else:
        if spec.centre_patient_mm is None or not spec.diameter_mm or spec.diameter_mm <= 0:
            res.refusal = "sphere method requires a centre and a positive diameter"
            return res
        if None in g.spacing_ijk:
            res.refusal = "non-uniform slice spacing"
            return res
        sm = sphere_mask(g, spec.centre_patient_mm, spec.diameter_mm)
        if sm is None:
            res.refusal = "sphere extends outside the image"
            return res
        m = sm
    n = int(m.sum())
    if n < MIN_VOXELS:
        res.refusal = f"only {n} voxels (< {MIN_VOXELS})"
        return res
    for les in lesion_masks or []:
        if (les & m).any():
            res.refusal = "reference region overlaps a supplied lesion segmentation"
            return res
    vals = suv[m]
    if (vals == 0).any():
        res.refusal = f"{int((vals == 0).sum())} region voxels have SUV exactly 0 (masked PET)"
        return res
    idx = np.argwhere(m)
    voxel_ml = float(np.prod([v for v in g.spacing_ijk if v is not None])) / 1000.0
    res.status = "COMPUTED"
    res.bbox_kji = [idx.min(0).tolist(), idx.max(0).tolist()]
    res.voxel_count = n
    res.volume_ml = n * voxel_ml
    res.suv_mean = float(vals.mean())
    res.suv_sd = float(vals.std(ddof=0))
    res.cov = res.suv_sd / res.suv_mean if res.suv_mean else None
    if sul is not None:
        sv = sul[m]
        res.sul_mean, res.sul_sd = float(sv.mean()), float(sv.std(ddof=0))
    return res
