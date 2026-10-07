"""Case-level quantification: strict SUV → lesion metrics → typed evidence + output files."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

import voxeltrace
from voxeltrace.ingest.dicom import IngestError, _get
from voxeltrace.ingest.segmentation import decode_dicom_seg
from voxeltrace.quant.lesions import quantify_segments, summarize
from voxeltrace.quant.suv import SUVOutcome, compute_suv_for_series
from voxeltrace.schemas import (
    EvidenceMeasured,
    LesionMetrics,
    QCWarning,
    QuantEvidence,
    SegmentationMetadata,
    VoxelTraceCase,
)


@dataclass
class QuantRun:
    case: VoxelTraceCase
    pet_series_uid: str | None
    outcome: SUVOutcome | None
    seg: SegmentationMetadata | None
    seg_masks: dict[int, np.ndarray] | None
    lesions: list[LesionMetrics]
    evidence: QuantEvidence
    warnings: list[QCWarning] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.outcome is not None and self.outcome.result is not None


def _select_pet(case: VoxelTraceCase, pet_uid: str | None) -> tuple[str | None, str | None]:
    pets = case.series_by_category("PET")
    if pet_uid:
        return (
            (pet_uid, None)
            if any(p.series_uid == pet_uid for p in pets)
            else (None, f"PET series {pet_uid} not found")
        )
    if len(pets) != 1:
        return None, f"{len(pets)} PET series found; select one explicitly"
    return pets[0].series_uid, None


def _select_seg(
    case: VoxelTraceCase, pet_uid: str, seg_uid: str | None
) -> tuple[SegmentationMetadata | None, str | None]:
    segs = [
        s
        for s in case.segmentations
        if s.source == "DICOM_SEG" and pet_uid in s.referenced_series_uids
    ]
    if seg_uid:
        segs = [s for s in segs if s.series_uid == seg_uid]
    if not segs:
        return None, "no DICOM SEG referencing the PET series"
    if len(segs) > 1:
        return None, f"{len(segs)} SEG objects reference the PET series; select one explicitly"
    return segs[0], None


def quantify_case(
    case: VoxelTraceCase,
    *,
    pet_uid: str | None = None,
    seg_uid: str | None = None,
    dataset: str | None = None,
    subject: str | None = None,
    compute_peak: bool = True,
) -> QuantRun:
    warnings: list[QCWarning] = []
    uid, problem = _select_pet(case, pet_uid)
    if uid is None:
        raise ValueError(problem)
    outcome = compute_suv_for_series(case.get_series(uid), dataset=dataset, subject=subject)
    seg, seg_problem = _select_seg(case, uid, seg_uid)
    if seg_problem:
        warnings.append(QCWarning(code="NO_SEGMENTATION", severity="info", message=seg_problem))

    masks = None
    lesions: list[LesionMetrics] = []
    if seg is not None:
        try:
            dec = decode_dicom_seg(seg.path, case.get_series(uid))
            masks, seg = dec.masks, dec.metadata
        except IngestError as exc:
            warnings.append(QCWarning(code="SEG_NOT_DECODED", severity="error", message=str(exc)))
    if outcome.result is not None and masks is not None:
        assert outcome.suv is not None and outcome.activity is not None
        lesions = quantify_segments(
            outcome.suv,
            outcome.activity.geometry,
            masks,
            seg.segments if seg else None,
            compute_peak=compute_peak,
        )
    elif masks is not None:
        warnings.append(
            QCWarning(
                code="LESION_METRICS_NOT_COMPUTED",
                message="SUV refused; lesion SUV metrics not computed",
            )
        )

    result, refusal = outcome.result, outcome.refusal
    src = result or refusal
    assert src is not None
    prov = src.provenance.model_copy()
    prov.seg_series_uid = seg.series_uid if seg else None
    all_warnings = list(src.validation.warnings) + warnings
    for les in lesions:
        all_warnings.extend(les.warnings)
    evidence = QuantEvidence(
        disclaimer=f"{voxeltrace.DISCLAIMER}. Quantitative values are validated only for the "
        "implemented DICOM BQML/START SUVbw path.",
        measured=EvidenceMeasured(
            suv_status="PASS" if result else "REFUSED",
            suv_volume_stats=result.suv_stats if result else None,
            lesions=lesions,
            lesion_summary=summarize(lesions) if lesions else None,
        ),
        provenance=prov,
        quantitative_inputs=src.inputs,
        scale_factors=result.scale if result else None,
        refusal_reasons=refusal.reasons if refusal else [],
        warnings=all_warnings,
    )
    return QuantRun(case, uid, outcome, seg, masks, lesions, evidence, warnings)


# --------------------------------------------------------------------------------------
# Output files
# --------------------------------------------------------------------------------------


def input_audit(run: QuantRun) -> dict[str, Any]:
    """Machine-readable audit of every PET field inspected. No patient identifiers."""
    assert run.outcome is not None
    audit = run.outcome.audit
    src = run.outcome.result or run.outcome.refusal
    assert src is not None
    per_slice = []
    for k, h in enumerate(audit.headers):
        per_slice.append(
            {
                "k": k,
                "sop_instance_uid": str(_get(h, "SOPInstanceUID")),
                **{
                    kw: (None if _get(h, kw) is None else str(_get(h, kw)))
                    for kw in (
                        "AcquisitionDate",
                        "AcquisitionTime",
                        "AcquisitionDateTime",
                        "FrameReferenceTime",
                        "DecayFactor",
                        "ActualFrameDuration",
                        "RescaleSlope",
                        "RescaleIntercept",
                    )
                },
            }
        )
    return {
        "schema": "voxeltrace.suv-input-audit/1",
        "pet_series_uid": run.pet_series_uid,
        "subject_pseudonym": src.provenance.subject_pseudonym,
        "dataset": src.provenance.dataset,
        "supported_path": src.validation.supported_path,
        "eligible": src.validation.eligible,
        "fields": [f.model_dump() for f in audit.fields.values()],
        "checks": [c.model_dump() for c in src.validation.checks],
        "refusal_reasons": [r.model_dump() for r in src.validation.reasons],
        "warnings": [w.model_dump() for w in src.validation.warnings],
        "timing": {
            "series_datetime": src.inputs.series_datetime,
            "earliest_acquisition_datetime": src.inputs.earliest_acquisition_datetime,
            "scan_reference_datetime": src.inputs.scan_reference_datetime,
            "scan_reference_datetime_source": src.inputs.scan_reference_datetime_source,
            "injection_datetime": src.inputs.injection_datetime,
            "injection_datetime_source": src.inputs.injection_datetime_source,
            "decay_interval_s": src.inputs.decay_interval_s,
        },
        "per_slice": per_slice,
        "identifiers_excluded": [
            "PatientName",
            "PatientID",
            "PatientBirthDate",
            "PatientSex",
            "PatientAge",
            "OtherPatientIDs",
            "AccessionNumber",
        ],
    }


def summary_text(run: QuantRun) -> str:
    ev = run.evidence
    lines = [
        "VOXELTRACE QUANTITATIVE SUMMARY",
        voxeltrace.DISCLAIMER,
        f"subject: {ev.provenance.subject_pseudonym}  dataset: {ev.provenance.dataset}",
        f"PET series: {ev.provenance.pet_series_uid}",
        f"SEG series: {ev.provenance.seg_series_uid}",
        f"calculation: {ev.provenance.calculation} ({ev.provenance.calculation_version}), "
        f"voxeltrace {ev.provenance.voxeltrace_version}, git {ev.provenance.git_commit}"
        f"{' (dirty)' if ev.provenance.git_dirty else ''}",
        "",
        f"SUV ELIGIBILITY: {ev.measured.suv_status}",
    ]
    for r in ev.refusal_reasons:
        lines.append(f"  REFUSED {r.code}: {r.message}")
    q = ev.quantitative_inputs
    lines += [
        f"  Units={q.units} DecayCorrection={q.decay_correction} "
        f"CorrectedImage={q.corrected_image}",
        f"  weight={q.patient_weight_kg} kg  dose={q.radionuclide_total_dose_bq} Bq  "
        f"T½={q.radionuclide_half_life_s} s",
        f"  injection={q.injection_datetime}  [{q.injection_datetime_source}]",
        f"  scan reference={q.scan_reference_datetime}  [{q.scan_reference_datetime_source}]",
        f"  Δt={q.decay_interval_s} s",
    ]
    if ev.scale_factors:
        s = ev.scale_factors
        lines += [
            f"  dose decay factor={s.dose_decay_factor:.8f}  decayed dose="
            f"{s.decayed_dose_bq:.6e} Bq  SUV per Bq/mL={s.suv_per_bqml:.8e} g/Bq"
        ]
    if ev.measured.suv_volume_stats:
        st = ev.measured.suv_volume_stats
        lines.append(
            f"  SUV volume: min={st.finite_min:.4f} max={st.finite_max:.4f} "
            f"mean={st.finite_mean:.4f} p99={st.p99:.4f} (g/mL)"
        )
    lines += ["", "LESIONS (supplied segmentation; MTV = mask volume; TLG = MTV × SUVmean)"]
    if not ev.measured.lesions:
        lines.append("  none computed")
    for les in ev.measured.lesions:
        pk = les.suv_peak
        if les.voxel_count == 0:
            lines.append(f"  segment {les.segment_number} '{les.segment_label}': EMPTY")
            continue
        lines.append(
            f"  segment {les.segment_number} '{les.segment_label}': voxels={les.voxel_count} "
            f"MTV={les.mtv_ml:.3f} mL SUVmax={les.suv_max:.3f} SUVmean={les.suv_mean:.3f} "
            f"SUVmedian={les.suv_median:.3f} SD={les.suv_std:.3f} TLG={les.tlg:.3f} g "
            f"components={les.n_components}"
        )
        if pk:
            lines.append(
                f"    SUVpeak[{pk.status}]={pk.value if pk.value is None else round(pk.value, 3)}"
                f" (1.0 cm³ sphere, r={pk.radius_mm:.4f} mm, {pk.kernel_voxel_count} "
                f"voxels = {pk.kernel_effective_volume_ml:.4f} mL)"
            )
    lines += ["", "WARNINGS"]
    lines += [f"  {w.severity.upper()} {w.code}: {w.message}" for w in ev.warnings] or ["  none"]
    lines += ["", "NOT ESTABLISHED: " + ", ".join(ev.not_established)]
    return "\n".join(lines) + "\n"


def write_outputs(run: QuantRun, out_dir: str | Path) -> list[Path]:
    """Write audit/result-or-refusal/lesions/evidence/summary. Removes a stale counterpart."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    assert run.outcome is not None
    written = []

    def dump(name: str, payload: Any) -> None:
        p = out / name
        p.write_text(json.dumps(payload, indent=2, default=str) + "\n")
        written.append(p)

    dump("suv_input_audit.json", input_audit(run))
    if run.outcome.result:
        dump("suv_result.json", run.outcome.result.model_dump(mode="json"))
        (out / "suv_refusal.json").unlink(missing_ok=True)
    else:
        assert run.outcome.refusal is not None
        dump("suv_refusal.json", run.outcome.refusal.model_dump(mode="json"))
        (out / "suv_result.json").unlink(missing_ok=True)
    dump(
        "lesion_metrics.json",
        {
            "status": "COMPUTED" if run.lesions else "NOT_COMPUTED",
            "seg_series_uid": run.seg.series_uid if run.seg else None,
            "definitions": {
                "MTV": "volume of the supplied segment mask (voxel count × voxel volume), mL",
                "TLG": "MTV [mL] × SUVmean [g/mL] = g; based on the supplied segmentation",
                "SUVpeak": "see suv_peak.definition",
            },
            "lesions": [x.model_dump(mode="json") for x in run.lesions],
            "summary": summarize(run.lesions).model_dump() if run.lesions else None,
            "warnings": [w.model_dump() for w in run.warnings],
        },
    )
    dump("evidence.json", run.evidence.model_dump(mode="json"))
    p = out / "quantitative_summary.txt"
    p.write_text(summary_text(run))
    written.append(p)
    return written
