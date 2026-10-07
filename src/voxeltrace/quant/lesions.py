"""Per-segment lesion metrics on a supplied segmentation (no automatic segmentation).

Definitions (see docs/quantification.md):
- MTV    = voxel_count × voxel volume of the supplied segment mask, in mL. No thresholding.
- TLG    = MTV [mL] × SUVmean (unit g, with SUV in g/mL). Based on the supplied mask only.
- SUVpeak (VoxelTrace definition, following the QIBA/PERCIST 1.0 cm³ sphere and the IBSI
  voxel-centre inclusion rule):
    sphere volume 1.0 cm³ (NOT 1 cm diameter), radius r = (3 / (4π))^(1/3) cm ≈ 6.2035 mm;
    candidate centres = every voxel centre inside the segment (exhaustive search);
    sphere voxels = all image voxels whose centres lie within r (physical mm, anisotropic
      spacing respected); voxels are NOT restricted to the segment;
    candidates whose sphere would extend beyond the image are excluded (no padding);
    SUVpeak = maximum sphere mean over the remaining candidates.
"""

from __future__ import annotations

import math

import numpy as np
import SimpleITK as sitk

from voxeltrace.schemas import (
    ImageGeometry,
    LesionComponent,
    LesionMetrics,
    LesionSummary,
    QCWarning,
    SegmentInfo,
    SUVPeak,
)

PEAK_SPHERE_ML = 1.0
PEAK_RADIUS_MM = (3.0 / (4.0 * math.pi)) ** (1.0 / 3.0) * 10.0  # 6.2035 mm
_BATCH = 20000


def sphere_offsets(
    spacing_kji: tuple[float, float, float], radius_mm: float = PEAK_RADIUS_MM
) -> np.ndarray:
    """Integer (dk, dj, di) offsets whose voxel centres lie within ``radius_mm``."""
    reach = [int(math.floor(radius_mm / s)) for s in spacing_kji]
    grids = np.mgrid[-reach[0] : reach[0] + 1, -reach[1] : reach[1] + 1, -reach[2] : reach[2] + 1]
    pts = grids.reshape(3, -1).T
    dist2 = ((pts * np.asarray(spacing_kji)) ** 2).sum(axis=1)
    return pts[dist2 <= radius_mm**2 * (1 + 1e-12)]


def suv_peak(
    suv: np.ndarray,
    mask: np.ndarray,
    spacing_kji: tuple[float, float, float],
    affine: list[list[float]] | None = None,
) -> SUVPeak:
    offs = sphere_offsets(spacing_kji)
    voxel_ml = float(np.prod(spacing_kji)) / 1000.0
    base = {
        "radius_mm": PEAK_RADIUS_MM,
        "kernel_voxel_count": len(offs),
        "kernel_effective_volume_ml": len(offs) * voxel_ml,
    }
    centres = np.argwhere(mask)
    reach = np.abs(offs).max(axis=0)
    shape = np.asarray(suv.shape)
    inside = np.all((centres - reach >= 0) & (centres + reach < shape), axis=1)
    cand = centres[inside]
    excluded = int((~inside).sum())
    if len(cand) == 0:
        return SUVPeak(
            status="NOT_AVAILABLE",
            candidates_excluded_at_image_edge=excluded,
            note="no candidate centre with the sphere fully inside the image",
            **base,
        )
    best_val, best_idx = -math.inf, -1
    for start in range(0, len(cand), _BATCH):
        c = cand[start : start + _BATCH]
        idx = c[:, None, :] + offs[None, :, :]
        means = suv[idx[..., 0], idx[..., 1], idx[..., 2]].mean(axis=1)
        j = int(np.argmax(means))
        if means[j] > best_val:
            best_val, best_idx = float(means[j]), start + j
    centre = cand[best_idx]
    pts = centre + offs
    frac = float(mask[pts[:, 0], pts[:, 1], pts[:, 2]].mean())
    centre_mm = None
    if affine is not None:
        k, j, i = (int(v) for v in centre)
        centre_mm = tuple(float(v) for v in (np.asarray(affine) @ [i, j, k, 1.0])[:3])
    note = None
    if frac < 1.0:
        note = "sphere includes voxels outside the segment (allowed by definition)"
    return SUVPeak(
        status="COMPUTED",
        value=best_val,
        center_kji=tuple(int(v) for v in centre),
        center_patient_mm=centre_mm,
        fraction_of_sphere_voxels_in_segment=frac,
        candidates_evaluated=len(cand),
        candidates_excluded_at_image_edge=excluded,
        note=note,
        **base,
    )


def _components(mask: np.ndarray, suv: np.ndarray, voxel_ml: float) -> list[LesionComponent]:
    img = sitk.GetImageFromArray(mask.astype(np.uint8))
    labels = sitk.GetArrayFromImage(sitk.ConnectedComponent(img, True))  # fully connected
    out = []
    for lab in range(1, int(labels.max()) + 1):
        vals = suv[labels == lab]
        out.append(
            LesionComponent(
                index=lab,
                voxel_count=int(vals.size),
                volume_ml=vals.size * voxel_ml,
                suv_max=float(vals.max()),
                suv_mean=float(vals.mean()),
            )
        )
    return sorted(out, key=lambda c: -c.voxel_count)


def quantify_segments(
    suv: np.ndarray,
    geometry: ImageGeometry,
    masks: dict[int, np.ndarray],
    segments: list[SegmentInfo] | None = None,
    compute_peak: bool = True,
) -> list[LesionMetrics]:
    """Metrics per supplied segment. ``suv`` and masks are ``[k, j, i]`` on the same grid."""
    sx, sy, sz = geometry.spacing_ijk
    if sz is None or not geometry.uniform_slice_spacing:
        raise ValueError("lesion metrics require uniform slice spacing")
    expected = (geometry.shape_ijk[2], geometry.shape_ijk[1], geometry.shape_ijk[0])
    if suv.shape != expected:
        raise ValueError(f"SUV shape {suv.shape} does not match geometry {expected}")
    spacing_kji = (float(sz), float(sy), float(sx))
    voxel_ml = sx * sy * sz / 1000.0
    labels = {s.number: s.label for s in segments or []}
    results = []
    for number in sorted(masks):
        m = masks[number]
        if m.shape != suv.shape or m.dtype != bool:
            raise ValueError(f"segment {number}: mask must be bool with shape {suv.shape}")
        vals = suv[m]
        lm = LesionMetrics(
            segment_number=number,
            segment_label=labels.get(number),
            voxel_count=int(vals.size),
            voxel_volume_ml=voxel_ml,
            mtv_ml=vals.size * voxel_ml,
        )
        if vals.size == 0:
            lm.warnings.append(QCWarning(code="EMPTY_SEGMENT", message=f"segment {number} empty"))
            results.append(lm)
            continue
        p10, p25, med, p75, p90 = np.percentile(vals, [10, 25, 50, 75, 90])
        lm.suv_min, lm.suv_max = float(vals.min()), float(vals.max())
        lm.suv_mean, lm.suv_median = float(vals.mean()), float(med)
        lm.suv_std = float(vals.std(ddof=0))
        lm.suv_p10, lm.suv_p25, lm.suv_p75, lm.suv_p90 = (
            float(p10),
            float(p25),
            float(p75),
            float(p90),
        )
        lm.tlg = lm.mtv_ml * lm.suv_mean
        lm.components = _components(m, suv, voxel_ml)
        lm.n_components = len(lm.components)
        if lm.n_components > 1:
            lm.warnings.append(
                QCWarning(
                    code="MULTIPLE_COMPONENTS",
                    severity="info",
                    message=f"segment {number} has {lm.n_components} disconnected components; "
                    "segment-level metrics pool them",
                )
            )
        if compute_peak:
            lm.suv_peak = suv_peak(suv, m, spacing_kji, geometry.affine)
            if lm.mtv_ml < PEAK_SPHERE_ML:
                lm.warnings.append(
                    QCWarning(
                        code="SEGMENT_SMALLER_THAN_PEAK_SPHERE",
                        message=f"MTV {lm.mtv_ml:.3f} mL < 1 mL; SUVpeak necessarily includes "
                        "voxels outside the segment",
                    )
                )
        results.append(lm)
    return results


def summarize(lesions: list[LesionMetrics]) -> LesionSummary:
    nonempty = [x for x in lesions if x.voxel_count > 0]
    top = max(nonempty, key=lambda x: x.suv_max or -math.inf, default=None)
    return LesionSummary(
        n_segments=len(lesions),
        n_nonempty_segments=len(nonempty),
        total_mtv_ml=sum(x.mtv_ml for x in lesions),
        total_tlg=sum(x.tlg or 0.0 for x in lesions),
        max_suv_max=top.suv_max if top else None,
        max_suv_max_segment=top.segment_number if top else None,
    )
