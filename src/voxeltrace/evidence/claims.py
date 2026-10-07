"""Deterministic claim gating. Every claim is checked against evidence; no LLM involved.

Statuses:
  SUPPORTED            evidence directly establishes the claim under the implemented rules
  PARTIALLY_SUPPORTED  evidence points the same way but relies on weaker evidence
                       (free-text-derived protocol facts, comparability with warnings)
  NOT_ESTABLISHED      required evidence is missing, or the claim type is out of scope
                       (diagnosis, treatment response, image noise in this milestone)
  CONTRADICTED         a measured value or protocol fact contradicts the claim
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from voxeltrace.evidence.comparability import ComparabilityAssessment
from voxeltrace.evidence.protocol import ProtocolEvidence
from voxeltrace.schemas import LesionMetrics, QuantEvidence

ClaimStatus = Literal["SUPPORTED", "PARTIALLY_SUPPORTED", "NOT_ESTABLISHED", "CONTRADICTED"]
ClaimType = Literal[
    "QUANTITATIVE_VALUE",
    "PROTOCOL_FACT",
    "LONGITUDINAL_CHANGE",
    "TREATMENT_RESPONSE",
    "DIAGNOSIS",
    "IMAGE_QUALITY",
]

RULES_VERSION = "claims-1"

METRICS: dict[str, tuple[str, str]] = {
    "suv_max": ("SUVmax", "g/mL"),
    "suv_mean": ("SUVmean", "g/mL"),
    "suv_median": ("SUVmedian", "g/mL"),
    "suv_peak": ("SUVpeak", "g/mL"),
    "mtv_ml": ("MTV", "mL"),
    "tlg": ("TLG", "g"),
}

COMMON_LIMITATIONS = [
    "Research prototype; not for clinical diagnosis.",
    "Quantitative values are validated only for the implemented DICOM BQML/START SUVbw path.",
]


class EvidenceRef(BaseModel):
    name: str
    value: Any = None
    unit: str | None = None
    source: str | None = None


class ClaimEvidence(BaseModel):
    claim_id: str
    claim_type: ClaimType
    statement: str
    status: ClaimStatus
    rule: str
    supporting_measurements: list[EvidenceRef] = Field(default_factory=list)
    supporting_protocol_evidence: list[EvidenceRef] = Field(default_factory=list)
    conflicting_evidence: list[EvidenceRef] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=lambda: list(COMMON_LIMITATIONS))


def _segment(ev: QuantEvidence, number: int | None) -> LesionMetrics | None:
    les = [x for x in ev.measured.lesions if x.voxel_count > 0]
    if number is None:
        return les[0] if len(les) == 1 else None
    return next((x for x in les if x.segment_number == number), None)


def _metric_value(les: LesionMetrics, metric: str) -> float | None:
    if metric == "suv_peak":
        return les.suv_peak.value if les.suv_peak and les.suv_peak.status == "COMPUTED" else None
    return getattr(les, metric)


def _tolerance(claimed: str | float) -> float:
    """Half a unit in the last stated decimal place (string claims); else 1e-9 relative."""
    if isinstance(claimed, str):
        exp = Decimal(claimed.strip()).as_tuple().exponent
        return 0.5 * 10.0 ** int(exp) if isinstance(exp, int) else 0.0
    return abs(float(claimed)) * 1e-9


def _suv_protocol_refs(ev: QuantEvidence) -> list[EvidenceRef]:
    q = ev.quantitative_inputs
    refs = [
        EvidenceRef(name="Units", value=q.units, source="(0054,1001)"),
        EvidenceRef(name="DecayCorrection", value=q.decay_correction, source="(0054,1102)"),
        EvidenceRef(
            name="decay_interval",
            value=q.decay_interval_s,
            unit="s",
            source=q.scan_reference_datetime_source,
        ),
    ]
    if ev.scale_factors:
        refs.append(
            EvidenceRef(
                name="suv_per_bqml",
                value=ev.scale_factors.suv_per_bqml,
                unit="g/Bq",
                source="strict SUVbw (suvbw-strict-1)",
            )
        )
    return refs


def claim_quantity(
    ev: QuantEvidence,
    metric: str,
    claimed: str | float,
    *,
    segment: int | None = None,
    claim_id: str | None = None,
) -> ClaimEvidence:
    """ "<metric> of segment <n> is <claimed>". String claims use their stated precision."""
    label, unit = METRICS[metric]
    seg_txt = f" (segment {segment})" if segment is not None else ""
    c = ClaimEvidence(
        claim_id=claim_id or f"value-{metric}-{segment if segment is not None else 'only'}",
        claim_type="QUANTITATIVE_VALUE",
        statement=f"{label}{seg_txt} is {claimed} {unit}",
        status="NOT_ESTABLISHED",
        rule="SUPPORTED only if the value is measured in the quantitative evidence and equals the "
        "claim within half a unit of the claim's last stated decimal; CONTRADICTED if "
        "measured and different",
        assumptions=list(ev.provenance.assumptions),
    )
    if metric == "mtv_ml":
        c.limitations.append("MTV is the volume of the supplied segmentation (no thresholding).")
    if metric == "tlg":
        c.limitations.append("TLG = MTV × SUVmean based on the supplied segmentation.")
    if ev.measured.suv_status != "PASS":
        c.missing_evidence.append("SUV refused: " + ", ".join(r.code for r in ev.refusal_reasons))
        return c
    les = _segment(ev, segment)
    if les is None:
        c.missing_evidence.append("no measured (unique) segment" + seg_txt)
        return c
    measured = _metric_value(les, metric)
    if measured is None:
        c.missing_evidence.append(f"{label} not available for segment {les.segment_number}")
        return c
    tol = _tolerance(claimed)
    ref = EvidenceRef(
        name=f"{label} segment {les.segment_number}",
        value=measured,
        unit=unit,
        source="evidence.measured.lesions",
    )
    c.supporting_protocol_evidence = _suv_protocol_refs(ev)
    if abs(measured - float(claimed)) <= tol:
        c.status = "SUPPORTED"
        c.supporting_measurements.append(ref)
    else:
        c.status = "CONTRADICTED"
        c.conflicting_evidence.append(ref)
    return c


_PROTOCOL_FACTS = {
    "attenuation_corrected": ("Images are attenuation corrected", "corrections", "attenuation"),
    "scatter_corrected": ("Images are scatter corrected", "corrections", "scatter"),
    "randoms_corrected": ("Images are randoms corrected", "corrections", "randoms"),
    "time_of_flight": ("Reconstruction used time-of-flight", "reconstruction", "time_of_flight"),
    "psf": (
        "Reconstruction used PSF / resolution modelling",
        "reconstruction",
        "psf_resolution_modelling",
    ),
}


def claim_protocol_fact(p: ProtocolEvidence, fact: str, claimed: bool = True) -> ClaimEvidence:
    text, cat, name = _PROTOCOL_FACTS[fact]
    obj = getattr(p, cat)
    f = obj.applied[name] if cat == "corrections" else getattr(obj, name)
    c = ClaimEvidence(
        claim_id=f"protocol-{fact}",
        claim_type="PROTOCOL_FACT",
        statement=text if claimed else f"NOT: {text}",
        status="NOT_ESTABLISHED",
        rule="standard attribute -> SUPPORTED/CONTRADICTED; vendor free text -> at most "
        "PARTIALLY_SUPPORTED; missing -> NOT_ESTABLISHED",
    )
    ref = EvidenceRef(name=f.name, value=f.value, source=f.source)
    if not f.known:
        c.missing_evidence.append(f"{f.name}: {f.note or 'missing'}")
        return c
    if f.value is claimed:
        c.supporting_protocol_evidence.append(ref)
        c.status = (
            "PARTIALLY_SUPPORTED"
            if f.derivation == "free_text_pattern" or f.status == "PRESENT_BUT_AMBIGUOUS"
            else "SUPPORTED"
        )
        if c.status == "PARTIALLY_SUPPORTED":
            c.limitations.append(
                f"{f.name} derived from vendor free text ({f.source}), not a "
                "structured DICOM attribute"
            )
    else:
        c.conflicting_evidence.append(ref)
        c.status = "CONTRADICTED"
    return c


def claim_uptake_change(
    ev_a: QuantEvidence | None,
    ev_b: QuantEvidence | None,
    comparability: ComparabilityAssessment | None,
    *,
    metric: str = "suv_max",
    direction: Literal["decrease", "increase"] = "decrease",
    segment_a: int | None = None,
    segment_b: int | None = None,
    same_target_confirmed: bool = False,
) -> ClaimEvidence:
    label, unit = METRICS[metric]
    c = ClaimEvidence(
        claim_id=f"change-{metric}-{direction}",
        claim_type="LONGITUDINAL_CHANGE",
        statement=f"{label} {'decreased' if direction == 'decrease' else 'increased'} between "
        "scan A and scan B (measurement change)",
        status="NOT_ESTABLISHED",
        rule="requires both scans quantified, the same target confirmed, protocol comparability "
        "COMPARABLE (SUPPORTED) or COMPARABLE_WITH_WARNINGS (PARTIALLY_SUPPORTED), and a "
        "computed percent change in the claimed direction",
    )
    c.limitations += [
        "Measurement change only; not a biological or treatment-response conclusion.",
        "Test-retest repeatability thresholds are not applied in this milestone.",
    ]
    values = {}
    for tag, ev, seg in (("A", ev_a, segment_a), ("B", ev_b, segment_b)):
        if ev is None:
            c.missing_evidence.append(f"scan {tag} quantitative evidence")
            continue
        if ev.measured.suv_status != "PASS":
            c.missing_evidence.append(f"scan {tag}: SUV refused")
            continue
        les = _segment(ev, seg)
        v = _metric_value(les, metric) if les else None
        if v is None:
            c.missing_evidence.append(f"scan {tag}: {label} not measured for the target")
            continue
        values[tag] = v
        c.supporting_measurements.append(
            EvidenceRef(
                name=f"{label} scan {tag}", value=v, unit=unit, source=ev.provenance.pet_series_uid
            )
        )
    if not same_target_confirmed:
        c.missing_evidence.append("lesion/target correspondence between scans not established")
    if comparability is None:
        c.missing_evidence.append("protocol comparability assessment")
    elif comparability.category in ("NOT_COMPARABLE", "INSUFFICIENT_INFORMATION"):
        c.missing_evidence.append(f"protocol comparability: {comparability.category}")
        c.conflicting_evidence += [
            EvidenceRef(name=n, source="comparability") for n in comparability.blocking_differences
        ]
    if len(values) == 2 and values["A"]:
        pct = (values["B"] - values["A"]) / values["A"] * 100.0
        c.supporting_measurements.append(
            EvidenceRef(name="percent_change", value=pct, unit="%", source="(B − A) / A × 100")
        )
    else:
        pct = None
    if c.missing_evidence or pct is None or comparability is None:
        return c
    c.supporting_protocol_evidence.append(
        EvidenceRef(name="comparability", value=comparability.category)
    )
    matches = pct < 0 if direction == "decrease" else pct > 0
    if not matches:
        c.status = "CONTRADICTED"
    elif comparability.category == "COMPARABLE":
        c.status = "SUPPORTED"
    else:
        c.status = "PARTIALLY_SUPPORTED"
        c.limitations.append("comparability with warnings: " + ", ".join(comparability.warnings))
    return c


def _out_of_scope(
    claim_id: str, ctype: ClaimType, statement: str, missing: list[str], rule: str
) -> ClaimEvidence:
    return ClaimEvidence(
        claim_id=claim_id,
        claim_type=ctype,
        statement=statement,
        status="NOT_ESTABLISHED",
        rule=rule,
        missing_evidence=missing,
    )


def claim_treatment_response(statement: str = "The lesion responded to treatment") -> ClaimEvidence:
    return _out_of_scope(
        "response",
        "TREATMENT_RESPONSE",
        statement,
        [
            "validated response criteria (e.g. PERCIST) not implemented",
            "comparable baseline and follow-up with confirmed target correspondence",
            "clinical context and treatment history",
        ],
        "treatment response is always NOT_ESTABLISHED in this milestone",
    )


def claim_diagnosis(statement: str = "The lesion is malignant") -> ClaimEvidence:
    return _out_of_scope(
        "diagnosis",
        "DIAGNOSIS",
        statement,
        ["VoxelTrace makes no diagnostic determinations", "histopathology / clinical correlation"],
        "diagnostic claims are always NOT_ESTABLISHED (research prototype)",
    )


def claim_image_noise(statement: str = "Image noise is elevated") -> ClaimEvidence:
    return _out_of_scope(
        "image-noise",
        "IMAGE_QUALITY",
        statement,
        [
            "validated noise metric (e.g. liver-VOI coefficient of variation) not implemented",
            "reference criterion for 'elevated'",
        ],
        "NOT_ESTABLISHED unless an explicit validated noise metric and criterion exist",
    )


def default_case_claims(ev: QuantEvidence, p: ProtocolEvidence | None) -> list[ClaimEvidence]:
    """Deterministic example claims for one case, generated from its own evidence."""
    claims: list[ClaimEvidence] = []
    for les in ev.measured.lesions:
        if les.voxel_count == 0:
            continue
        for m in METRICS:
            v = _metric_value(les, m)
            c = claim_quantity(
                ev,
                m,
                f"{v:.3f}" if v is not None else "0",
                segment=les.segment_number,
                claim_id=f"value-{m}-seg{les.segment_number}",
            )
            if v is None:  # e.g. SUVpeak NOT_AVAILABLE: claim only that a value exists
                c.statement = f"{METRICS[m][0]} (segment {les.segment_number}) has a value"
            claims.append(c)
    if p is not None:
        claims += [claim_protocol_fact(p, f) for f in _PROTOCOL_FACTS]
    claims += [
        claim_uptake_change(ev, None, None),
        claim_treatment_response(),
        claim_diagnosis(),
        claim_image_noise(),
    ]
    return claims
