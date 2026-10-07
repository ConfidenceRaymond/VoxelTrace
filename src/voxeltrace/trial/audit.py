"""Batch trial comparability audit (deterministic; no AI; no response assessment)."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from voxeltrace.evidence.comparability import compare_protocols
from voxeltrace.rules.registry import assess_pair
from voxeltrace.rules.trial_overrides import effective_ruleset
from voxeltrace.trial.discovery import discover_trial
from voxeltrace.trial.pairing import make_pairs
from voxeltrace.trial.schema import PairAssessabilityResult, PairContext, ScanTimepoint
from voxeltrace.trial.timepoint import build_timepoint


class TrialAudit(BaseModel):
    trial_id: str
    ruleset_id: str
    ruleset_version: str
    standard: str
    overrides: list[str] = Field(default_factory=list)
    documented_not_implemented: list[str] = Field(default_factory=list)
    timepoints: list[ScanTimepoint]
    pairs: list[PairAssessabilityResult]
    disclaimer: str = (
        "Comparability/assessability audit only. RESEARCH PROTOTYPE - NOT FOR "
        "CLINICAL DIAGNOSIS. No biological or treatment response is assessed."
    )


def run_trial_audit(root: str | Path, ruleset: str | None = None) -> TrialAudit:
    """Audit a trial directory. ``ruleset`` overrides trial.yaml (explicit, recorded)."""
    layout = discover_trial(root)
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
                liver_spec=layout.reference_regions.get(key),
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
        timepoints=list(tps.values()),
        pairs=pairs,
    )
