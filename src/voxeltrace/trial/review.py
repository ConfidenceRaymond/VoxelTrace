"""Reviewer working context for reference-region proposals (no UI, no AI).

Used by the Reference Review page. It loads one scan exactly as the trial audit does (strict
SUV, SUL LBMJAMES128, supplied lesions, CT-guided proposal), re-measures a candidate region
on the PET grid when the reviewer moves its centre, and computes ADVISORY QC aids. The aids
help the reviewer look; they are not standard thresholds, they never gate anything and they
never make a decision. Nothing here writes a review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from voxeltrace.ingest import build_case
from voxeltrace.quant.evidence import quantify_case
from voxeltrace.quant.reference_auto import ReferenceProposal, WorkGrid
from voxeltrace.quant.reference_region import (
    ReferenceRegionResult,
    cylinder_mask,
    measure_reference_region,
    sphere_mask,
)
from voxeltrace.quant.sul import apply_sul, compute_sul
from voxeltrace.schemas import ImageGeometry
from voxeltrace.training.ground_truth import pseudonym
from voxeltrace.trial.schema import ScanTimepoint

SUL_FORMULA = "LBMJAMES128"

# Advisory reviewer aids (documented in docs/reference_region_review.md). Not standards.
ADVISORY_COV = 0.20
ADVISORY_FOCAL_RATIO = 1.5
ADVISORY_HU_SD = 30.0
ADVISORY_LESION_MM = 15.0

CHECKLIST = {
    "LIVER": [
        "The whole sphere lies in liver tissue of the right lobe.",
        "It stays clear of the liver edge, the diaphragm, large vessels and the gallbladder.",
        "It contains no area of focal uptake and no supplied lesion outline.",
        "It is not in kidney, lung, bowel or another organ.",
    ],
    "BLOOD_POOL": [
        "The whole cylinder lies inside the lumen of the descending thoracic aorta.",
        "It does not touch the aortic wall, spine, oesophagus, heart or lung.",
        "It is aligned with the vessel on the coronal view and spans 2 cm of it.",
        "It contains no area of focal uptake.",
    ],
}


@dataclass
class ReviewContext:
    subject: str
    timepoint: str
    case_dir: str
    pet_series_pseudonym: str | None
    suv: np.ndarray | None
    pet_geom: ImageGeometry | None
    sul_img: np.ndarray | None
    sul_status: str
    lesion_masks: list[np.ndarray]
    work: WorkGrid | None
    proposals: dict[str, ReferenceProposal]
    problems: list[str] = field(default_factory=list)


def load_review_context(case_dir: str | Path, subject: str, timepoint: str) -> ReviewContext:
    """Same inputs and proposer call as ``trial.timepoint.build_timepoint``."""
    from voxeltrace.trial.timepoint import _auto_proposals

    case = build_case(case_dir, subject_id=subject)
    ctx = ReviewContext(
        subject=subject,
        timepoint=timepoint,
        case_dir=str(case_dir),
        pet_series_pseudonym=None,
        suv=None,
        pet_geom=None,
        sul_img=None,
        sul_status="NOT_RUN",
        lesion_masks=[],
        work=None,
        proposals={},
    )
    try:
        run = quantify_case(case, subject=subject)
    except ValueError as exc:
        ctx.problems.append(str(exc))
        return ctx
    if not (run.passed and run.outcome and run.outcome.result):
        ctx.problems.append("strict SUV refused; no reference region can be measured")
        return ctx
    import pydicom

    ctx.pet_series_pseudonym = pseudonym(run.pet_series_uid, "pet")
    ctx.suv = run.outcome.suv
    ctx.pet_geom = run.outcome.activity.geometry
    pet = case.get_series(run.pet_series_uid or "")
    headers = [pydicom.dcmread(i.path, stop_before_pixels=True) for i in pet.instances]
    sul = compute_sul(run.outcome.result, headers, SUL_FORMULA)  # type: ignore[arg-type]
    ctx.sul_status = sul.status
    if sul.status == "PASS":
        ctx.sul_img = apply_sul(run.outcome.activity.array, sul)
    ctx.lesion_masks = list((run.seg_masks or {}).values())
    tp = ScanTimepoint(
        subject_id=subject, timepoint=timepoint, pet_series_pseudonym=ctx.pet_series_pseudonym
    )
    ctx.proposals, _, ctx.work = _auto_proposals(case, run, tp, ctx.lesion_masks, None)
    return ctx


def candidate_mask(ctx: ReviewContext, p: ReferenceProposal, centre) -> np.ndarray | None:
    assert ctx.pet_geom is not None and p.diameter_mm is not None
    if p.method == "SPHERE_AT_SUPPLIED_CENTRE":
        return sphere_mask(ctx.pet_geom, centre, p.diameter_mm)
    return cylinder_mask(ctx.pet_geom, centre, p.diameter_mm, p.length_mm or 0.0)


def measure_candidate(
    ctx: ReviewContext, p: ReferenceProposal, centre: tuple[float, float, float]
) -> tuple[ReferenceRegionResult, dict[str, Any]]:
    """Measure the region (fixed method and size) at ``centre`` on the PET grid, exactly as
    the audit will, plus CT HU and the advisory QC aids."""
    if ctx.suv is None or ctx.pet_geom is None:
        raise ValueError("no quantitative PET for this scan")
    spec = p.to_spec("reviewer candidate (not yet recorded)", centre=centre)
    res = measure_reference_region(
        ctx.suv, ctx.pet_geom, spec, lesion_masks=ctx.lesion_masks, sul=ctx.sul_img
    )
    qc: dict[str, Any] = {"advisory": []}
    if ctx.work is not None:
        from voxeltrace.visualization.reference_qc import region_mask_on_work

        m = region_mask_on_work(ctx.work, spec)
        if m.any():
            qc["ct_hu_mean"] = float(ctx.work.hu[m].mean())
            qc["ct_hu_sd"] = float(ctx.work.hu[m].std())
            if qc["ct_hu_sd"] > ADVISORY_HU_SD:
                qc["advisory"].append(
                    f"CT density varies within the region (HU SD {qc['ct_hu_sd']:.0f} > "
                    f"{ADVISORY_HU_SD:.0f}); check for edges or vessels"
                )
    if res.status != "COMPUTED":
        qc["blocking"] = res.refusal
        return res, qc
    if res.cov is not None and res.cov > ADVISORY_COV:
        qc["advisory"].append(
            f"uptake varies within the region (CoV {res.cov:.2f} > {ADVISORY_COV:.2f})"
        )
    if res.suv_max and res.suv_mean and res.suv_max > ADVISORY_FOCAL_RATIO * res.suv_mean:
        qc["advisory"].append(
            f"SUVmax is {res.suv_max / res.suv_mean:.2f} x SUVmean (> {ADVISORY_FOCAL_RATIO}); "
            "check for focal uptake inside the region"
        )
    d = lesion_distance_mm(ctx, centre)
    if d is not None:
        qc["nearest_supplied_lesion_mm"] = d
        r = (p.diameter_mm or 0) / 2
        if d - r < ADVISORY_LESION_MM:
            qc["advisory"].append(
                f"a supplied lesion is {d - r:.0f} mm from the region edge "
                f"(< {ADVISORY_LESION_MM:.0f} mm)"
            )
    return res, qc


def lesion_distance_mm(ctx: ReviewContext, centre) -> float | None:
    """Distance from ``centre`` to the nearest supplied lesion voxel centre (None if none)."""
    if not ctx.lesion_masks or ctx.pet_geom is None:
        return None
    union = np.zeros_like(ctx.lesion_masks[0], dtype=bool)
    for m in ctx.lesion_masks:
        union |= m.astype(bool)
    kji = np.argwhere(union)
    if kji.size == 0:
        return None
    aff = np.asarray(ctx.pet_geom.affine)
    ijk1 = np.c_[kji[:, 2], kji[:, 1], kji[:, 0], np.ones(len(kji))]
    pts = ijk1 @ aff.T
    return float(np.sqrt(((pts[:, :3] - np.asarray(centre)) ** 2).sum(1)).min())
