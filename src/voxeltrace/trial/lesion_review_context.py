"""Lesion review context for the Lesion Review page and the lesion-qc CLI (no decisions here).

For one scan directory: quantify (unchanged strict SUV), build one LesionCandidate per
supplied segment, resolve its review status against the review log, and render a QC image.
``build_review`` turns an explicit human decision into a LesionReview record; it never runs
without a reviewer-supplied decision.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

import voxeltrace
from voxeltrace.ingest import build_case
from voxeltrace.ingest.dicom import load_series_volume
from voxeltrace.quant.evidence import quantify_case
from voxeltrace.trial.lesion_review import LesionEvidence, LesionReview, resolve
from voxeltrace.trial.timepoint import lesion_candidates


def load_lesion_context(
    scan_dir: str | Path, subject: str, timepoint: str, reviews: tuple[list, dict]
) -> dict[str, Any]:
    from voxeltrace.visualization.ct import resample_ct_to_pet
    from voxeltrace.visualization.lesion_qc import render_lesion_qc

    case = build_case(scan_dir, subject_id=subject)
    run = quantify_case(case, subject=subject)
    cands = lesion_candidates(run, subject, timepoint)
    evidence = [resolve(c, reviews[0], reviews[1]) for c in cands]
    quant_ok = bool(run.passed and run.outcome and run.outcome.result)
    if quant_ok:
        vol, unit, geom = run.outcome.suv, "SUV", run.outcome.activity.geometry  # type: ignore[union-attr]
    else:
        pv = load_series_volume(case.get_series(run.pet_series_uid or ""))
        vol, unit, geom = pv.array, "stored units (SUV refused)", pv.geometry
    pet = case.get_series(run.pet_series_uid or "")
    ct_on_pet, ct_note = None, "no CT in the PET frame of reference"
    cts = [
        s
        for s in case.series_by_category("CT")
        if set(s.frame_of_reference_uids) == set(pet.frame_of_reference_uids)
    ]
    if len(cts) == 1 and len(cts[0].instances) >= 2:
        try:
            ct = load_series_volume(cts[0])
            ct_on_pet = resample_ct_to_pet(ct.array, ct.geometry, geom, cts[0].frame_of_reference_uids[0],
                                           pet.frame_of_reference_uids[0])  # fmt: skip
            ct_note = "CT resampled onto the PET grid (display only)"
        except Exception as exc:  # noqa: BLE001
            ct_note = f"CT not displayed: {exc}"
    items = []
    for ev in evidence:
        m = run.seg_masks[ev.candidate.segment_number] if run.seg_masks else None
        qc = []
        if not quant_ok:
            qc.append("SUV refused: metrics are NOT quantitatively eligible")
        if ev.candidate.voxel_count == 0:
            qc.append("EMPTY_SEGMENT")
        les = next(
            (x for x in run.lesions if x.segment_number == ev.candidate.segment_number), None
        )
        peak_kji = (
            tuple(les.suv_peak.center_kji)
            if les and les.suv_peak and les.suv_peak.center_kji
            else None
        )
        if (
            les
            and les.suv_peak
            and les.suv_peak.fraction_of_sphere_voxels_in_segment is not None
            and les.suv_peak.fraction_of_sphere_voxels_in_segment < 1
        ):
            qc.append(
                f"SUVpeak sphere {les.suv_peak.fraction_of_sphere_voxels_in_segment:.0%} inside the segment"
            )
        if les and any(c.zero_suv_voxels for c in les.components):
            qc.append("segment contains voxels with SUV exactly 0 (outside body / masked PET?)")
        png, max_kji = None, None
        if m is not None and m.any():
            masked = np.where(m, vol, -np.inf)
            max_kji = tuple(int(v) for v in np.unravel_index(int(np.argmax(masked)), vol.shape))
            png = render_lesion_qc(vol, m, unit=unit, ct_on_pet=ct_on_pet, suvmax_kji=max_kji, suvpeak_kji=peak_kji,  # type: ignore[arg-type]
                                   title=f"{subject} {timepoint} segment {ev.candidate.segment_number} "
                                   f"[{ev.candidate.source_type}; review {ev.review_status}]")  # fmt: skip
        items.append(
            {
                "evidence": ev,
                "png": png,
                "qc_warnings": qc,
                "suvmax_kji": max_kji,
                "suvpeak_kji": peak_kji,
            }
        )
    return {"subject": subject, "timepoint": timepoint, "quant_eligible": quant_ok, "unit": unit,
            "ct_note": ct_note, "items": items}  # fmt: skip


def build_review(ev: LesionEvidence, *, reviewer_id: str, reviewer_role: str, decision: str, note: str = "",
                 created_via: str = "HUMAN_UI") -> LesionReview:  # fmt: skip
    from voxeltrace.quant.suv import git_state

    if not reviewer_id.strip():
        raise ValueError("reviewer identifier required")
    if decision not in ("ACCEPT", "REJECT", "REJECT_AND_REPLACE_REQUIRED"):
        raise ValueError("an explicit decision is required")
    c = ev.candidate
    return LesionReview(
        subject=c.subject, timepoint=c.timepoint, study_hash=c.study_hash, pet_series_hash=c.pet_series_hash,
        seg_series_hash=c.seg_series_hash, seg_file_sha256=c.seg_file_sha256, segment_number=c.segment_number,
        segment_label=c.segment_label, mask_sha256=c.mask_sha256, source_type=c.source_type,
        source_provenance=c.source_provenance, reviewer_id=reviewer_id.strip(), reviewer_role=reviewer_role,  # type: ignore[arg-type]
        decision=decision, timestamp=datetime.now(UTC), software_version=voxeltrace.__version__,  # type: ignore[arg-type]
        git_commit=git_state()[0], note=note, created_via=created_via,  # type: ignore[arg-type]
    )  # fmt: skip
