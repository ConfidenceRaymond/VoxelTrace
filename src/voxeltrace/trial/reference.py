"""Reference-region resolution for a timepoint: supplied region, or human-reviewed proposal.

Precedence for each region (LIVER, BLOOD_POOL) of each subject/timepoint:
  1. a region SUPPLIED in trial.yaml (mask or reviewed centre)  -> measured, source SUPPLIED;
  2. otherwise, if automatic proposals are enabled, the ``vt-refauto-1`` proposal:
       valid review ACCEPT (same proposal_sha256)       -> measured, COMPUTED
       valid review ADJUST (same sha, reviewer centre)  -> measured at the reviewer's centre
       valid review REJECT (same sha)                   -> REJECTED_BY_REVIEWER
       review naming a different proposal_sha256        -> REVIEW_OUTDATED (never reused)
       review failing validation                        -> REVIEW_INVALID
       no review                                        -> PROPOSED_REQUIRES_REVIEW
     (an unreviewed region is still measured, for the reviewer only; its status is never
     COMPUTED, so no assessability rule can use it);
     proposal NOT_FOUND                                 -> AUTO_NOT_FOUND;
  3. otherwise MANUAL_OR_REFERENCE_MASK_REQUIRED.

Reviews are HUMAN QC decisions. They live in ``<trial>/reference_review.yaml``, written by the
review page (``app/pages/4_Reference_Review.py``) via :func:`record_review`, or by hand from
the exported worksheet. No code path creates a decision on its own: :func:`record_review`
requires an explicit confirmation flag set by the reviewer's action, and SIMULATED reviews
(tests only) are refused in project data/output trees and ignored by audits.

File format (schema ``voxeltrace.reference-review/2``)::

    schema: voxeltrace.reference-review/2
    reviews:
      SUBJ/BASELINE:
        LIVER:
          subject: SUBJ
          timepoint: BASELINE
          region: LIVER
          decision: ACCEPT            # ACCEPT | ADJUST | REJECT | PENDING
          proposal_sha256: <64 hex>
          proposal_algorithm_version: vt-refauto-1
          proposal_geometry: {method, centre_patient_mm, diameter_mm, length_mm}
          final_geometry: {...}       # = proposal for ACCEPT; moved centre for ADJUST;
                                      #   null for REJECT
          final_region_sha256: <64 hex>   # optional; verified when present
          reviewer: <entered by the reviewer>
          reviewed_at: 2026-10-08T14:03:00+00:00
          note: null
          software_version: 0.1.0
          git_commit: <sha>
          rule_context: {ruleset_id, ruleset_version, region_definition, rule_ids}
          review_sha256: <64 hex>     # optional integrity hash; verified when present
    superseded: []                    # earlier decisions replaced by a re-review
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ValidationError, model_validator

from voxeltrace.quant.reference_auto import ReferenceProposal
from voxeltrace.quant.reference_region import (
    ReferenceRegionResult,
    ReferenceRegionSpec,
    Region,
)

REGIONS: tuple[Region, ...] = ("LIVER", "BLOOD_POOL")
REVIEW_SCHEMA = "voxeltrace.reference-review/2"
Measure = Callable[[ReferenceRegionSpec], ReferenceRegionResult]
ReviewStatus = Literal["UNREVIEWED", "ACCEPTED", "ADJUSTED", "REJECTED", "OUTDATED", "INVALID"]


def _sha(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=list).encode()).hexdigest()


class RegionGeometry(BaseModel):
    method: Literal["SPHERE_AT_SUPPLIED_CENTRE", "CYLINDER_AT_SUPPLIED_CENTRE"]
    centre_patient_mm: tuple[float, float, float]
    diameter_mm: float
    length_mm: float | None = None

    @classmethod
    def of(cls, p: ReferenceProposal) -> RegionGeometry:
        if p.status != "PROPOSED":
            raise ValueError("no proposal geometry")
        return cls(
            method=p.method,  # type: ignore[arg-type]
            centre_patient_mm=p.centre_patient_mm,  # type: ignore[arg-type]
            diameter_mm=p.diameter_mm,  # type: ignore[arg-type]
            length_mm=p.length_mm,
        )

    def same_shape(self, other: RegionGeometry) -> bool:
        return (self.method, self.diameter_mm, self.length_mm) == (
            other.method,
            other.diameter_mm,
            other.length_mm,
        )


class RuleContext(BaseModel):
    ruleset_id: str
    ruleset_version: str
    region_definition: str
    rule_ids: list[str]


def rule_context_for(region: Region) -> RuleContext:
    """The rule context a reference-region review serves (PERCIST 1.0)."""
    from voxeltrace.rules import percist

    if region == "LIVER":
        return RuleContext(
            ruleset_id="percist-1.0",
            ruleset_version=percist.V,
            region_definition="PERCIST 1.0 liver reference: 3 cm diameter sphere in normal "
            "right-lobe liver tissue",
            rule_ids=[percist.LIVER.rule_id, percist.MEASURABLE.rule_id],
        )
    return RuleContext(
        ruleset_id="percist-1.0",
        ruleset_version=percist.V,
        region_definition="PERCIST 1.0 blood-pool reference: 1 cm diameter x 2 cm cylinder "
        "in the descending thoracic aorta (measured and reported; no rule uses it)",
        rule_ids=[],
    )


def final_region_sha256(proposal_sha256: str, g: RegionGeometry | None) -> str | None:
    return None if g is None else _sha({"proposal": proposal_sha256, **g.model_dump()})


class ReferenceReview(BaseModel):
    subject: str
    timepoint: str
    region: Region
    decision: Literal["ACCEPT", "ADJUST", "REJECT"]
    proposal_sha256: str
    proposal_algorithm_version: str
    proposal_geometry: RegionGeometry
    final_geometry: RegionGeometry | None = None
    final_region_sha256: str | None = None
    reviewer: str
    reviewed_at: str
    note: str | None = None
    software_version: str
    git_commit: str
    rule_context: RuleContext
    simulated: bool = False
    review_sha256: str | None = None

    def content_sha256(self) -> str:
        return _sha(self.model_dump(exclude={"review_sha256"}))

    @property
    def centre_patient_mm(self) -> tuple[float, float, float] | None:
        return self.final_geometry.centre_patient_mm if self.final_geometry else None

    @model_validator(mode="after")
    def _complete(self) -> ReferenceReview:
        if len(self.reviewer.strip()) < 2:
            raise ValueError("a review needs the reviewer's name or identifier")
        try:
            datetime.fromisoformat(str(self.reviewed_at))
        except ValueError as exc:
            raise ValueError("reviewed_at must be an ISO-8601 timestamp") from exc
        if len(self.proposal_sha256) != 64:
            raise ValueError("proposal_sha256 must be the full 64-character hash")
        g, p = self.final_geometry, self.proposal_geometry
        if self.decision == "REJECT":
            if g is not None:
                raise ValueError("REJECT records no final geometry")
        elif g is None:
            raise ValueError(f"{self.decision} requires final_geometry")
        elif not g.same_shape(p):
            raise ValueError(
                "region method and dimensions are fixed by the rule; only the "
                "centre may be adjusted"
            )
        elif self.decision == "ACCEPT" and g.centre_patient_mm != p.centre_patient_mm:
            raise ValueError("ACCEPT keeps the proposed centre; use ADJUST to move it")
        elif self.decision == "ADJUST" and g.centre_patient_mm == p.centre_patient_mm:
            raise ValueError("ADJUST must move the centre; use ACCEPT otherwise")
        want = final_region_sha256(self.proposal_sha256, g)
        if self.final_region_sha256 is not None and self.final_region_sha256 != want:
            raise ValueError("final_region_sha256 does not match final_geometry")
        if self.review_sha256 is not None and self.review_sha256 != self.content_sha256():
            raise ValueError("review_sha256 does not match the record (edited after saving?)")
        return self


class InvalidReview(BaseModel):
    """A review entry that is present but unusable; reported, never applied."""

    error: str
    proposal_sha256: str | None = None
    decision: str | None = None
    reviewer: str | None = None


ReviewEntry = ReferenceReview | InvalidReview


def load_reviews(
    path: str | Path | None, *, allow_simulated: bool = False
) -> dict[str, dict[str, ReviewEntry]]:
    """{'SUBJ/TP': {'LIVER': review or InvalidReview}}. PENDING entries are skipped.

    An entry is INVALID (never applied) when it fails validation, is filed under a different
    subject/timepoint or region than it states, or is SIMULATED (unless ``allow_simulated``,
    which only tests use)."""
    if path is None or not Path(path).exists():
        return {}
    raw = yaml.safe_load(Path(path).read_text()) or {}
    out: dict[str, dict[str, ReviewEntry]] = {}
    for key, regions in (raw.get("reviews") or {}).items():
        for region, entry in (regions or {}).items():
            if region not in REGIONS:
                raise ValueError(f"{key}: unknown reference region {region}")
            entry = entry or {}
            if entry.get("decision", "PENDING") == "PENDING":
                continue
            bad = None
            try:
                rv: ReviewEntry = ReferenceReview.model_validate(
                    {k: entry[k] for k in ReferenceReview.model_fields if k in entry}
                )
            except (ValidationError, ValueError) as exc:
                bad = (
                    "; ".join(e["msg"] for e in exc.errors())
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )
            else:
                if f"{rv.subject}/{rv.timepoint}" != key:
                    bad = f"review is for {rv.subject}/{rv.timepoint}, filed under {key}"
                elif rv.region != region:
                    bad = f"review is for region {rv.region}, filed under {region}"
                elif rv.simulated and not allow_simulated:
                    bad = "SIMULATED review (tests only) refused"
            if bad is not None:
                rv = InvalidReview(
                    error=bad,
                    proposal_sha256=entry.get("proposal_sha256"),
                    decision=entry.get("decision"),
                    reviewer=entry.get("reviewer"),
                )
            out.setdefault(key, {})[region] = rv
    return out


def review_status(proposal_sha256: str | None, review: ReviewEntry | None) -> ReviewStatus:
    if review is None:
        return "UNREVIEWED"
    if isinstance(review, InvalidReview):
        return "INVALID"
    if review.proposal_sha256 != proposal_sha256:
        return "OUTDATED"
    return {"ACCEPT": "ACCEPTED", "ADJUST": "ADJUSTED", "REJECT": "REJECTED"}[review.decision]  # type: ignore[return-value]


# --------------------------------------------------------------------------------------
# Creating a review record (human action only)
# --------------------------------------------------------------------------------------


def build_review(
    *,
    subject: str,
    timepoint: str,
    proposal: ReferenceProposal,
    decision: Literal["ACCEPT", "ADJUST", "REJECT"],
    reviewer: str,
    note: str | None = None,
    adjusted_centre: tuple[float, float, float] | None = None,
    reviewed_at: str | None = None,
    simulated: bool = False,
) -> ReferenceReview:
    """Assemble (and validate) a review record from the reviewer's explicit choices."""
    import voxeltrace
    from voxeltrace.quant.suv import git_state

    pg = RegionGeometry.of(proposal)
    if decision == "REJECT":
        fg = None
    elif decision == "ACCEPT":
        fg = pg
    else:
        if adjusted_centre is None:
            raise ValueError("ADJUST requires the adjusted centre")
        fg = pg.model_copy(
            update={"centre_patient_mm": tuple(round(v, 1) for v in adjusted_centre)}
        )
    commit, dirty = git_state()
    rv = ReferenceReview(
        subject=subject,
        timepoint=timepoint,
        region=proposal.region,
        decision=decision,
        proposal_sha256=proposal.sha256,
        proposal_algorithm_version=proposal.algorithm_version,
        proposal_geometry=pg,
        final_geometry=fg,
        final_region_sha256=final_region_sha256(proposal.sha256, fg),
        reviewer=reviewer.strip(),
        reviewed_at=reviewed_at or datetime.now(UTC).isoformat(timespec="seconds"),
        note=(note or "").strip() or None,
        software_version=voxeltrace.__version__,
        git_commit=f"{commit}{'+dirty' if dirty else ''}",
        rule_context=rule_context_for(proposal.region),
        simulated=simulated,
    )
    rv.review_sha256 = rv.content_sha256()
    return rv


def _protected_roots() -> list[Path]:
    from voxeltrace.config import REPO_ROOT

    root = REPO_ROOT.parent.resolve()
    return [root / "outputs", root / "data"]


def record_review(
    path: str | Path, review: ReferenceReview, *, confirmed: bool, replace: bool = False
) -> Path:
    """Write one human decision into ``reference_review.yaml``.

    ``confirmed`` must be set by the reviewer's explicit confirmation; nothing is written
    otherwise. A SIMULATED review is refused inside the project's data/output trees. An
    existing decision for the same scan and region is replaced only with ``replace=True``
    and is kept under ``superseded``."""
    if not confirmed:
        raise PermissionError("a review is written only after explicit reviewer confirmation")
    p = Path(path).resolve()
    if review.simulated and any(r in (p, *p.parents) for r in _protected_roots()):
        raise PermissionError("SIMULATED reviews may not be written to project data/outputs")
    if review.review_sha256 != review.content_sha256():
        raise ValueError("review_sha256 missing or stale; build the record with build_review")
    doc = yaml.safe_load(p.read_text()) if p.exists() else None
    doc = doc or {}
    doc.setdefault("schema", REVIEW_SCHEMA)
    reviews = doc.setdefault("reviews", {}) or {}
    doc["reviews"] = reviews
    key = f"{review.subject}/{review.timepoint}"
    slot = reviews.setdefault(key, {}) or {}
    reviews[key] = slot
    old = slot.get(review.region)
    if old and old.get("decision", "PENDING") != "PENDING":
        if not replace:
            raise FileExistsError(f"{key} {review.region} already has a decision")
        doc.setdefault("superseded", []).append(
            {**old, "superseded_at": datetime.now(UTC).isoformat(timespec="seconds")}
        )
    slot[review.region] = json.loads(review.model_dump_json())
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(doc, sort_keys=True, width=100))
    os.replace(tmp, p)
    return p


# --------------------------------------------------------------------------------------
# Resolution used by the audit
# --------------------------------------------------------------------------------------


def resolve_region(
    region: Region,
    *,
    supplied: ReferenceRegionSpec | None,
    proposal: ReferenceProposal | None,
    review: ReviewEntry | None,
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
        "centre_patient_mm": proposal.centre_patient_mm,
        "diameter_mm": proposal.diameter_mm,
        "length_mm": proposal.length_mm,
    }
    if isinstance(review, InvalidReview):
        return ReferenceRegionResult(
            status="REVIEW_INVALID",
            region=region,
            refusal=f"review entry not usable: {review.error}",
            review_decision=review.decision,
            reviewer=review.reviewer,
            **common,  # type: ignore[arg-type]
        )
    if review is not None and (
        review.proposal_sha256 != sha or RegionGeometry.of(proposal) != review.proposal_geometry
    ):
        return ReferenceRegionResult(
            status="REVIEW_OUTDATED",
            region=region,
            refusal=f"review was recorded for proposal {review.proposal_sha256[:12]}; the "
            f"current proposal is {sha[:12]}; the old review is not reused",
            review_decision=review.decision,
            reviewer=review.reviewer,
            **common,  # type: ignore[arg-type]
        )
    if review is not None and review.decision == "REJECT":
        return ReferenceRegionResult(
            status="REJECTED_BY_REVIEWER",
            region=region,
            refusal=review.note or "proposal rejected by reviewer",
            review_decision="REJECT",
            reviewer=review.reviewer,
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
        if k != "centre_patient_mm":
            setattr(res, k, v)
    res.review_decision = review.decision
    res.reviewer = review.reviewer
    return res


STATUS_TO_REASON = {
    "MANUAL_OR_REFERENCE_MASK_REQUIRED": "MANUAL_OR_REFERENCE_MASK_REQUIRED",
    "PROPOSED_REQUIRES_REVIEW": "REFERENCE_REVIEW_REQUIRED",
    "REVIEW_OUTDATED": "REFERENCE_REVIEW_OUTDATED",
    "REVIEW_INVALID": "REFERENCE_REVIEW_INVALID",
    "REJECTED_BY_REVIEWER": "REFERENCE_REJECTED_BY_REVIEWER",
    "AUTO_NOT_FOUND": "REFERENCE_AUTO_NOT_FOUND",
    "REFUSED": "REFERENCE_QC_FAILED",
    "INHERITANCE_REFUSED": "REFERENCE_INHERITANCE_REFUSED",
    "SYNTHETIC_INHERITED_REFERENCE": "REFERENCE_INHERITANCE_REFUSED",
}


def reference_reason(
    timepoint: str,
    res: ReferenceRegionResult | None,
    region: Region,
    subject: str | None = None,
    *,
    synthetic: bool = False,
):
    """Actionable reason when a reference region is not usable (None if usable). The detail
    names the exact scan, region and proposal hash that still needs a decision.

    Usable: COMPUTED; or SYNTHETIC_INHERITED_REFERENCE on a SYNTHETIC scan only (it is
    rejected on real data)."""
    from voxeltrace.trial.reasons import Reason

    if res is not None and res.status == "COMPUTED":
        return None
    if res is not None and res.status == "SYNTHETIC_INHERITED_REFERENCE":
        if synthetic and res.source == "SYNTHETIC_INHERITED" and res.inherited_from:
            return None
        res = res.model_copy(
            update={"refusal": "synthetic inherited reference offered for a real scan"}
        )
    where = f"{subject}/{timepoint}" if subject else timepoint
    if res is None:
        return Reason(
            code="MANUAL_OR_REFERENCE_MASK_REQUIRED",
            field=f"{timepoint}.{region.lower()}",
            detail=f"{where} {region}: reference region not evaluated (no quantitative SUV)",
            confidence="CONFIRMED",
        )
    detail = f"{where} {region}: {res.refusal or res.status}"
    if res.status == "PROPOSED_REQUIRES_REVIEW":
        detail = (
            f"{where} {region}: automatic proposal awaits a human ACCEPT/ADJUST/REJECT decision "
            f"in <trial>/reference_review.yaml" + (f" ({res.refusal})" if res.refusal else "")
        )
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
