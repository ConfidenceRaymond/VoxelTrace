"""Protocol comparability between two PET scans. Says nothing about biology.

Each check compares one protocol attribute and is classified by impact:
  blocking: a difference makes quantitative comparison unsupported (NOT_COMPARABLE), and an
            unknown value makes it INSUFFICIENT_INFORMATION;
  warning:  a difference or unknown value gives COMPARABLE_WITH_WARNINGS;
  info:     reported only.

Tolerances (VoxelTrace defaults, documented in docs/comparability.md):
  uptake interval ±10 min (QIBA FDG-PET/CT Profile: follow-up uptake within 10 min of
  baseline); voxel size ±0.01 mm per axis; injected activity ±20 % (warning only; activity
  changes noise, not SUV calibration); frame/bed duration ±1 %.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from voxeltrace.evidence.protocol import ProtocolEvidence
from voxeltrace.schemas import EvidenceField

Impact = Literal["blocking", "warning", "info"]
Result = Literal["SAME", "WITHIN_TOLERANCE", "DIFFERENT", "UNKNOWN"]
Category = Literal[
    "COMPARABLE", "COMPARABLE_WITH_WARNINGS", "NOT_COMPARABLE", "INSUFFICIENT_INFORMATION"
]

UPTAKE_TOLERANCE_S = 600.0
VOXEL_TOLERANCE_MM = 0.01
ACTIVITY_REL_TOLERANCE = 0.20
DURATION_REL_TOLERANCE = 0.01
CORRECTIONS_COMPARED = ("attenuation", "scatter", "randoms", "decay", "normalization", "dead_time")


class ComparisonCheck(BaseModel):
    name: str
    impact: Impact
    result: Result
    value_a: Any = None
    value_b: Any = None
    difference: Any = None
    tolerance: str | None = None
    message: str


class ComparabilityAssessment(BaseModel):
    series_a: str
    series_b: str
    category: Category
    checks: list[ComparisonCheck]
    blocking_differences: list[str] = Field(default_factory=list)
    blocking_unknowns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    statement: str
    scope_note: str = (
        "This assesses protocol comparability only. It does not establish biological change, "
        "treatment response or any clinical conclusion."
    )


def _norm(v: Any) -> Any:
    if isinstance(v, str):
        return " ".join(v.split()).casefold()
    if isinstance(v, list):
        return [_norm(x) for x in v]
    return v


def _exact(
    name: str,
    a: EvidenceField,
    b: EvidenceField,
    impact: Impact,
    fallback_same: bool = False,
    unknown_impact: Impact | None = None,
) -> ComparisonCheck:
    if a.known and b.known:
        same = _norm(a.value) == _norm(b.value)
        return ComparisonCheck(
            name=name,
            impact=impact,
            result="SAME" if same else "DIFFERENT",
            value_a=a.value,
            value_b=b.value,
            message=f"{name} {'identical' if same else 'differs'}",
        )
    if fallback_same:
        return ComparisonCheck(
            name=name,
            impact=impact,
            result="SAME",
            value_a=a.value,
            value_b=b.value,
            message=f"{name} not stated separately, but "
            "the ReconstructionMethod text is identical on both scans",
        )
    return ComparisonCheck(
        name=name,
        impact=unknown_impact or impact,
        result="UNKNOWN",
        value_a=a.value,
        value_b=b.value,
        message=f"{name} unknown on "
        + ("both scans" if not a.known and not b.known else "scan A" if not a.known else "scan B"),
    )


def _numeric(
    name: str,
    a: EvidenceField,
    b: EvidenceField,
    impact: Impact,
    *,
    abs_tol: float | None = None,
    rel_tol: float | None = None,
    tol_text: str,
) -> ComparisonCheck:
    if not (a.known and b.known):
        return _exact(name, a, b, impact)
    va, vb = float(a.value), float(b.value)  # type: ignore[arg-type]
    diff = vb - va
    ok = (
        (abs(diff) <= abs_tol)
        if abs_tol is not None
        else (abs(diff) <= rel_tol * max(abs(va), 1e-300))
    )  # type: ignore[operator]
    result: Result = "SAME" if diff == 0 else ("WITHIN_TOLERANCE" if ok else "DIFFERENT")
    return ComparisonCheck(
        name=name,
        impact=impact,
        result=result,
        value_a=va,
        value_b=vb,
        difference=diff,
        tolerance=tol_text,
        message=f"{name}: B − A = {diff:.6g}"
        + (f" (rel {diff / va:+.1%})" if rel_tol is not None and va else ""),
    )


def _voxels(a: EvidenceField, b: EvidenceField) -> ComparisonCheck:
    if not (a.known and b.known):
        return _exact("voxel_size", a, b, "blocking")
    va, vb = list(a.value), list(b.value)  # type: ignore[arg-type]
    diff = [y - x for x, y in zip(va, vb, strict=True)]
    ok = all(abs(d) <= VOXEL_TOLERANCE_MM for d in diff)
    return ComparisonCheck(
        name="voxel_size",
        impact="blocking",
        result=("SAME" if not any(diff) else "WITHIN_TOLERANCE") if ok else "DIFFERENT",
        value_a=va,
        value_b=vb,
        difference=diff,
        tolerance=f"±{VOXEL_TOLERANCE_MM} mm per axis",
        message="voxel size (i, j, k) " + ("matches" if ok else "differs"),
    )


def _corrections(pa: ProtocolEvidence, pb: ProtocolEvidence) -> ComparisonCheck:
    sa, sb = pa.corrections.applied_set(), pb.corrections.applied_set()
    if sa is None or sb is None:
        return ComparisonCheck(
            name="correction_state",
            impact="blocking",
            result="UNKNOWN",
            message="CorrectedImage unknown on at least one scan",
        )
    ka = sorted(sa & set(CORRECTIONS_COMPARED))
    kb = sorted(sb & set(CORRECTIONS_COMPARED))
    return ComparisonCheck(
        name="correction_state",
        impact="blocking",
        result="SAME" if ka == kb else "DIFFERENT",
        value_a=ka,
        value_b=kb,
        difference=sorted(set(ka) ^ set(kb)) or None,
        message="applied corrections " + ("identical" if ka == kb else "differ"),
    )


def compare_protocols(pa: ProtocolEvidence, pb: ProtocolEvidence) -> ComparabilityAssessment:
    ra, rb = pa.reconstruction, pb.reconstruction
    aa, ab = pa.acquisition, pb.acquisition
    same_text = (
        ra.reconstruction_method.known
        and rb.reconstruction_method.known
        and _norm(ra.reconstruction_method.value) == _norm(rb.reconstruction_method.value)
    )
    tracer_a = aa.radiopharmaceutical_code if aa.radiopharmaceutical_code.known else aa.tracer
    tracer_b = ab.radiopharmaceutical_code if ab.radiopharmaceutical_code.known else ab.tracer
    checks = [
        _exact("tracer", tracer_a, tracer_b, "blocking"),
        _exact("radionuclide", aa.radionuclide, ab.radionuclide, "blocking"),
        _exact("manufacturer", pa.scanner.manufacturer, pb.scanner.manufacturer, "blocking"),
        _exact(
            "scanner_model",
            pa.scanner.manufacturer_model_name,
            pb.scanner.manufacturer_model_name,
            "blocking",
        ),
        _exact(
            "software_version",
            pa.scanner.software_versions,
            pb.scanner.software_versions,
            "warning",
        ),
        _exact("image_units", aa.image_units, ab.image_units, "blocking"),
        _exact("decay_correction", aa.decay_correction, ab.decay_correction, "blocking"),
        _corrections(pa, pb),
        _numeric(
            "uptake_interval",
            aa.uptake_interval_s,
            ab.uptake_interval_s,
            "blocking",
            abs_tol=UPTAKE_TOLERANCE_S,
            tol_text="±600 s (QIBA ±10 min)",
        ),
        _numeric(
            "injected_activity",
            aa.injected_activity_bq,
            ab.injected_activity_bq,
            "warning",
            rel_tol=ACTIVITY_REL_TOLERANCE,
            tol_text="±20 % relative",
        ),
        _numeric(
            "frame_duration",
            aa.frame_duration_ms,
            ab.frame_duration_ms,
            "warning",
            rel_tol=DURATION_REL_TOLERANCE,
            tol_text="±1 % relative",
        ),
        _voxels(ra.voxel_size_mm, rb.voxel_size_mm),
        _exact("matrix_rows", ra.matrix_rows, rb.matrix_rows, "info"),
        _exact("matrix_columns", ra.matrix_columns, rb.matrix_columns, "info"),
        _exact("slice_thickness", ra.slice_thickness_mm, rb.slice_thickness_mm, "warning"),
        _exact(
            "reconstruction_method", ra.reconstruction_method, rb.reconstruction_method, "blocking"
        ),
        _exact(
            "iterations",
            ra.iterations,
            rb.iterations,
            "blocking",
            fallback_same=same_text,
            unknown_impact="warning",
        ),
        _exact(
            "subsets",
            ra.subsets,
            rb.subsets,
            "blocking",
            fallback_same=same_text,
            unknown_impact="warning",
        ),
        _exact(
            "time_of_flight",
            ra.time_of_flight,
            rb.time_of_flight,
            "blocking",
            fallback_same=same_text,
            unknown_impact="warning",
        ),
        _exact(
            "psf_resolution_modelling",
            ra.psf_resolution_modelling,
            rb.psf_resolution_modelling,
            "blocking",
            fallback_same=same_text,
            unknown_impact="warning",
        ),
        _exact(
            "post_filter",
            ra.convolution_kernel,
            rb.convolution_kernel,
            "blocking",
            unknown_impact="warning",
        ),
        _exact(
            "reconstruction_diameter",
            ra.reconstruction_diameter_mm,
            rb.reconstruction_diameter_mm,
            "info",
        ),
    ]
    blocking_diff = [c.name for c in checks if c.impact == "blocking" and c.result == "DIFFERENT"]
    blocking_unk = [c.name for c in checks if c.impact == "blocking" and c.result == "UNKNOWN"]
    warns = [
        c.name for c in checks if c.impact == "warning" and c.result in ("DIFFERENT", "UNKNOWN")
    ]
    if blocking_diff:
        cat: Category = "NOT_COMPARABLE"
        stmt = "Quantitative comparison NOT supported: " + ", ".join(blocking_diff) + " differ."
    elif blocking_unk:
        cat = "INSUFFICIENT_INFORMATION"
        stmt = "Comparability cannot be established: " + ", ".join(blocking_unk) + " unknown."
    elif warns:
        cat = "COMPARABLE_WITH_WARNINGS"
        stmt = "Protocols comparable on all blocking criteria; check: " + ", ".join(warns) + "."
    else:
        cat = "COMPARABLE"
        stmt = "Protocols comparable on all checked criteria."
    return ComparabilityAssessment(
        series_a=pa.series_uid,
        series_b=pb.series_uid,
        category=cat,
        checks=checks,
        blocking_differences=blocking_diff,
        blocking_unknowns=blocking_unk,
        warnings=warns,
        statement=stmt,
    )
