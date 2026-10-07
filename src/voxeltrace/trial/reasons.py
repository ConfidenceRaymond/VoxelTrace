"""Actionable INSUFFICIENT_INFORMATION reason codes.

Every reason states what is missing, why it matters, whether the site can fix it and how.
Causal codes (NEVER_ENCODED / STRIPPED_BY_ANONYMIZATION) carry a ``confidence`` and an
``evidence_basis``; STRIPPED_BY_ANONYMIZATION is only used when the data themselves show it
(e.g. an attribute present but emptied under a declared de-identification profile), otherwise
UNKNOWN_OR_STRIPPED is used. See docs/trial_audit.md.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReasonCode = Literal[
    "NEVER_ENCODED",
    "STRIPPED_BY_ANONYMIZATION",
    "UNKNOWN_OR_STRIPPED",
    "MISSING_REQUIRED_TAG",
    "INCONSISTENT_METADATA",
    "UNSUPPORTED_VENDOR",
    "UNSUPPORTED_SOFTWARE_VERSION",
    "PRIVATE_TAG_NOT_AVAILABLE",
    "UNSUPPORTED_PRIVATE_TAG",
    "AMBIGUOUS_RECONSTRUCTION",
    "AMBIGUOUS_TIMING",
    "UNKNOWN_PROVENANCE",
    "MANUAL_OR_REFERENCE_MASK_REQUIRED",
    "ANTHROPOMETRICS_MISSING",
    "SUV_REFUSED",
]
Confidence = Literal["CONFIRMED", "PROBABLE", "POSSIBLE", "UNKNOWN"]


class ReasonInfo(BaseModel):
    code: ReasonCode
    what: str
    why_it_matters: str
    site_can_fix: Literal["YES", "NO", "MAYBE"]
    remediation: str


CATALOG: dict[str, ReasonInfo] = {
    "NEVER_ENCODED": ReasonInfo(
        code="NEVER_ENCODED",
        what="attribute absent and its absence is not explained by the declared "
        "de-identification profile",
        why_it_matters="the scanner/site export did not record information needed downstream",
        site_can_fix="MAYBE",
        remediation="check scanner export configuration; if recorded elsewhere (e.g. RIS), "
        "re-export with the attribute populated",
    ),
    "STRIPPED_BY_ANONYMIZATION": ReasonInfo(
        code="STRIPPED_BY_ANONYMIZATION",
        what="attribute present but emptied/replaced consistent with a declared "
        "de-identification action",
        why_it_matters="quantitative information was removed before analysis",
        site_can_fix="YES",
        remediation="request re-export preserving approved quantitative attributes (e.g. "
        "DICOM PS3.15 Retain Patient Characteristics / Retain Safe Private options)",
    ),
    "UNKNOWN_OR_STRIPPED": ReasonInfo(
        code="UNKNOWN_OR_STRIPPED",
        what="attribute absent; the evidence cannot distinguish 'never recorded' from "
        "'removed during de-identification'",
        why_it_matters="required evidence unavailable; cause undetermined",
        site_can_fix="MAYBE",
        remediation="ask the site whether the attribute exists in the original export and "
        "which de-identification profile/options were applied",
    ),
    "MISSING_REQUIRED_TAG": ReasonInfo(
        code="MISSING_REQUIRED_TAG",
        what="a standard attribute required by the applied rule is missing or invalid",
        why_it_matters="the rule cannot be evaluated",
        site_can_fix="MAYBE",
        remediation="re-export with the attribute populated, or supply it via a documented "
        "trial-data channel (e.g. CRF) with provenance",
    ),
    "INCONSISTENT_METADATA": ReasonInfo(
        code="INCONSISTENT_METADATA",
        what="values differ between slices/instances or contradict each other",
        why_it_matters="no single defensible value exists",
        site_can_fix="YES",
        remediation="re-export the original series; investigate post-processing that altered "
        "headers",
    ),
    "UNSUPPORTED_VENDOR": ReasonInfo(
        code="UNSUPPORTED_VENDOR",
        what="vendor-specific handling required but not implemented",
        why_it_matters="parameters may exist only in vendor-specific form",
        site_can_fix="NO",
        remediation="VoxelTrace vendor support (documented, validated) needed",
    ),
    "UNSUPPORTED_SOFTWARE_VERSION": ReasonInfo(
        code="UNSUPPORTED_SOFTWARE_VERSION",
        what="vendor support exists but not validated for this software version",
        why_it_matters="private/derived semantics can change between versions",
        site_can_fix="NO",
        remediation="validate the version against a conformance statement",
    ),
    "PRIVATE_TAG_NOT_AVAILABLE": ReasonInfo(
        code="PRIVATE_TAG_NOT_AVAILABLE",
        what="a documented vendor private attribute that would resolve the question is absent",
        why_it_matters="cannot cross-check timing/reconstruction",
        site_can_fix="MAYBE",
        remediation="re-export retaining safe private attributes",
    ),
    "UNSUPPORTED_PRIVATE_TAG": ReasonInfo(
        code="UNSUPPORTED_PRIVATE_TAG",
        what="private attribute present but its meaning is not verified from a documented source",
        why_it_matters="cannot be used without risking misinterpretation",
        site_can_fix="NO",
        remediation="obtain the vendor conformance statement",
    ),
    "AMBIGUOUS_RECONSTRUCTION": ReasonInfo(
        code="AMBIGUOUS_RECONSTRUCTION",
        what="reconstruction parameters missing, free-text only, or ambiguous",
        why_it_matters="reconstruction strongly affects SUVmax/SUVpeak comparability",
        site_can_fix="YES",
        remediation="provide reconstruction protocol (algorithm, iterations, subsets, TOF, "
        "PSF, filter, voxel size) from the site imaging manual or structured attributes",
    ),
    "AMBIGUOUS_TIMING": ReasonInfo(
        code="AMBIGUOUS_TIMING",
        what="injection/scan reference timing cannot be established unambiguously",
        why_it_matters="decay correction and uptake-time rules depend on it",
        site_can_fix="YES",
        remediation="provide RadiopharmaceuticalStartDateTime and unmodified series timing",
    ),
    "UNKNOWN_PROVENANCE": ReasonInfo(
        code="UNKNOWN_PROVENANCE",
        what="origin/processing history of the series is unknown (e.g. derived/secondary "
        "images without derivation description)",
        why_it_matters="cannot tell whether quantitative values were altered",
        site_can_fix="MAYBE",
        remediation="send the original reconstructed series",
    ),
    "MANUAL_OR_REFERENCE_MASK_REQUIRED": ReasonInfo(
        code="MANUAL_OR_REFERENCE_MASK_REQUIRED",
        what="reference region (liver/blood pool) not supplied and automatic placement is "
        "not implemented",
        why_it_matters="PERCIST-style reference checks need it",
        site_can_fix="YES",
        remediation="supply a reference-region mask or a reviewed sphere centre (physical "
        "coordinates) per timepoint",
    ),
    "ANTHROPOMETRICS_MISSING": ReasonInfo(
        code="ANTHROPOMETRICS_MISSING",
        what="sex and/or height missing for lean-body-mass normalisation (SUL)",
        why_it_matters="SUL cannot be computed",
        site_can_fix="YES",
        remediation="re-export with Retain Patient Characteristics, or supply height/sex via "
        "a documented trial-data channel",
    ),
    "SUV_REFUSED": ReasonInfo(
        code="SUV_REFUSED",
        what="strict SUVbw refused (see SUV refusal codes)",
        why_it_matters="no quantitative values for this timepoint",
        site_can_fix="MAYBE",
        remediation="see the specific SUV refusal reasons",
    ),
}


class Reason(BaseModel):
    code: ReasonCode
    field: str | None = None
    detail: str
    confidence: Confidence = "UNKNOWN"
    evidence_basis: str | None = None
    info: ReasonInfo | None = Field(default=None, description="catalog entry (filled in)")

    def model_post_init(self, __context) -> None:  # noqa: D401
        if self.info is None:
            self.info = CATALOG[self.code]


SUV_REFUSAL_TO_REASON: dict[str, ReasonCode] = {
    "INCONSISTENT": "INCONSISTENT_METADATA",
    "TIME": "AMBIGUOUS_TIMING",
    "DATETIME": "AMBIGUOUS_TIMING",
    "INTERVAL": "AMBIGUOUS_TIMING",
    "TIMEZONE": "AMBIGUOUS_TIMING",
    "SCAN_REFERENCE": "AMBIGUOUS_TIMING",
    "SERIES_TIME": "AMBIGUOUS_TIMING",
    "MISSING": "MISSING_REQUIRED_TAG",
    "INVALID": "MISSING_REQUIRED_TAG",
}


def reason_for_suv_refusal(code: str, message: str) -> Reason:
    for key, rc in SUV_REFUSAL_TO_REASON.items():
        if key in code:
            return Reason(
                code=rc,
                field=code,
                detail=message,
                confidence="CONFIRMED",
                evidence_basis="strict SUV validator refusal",
            )
    return Reason(
        code="SUV_REFUSED",
        field=code,
        detail=message,
        confidence="CONFIRMED",
        evidence_basis="strict SUV validator refusal",
    )
