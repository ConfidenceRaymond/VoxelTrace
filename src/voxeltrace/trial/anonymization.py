"""Anonymization-loss audit: present vs absent quantitative/reconstruction attributes and what
the declared de-identification profile can (and cannot) tell us about WHY something is absent.

Verified basis (DICOM PS3.15, current edition):
  E.3.7  Retain Patient Characteristics Option: "information about age, sex, height and weight
         and other characteristics present in the Attributes shall be retained" (purpose:
         SUV-type metabolic measures).
  E.3.8  Retain Device Identity Option (device identifiers retained).
  E.3.10 Retain Safe Private Option: only private attributes "known by the de-identifier to be
         safe from identity leakage" are retained.
  E.3.5  Clean Descriptors Option: identifying text removed from descriptors (content may be
         modified, not necessarily removed).
Rules: never assert STRIPPED_BY_ANONYMIZATION unless an explicit removal marker is present;
absence covered by a declared retention option -> NEVER_ENCODED (PROBABLE); otherwise
UNKNOWN_OR_STRIPPED.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydicom.dataset import Dataset

from voxeltrace.ingest.dicom import _get
from voxeltrace.quant.dicom_time import DicomTimeError, combine_da_tm, parse_dt
from voxeltrace.trial.reasons import Reason
from voxeltrace.vendors import PrivateEvidence, parser_for

OPTION_MEANINGS = {
    "113100": ("Basic Application Confidentiality Profile", "E.2"),
    "113101": ("Clean Pixel Data Option", "E.3.1"),
    "113104": ("Clean Structured Content Option", "E.3.4"),
    "113105": ("Clean Descriptors Option", "E.3.5"),
    "113106": ("Retain Longitudinal Temporal Information Full Dates Option", "E.3.6"),
    "113107": ("Retain Longitudinal Temporal Information Modified Dates Option", "E.3.6"),
    "113108": ("Retain Patient Characteristics Option", "E.3.7"),
    "113109": ("Retain Device Identity Option", "E.3.8"),
    "113111": ("Retain Safe Private Option", "E.3.10"),
}
# attribute class -> (attributes, option code that retains the class)
CLASSES: dict[str, tuple[tuple[str, ...], str | None]] = {
    "patient_characteristics": (
        ("PatientSex", "PatientSize", "PatientWeight", "PatientAge"),
        "113108",
    ),
    "device_identity": (("DeviceSerialNumber", "StationName"), "113109"),
    "pet_quantitative": (
        (
            "Units",
            "DecayCorrection",
            "CorrectedImage",
            "RescaleSlope",
            "SeriesTime",
            "AcquisitionTime",
            "ActualFrameDuration",
            "FrameReferenceTime",
            "DecayFactor",
        ),
        None,
    ),
    "reconstruction": (
        (
            "ReconstructionMethod",
            "ConvolutionKernel",
            "ReconstructionDiameter",
            "SliceThickness",
            "SpacingBetweenSlices",
        ),
        None,
    ),
    "radiopharmaceutical": (
        (
            "RadionuclideTotalDose",
            "RadionuclideHalfLife",
            "RadiopharmaceuticalStartTime",
            "RadiopharmaceuticalStartDateTime",
        ),
        None,
    ),
}
REMOVAL_MARKERS = ("REMOVED", "ANONYMIZED", "ANONYMISED", "DEIDENTIFIED", "DE-IDENTIFIED")


class FieldAudit(BaseModel):
    field: str
    attribute_class: str
    presence: Literal["PRESENT", "EMPTY", "ABSENT"]
    reason: Reason | None = None


class AnonymizationAudit(BaseModel):
    deidentification_declared: bool | None
    patient_identity_removed: str | None
    deidentification_method: str | None
    options: list[dict[str, str]] = Field(default_factory=list)
    fields: list[FieldAudit] = Field(default_factory=list)
    vendor_private: list[PrivateEvidence] = Field(default_factory=list)
    timing_crosschecks: list[Reason] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


def _rp(ds: Dataset) -> Dataset | None:
    seq = _get(ds, "RadiopharmaceuticalInformationSequence")
    return seq[0] if seq else None


def _value(ds: Dataset, kw: str) -> Any:
    v = _get(ds, kw)
    if v is None:
        item = _rp(ds)
        v = _get(item, kw) if item is not None else None
    return v


def audit_anonymization(headers: Sequence[Dataset]) -> AnonymizationAudit:
    ds = headers[0]
    codes = [
        str(c.CodeValue)
        for c in (_get(ds, "DeidentificationMethodCodeSequence") or [])
        if "CodeValue" in c
    ]
    pir = _get(ds, "PatientIdentityRemoved")
    declared = None if pir is None and not codes else (str(pir).upper() == "YES" or bool(codes))
    audit = AnonymizationAudit(
        deidentification_declared=declared,
        patient_identity_removed=str(pir) if pir is not None else None,
        deidentification_method=str(_get(ds, "DeidentificationMethod") or "") or None,
        options=[
            {
                "code": c,
                "meaning": OPTION_MEANINGS.get(c, ("unknown option", "?"))[0],
                "ps3_15_section": OPTION_MEANINGS.get(c, ("", "?"))[1],
            }
            for c in codes
        ],
    )
    for cls, (attrs, retain_code) in CLASSES.items():
        for kw in attrs:
            v = _value(ds, kw)
            raw = "" if v is None else str(v).strip()
            presence = "ABSENT" if v is None else ("EMPTY" if not raw else "PRESENT")
            reason = None
            if presence == "PRESENT" and raw.upper() in REMOVAL_MARKERS:
                reason = Reason(
                    code="STRIPPED_BY_ANONYMIZATION",
                    field=kw,
                    detail=f"{kw} carries removal marker {raw!r}",
                    confidence="CONFIRMED",
                    evidence_basis="explicit marker",
                )
            elif presence != "PRESENT":
                if declared and retain_code and retain_code in codes:
                    reason = Reason(
                        code="NEVER_ENCODED",
                        field=kw,
                        confidence="PROBABLE",
                        detail=f"{kw} {presence.lower()} although the declared profile "
                        f"retains {cls.replace('_', ' ')}",
                        evidence_basis=f"PS3.15 {OPTION_MEANINGS[retain_code][1]} "
                        f"({OPTION_MEANINGS[retain_code][0]}) declared ({retain_code})",
                    )
                else:
                    reason = Reason(
                        code="UNKNOWN_OR_STRIPPED",
                        field=kw,
                        confidence="UNKNOWN",
                        detail=f"{kw} {presence.lower()}; the evidence cannot distinguish "
                        "absent-at-source from removed downstream",
                        evidence_basis="no declared retention option covers this attribute"
                        if declared
                        else "no de-identification declared; undeclared "
                        "processing cannot be excluded",
                    )
            audit.fields.append(
                FieldAudit(field=kw, attribute_class=cls, presence=presence, reason=reason)
            )
    parser = parser_for(str(_get(ds, "Manufacturer") or ""))
    if parser is not None:
        audit.vendor_private = parser.read(ds)
        for ev in audit.vendor_private:
            if ev.status == "NOT_PRESENT":
                safe = "113111" in codes
                audit.timing_crosschecks.append(
                    Reason(
                        code="UNKNOWN_OR_STRIPPED",
                        field=f"{ev.vendor} {ev.name}",
                        confidence="UNKNOWN",
                        detail=f"documented private attribute {ev.tag} absent",
                        evidence_basis="Retain Safe Private declared (E.3.10): retention depends "
                        "on the de-identifier's safety knowledge"
                        if safe
                        else "private attributes may be removed by de-identification",
                    )
                )
            if ev.status == "SUPPORTED_READ_ONLY" and ev.name == "acquisition_start_datetime":
                audit.timing_crosschecks.append(_compare_private_start(ds, ev))
    for f in audit.fields:
        key = f.reason.code if f.reason else f.presence
        audit.summary[key] = audit.summary.get(key, 0) + 1
    return audit


def _compare_private_start(ds: Dataset, ev: PrivateEvidence) -> Reason:
    try:
        series = combine_da_tm(_get(ds, "SeriesDate"), _get(ds, "SeriesTime"))
        priv = parse_dt(str(ev.value)) if len(str(ev.value)) >= 14 else None
    except DicomTimeError as exc:
        return Reason(
            code="AMBIGUOUS_TIMING",
            field=ev.name,
            detail=str(exc),
            confidence="UNKNOWN",
            evidence_basis=ev.source,
        )
    if priv is None:
        return Reason(
            code="AMBIGUOUS_TIMING",
            field=ev.name,
            confidence="UNKNOWN",
            detail="private start is time-only; date cannot be compared",
            evidence_basis=ev.source,
        )
    diff = (priv.replace(tzinfo=None) - series).total_seconds()
    if abs(diff) <= 1.0:
        return Reason(
            code="UNKNOWN_PROVENANCE",
            field=ev.name,
            confidence="CONFIRMED",
            detail="private acquisition start agrees with SeriesDate/Time (no issue)",
            evidence_basis=ev.source,
        )
    return Reason(
        code="INCONSISTENT_METADATA",
        field=ev.name,
        confidence="CONFIRMED",
        detail=f"private acquisition start {ev.value} differs from SeriesDate/Time by "
        f"{diff:+.0f} s"
        + (
            " (whole days: consistent with a date-shift applied to standard "
            "but not private attributes)"
            if diff % 86400 == 0
            else ""
        ),
        evidence_basis=ev.source,
    )
