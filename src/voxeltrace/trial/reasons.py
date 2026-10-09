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
    "REFERENCE_REVIEW_REQUIRED",
    "REFERENCE_REVIEW_OUTDATED",
    "REFERENCE_REVIEW_INVALID",
    "REFERENCE_REJECTED_BY_REVIEWER",
    "REFERENCE_AUTO_NOT_FOUND",
    "REFERENCE_QC_FAILED",
    "REFERENCE_INHERITANCE_REFUSED",
    "ANTHROPOMETRICS_MISSING",
    "SUV_REFUSED",
    "EXTERNAL_RECONSTRUCTION_ATTESTATION",
    "RECONSTRUCTION_ATTESTATION_NOT_USABLE",
    "RECONSTRUCTION_ATTESTATION_CONTRADICTS",
    "LESION_REVIEW_REQUIRED",
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
        what="reference region (liver/blood pool) not supplied and automatic proposals are "
        "disabled for this trial",
        why_it_matters="PERCIST-style reference checks need it",
        site_can_fix="YES",
        remediation="supply a reference-region mask or a reviewed centre (physical "
        "coordinates) per timepoint in trial.yaml, or enable reference_proposals: auto",
    ),
    "REFERENCE_REVIEW_REQUIRED": ReasonInfo(
        code="REFERENCE_REVIEW_REQUIRED",
        what="an automatic reference-region proposal exists but has not been reviewed",
        why_it_matters="unreviewed automatic placements are never used by assessability rules",
        site_can_fix="YES",
        remediation="review the proposal on the Reference Review page (or the exported "
        "worksheet) and record ACCEPT, ADJUST or REJECT for that proposal_sha256 in "
        "<trial>/reference_review.yaml, then re-run the audit",
    ),
    "REFERENCE_REVIEW_INVALID": ReasonInfo(
        code="REFERENCE_REVIEW_INVALID",
        what="a review entry exists but fails validation (e.g. filed under another subject or "
        "region, inconsistent geometry or hash, missing reviewer or timestamp, or SIMULATED)",
        why_it_matters="an invalid review is never applied",
        site_can_fix="YES",
        remediation="re-record the decision with the reference review page, which writes a "
        "complete, hash-bound record",
    ),
    "REFERENCE_REVIEW_OUTDATED": ReasonInfo(
        code="REFERENCE_REVIEW_OUTDATED",
        what="the recorded review refers to a different proposal than the current one",
        why_it_matters="the reviewed region is not the region that would be measured",
        site_can_fix="YES",
        remediation="re-review the current proposal (new proposal_sha256 in the worksheet)",
    ),
    "REFERENCE_REJECTED_BY_REVIEWER": ReasonInfo(
        code="REFERENCE_REJECTED_BY_REVIEWER",
        what="a reviewer rejected the automatic reference-region proposal",
        why_it_matters="no accepted reference region exists for this timepoint",
        site_can_fix="YES",
        remediation="record ADJUST with a reviewed centre, or supply a mask/centre in "
        "trial.yaml reference_regions",
    ),
    "REFERENCE_AUTO_NOT_FOUND": ReasonInfo(
        code="REFERENCE_AUTO_NOT_FOUND",
        what="the deterministic CT-guided proposer could not place the region (see detail, "
        "e.g. no CT series, lungs not found, no consistent aorta segment)",
        why_it_matters="no reference region is available for reference-based rules",
        site_can_fix="YES",
        remediation="supply a reference-region mask or reviewed centre in trial.yaml "
        "reference_regions, or provide the attenuation-correction CT with the PET",
    ),
    "REFERENCE_INHERITANCE_REFUSED": ReasonInfo(
        code="REFERENCE_INHERITANCE_REFUSED",
        what="a synthetic-fixture reference inheritance was declared but refused (real scan, "
        "missing synthetic label or fixture manifest, parent PET hash, CT geometry or CT pixel "
        "mismatch, or no accepted parent region), or an inherited region was offered for "
        "a real scan",
        why_it_matters="inherited reference geometry is valid only for synthetic test fixtures "
        "whose CT is the unchanged parent CT; it is never a substitute for human review",
        site_can_fix="NO",
        remediation="real scans need a supplied region or a human-reviewed proposal; fix the "
        "synthetic fixture if this is a test fixture",
    ),
    "REFERENCE_QC_FAILED": ReasonInfo(
        code="REFERENCE_QC_FAILED",
        what="the reference region was refused by measurement QC (outside image, overlaps a "
        "lesion, masked SUV 0 voxels, or too few voxels)",
        why_it_matters="the region cannot be measured defensibly",
        site_can_fix="YES",
        remediation="move the region (ADJUST with a new centre) or supply a corrected mask",
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
    "EXTERNAL_RECONSTRUCTION_ATTESTATION": ReasonInfo(
        code="EXTERNAL_RECONSTRUCTION_ATTESTATION",
        what="reconstruction identity rests on a validated external attestation (LEVEL_C), "
        "not on DICOM (QIBA rule set only)",
        why_it_matters="identity is externally attested, not DICOM-proven",
        site_can_fix="MAYBE",
        remediation="re-export with standard reconstruction attributes to obtain DICOM proof",
    ),
    "RECONSTRUCTION_ATTESTATION_NOT_USABLE": ReasonInfo(
        code="RECONSTRUCTION_ATTESTATION_NOT_USABLE",
        what="a reconstruction attestation was supplied but is invalid, stale, out of scope, "
        "charter-only or incomplete",
        why_it_matters="it cannot contribute evidence of reconstruction identity",
        site_can_fix="YES",
        remediation="supply a hash-bound, scan-bound attestation by an accepted role for both "
        "timepoints, scoped to the rule set, stating every unknown parameter",
    ),
    "LESION_REVIEW_REQUIRED": ReasonInfo(
        code="LESION_REVIEW_REQUIRED",
        what="lesion segmentations are supplied but none is a human-ACCEPTED target for the "
        "exact mask (unreviewed, rejected, outdated or invalid review)",
        why_it_matters="unreviewed masks are never quantitative ground truth",
        site_can_fix="NO",
        remediation="a qualified reviewer accepts or rejects each segment on the Lesion Review "
        "page; a rejected mask needs a replacement segmentation",
    ),
    "RECONSTRUCTION_ATTESTATION_CONTRADICTS": ReasonInfo(
        code="RECONSTRUCTION_ATTESTATION_CONTRADICTS",
        what="attested reconstruction disagrees with DICOM, with another attestation, or "
        "between timepoints",
        why_it_matters="identity is contradicted; the pair is not comparable",
        site_can_fix="MAYBE",
        remediation="resolve the discrepancy with the site physicist; correct the record",
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
