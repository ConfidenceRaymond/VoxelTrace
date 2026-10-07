"""EANM FDG PET/CT procedure guideline v2.0 longitudinal rules (verified text only)."""

from __future__ import annotations

from voxeltrace.rules.common import check, reconstruction_identity, uptake_difference, uptake_window
from voxeltrace.rules.schema import Rule
from voxeltrace.rules.sources import EANM_EARL, EANM_TIMING
from voxeltrace.trial.reasons import Reason
from voxeltrace.trial.schema import PairContext

V = "EANM-FDG-2.0"

UPTAKE_WINDOW = Rule(
    rule_id="EANM-UPTAKE-WINDOW",
    name="uptake within acceptable range",
    version=V,
    standard="EANM_FDG_2.0",
    evidence_requirements=["timepoint.uptake_s"],
    logic="55 <= uptake <= 75 min at each timepoint",
    parameters={"min_min": 55.0, "max_min": 75.0},
    impact="blocking",
    sources=[EANM_TIMING],
)
UPTAKE_DIFF = Rule(
    rule_id="EANM-UPTAKE-DIFF",
    name="same uptake interval to within 10 min",
    version=V,
    standard="EANM_FDG_2.0",
    evidence_requirements=["timepoint.uptake_s"],
    logic="|follow-up - baseline| <= 10 min",
    parameters={"max_diff_min": 10.0},
    impact="blocking",
    sources=[EANM_TIMING],
    limitations=["5 min applies only to limited-view longitudinal imaging (not modelled)"],
)
SAME_SETTINGS = Rule(
    rule_id="EANM-SAME-SYSTEM-SETTINGS",
    name="same system, identical acquisition and reconstruction settings",
    version=V,
    standard="EANM_FDG_2.0",
    evidence_requirements=["protocol"],
    logic="scanner and reconstruction identity",
    impact="blocking",
    sources=[EANM_TIMING],
)
EARL = Rule(
    rule_id="EANM-EARL-RECON",
    name="EARL-approved reconstruction",
    version=V,
    standard="EANM_FDG_2.0",
    evidence_requirements=["trial override: site EARL flag"],
    logic="site/reconstruction declared EARL-approved in the trial configuration",
    impact="warning",
    sources=[EANM_EARL],
    limitations=["EARL status is not encoded in DICOM; must come from trial configuration"],
)


def earl(rule: Rule, ctx: PairContext):
    flag = ctx.site_flags.get("earl_approved_reconstruction")
    if flag is None:
        return check(
            rule,
            "UNKNOWN",
            None,
            "EARL-approved reconstruction declared",
            reasons=[
                Reason(
                    code="NEVER_ENCODED",
                    field="EARL status",
                    detail="EARL approval is not a DICOM attribute; supply it "
                    "in the trial configuration",
                    confidence="CONFIRMED",
                    evidence_basis="not part of the DICOM PET IOD",
                )
            ],
        )
    return check(rule, "PASS" if flag else "FAIL", flag, "EARL-approved reconstruction")


RULES = [
    (UPTAKE_WINDOW, uptake_window),
    (UPTAKE_DIFF, uptake_difference),
    (SAME_SETTINGS, reconstruction_identity),
    (EARL, earl),
]
DOCUMENTED_NOT_IMPLEMENTED = [
    "Plasma glucose < 11 mmol/L (clinical) / research range: not in image metadata",
    "Janmahasatian LBM (SUL) is the EANM formula (LBMJANMA) when SUL is needed",
]
