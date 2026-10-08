"""Build the evidence for one scan timepoint (strict SUV, lesions, protocol, SUL, liver and
blood-pool reference regions)."""

from __future__ import annotations

from pathlib import Path

import pydicom

from voxeltrace.evidence.outputs import protocol_for_run
from voxeltrace.ingest import build_case
from voxeltrace.ingest.dicom import IngestError, load_series_volume
from voxeltrace.quant.evidence import quantify_case
from voxeltrace.quant.reference_auto import (
    ReferenceProposal,
    WorkGrid,
    propose_reference_regions,
)
from voxeltrace.quant.reference_region import ReferenceRegionSpec, measure_reference_region
from voxeltrace.quant.sul import apply_sul, compute_sul
from voxeltrace.training.ground_truth import pseudonym
from voxeltrace.trial.anonymization import audit_anonymization
from voxeltrace.trial.reasons import Reason, reason_for_suv_refusal
from voxeltrace.trial.reference import REGIONS, ReferenceReview, resolve_region
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
    reference_specs: dict[str, ReferenceRegionSpec] | None = None,
    reviews: dict[str, ReferenceReview] | None = None,
    auto_reference: bool = True,
    qc_dir: str | Path | None = None,
) -> ScanTimepoint:
    """``reference_specs``/``reviews`` are keyed by region (LIVER, BLOOD_POOL);
    ``liver_spec`` is kept for callers that only supply a liver region."""
    specs = dict(reference_specs or {})
    if liver_spec is not None:
        specs.setdefault("LIVER", liver_spec)
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
        lesion_masks = list((run.seg_masks or {}).values())

        def measure(spec: ReferenceRegionSpec):
            return measure_reference_region(
                run.outcome.suv,  # type: ignore[union-attr]
                run.outcome.activity.geometry,  # type: ignore[union-attr]
                spec,
                lesion_masks=lesion_masks,
                sul=sul_img,
            )

        need_auto = auto_reference and any(r not in specs for r in REGIONS)
        proposals, qc_images, _ = (
            _auto_proposals(case, run, tp, lesion_masks, qc_dir) if need_auto else ({}, {}, None)
        )
        for region in REGIONS:
            res = resolve_region(
                region,
                supplied=specs.get(region),
                proposal=proposals.get(region),
                review=(reviews or {}).get(region),
                measure=measure,
                auto_enabled=auto_reference,
                qc_image=qc_images.get(region),
            )
            if region == "LIVER":
                tp.liver = res
            else:
                tp.blood_pool = res
    else:
        tp.suv_status = "REFUSED"
        tp.suv_refusal_codes = [r.code for r in run.evidence.refusal_reasons]
        tp.reasons += [
            reason_for_suv_refusal(r.code, r.message) for r in run.evidence.refusal_reasons
        ]
    return tp


def _auto_proposals(
    case, run, tp: ScanTimepoint, lesion_masks, qc_dir: str | Path | None
) -> tuple[dict[str, ReferenceProposal], dict[str, str], WorkGrid | None]:
    """Deterministic CT-guided proposals (vt-refauto-1) and, if ``qc_dir``, QC renders."""
    pet = case.get_series(run.pet_series_uid or "")
    pet_for = set(pet.frame_of_reference_uids)
    cts = [
        s
        for s in case.series
        if s.category == "CT" and pet_for and set(s.frame_of_reference_uids) == pet_for
    ]
    ids = {"pet_series_pseudonym": tp.pet_series_pseudonym}

    def nf(why: str) -> dict[str, ReferenceProposal]:
        return {
            r: ReferenceProposal(region=r, status="NOT_FOUND", failure_reason=why, **ids)
            for r in REGIONS
        }

    if not cts:
        return nf("no CT series in the PET frame of reference"), {}, None
    if len(cts) > 1:
        return nf(f"{len(cts)} CT series in the PET frame of reference (ambiguous)"), {}, None
    try:
        ct = load_series_volume(cts[0])
    except IngestError as exc:
        return nf(f"CT not loadable: {exc}"), {}, None
    props, work = propose_reference_regions(
        ct.array,
        ct.geometry,
        suv=run.outcome.suv,
        pet_geom=run.outcome.activity.geometry,
        lesion_masks=lesion_masks,
        pet_series_pseudonym=tp.pet_series_pseudonym,
        ct_series_pseudonym=pseudonym(cts[0].series_uid, "ct"),
    )
    images: dict[str, str] = {}
    if qc_dir is not None and work is not None:
        from voxeltrace.visualization.reference_qc import render_proposal_qc

        d = Path(qc_dir)
        d.mkdir(parents=True, exist_ok=True)
        for region, p in props.items():
            if p.status != "PROPOSED":
                continue
            name = f"{tp.subject_id}_{tp.timepoint}_{region}.png"
            (d / name).write_bytes(
                render_proposal_qc(work, p, title=f"{tp.subject_id} {tp.timepoint} {region}")
            )
            images[region] = f"{d.name}/{name}"
    return props, images, work
