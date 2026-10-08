"""Reference-region measurement (liver / blood pool) on a supplied or reviewed region. No AI.

Supported inputs:
  - SUPPLIED_MASK: a boolean mask on the PET grid (e.g. reviewed segmentation);
  - SPHERE_AT_SUPPLIED_CENTRE: a sphere of given diameter at a supplied (reviewed) patient-LPS
    centre; voxels whose centres lie within the radius (same rule as SUVpeak);
  - CYLINDER_AT_SUPPLIED_CENTRE: a cylinder of given diameter and length whose axis is the
    patient superior-inferior (LPS z) axis, e.g. the PERCIST 1 cm x 2 cm descending-aorta
    blood-pool region; voxels whose centres lie inside.
Automatic proposals (``quant/reference_auto.py``) become one of these specs only after human
review (``trial/reference.py``); an unreviewed proposal is never reported as COMPUTED.
QC (all recorded): inside image, no overlap with lesion masks, no SUV==0 voxels (masked PET),
minimum voxel count, coefficient of variation reported (no standard threshold is applied
unless a rule supplies one).
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field

from voxeltrace.schemas import ImageGeometry, QCWarning

Region = Literal["LIVER", "BLOOD_POOL"]
Method = Literal["SUPPLIED_MASK", "SPHERE_AT_SUPPLIED_CENTRE", "CYLINDER_AT_SUPPLIED_CENTRE"]
Status = Literal[
    "COMPUTED",
    "MANUAL_OR_REFERENCE_MASK_REQUIRED",
    "REFUSED",
    "PROPOSED_REQUIRES_REVIEW",
    "REJECTED_BY_REVIEWER",
    "REVIEW_OUTDATED",
    "REVIEW_INVALID",
    "SYNTHETIC_INHERITED_REFERENCE",
    "INHERITANCE_REFUSED",
    "AUTO_NOT_FOUND",
]
MIN_VOXELS = 10


class ReferenceRegionSpec(BaseModel):
    region: Region
    method: Method
    centre_patient_mm: tuple[float, float, float] | None = None
    diameter_mm: float | None = None
    length_mm: float | None = Field(default=None, description="cylinder only (S-I extent)")
    provenance: str = Field(description="who/what supplied the region (e.g. 'reviewer X')")


class ReferenceRegionResult(BaseModel):
    status: Status
    region: Region
    method: Method | None = None
    provenance: str | None = None
    centre_patient_mm: tuple[float, float, float] | None = None
    diameter_mm: float | None = None
    length_mm: float | None = None
    bbox_kji: list[list[int]] | None = None
    voxel_count: int = 0
    volume_ml: float = 0.0
    suv_mean: float | None = None
    suv_sd: float | None = None
    cov: float | None = None
    suv_max: float | None = None
    sul_mean: float | None = None
    sul_sd: float | None = None
    qc_warnings: list[QCWarning] = Field(default_factory=list)
    refusal: str | None = None
    source: Literal["SUPPLIED", "AUTO_PROPOSAL", "SYNTHETIC_INHERITED"] | None = None
    proposal_sha256: str | None = None
    algorithm_version: str | None = None
    review_decision: str | None = None
    reviewer: str | None = None
    qc_image: str | None = None
    inherited_from: dict[str, Any] | None = Field(
        default=None, description="SYNTHETIC TEST FIXTURE inheritance provenance"
    )


def _local_grid(
    g: ImageGeometry, centre_mm: tuple[float, float, float], half_extent_patient_mm: np.ndarray
) -> tuple[tuple[slice, slice, slice], np.ndarray] | None:
    """Index box (k, j, i slices) covering a patient-axis-aligned box of the given
    half-extents around the centre, and the patient-LPS coordinates of its voxel centres;
    None if the box leaves the image."""
    nk, nj, ni = g.shape_ijk[2], g.shape_ijk[1], g.shape_ijk[0]
    aff = np.asarray(g.affine)
    ijk_c = np.linalg.solve(aff, [*centre_mm, 1.0])[:3]
    sp = np.asarray([v for v in g.spacing_ijk], dtype=float)
    d = np.abs(np.asarray(g.direction, dtype=float).reshape(3, 3))
    half_index_mm = d.T @ np.asarray(half_extent_patient_mm, dtype=float)
    lo = np.floor(ijk_c - half_index_mm / sp).astype(int)
    hi = np.ceil(ijk_c + half_index_mm / sp).astype(int)
    if (lo < 0).any() or hi[0] >= ni or hi[1] >= nj or hi[2] >= nk:
        return None
    kk, jj, ii = np.mgrid[lo[2] : hi[2] + 1, lo[1] : hi[1] + 1, lo[0] : hi[0] + 1]
    pts = np.stack([ii, jj, kk, np.ones_like(ii)], axis=-1) @ aff.T
    box = (slice(lo[2], hi[2] + 1), slice(lo[1], hi[1] + 1), slice(lo[0], hi[0] + 1))
    return box, pts[..., :3]


def sphere_mask(
    g: ImageGeometry, centre_mm: tuple[float, float, float], diameter_mm: float
) -> np.ndarray | None:
    """Voxel-centre sphere on the grid; None if any part of the sphere leaves the image.

    Only the bounding box of the sphere is evaluated (the full-grid result is identical)."""
    r = diameter_mm / 2.0
    loc = _local_grid(g, centre_mm, np.full(3, r))
    if loc is None:
        return None
    box, pts = loc
    out = np.zeros((g.shape_ijk[2], g.shape_ijk[1], g.shape_ijk[0]), dtype=bool)
    out[box] = ((pts - np.asarray(centre_mm)) ** 2).sum(-1) <= r * r * (1 + 1e-12)
    return out


def cylinder_mask(
    g: ImageGeometry, centre_mm: tuple[float, float, float], diameter_mm: float, length_mm: float
) -> np.ndarray | None:
    """Voxel centres inside a cylinder with its axis along patient z (S-I); None if any part
    leaves the image. Radial and axial boundaries are inclusive."""
    r, h = diameter_mm / 2.0, length_mm / 2.0
    loc = _local_grid(g, centre_mm, np.array([r, r, h]))
    if loc is None:
        return None
    box, pts = loc
    c = np.asarray(centre_mm)
    d_xy = (pts[..., 0] - c[0]) ** 2 + (pts[..., 1] - c[1]) ** 2
    d_z = np.abs(pts[..., 2] - c[2])
    out = np.zeros((g.shape_ijk[2], g.shape_ijk[1], g.shape_ijk[0]), dtype=bool)
    out[box] = (d_xy <= r * r * (1 + 1e-12)) & (d_z <= h * (1 + 1e-12))
    return out


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
        length_mm=spec.length_mm,
    )
    if spec.method == "SUPPLIED_MASK":
        if mask is None or mask.shape != suv.shape or mask.dtype != bool:
            res.refusal = "supplied mask missing or not a boolean mask on the PET grid"
            return res
        m = mask
    else:
        shape = "sphere" if spec.method == "SPHERE_AT_SUPPLIED_CENTRE" else "cylinder"
        if spec.centre_patient_mm is None or not spec.diameter_mm or spec.diameter_mm <= 0:
            res.refusal = f"{shape} method requires a centre and a positive diameter"
            return res
        if shape == "cylinder" and (not spec.length_mm or spec.length_mm <= 0):
            res.refusal = "cylinder method requires a positive length"
            return res
        if None in g.spacing_ijk:
            res.refusal = "non-uniform slice spacing"
            return res
        sm = (
            sphere_mask(g, spec.centre_patient_mm, spec.diameter_mm)
            if shape == "sphere"
            else cylinder_mask(g, spec.centre_patient_mm, spec.diameter_mm, spec.length_mm)  # type: ignore[arg-type]
        )
        if sm is None:
            res.refusal = f"{shape} extends outside the image"
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
    res.suv_max = float(vals.max())
    if sul is not None:
        sv = sul[m]
        res.sul_mean, res.sul_sd = float(sv.mean()), float(sv.std(ddof=0))
    return res
