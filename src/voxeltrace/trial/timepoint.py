"""Build the evidence for one scan timepoint (strict SUV, lesions, protocol, SUL, liver and
blood-pool reference regions)."""

from __future__ import annotations

from pathlib import Path

import pydicom

from voxeltrace.evidence.outputs import protocol_for_run
from voxeltrace.ids import pseudonym
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
from voxeltrace.trial.anonymization import audit_anonymization
from voxeltrace.trial.reasons import Reason, reason_for_suv_refusal
from voxeltrace.trial.reference import REGIONS, ReferenceReview, resolve_region
from voxeltrace.trial.schema import ScanTimepoint
from voxeltrace.trial.synthetic_reference import (
    InheritanceRequest,
    SyntheticFixtureManifest,
    geometry_sha256,
    inherit_region,
    same_case_dir,
    volume_sha256,
)

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
    inherit_from: tuple[str, str, ScanTimepoint, dict[str, str | None]] | None = None,
    lesion_reviews: tuple[list, dict] | None = None,
    lesion_policy: str = "REVIEW_REQUIRED",
) -> ScanTimepoint:
    """``reference_specs``/``reviews`` are keyed by region (LIVER, BLOOD_POOL);
    ``liver_spec`` is kept for callers that only supply a liver region.
    ``inherit_from`` = (parent key, parent case dir, parent timepoint, parent review sha by
    region) requests SYNTHETIC-fixture reference inheritance (trial/synthetic_reference.py)."""
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
    tp.pet_synthetic_label = bool(headers) and all(
        str(h.get("SeriesDescription", "")).startswith("SYNTHETIC_PERTURBATION") for h in headers
    )
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
        _apply_lesion_gate(tp, run, lesion_reviews, lesion_policy)
        if lesion_policy == "LEGACY_UNREVIEWED_ALLOWED":  # historical path, verbatim (labelled)
            if les and les[0].suv_peak and les[0].suv_peak.status == "COMPUTED":
                tp.lesion_suvpeak = les[0].suv_peak.value
            if les:
                tp.lesion_suvmax = les[0].suv_max
        else:
            target = next((e for e in tp.lesion_evidence if e.used_as_target), None)
            if target is not None:
                tp.lesion_suvpeak = target.candidate.suv_peak
                tp.lesion_suvmax = target.candidate.suv_max
        act = run.outcome.activity
        tp.pet_content_sha256 = volume_sha256(act.array, act.geometry)  # type: ignore[union-attr]
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

        inherited: dict[str, object] = {}
        if inherit_from is not None:
            parent_key, parent_dir, parent_tp, parent_review_sha = inherit_from
            _ct_fingerprint(case, run, tp)
            fixture = SyntheticFixtureManifest.load(case_dir)
            req = InheritanceRequest(
                child_key=f"{subject}/{timepoint}",
                parent_key=parent_key,
                declared_synthetic=bool(synthetic),
                dicom_synthetic_label=tp.pet_synthetic_label,
                fixture=fixture,
                parent_pet_content_sha256=parent_tp.pet_content_sha256,
                parent_ct_geometry_sha256=parent_tp.ct_geometry_sha256,
                parent_ct_pixel_sha256=parent_tp.ct_pixel_sha256,
                child_ct_geometry_sha256=tp.ct_geometry_sha256,
                child_ct_pixel_sha256=tp.ct_pixel_sha256,
                parent_fixture_match=fixture is not None
                and same_case_dir(fixture.parent_case_dir, parent_dir),
            )
            for region in REGIONS:
                if region not in specs:
                    parent_res = parent_tp.liver if region == "LIVER" else parent_tp.blood_pool
                    inherited[region] = inherit_region(
                        region, req, parent_res, parent_review_sha.get(region), measure
                    )
        need_auto = auto_reference and any(r not in specs and r not in inherited for r in REGIONS)
        proposals, qc_images, _ = (
            _auto_proposals(case, run, tp, lesion_masks, qc_dir) if need_auto else ({}, {}, None)
        )
        for region in REGIONS:
            if region in inherited:
                res = inherited[region]
            else:
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
    tp.ct_series_pseudonym = pseudonym(cts[0].series_uid, "ct")
    tp.ct_geometry_sha256 = geometry_sha256(ct.geometry)
    tp.ct_pixel_sha256 = volume_sha256(ct.array, ct.geometry)
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


def lesion_candidates(run, subject: str, timepoint: str) -> list:
    """One LesionCandidate per supplied segment (mask on the PET grid); never modifies files."""
    import numpy as np

    from voxeltrace.bundle import sha256_file
    from voxeltrace.trial.lesion_review import (
        LesionCandidate,
        classify_source,
        hashes,
        mask_sha256,
        target_eligible,
    )

    if run.seg is None or not run.seg_masks:
        return []
    pet = run.case.get_series(run.pet_series_uid or "")
    try:
        h = pydicom.dcmread(run.seg.path, stop_before_pixels=True)
        desc = str(h.get("SeriesDescription", "")) or None
        names = {int(it.SegmentNumber): str(it.get("SegmentAlgorithmName", "")) or None
                 for it in (h.get("SegmentSequence") or [])}  # fmt: skip
        seg_manufacturer = str(h.get("Manufacturer", "")) or None
    except Exception:  # noqa: BLE001 - provenance unreadable -> UNKNOWN source
        desc, names, seg_manufacturer = None, {}, None
    seg_sha = sha256_file(Path(run.seg.path))
    info = {s.number: s for s in run.seg.segments}
    metrics = {m.segment_number: m for m in run.lesions}
    ids = hashes(pet.study_uid, pet.series_uid, run.seg.series_uid)
    out = []
    for num, mask in sorted(run.seg_masks.items()):
        si = info.get(num)
        src, why = classify_source(desc, si.algorithm_type if si else None, names.get(num))
        m = metrics.get(num)
        label = (si.label if si else None) or (m.segment_label if m else None)
        peak = m.suv_peak.value if m and m.suv_peak and m.suv_peak.status == "COMPUTED" else None
        prov = {
            "basis": why,
            "seg_series_description": desc,
            "segment_algorithm_type": si.algorithm_type if si else None,
            "segment_algorithm_name": names.get(num),
            "seg_manufacturer": seg_manufacturer,
            "seg_file": Path(run.seg.path).name,
        }
        idx = np.argwhere(np.asarray(mask).astype(bool))
        out.append(LesionCandidate(
            subject=subject, timepoint=timepoint, **ids, seg_file_sha256=seg_sha,
            segment_number=num, segment_label=label,
            mask_sha256=mask_sha256(mask), source_type=src, source_provenance=prov,
            segment_category=si.category if si else None, segment_type=si.type if si else None,
            target_eligible=target_eligible(si.category if si else None),
            voxel_count=int(idx.shape[0]),
            volume_ml=m.mtv_ml if m else None, mtv_ml=m.mtv_ml if m else None,
            suv_max=m.suv_max if m else None, suv_mean=m.suv_mean if m else None,
            suv_peak=peak,
            tlg=m.tlg if m else None,
            bbox_kji=[idx.min(0).tolist(), idx.max(0).tolist()] if idx.size else None,
            centroid_kji=idx.mean(0).round(2).tolist() if idx.size else None,
        ))  # fmt: skip
    return out


def _apply_lesion_gate(tp: ScanTimepoint, run, lesion_reviews, policy: str) -> None:
    from voxeltrace.trial.lesion_review import choose_target, resolve

    cands = lesion_candidates(run, tp.subject_id, tp.timepoint)
    reviews, chain = lesion_reviews or ([], {"status": "NO_FILE"})
    tp.lesion_evidence = [resolve(c, reviews, chain) for c in cands]
    _t, tp.lesion_target_status = choose_target(tp.lesion_evidence, policy)  # type: ignore[arg-type]


def _pet_frame_cts(case, run) -> list:
    pet = case.get_series(run.pet_series_uid or "")
    pet_for = set(pet.frame_of_reference_uids)
    return [
        s
        for s in case.series
        if s.category == "CT" and pet_for and set(s.frame_of_reference_uids) == pet_for
    ]


def _ct_fingerprint(case, run, tp: ScanTimepoint) -> None:
    """Record the CT geometry/pixel hashes (the one CT in the PET frame of reference)."""
    cts = _pet_frame_cts(case, run)
    if len(cts) != 1:
        return
    try:
        ct = load_series_volume(cts[0])
    except IngestError:
        return
    tp.ct_series_pseudonym = pseudonym(cts[0].series_uid, "ct")
    tp.ct_geometry_sha256 = geometry_sha256(ct.geometry)
    tp.ct_pixel_sha256 = volume_sha256(ct.array, ct.geometry)
