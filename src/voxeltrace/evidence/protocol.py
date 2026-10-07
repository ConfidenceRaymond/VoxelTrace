"""Protocol bundle (scanner + acquisition + reconstruction + corrections) and protocol QC.

QC never fails a whole case. Each gap is mapped to the downstream uses it blocks
(``suv``, ``lesion_metrics``, ``cross_scan_comparison``); everything else is informational.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field

from voxeltrace.evidence._dicom import read_headers
from voxeltrace.evidence.acquisition import AcquisitionProtocol, extract_acquisition
from voxeltrace.evidence.corrections import CorrectionEvidence, extract_corrections
from voxeltrace.evidence.reconstruction import ReconstructionProtocol, extract_reconstruction
from voxeltrace.evidence.scanner import ScannerEvidence, extract_scanner
from voxeltrace.ingest.dicom import series_geometry
from voxeltrace.schemas import EvidenceField, ImagingSeries, SUVInputs, SUVValidation

Downstream = Literal["suv", "lesion_metrics", "cross_scan_comparison"]

# QIBA FDG-PET/CT Profile: uptake 55–75 min after injection.
QIBA_UPTAKE_WINDOW_S = (55 * 60.0, 75 * 60.0)


class ProtocolEvidence(BaseModel):
    series_uid: str
    scanner: ScannerEvidence
    acquisition: AcquisitionProtocol
    reconstruction: ReconstructionProtocol
    corrections: CorrectionEvidence


class QCItem(BaseModel):
    code: str
    category: Literal["scanner", "acquisition", "reconstruction", "corrections"]
    field: str
    status: str
    severity: Literal["info", "warning", "error"]
    blocks: list[Downstream] = Field(default_factory=list)
    message: str


class ProtocolQC(BaseModel):
    series_uid: str
    items: list[QCItem]
    status_counts: dict[str, int]
    fields: dict[str, str] = Field(description="category.field -> status")
    usable_for: dict[str, bool]
    blocked_by: dict[str, list[str]]


def extract_protocol(
    series: ImagingSeries,
    suv_inputs: SUVInputs | None = None,
    suv_validation: SUVValidation | None = None,
) -> ProtocolEvidence:
    """Header-only extraction (no pixel data). SUV timing inputs are passed in, not recomputed,
    so protocol evidence and SUV share one validated timing source."""
    headers = read_headers(series)
    geometry, _ = series_geometry(series)
    uid = series.series_uid
    return ProtocolEvidence(
        series_uid=uid,
        scanner=extract_scanner(uid, headers),
        acquisition=extract_acquisition(uid, headers, geometry, suv_inputs, suv_validation),
        reconstruction=extract_reconstruction(uid, headers, geometry),
        corrections=extract_corrections(uid, headers),
    )


def iter_fields(p: ProtocolEvidence):
    for cat in ("scanner", "acquisition", "reconstruction", "corrections"):
        obj = getattr(p, cat)
        for name in type(obj).model_fields:
            v = getattr(obj, name)
            if isinstance(v, EvidenceField):
                yield cat, name, v
            elif isinstance(v, dict):
                for k, f in v.items():
                    if isinstance(f, EvidenceField):
                        yield cat, f"{name}.{k}", f


# (category, field, code, blocks, severity_if_missing)
_RULES: list[tuple[str, str, str, list[Downstream], str]] = [
    ("scanner", "manufacturer", "MISSING_MANUFACTURER", ["cross_scan_comparison"], "warning"),
    (
        "scanner",
        "manufacturer_model_name",
        "MISSING_SCANNER_MODEL",
        ["cross_scan_comparison"],
        "warning",
    ),
    ("scanner", "software_versions", "MISSING_SOFTWARE_VERSION", [], "info"),
    (
        "reconstruction",
        "reconstruction_method",
        "MISSING_RECONSTRUCTION_ALGORITHM",
        ["cross_scan_comparison"],
        "warning",
    ),
    (
        "reconstruction",
        "voxel_size_mm",
        "MISSING_VOXEL_SIZE",
        ["lesion_metrics", "cross_scan_comparison"],
        "error",
    ),
    ("reconstruction", "iterations", "MISSING_ITERATIONS", [], "info"),
    ("reconstruction", "subsets", "MISSING_SUBSETS", [], "info"),
    ("reconstruction", "time_of_flight", "MISSING_TOF_INFORMATION", [], "info"),
    ("reconstruction", "psf_resolution_modelling", "MISSING_PSF_INFORMATION", [], "info"),
    ("reconstruction", "convolution_kernel", "MISSING_FILTER", [], "info"),
    ("reconstruction", "reconstruction_diameter_mm", "MISSING_RECONSTRUCTION_DIAMETER", [], "info"),
    (
        "corrections",
        "corrected_image",
        "MISSING_CORRECTIONS",
        ["suv", "cross_scan_comparison"],
        "error",
    ),
    (
        "acquisition",
        "uptake_interval_s",
        "MISSING_UPTAKE_TIME",
        ["suv", "cross_scan_comparison"],
        "error",
    ),
    ("acquisition", "injected_activity_bq", "MISSING_DOSE", ["suv"], "error"),
    ("acquisition", "tracer", "MISSING_TRACER", ["cross_scan_comparison"], "warning"),
    ("acquisition", "frame_duration_ms", "MISSING_ACQUISITION_DURATION", [], "warning"),
    ("acquisition", "image_units", "MISSING_UNITS", ["suv"], "error"),
]


def assess_protocol_qc(p: ProtocolEvidence, suv_eligible: bool | None = None) -> ProtocolQC:
    items: list[QCItem] = []
    fields = {f"{c}.{n}": f.status for c, n, f in iter_fields(p)}
    for cat, name, code, blocks, sev in _RULES:
        f = getattr(getattr(p, cat), name)
        if f.status == "MISSING":
            items.append(
                QCItem(
                    code=code,
                    category=cat,
                    field=name,
                    status=f.status,  # type: ignore[arg-type]
                    severity=sev,
                    blocks=blocks,  # type: ignore[arg-type]
                    message=f"{name} missing" + (f" ({f.note})" if f.note else ""),
                )
            )
        elif f.status == "PRESENT_BUT_AMBIGUOUS":
            items.append(
                QCItem(
                    code=code.replace("MISSING_", "AMBIGUOUS_"),
                    category=cat,  # type: ignore[arg-type]
                    field=name,
                    status=f.status,
                    severity="warning",
                    blocks=[],
                    message=f"{name}: {f.note or 'ambiguous'}",
                )
            )
    ruled = {(c, n) for c, n, *_ in _RULES}
    for cat, name, f in iter_fields(p):
        if f.status == "PRESENT_BUT_AMBIGUOUS" and (cat, name) not in ruled:
            items.append(
                QCItem(
                    code=f"AMBIGUOUS_{name.upper().replace('.', '_')}",
                    category=cat,
                    field=name,
                    status=f.status,  # type: ignore[arg-type]
                    severity="warning",
                    message=f"{name}: {f.note or 'ambiguous'}",
                )
            )
        if f.derivation == "free_text_pattern" and f.status == "PRESENT":
            items.append(
                QCItem(
                    code="FREE_TEXT_DERIVED",
                    category=cat,
                    field=name,  # type: ignore[arg-type]
                    status=f.status,
                    severity="info",
                    message=f"{name} derived from vendor free text ({f.source})",
                )
            )
    rec = p.reconstruction
    if rec.unsupported_private_metadata:
        only_private = rec.reconstruction_method.status == "MISSING"
        items.append(
            QCItem(
                code="PRIVATE_RECONSTRUCTION_METADATA_UNSUPPORTED",
                category="reconstruction",
                field="unsupported_private_metadata",
                status="UNSUPPORTED",
                severity="warning" if only_private else "info",
                message=(
                    "reconstruction details may exist only in private tags (not parsed): "
                    if only_private
                    else "private creators present (not parsed): "
                )
                + ", ".join(rec.unsupported_private_metadata),
            )
        )
    up = p.acquisition.uptake_interval_s
    if up.known and not QIBA_UPTAKE_WINDOW_S[0] <= float(up.value) <= QIBA_UPTAKE_WINDOW_S[1]:  # type: ignore[arg-type]
        items.append(
            QCItem(
                code="UPTAKE_OUTSIDE_QIBA_WINDOW",
                category="acquisition",
                field="uptake_interval_s",
                status=up.status,
                severity="warning",
                message=f"uptake {float(up.value) / 60:.1f} min outside QIBA "  # type: ignore[arg-type]
                "55–75 min",
            )
        )
    blocked: dict[str, list[str]] = {"suv": [], "lesion_metrics": [], "cross_scan_comparison": []}
    for it in items:
        for b in it.blocks:
            blocked[b].append(it.field)
    if suv_eligible is False:
        blocked["suv"].append("strict SUV validator refused")
    if blocked["suv"]:
        blocked["lesion_metrics"].append("SUV not available")
    counts = Counter(fields.values())
    return ProtocolQC(
        series_uid=p.series_uid,
        items=items,
        status_counts={
            s: counts.get(s, 0)
            for s in ("PRESENT", "PRESENT_BUT_AMBIGUOUS", "MISSING", "UNSUPPORTED")
        },
        fields=fields,
        usable_for={k: not v for k, v in blocked.items()},
        blocked_by=blocked,
    )
