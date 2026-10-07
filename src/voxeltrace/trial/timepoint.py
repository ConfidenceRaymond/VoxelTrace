"""Build the evidence for one scan timepoint (strict SUV, lesions, protocol, SUL, liver)."""

from __future__ import annotations

from pathlib import Path

import pydicom

from voxeltrace.evidence.outputs import protocol_for_run
from voxeltrace.ingest import build_case
from voxeltrace.quant.evidence import quantify_case
from voxeltrace.quant.reference_region import ReferenceRegionSpec, measure_reference_region
from voxeltrace.quant.sul import apply_sul, compute_sul
from voxeltrace.training.ground_truth import pseudonym
from voxeltrace.trial.anonymization import audit_anonymization
from voxeltrace.trial.reasons import Reason, reason_for_suv_refusal
from voxeltrace.trial.schema import ScanTimepoint

SUL_FORMULAS = ("LBMJAMES128", "LBMJANMA")


def build_timepoint(
    case_dir: str | Path,
    *,
    subject: str,
    timepoint: str,
    site: str | None = None,
    synthetic: str | None = None,
    liver_spec: ReferenceRegionSpec | None = None,
) -> ScanTimepoint:
    tp = ScanTimepoint(
        subject_id=subject, timepoint=timepoint, site_id=site, synthetic_perturbation=synthetic
    )
    case = build_case(case_dir, subject_id=subject)
    try:
        run = quantify_case(case, subject=subject)
    except ValueError as exc:  # e.g. no or several PET series
        tp.reasons.append(
            Reason(code="MISSING_REQUIRED_TAG", detail=str(exc), confidence="CONFIRMED")
        )
        return tp
    tp.pet_series_pseudonym = pseudonym(run.pet_series_uid, "pet")
    pet = case.get_series(run.pet_series_uid or "")
    headers = [pydicom.dcmread(i.path, stop_before_pixels=True) for i in pet.instances]
    tp.anonymization = audit_anonymization(headers)
    proto, _ = protocol_for_run(run)
    tp.protocol = proto
    tp.injected_bq = proto.acquisition.injected_activity_bq.value  # type: ignore[assignment]
    if run.passed and run.outcome and run.outcome.result:
        res = run.outcome.result
        tp.suv_status = "PASS"
        tp.uptake_s = res.inputs.decay_interval_s
        tp.weight_kg = res.inputs.patient_weight_kg
        les = [x for x in run.evidence.measured.lesions if x.voxel_count > 0]
        if les and les[0].suv_peak and les[0].suv_peak.status == "COMPUTED":
            tp.lesion_suvpeak = les[0].suv_peak.value
        for f in SUL_FORMULAS:
            tp.sul[f] = compute_sul(res, headers, f)  # type: ignore[arg-type]
        sul_img = None
        ok = tp.sul.get("LBMJAMES128")
        if ok and ok.status == "PASS":
            sul_img = apply_sul(run.outcome.activity.array, ok)  # type: ignore[union-attr]
        tp.liver = measure_reference_region(
            run.outcome.suv,
            run.outcome.activity.geometry,
            liver_spec,  # type: ignore
            lesion_masks=list((run.seg_masks or {}).values()),
            sul=sul_img,
        )
    else:
        tp.suv_status = "REFUSED"
        tp.suv_refusal_codes = [r.code for r in run.evidence.refusal_reasons]
        tp.reasons += [
            reason_for_suv_refusal(r.code, r.message) for r in run.evidence.refusal_reasons
        ]
    return tp
