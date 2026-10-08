"""Batch trial comparability audit (deterministic; no AI; no response assessment)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from voxeltrace.evidence.comparability import compare_protocols
from voxeltrace.rules.registry import assess_pair
from voxeltrace.rules.trial_overrides import effective_ruleset
from voxeltrace.trial.discovery import discover_trial
from voxeltrace.trial.pairing import make_pairs
from voxeltrace.trial.reference import load_reviews
from voxeltrace.trial.schema import PairAssessabilityResult, PairContext, ScanTimepoint
from voxeltrace.trial.timepoint import build_timepoint


class TrialAudit(BaseModel):
    trial_id: str
    ruleset_id: str
    ruleset_version: str
    standard: str
    overrides: list[str] = Field(default_factory=list)
    documented_not_implemented: list[str] = Field(default_factory=list)
    reference_proposals: str = "auto"
    reference_review_file: str | None = None
    reference_reviews_applied: int = 0
    reference_reviews_unmatched: list[str] = Field(
        default_factory=list, description="review keys with no matching subject/timepoint"
    )
    timepoints: list[ScanTimepoint]
    pairs: list[PairAssessabilityResult]
    disclaimer: str = (
        "Comparability/assessability audit only. RESEARCH PROTOTYPE - NOT FOR "
        "CLINICAL DIAGNOSIS. No biological or treatment response is assessed."
    )


def run_trial_audit(
    root: str | Path,
    ruleset: str | None = None,
    *,
    qc_dir: str | Path | None = None,
    reviews_file: str | Path | None = None,
    allow_simulated_reviews: bool = False,
) -> TrialAudit:
    """Audit a trial directory. ``ruleset`` overrides trial.yaml (explicit, recorded).
    ``qc_dir`` receives reference-proposal QC renders; ``reviews_file`` overrides the
    trial's reference_review_file. ``allow_simulated_reviews`` exists for tests only;
    production audits ignore SIMULATED review records (they become REVIEW_INVALID)."""
    layout = discover_trial(root)
    review_path = reviews_file or layout.reference_review_file
    reviews = load_reviews(review_path, allow_simulated=allow_simulated_reviews)
    if ruleset is not None:
        layout.config = layout.config.model_copy(update={"ruleset": ruleset})
    rs = effective_ruleset(layout.config)
    tps: dict[tuple[str, str], ScanTimepoint] = {}
    for subj, scans in layout.scans.items():
        for tp_name, d in scans.items():
            key = f"{subj}/{tp_name}"
            tps[(subj, tp_name)] = build_timepoint(
                d,
                subject=subj,
                timepoint=tp_name,
                site=layout.sites.get(subj),
                synthetic=layout.synthetic.get(key),
                reference_specs=layout.reference_regions.get(key),
                reviews=reviews.get(key),
                auto_reference=layout.reference_proposals == "auto",
                qc_dir=qc_dir,
            )
    pairs = []
    for subj, scans in layout.scans.items():
        for pair in make_pairs(subj, list(scans), layout.timepoint_order):
            b, f = tps[(subj, pair.baseline)], tps[(subj, pair.followup)]
            site = layout.sites.get(subj)
            ctx = PairContext(
                pair=pair,
                baseline=b,
                followup=f,
                site_flags=layout.config.site_flags.get(site or "", {}),
            )
            cat = (
                compare_protocols(b.protocol, f.protocol).category
                if b.protocol and f.protocol
                else None
            )
            pairs.append(assess_pair(rs, ctx, cat))
    return TrialAudit(
        trial_id=layout.config.trial_id,
        ruleset_id=rs.ruleset_id,
        ruleset_version=rs.version,
        standard=rs.standard,
        overrides=rs.overrides,
        documented_not_implemented=rs.documented_not_implemented,
        reference_proposals=layout.reference_proposals,
        reference_review_file=str(review_path) if review_path else None,
        reference_reviews_applied=sum(
            1
            for t in tps.values()
            for r in (t.liver, t.blood_pool)
            if r is not None
            and r.review_decision
            and r.status not in ("REVIEW_OUTDATED", "REVIEW_INVALID")
        ),
        reference_reviews_unmatched=sorted(k for k in reviews if tuple(k.split("/", 1)) not in tps),
        timepoints=list(tps.values()),
        pairs=pairs,
    )
