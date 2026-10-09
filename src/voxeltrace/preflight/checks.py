"""Preflight checks on the headers of ONE series (no pixel data, no SUV computation)."""

from __future__ import annotations

from collections.abc import Sequence

from pydicom.dataset import Dataset

from voxeltrace.census.sampled import predict_pet
from voxeltrace.preflight.reasons import spec
from voxeltrace.preflight.schema import PreflightFinding
from voxeltrace.trial.anonymization import audit_anonymization
from voxeltrace.vendors import parser_for

SECONDARY_CAPTURE_SOPS = {
    "1.2.840.10008.5.1.4.1.1.7",  # Secondary Capture Image Storage
    "1.2.840.10008.5.1.4.1.1.7.1",
    "1.2.840.10008.5.1.4.1.1.7.2",
    "1.2.840.10008.5.1.4.1.1.7.3",
    "1.2.840.10008.5.1.4.1.1.7.4",
}
RECON_FIELDS = (
    "reconstruction_method",
    "iterations",
    "subsets",
    "convolution_kernel",
    "time_of_flight",
    "psf_resolution_modelling",
)
# quantitative attributes whose loss in de-identification matters for preflight
ANON_FIELDS = {
    "PatientWeight", "PatientSize", "PatientSex", "RadiopharmaceuticalStartTime",
    "RadiopharmaceuticalStartDateTime", "RadionuclideTotalDose", "SeriesTime",
    "AcquisitionTime", "Manufacturer", "ManufacturerModelName", "SoftwareVersions",
}  # fmt: skip


def finding(code: str, evidence: str, source: str, *, refusal: bool | None = None, **over):
    s = spec(code, refusal=refusal)
    return PreflightFinding(
        reason_code=code,
        severity=over.get("severity", s.severity),
        field=over.get("field", s.field),
        evidence=evidence,
        remediation=s.remediation,
        recoverable=s.recoverable,  # type: ignore[arg-type]
        source=source,
    )


def _str(v) -> str:
    return "" if v is None else str(v).strip()


def pet_checks(series_uid: str, headers: Sequence[Dataset]) -> tuple[list[PreflightFinding], dict]:
    """All PET checks. Returns (findings, facts)."""
    h0 = headers[0]
    out: list[PreflightFinding] = []
    # --- object / processing state
    sop = _str(h0.get("SOPClassUID"))
    itype = [str(x).upper() for x in (h0.get("ImageType") or [])]
    if sop in SECONDARY_CAPTURE_SOPS:
        out.append(finding("SECONDARY_CAPTURE", f"SOPClassUID {sop}", "object"))
    if "DERIVED" in itype or "SECONDARY" in itype:
        out.append(finding("DERIVED_IMAGE", "ImageType " + "\\".join(itype), "object"))
    # --- strict input validator + protocol extractors (unchanged code; no SUV computed)
    p = predict_pet(series_uid, headers)
    val = p["validation"]
    for r in val.reasons:
        out.append(finding(r.code, r.message, "strict SUV input validator", refusal=True))
    for w in val.warnings:
        if w.code in ("NEGATIVE_SUV", "NONFINITE_SUV", "GEOMETRY"):
            continue  # pixel-level warnings: not decidable from headers
        out.append(finding(w.code, w.message, "strict SUV input validator", refusal=False))
    proto = p["protocol"]
    # --- SUL anthropometrics
    if not p["height_present"]:
        out.append(finding("MISSING_PATIENTSIZE", "PatientSize absent or empty", "anthropometrics"))
    sex = _str(h0.get("PatientSex")).upper()
    if sex not in ("M", "F"):
        out.append(
            finding(
                "UNSUPPORTED_PATIENTSEX_FOR_SUL",
                f"PatientSex {sex or '(absent)'!r}",
                "anthropometrics",
            )
        )
    # --- tracer
    acq = proto.acquisition
    if not (acq.tracer.known or acq.radiopharmaceutical_code.known):
        out.append(finding("TRACER_UNKNOWN", "no radiopharmaceutical name or code", "acquisition"))
    # --- scanner / software / vendor coverage
    sc = proto.scanner
    if not (sc.manufacturer.known and sc.manufacturer_model_name.known):
        out.append(finding("SCANNER_UNKNOWN", "manufacturer or model missing", "scanner"))
    if not sc.software_versions.known:
        out.append(finding("SOFTWARE_UNKNOWN", "SoftwareVersions missing", "scanner"))
    manu = _str(h0.get("Manufacturer"))
    if manu and parser_for(manu) is None:
        out.append(finding("NO_VENDOR_PRIVATE_PARSER", f"Manufacturer {manu!r}", "vendor coverage"))
    # --- reconstruction completeness (affects comparability, not quantification)
    rc = proto.reconstruction
    missing = [f for f in RECON_FIELDS if not getattr(rc, f).known]
    if missing:
        out.append(
            finding("RECONSTRUCTION_INCOMPLETE", f"missing: {', '.join(missing)}", "reconstruction")
        )
    # --- de-identification loss of quantitative / device attributes
    anon = audit_anonymization(headers)
    lost = [
        f"{fa.field}={fa.presence}" + (f" ({fa.reason.code})" if fa.reason else "")
        for fa in anon.fields
        if fa.field in ANON_FIELDS
        and fa.presence in ("EMPTY", "ABSENT")
        and fa.reason is not None
        and fa.reason.code in ("STRIPPED_BY_ANONYMIZATION", "UNKNOWN_OR_STRIPPED")
    ]
    if lost:
        out.append(finding("ANONYMIZATION_LOSS", "; ".join(lost), "de-identification audit"))
    facts = {
        "manufacturer": sc.manufacturer.value,
        "model": sc.manufacturer_model_name.value,
        "software": sc.software_versions.value,
        "units": _str(h0.get("Units")),
        "decay_correction": _str(h0.get("DecayCorrection")),
        "corrected_image": [str(x) for x in (h0.get("CorrectedImage") or [])],
        "tracer": acq.tracer.value,
        "weight_present": p["weight_present"],
        "height_present": p["height_present"],
        "patient_sex_supported_for_sul": sex in ("M", "F"),
        "frame_reference_time_present": all(
            h.get("FrameReferenceTime") is not None for h in headers
        ),
        "decay_factor_present": all(h.get("DecayFactor") is not None for h in headers),
        "multi_bed_detected": p["multi_bed_detected"],
        "frame_of_reference": _str(h0.get("FrameOfReferenceUID")) and "present",
        "reconstruction_missing": missing,
        "deidentification_declared": anon.deidentification_declared,
        "validator_eligible": val.eligible,
    }
    return out, facts
