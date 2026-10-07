"""QIBA FDG-PET/CT Profile v1.14 longitudinal rules (only those with verified text)."""

from __future__ import annotations

from voxeltrace.rules.common import same_system, uptake_difference, uptake_window
from voxeltrace.rules.schema import Rule
from voxeltrace.rules.sources import QIBA_SYSTEM, QIBA_TIMING

V = "QIBA-FDG-PETCT-1.14"

UPTAKE_WINDOW = Rule(
    rule_id="QIBA-UPTAKE-WINDOW",
    name="uptake time within acceptable window",
    version=V,
    standard="QIBA_FDG_PETCT_1.14",
    scope="pair",
    evidence_requirements=["timepoint.uptake_s (strict timing)"],
    logic="55 <= uptake <= 75 min at each timepoint",
    parameters={"min_min": 55.0, "max_min": 75.0},
    impact="blocking",
    sources=[QIBA_TIMING],
)
UPTAKE_DIFF = Rule(
    rule_id="QIBA-UPTAKE-DIFF",
    name="follow-up uptake within +/-10 min of baseline",
    version=V,
    standard="QIBA_FDG_PETCT_1.14",
    evidence_requirements=["timepoint.uptake_s (strict timing)"],
    logic="|follow-up - baseline| <= 10 min and no scan before 55 min",
    parameters={"max_diff_min": 10.0, "min_start_min": 55.0},
    impact="blocking",
    sources=[QIBA_TIMING],
    limitations=[
        "the Profile notes a majority view that +/-5 min is better; trials may "
        "tighten via an explicit override"
    ],
)
SAME_SYSTEM = Rule(
    rule_id="QIBA-SAME-SYSTEM",
    name="same PET/CT system and software version",
    version=V,
    standard="QIBA_FDG_PETCT_1.14",
    evidence_requirements=["scanner model", "software version"],
    logic="same manufacturer/model and software version (strongly recommended)",
    impact="warning",
    sources=[QIBA_SYSTEM],
)

RULES = [
    (UPTAKE_WINDOW, uptake_window),
    (UPTAKE_DIFF, uptake_difference),
    (SAME_SYSTEM, lambda r, c: same_system(r, c, software=True)),
]
DOCUMENTED_NOT_IMPLEMENTED = [
    "QIBA Claim (wCV 10-12 %, -28 %/+39 % for true change) applies to tumours >= 2 cm with "
    "baseline SUVmax >= 4 g/mL, single-centre same scanner: response-level, not evaluated",
    "Liver ROI (3 cm sphere) used for QC only; the Profile sets no numeric liver-change limit",
    "Serum glucose: study-specified; not available in image metadata",
]
