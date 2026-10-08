"""Reference-region resolution for a timepoint: supplied region, or reviewed auto-proposal.

Precedence for each region (LIVER, BLOOD_POOL) of each subject/timepoint:
  1. a region SUPPLIED in trial.yaml (mask or reviewed centre)  -> measured, source SUPPLIED;
  2. otherwise, if automatic proposals are enabled, the ``vt-refauto-1`` proposal:
       review ACCEPT (matching proposal_sha256)      -> measured, COMPUTED
       review ADJUST (matching sha, reviewer centre)  -> measured at the reviewer's centre
       review REJECT (matching sha)                   -> REJECTED_BY_REVIEWER
       review with a different proposal_sha256        -> REVIEW_STALE
       no review                                      -> PROPOSED_REQUIRES_REVIEW
     (the unreviewed region is still measured, for the reviewer only; its status is never
     COMPUTED, so no assessability rule can use it);
     proposal NOT_FOUND                               -> AUTO_NOT_FOUND;
  3. otherwise MANUAL_OR_REFERENCE_MASK_REQUIRED.

Reviews live in ``reference_review.yaml`` (same format as the exported worksheet)::

    reviews:
      SUBJ/BASELINE:
        LIVER:
          decision: ACCEPT          # ACCEPT | ADJUST | REJECT | PENDING
          proposal_sha256: <sha from the worksheet / QC image>
          reviewer: <name or role>
          reviewed_at: 2026-10-08
          centre_patient_mm: null   # required for ADJUST, LPS mm
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, model_validator

from voxeltrace.quant.reference_auto import ReferenceProposal
from voxeltrace.quant.reference_region import (
    ReferenceRegionResult,
    ReferenceRegionSpec,
    Region,
)

REGIONS: tuple[Region, ...] = ("LIVER", "BLOOD_POOL")
Measure = Callable[[ReferenceRegionSpec], ReferenceRegionResult]


class ReferenceReview(BaseModel):
    decision: Literal["ACCEPT", "ADJUST", "REJECT"]
    proposal_sha256: str
    reviewer: str
    reviewed_at: str
    centre_patient_mm: tuple[float, float, float] | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _complete(self) -> ReferenceReview:
        if len(self.reviewer.strip()) < 2 or not str(self.reviewed_at).strip():
            raise ValueError("a review needs a reviewer and a review date")
        if len(self.proposal_sha256) != 64:
            raise ValueError("proposal_sha256 must be the full 64-character hash")
        if self.decision == "ADJUST" and self.centre_patient_mm is None:
            raise ValueError("ADJUST requires centre_patient_mm")
        if self.decision != "ADJUST" and self.centre_patient_mm is not None:
            raise ValueError("centre_patient_mm is only allowed with ADJUST")
        return self


def load_reviews(path: str | Path | None) -> dict[str, dict[str, ReferenceReview]]:
    """{'SUBJ/TP': {'LIVER': review}}. PENDING entries and display-only keys are ignored."""
    if path is None or not Path(path).exists():
        return {}
    raw = yaml.safe_load(Path(path).read_text()) or {}
    out: dict[str, dict[str, ReferenceReview]] = {}
    for key, regions in (raw.get("reviews") or {}).items():
        for region, entry in (regions or {}).items():
            if region not in REGIONS:
                raise ValueError(f"{key}: unknown reference region {region}")
            if (entry or {}).get("decision", "PENDING") == "PENDING":
                continue
            fields = {k: entry[k] for k in ReferenceReview.model_fields if k in entry}
            out.setdefault(key, {})[region] = ReferenceReview.model_validate(fields)
    return out


def resolve_region(
    region: Region,
    *,
    supplied: ReferenceRegionSpec | None,
    proposal: ReferenceProposal | None,
    review: ReferenceReview | None,
    measure: Measure,
    auto_enabled: bool,
    qc_image: str | None = None,
) -> ReferenceRegionResult:
    if supplied is not None:
        if supplied.region != region:
            raise ValueError(f"supplied spec is for {supplied.region}, not {region}")
        res = measure(supplied)
        res.source = "SUPPLIED"
        return res
    if not auto_enabled:
        return ReferenceRegionResult(
            status="MANUAL_OR_REFERENCE_MASK_REQUIRED",
            region=region,
            refusal="no supplied reference region; automatic proposals are disabled",
        )
    if proposal is None or proposal.status != "PROPOSED":
        return ReferenceRegionResult(
            status="AUTO_NOT_FOUND",
            region=region,
            source="AUTO_PROPOSAL",
            algorithm_version=proposal.algorithm_version if proposal else None,
            refusal=(proposal.failure_reason if proposal else None)
            or "automatic proposal unavailable",
        )
    sha = proposal.sha256
    common = {
        "source": "AUTO_PROPOSAL",
        "proposal_sha256": sha,
        "algorithm_version": proposal.algorithm_version,
        "qc_image": qc_image,
    }
    if review is not None and review.proposal_sha256 != sha:
        return ReferenceRegionResult(
            status="REVIEW_STALE",
            region=region,
            refusal=f"review was recorded for proposal {review.proposal_sha256[:12]}; the "
            f"current proposal is {sha[:12]}",
            review_decision=review.decision,
            reviewer=review.reviewer,
            centre_patient_mm=proposal.centre_patient_mm,
            **common,  # type: ignore[arg-type]
        )
    if review is not None and review.decision == "REJECT":
        return ReferenceRegionResult(
            status="REJECTED_BY_REVIEWER",
            region=region,
            refusal=review.note or "proposal rejected by reviewer",
            review_decision="REJECT",
            reviewer=review.reviewer,
            centre_patient_mm=proposal.centre_patient_mm,
            **common,  # type: ignore[arg-type]
        )
    if review is None:
        res = measure(proposal.to_spec(f"automatic proposal {proposal.algorithm_version}"))
        measured_ok = res.status == "COMPUTED"
        res.status = "PROPOSED_REQUIRES_REVIEW"
        if not measured_ok:
            res.refusal = f"proposal fails measurement QC: {res.refusal}"
        for k, v in common.items():
            setattr(res, k, v)
        return res
    prov = (
        f"automatic proposal {proposal.algorithm_version} {sha[:12]} "
        f"{'accepted' if review.decision == 'ACCEPT' else 'adjusted'} by {review.reviewer} "
        f"({review.reviewed_at})"
    )
    res = measure(proposal.to_spec(prov, centre=review.centre_patient_mm))
    for k, v in common.items():
        setattr(res, k, v)
    res.review_decision = review.decision
    res.reviewer = review.reviewer
    return res


STATUS_TO_REASON = {
    "MANUAL_OR_REFERENCE_MASK_REQUIRED": "MANUAL_OR_REFERENCE_MASK_REQUIRED",
    "PROPOSED_REQUIRES_REVIEW": "REFERENCE_REVIEW_REQUIRED",
    "REVIEW_STALE": "REFERENCE_REVIEW_STALE",
    "REJECTED_BY_REVIEWER": "REFERENCE_REJECTED_BY_REVIEWER",
    "AUTO_NOT_FOUND": "REFERENCE_AUTO_NOT_FOUND",
    "REFUSED": "REFERENCE_QC_FAILED",
}


def reference_reason(timepoint: str, res: ReferenceRegionResult | None, region: Region):
    """Actionable reason when a reference region is not usable (None if COMPUTED)."""
    from voxeltrace.trial.reasons import Reason

    if res is not None and res.status == "COMPUTED":
        return None
    if res is None:
        return Reason(
            code="MANUAL_OR_REFERENCE_MASK_REQUIRED",
            field=f"{timepoint}.{region.lower()}",
            detail="reference region not evaluated (no quantitative SUV at this timepoint)",
            confidence="CONFIRMED",
        )
    detail = res.refusal or res.status
    if res.proposal_sha256:
        detail += f" [proposal_sha256 {res.proposal_sha256}]"
    return Reason(
        code=STATUS_TO_REASON[res.status],  # type: ignore[arg-type]
        field=f"{timepoint}.{region.lower()}",
        detail=detail,
        confidence="CONFIRMED",
        evidence_basis=f"reference region status {res.status}"
        + (f", source {res.source}" if res.source else ""),
    )
