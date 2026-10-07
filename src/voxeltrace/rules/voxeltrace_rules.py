"""Explicit VoxelTrace prerequisites (engineering criteria, NOT a published standard).

They deliberately exclude uptake time and injected activity, whose limits are
standard-specific and live in the selected standard's rule set.
"""

from __future__ import annotations

from voxeltrace.rules.common import check, reconstruction_identity
from voxeltrace.rules.schema import Rule
from voxeltrace.rules.sources import VT
from voxeltrace.trial.reasons import Reason, reason_for_suv_refusal
from voxeltrace.trial.schema import PairContext

VT_SUV = Rule(
    rule_id="VT-SUV-BOTH",
    name="strict SUVbw available at both timepoints",
    version="1",
    standard="VOXELTRACE",
    evidence_requirements=["timepoint.suv_status"],
    logic="both timepoints PASS the strict SUVbw validator",
    impact="blocking",
    sources=[VT],
)
VT_TRACER = Rule(
    rule_id="VT-TRACER-SAME",
    name="same tracer",
    version="1",
    standard="VOXELTRACE",
    evidence_requirements=["acquisition.radiopharmaceutical_code|tracer"],
    logic="radiopharmaceutical code meaning (else name) identical",
    impact="blocking",
    sources=[VT],
)
VT_RECON = Rule(
    rule_id="VT-PROTOCOL-IDENTITY",
    name="acquisition/reconstruction/correction identity",
    version="1",
    standard="VOXELTRACE",
    evidence_requirements=["protocol (scanner, reconstruction, corrections, voxel size)"],
    logic="VoxelTrace comparability checks restricted to scanner, units, decay correction, "
    "correction state, voxel size and reconstruction parameters (uptake/dose excluded)",
    impact="blocking",
    sources=[VT],
    limitations=["iterations/subsets/TOF/PSF may come from vendor free text"],
)


def suv_both(rule: Rule, ctx: PairContext):
    obs = {
        ctx.baseline.timepoint: ctx.baseline.suv_status,
        ctx.followup.timepoint: ctx.followup.suv_status,
    }
    if all(t.suv_status == "PASS" for t in (ctx.baseline, ctx.followup)):
        return check(rule, "PASS", obs, "PASS at both timepoints")
    reasons = [
        reason_for_suv_refusal(c, f"{t.timepoint}: {c}")
        for t in (ctx.baseline, ctx.followup)
        for c in t.suv_refusal_codes
    ] or [Reason(code="SUV_REFUSED", detail="SUV not computed", confidence="CONFIRMED")]
    return check(rule, "UNKNOWN", obs, "PASS at both timepoints", reasons=reasons)


def tracer_same(rule: Rule, ctx: PairContext):
    vals = []
    for t in (ctx.baseline, ctx.followup):
        if t.protocol is None:
            vals.append(None)
            continue
        a = t.protocol.acquisition
        f = a.radiopharmaceutical_code if a.radiopharmaceutical_code.known else a.tracer
        vals.append(str(f.value).casefold() if f.known else None)
    if None in vals:
        return check(
            rule,
            "UNKNOWN",
            vals,
            "identical tracer",
            reasons=[
                Reason(
                    code="MISSING_REQUIRED_TAG",
                    field="tracer",
                    detail="tracer unknown",
                    confidence="CONFIRMED",
                )
            ],
        )
    return check(rule, "PASS" if vals[0] == vals[1] else "FAIL", vals, "identical tracer")


VOXELTRACE_RULES = [
    (VT_SUV, suv_both),
    (VT_TRACER, tracer_same),
    (VT_RECON, reconstruction_identity),
]
