"""Build a GroundTruthCase from a validated quantification run (no model involvement).

Spatial lesion facts (centroid, bbox, SUVmax voxel, slices) are recomputed from the supplied
mask and the strict SUV array, and cross-checked against the Milestone 3 lesion metrics; any
disagreement raises (a quantitative inconsistency is a stop condition, never patched).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import SimpleITK as sitk

from voxeltrace.evidence.claims import ClaimEvidence
from voxeltrace.evidence.protocol import ProtocolEvidence, iter_fields
from voxeltrace.quant.evidence import QuantRun
from voxeltrace.schemas import EvidenceField, ImageGeometry
from voxeltrace.training.schema import (
    ClaimGroundTruth,
    GroundTruthCase,
    GroundTruthComponent,
    GroundTruthLesion,
    GTValue,
    ProtocolGroundTruth,
    QuantitativeGroundTruth,
    gt,
)
from voxeltrace.visualization.render import voxel_to_patient

PSEUDONYM_SALT = "voxeltrace-pseudonym-v1"


class GroundTruthInconsistency(RuntimeError):
    """Recomputed spatial facts disagree with validated metrics (stop condition)."""


def pseudonym(uid: str | None, prefix: str) -> str:
    if not uid:
        return f"{prefix}_none"
    return f"{prefix}_" + hashlib.sha256(f"{PSEUDONYM_SALT}:{uid}".encode()).hexdigest()[:16]


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class CaseArrays:
    """In-memory arrays for rendering (never exported as-is)."""

    suv: np.ndarray
    geometry: ImageGeometry
    masks: dict[int, np.ndarray]
    ct_on_pet: np.ndarray | None


def _d(value: Any, ref: str, derivation: str = "lesion_metric", unit: str | None = None) -> GTValue:
    return gt(value, "DETERMINISTIC_DERIVATION", ref, derivation, "VALIDATED", unit)  # type: ignore[arg-type]


def protocol_gt(p: ProtocolEvidence) -> ProtocolGroundTruth:
    out: dict[str, GTValue] = {}
    for cat, name, f in iter_fields(p):
        if name == "frame_of_reference_uid" and f.value is not None:  # never export raw UIDs
            f = f.model_copy(update={"value": pseudonym(str(f.value), "for")})
        out[f"{cat}.{name}"] = field_to_gt(f, f"protocol.{cat}.{name}")
    return ProtocolGroundTruth(fields=out)


def field_to_gt(f: EvidenceField, ref: str) -> GTValue:
    src = f"{ref} [{f.source}]"
    if f.status == "MISSING":
        return gt(
            None, "PRIMARY_DICOM_METADATA", src, "dicom_attribute", "VALIDATED_ABSENT", f.unit
        )
    if f.status in ("PRESENT_BUT_AMBIGUOUS", "UNSUPPORTED"):
        return gt(
            f.value,
            "DETERMINISTIC_DERIVATION",
            src,
            "dicom_free_text_pattern" if f.derivation == "free_text_pattern" else "dicom_attribute",
            "UNVALIDATED",
            f.unit,
        )
    if f.derivation == "free_text_pattern":
        return gt(
            f.value,
            "DETERMINISTIC_DERIVATION",
            src,
            "dicom_free_text_pattern",
            "UNVALIDATED",
            f.unit,
        )
    if f.derivation in ("standard_tag", "standard_enumeration"):
        return gt(f.value, "PRIMARY_DICOM_METADATA", src, "dicom_attribute", "VALIDATED", f.unit)
    if f.derivation == "derived_from_geometry":
        return _d(f.value, src, "geometry_transform", f.unit)
    if f.derivation == "validated_suv_input":
        return _d(f.value, src, "suv_strict", f.unit)
    return gt(f.value, "DETERMINISTIC_DERIVATION", src, "dicom_attribute", "UNVALIDATED", f.unit)


def claims_gt(claims: list[ClaimEvidence]) -> list[ClaimGroundTruth]:
    return [
        ClaimGroundTruth(
            claim_id=c.claim_id,
            claim_type=c.claim_type,
            statement=c.statement,
            status=gt(c.status, "RULE_DERIVATION", f"claims-1:{c.claim_id}", "rule_engine"),
            rule=c.rule,
        )
        for c in claims
    ]


def _components(
    mask: np.ndarray, suv: np.ndarray, voxel_ml: float, ref: str
) -> list[GroundTruthComponent]:
    labels = sitk.GetArrayFromImage(
        sitk.ConnectedComponent(sitk.GetImageFromArray(mask.astype(np.uint8)), True)
    )
    comps = []
    for lab in range(1, int(labels.max()) + 1):
        idx = np.argwhere(labels == lab)
        comps.append((len(idx), lab, idx))
    comps.sort(key=lambda c: (-c[0], tuple(c[2][0])))  # size desc, then position (stable)
    out = []
    for n, (count, _, idx) in enumerate(comps, start=1):
        vals = suv[tuple(idx.T)]
        out.append(
            GroundTruthComponent(
                component_index=n,
                voxel_count=_d(count, f"{ref}.components[{n}]", "connected_components"),
                volume_ml=_d(
                    count * voxel_ml, f"{ref}.components[{n}]", "connected_components", "mL"
                ),
                suv_max=_d(
                    float(vals.max()), f"{ref}.components[{n}]", "connected_components", "g/mL"
                ),
                centroid_kji=_d(
                    [float(v) for v in idx.mean(axis=0)],
                    f"{ref}.components[{n}]",
                    "geometry_transform",
                ),
                bbox_kji=_d(
                    [idx.min(axis=0).tolist(), idx.max(axis=0).tolist()],
                    f"{ref}.components[{n}]",
                    "geometry_transform",
                ),
                slices_k=_d(
                    sorted({int(k) for k in idx[:, 0]}),
                    f"{ref}.components[{n}]",
                    "geometry_transform",
                ),
                zero_suv_voxels=_d(
                    int((vals == 0).sum()), f"{ref}.components[{n}]", "connected_components"
                ),
            )
        )
    return out


def build_ground_truth(
    run: QuantRun,
    protocol: ProtocolEvidence,
    claims: list[ClaimEvidence],
    *,
    dataset: str,
    license: str,
    citation: str | None,
    ct_on_pet: np.ndarray | None = None,
    evidence_files: dict[str, str] | None = None,
    provenance: dict[str, Any] | None = None,
) -> tuple[GroundTruthCase, CaseArrays]:
    if not run.passed or run.outcome is None or run.outcome.suv is None:
        raise ValueError("ground truth requires a PASSed strict SUV run")
    assert run.outcome.activity is not None and run.outcome.result is not None
    suv = run.outcome.suv
    g = run.outcome.activity.geometry
    ev = run.evidence
    masks = run.seg_masks or {}
    voxel_ml = float(np.prod([v for v in g.spacing_ijk if v is not None])) / 1000.0
    lesions: list[GroundTruthLesion] = []
    for li, les in enumerate(ev.measured.lesions):
        m = masks.get(les.segment_number)
        ref = f"evidence.measured.lesions[{li}]"
        if m is None or les.voxel_count == 0:
            continue
        idx = np.argwhere(m)
        if len(idx) != les.voxel_count:
            raise GroundTruthInconsistency("mask voxel count != validated voxel count")
        vals = suv[tuple(idx.T)]
        amax = idx[int(np.argmax(vals))]  # first in C order on ties
        if float(vals.max()) != les.suv_max or float(vals.mean()) != les.suv_mean:
            raise GroundTruthInconsistency("recomputed SUVmax/SUVmean differ from evidence")
        cen = idx.mean(axis=0)
        per_slice: dict[int, int] = {}
        zero_slice: dict[int, int] = {}
        for (k, _, _), v in zip(idx, vals, strict=True):
            per_slice[int(k)] = per_slice.get(int(k), 0) + 1
            if v == 0:
                zero_slice[int(k)] = zero_slice.get(int(k), 0) + 1
        pk = les.suv_peak
        pk_ok = pk is not None and pk.status == "COMPUTED"
        comps = _components(m, suv, voxel_ml, ref)
        if [c.voxel_count.value for c in comps] != [c.voxel_count for c in les.components]:
            raise GroundTruthInconsistency("component sizes differ from validated metrics")
        lid = f"seg{les.segment_number}"
        lesions.append(
            GroundTruthLesion(
                lesion_id=lid,
                segment_number=gt(
                    les.segment_number,
                    "REFERENCE_SEGMENTATION",
                    f"{ref}.segment_number",
                    "segmentation_decode",
                ),
                segment_label=gt(
                    les.segment_label,
                    "REFERENCE_SEGMENTATION",
                    f"{ref}.segment_label",
                    "segmentation_decode",
                ),
                voxel_count=_d(les.voxel_count, f"{ref}.voxel_count"),
                mtv_ml=_d(les.mtv_ml, f"{ref}.mtv_ml", unit="mL"),
                suv_max=_d(les.suv_max, f"{ref}.suv_max", unit="g/mL"),
                suv_mean=_d(les.suv_mean, f"{ref}.suv_mean", unit="g/mL"),
                suv_median=_d(les.suv_median, f"{ref}.suv_median", unit="g/mL"),
                suv_peak=_d(pk.value if pk_ok else None, f"{ref}.suv_peak.value", unit="g/mL")
                if pk_ok
                else gt(
                    None,
                    "DETERMINISTIC_DERIVATION",
                    f"{ref}.suv_peak.status",
                    "lesion_metric",
                    "VALIDATED_ABSENT",
                    "g/mL",
                ),
                tlg=_d(les.tlg, f"{ref}.tlg", unit="g"),
                centroid_kji=_d([float(v) for v in cen], ref, "geometry_transform"),
                centroid_patient_mm=_d(
                    list(voxel_to_patient(g, tuple(cen))), ref, "geometry_transform", "mm"
                ),
                bbox_kji=_d(
                    [idx.min(axis=0).tolist(), idx.max(axis=0).tolist()], ref, "geometry_transform"
                ),
                suvmax_voxel_kji=_d([int(v) for v in amax], f"{ref}.suv_max", "geometry_transform"),
                suvmax_patient_mm=_d(
                    list(voxel_to_patient(g, tuple(float(v) for v in amax))),
                    f"{ref}.suv_max",
                    "geometry_transform",
                    "mm",
                ),
                suvpeak_center_kji=_d(
                    list(pk.center_kji) if pk_ok else None,
                    f"{ref}.suv_peak.center_kji",
                    "geometry_transform",
                ),
                suvpeak_center_patient_mm=_d(
                    list(pk.center_patient_mm) if pk_ok and pk.center_patient_mm else None,
                    f"{ref}.suv_peak.center_patient_mm",
                    "geometry_transform",
                    "mm",
                ),
                slices_k=_d(sorted(per_slice), ref, "geometry_transform"),
                voxels_per_slice=_d(
                    {str(k): v for k, v in sorted(per_slice.items())}, ref, "geometry_transform"
                ),
                zero_suv_voxels_per_slice=_d(
                    {str(k): v for k, v in sorted(zero_slice.items())}, ref, "lesion_metric"
                ),
                components=comps,
            )
        )
    res = run.outcome.result
    quant = QuantitativeGroundTruth(
        suv_status=gt("PASS", "RULE_DERIVATION", "evidence.measured.suv_status", "suv_strict"),
        suv_per_bqml=_d(
            res.scale.suv_per_bqml, "suv_result.scale.suv_per_bqml", "suv_strict", "g/Bq"
        ),
        decay_interval_s=_d(
            res.scale.decay_interval_s, "suv_result.scale.decay_interval_s", "suv_strict", "s"
        ),
        suv_volume_max=_d(
            res.suv_stats.finite_max, "suv_result.suv_stats.finite_max", "suv_strict", "g/mL"
        ),
        lesions=lesions,
    )
    series = run.case.get_series(run.pet_series_uid or "")
    case = GroundTruthCase(
        case_id=ev.provenance.subject_pseudonym or pseudonym(run.pet_series_uid, "case"),
        dataset=dataset,
        license=license,
        citation=citation,
        subject_pseudonym=ev.provenance.subject_pseudonym or "unknown",
        study_pseudonym=pseudonym(series.study_uid, "study"),
        pet_series_pseudonym=pseudonym(run.pet_series_uid, "pet"),
        seg_series_pseudonym=pseudonym(run.seg.series_uid if run.seg else None, "seg"),
        geometry=_d(
            {
                "shape_ijk": list(g.shape_ijk),
                "spacing_ijk_mm": list(g.spacing_ijk),
                "orientation": "standard axial (LPS)",
            },
            "suv_result geometry",
            "geometry_transform",
        ),
        quantitative=quant,
        protocol=protocol_gt(protocol),
        claims=claims_gt(claims),
        evidence_sha256={k: sha256_file(v) for k, v in (evidence_files or {}).items()},
        provenance=provenance or {},
    )
    return case, CaseArrays(suv=suv, geometry=g, masks=masks, ct_on_pet=ct_on_pet)
