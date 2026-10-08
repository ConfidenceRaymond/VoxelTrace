"""PERCIST 1.0 (Wahl et al. 2009) with Practical PERCIST (O, Lodge, Wahl 2016) boundary
definitions. Only rules with verified text are implemented. SUL uses LBMJAMES128 as suggested
by Practical PERCIST (PERCIST 1.0 itself gives no LBM equation)."""

from __future__ import annotations

from voxeltrace.rules.common import check, same_system, uptake_difference, uptake_window
from voxeltrace.rules.schema import Rule
from voxeltrace.rules.sources import (
    PERCIST_DOSE,
    PERCIST_EQUIP,
    PERCIST_LIVER,
    PERCIST_MEASURABLE,
    PERCIST_UPTAKE,
    PPERCIST_UPTAKE,
)
from voxeltrace.trial.reasons import Reason
from voxeltrace.trial.reference import reference_reason
from voxeltrace.trial.schema import PairContext, ScanTimepoint

V = "PERCIST-1.0/PRACTICAL-2016"
SUL_FORMULA = "LBMJAMES128"

UPTAKE_WINDOW = Rule(
    rule_id="PERCIST-UPTAKE-WINDOW",
    name="injection-to-imaging 50-70 min",
    version=V,
    standard="PERCIST_1.0",
    evidence_requirements=["timepoint.uptake_s"],
    logic="50 <= uptake <= 70 min at each timepoint (Practical PERCIST)",
    parameters={"min_min": 50.0, "max_min": 70.0},
    impact="warning",
    sources=[PPERCIST_UPTAKE],
)
UPTAKE_DIFF = Rule(
    rule_id="PERCIST-UPTAKE-DIFF",
    name="uptake times within 15 min (assessability)",
    version=V,
    standard="PERCIST_1.0",
    evidence_requirements=["timepoint.uptake_s"],
    logic="|follow-up - baseline| <= 15 min and no scan before 50 min",
    parameters={"max_diff_min": 15.0, "min_start_min": 50.0},
    impact="blocking",
    sources=[PERCIST_UPTAKE, PPERCIST_UPTAKE],
)
LIVER = Rule(
    rule_id="PERCIST-LIVER-SUL-STABILITY",
    name="liver SULmean stable (assessability)",
    version=V,
    standard="PERCIST_1.0",
    evidence_requirements=[
        "liver reference region (3 cm sphere) at both timepoints",
        f"SUL ({SUL_FORMULA})",
    ],
    logic="|delta liver SULmean| <= 20 % of the larger AND <= 0.3 SUL units",
    parameters={"rel_of_larger": 0.20, "abs_sul": 0.3},
    impact="blocking",
    sources=[PERCIST_LIVER],
    assumptions=[
        "liver region supplied (mask or reviewed centre) or an automatic proposal accepted or "
        "adjusted by a reviewer; unreviewed proposals are never used"
    ],
)
DOSE = Rule(
    rule_id="PERCIST-DOSE-DIFF",
    name="injected dose within 20 %",
    version=V,
    standard="PERCIST_1.0",
    evidence_requirements=["RadionuclideTotalDose"],
    logic="|follow-up - baseline| / baseline <= 0.20",
    parameters={"max_rel": 0.20},
    impact="warning",
    sources=[PERCIST_DOSE],
    assumptions=[
        "the 20 % is taken relative to the baseline dose (the source does not state "
        "'of the larger' for dose)"
    ],
)
EQUIP = Rule(
    rule_id="PERCIST-SAME-SCANNER-SOFTWARE",
    name="same scanner model and software",
    version=V,
    standard="PERCIST_1.0",
    evidence_requirements=["scanner model", "software version"],
    logic="same manufacturer/model and software version",
    impact="warning",
    sources=[PERCIST_EQUIP],
)
MEASURABLE = Rule(
    rule_id="PERCIST-BASELINE-MEASURABLE",
    name="baseline target metabolically measurable",
    version=V,
    standard="PERCIST_1.0",
    evidence_requirements=["baseline lesion SULpeak", "baseline liver SULmean and SD"],
    logic="baseline SULpeak >= 1.5 x liver SULmean + 2 x liver SD",
    parameters={"factor": 1.5, "sd_factor": 2.0},
    impact="blocking",
    sources=[PERCIST_MEASURABLE],
    limitations=[
        "blood-pool fallback not implemented (PERCIST 1.0 text and table disagree on "
        "the +2 SD term)"
    ],
)


def _liver_sul(tp: ScanTimepoint):
    r = reference_reason(tp.timepoint, tp.liver, "LIVER", subject=tp.subject_id)
    if r is not None:
        return None, r
    assert tp.liver is not None
    if tp.liver.sul_mean is None:
        sul = tp.sul.get(SUL_FORMULA)
        refs = ", ".join(r.code for r in sul.refusals) if sul else "SUL not computed"
        return None, Reason(
            code="ANTHROPOMETRICS_MISSING",
            field=f"{tp.timepoint}.SUL",
            detail=refs,
            confidence="CONFIRMED",
        )
    return tp.liver, None


def liver_stability(rule: Rule, ctx: PairContext):
    vals, reasons = [], []
    for tp in (ctx.baseline, ctx.followup):
        lv, r = _liver_sul(tp)
        vals.append(lv.sul_mean if lv else None)
        if r:
            reasons.append(r)
    exp = "|delta| <= 0.20 x larger and <= 0.3 SUL"
    if reasons:
        return check(rule, "UNKNOWN", vals, exp, reasons=reasons)
    d = abs(vals[1] - vals[0])
    eps = 1e-9  # floating-point representation tolerance for the inclusive boundaries
    ok = (
        d <= rule.parameters["rel_of_larger"] * max(vals) + eps
        and d <= rule.parameters["abs_sul"] + eps
    )
    return check(rule, "PASS" if ok else "FAIL", {"liver_sul_mean": vals, "abs_delta": d}, exp)


def dose_diff(rule: Rule, ctx: PairContext):
    b, f = ctx.baseline.injected_bq, ctx.followup.injected_bq
    if not b or not f:
        return check(
            rule,
            "UNKNOWN",
            [b, f],
            "|delta|/baseline <= 20 %",
            reasons=[
                Reason(
                    code="MISSING_REQUIRED_TAG",
                    field="RadionuclideTotalDose",
                    detail="injected activity unavailable",
                    confidence="CONFIRMED",
                )
            ],
        )
    rel = abs(f - b) / b
    return check(
        rule,
        "PASS" if rel <= rule.parameters["max_rel"] else "FAIL",
        {"relative_difference": round(rel, 4)},
        "|delta|/baseline <= 20 %",
    )


def baseline_measurable(rule: Rule, ctx: PairContext):
    b = ctx.baseline
    lv, r = _liver_sul(b)
    sul = b.sul.get(SUL_FORMULA)
    if r or sul is None or sul.status != "PASS" or b.lesion_suvpeak is None or not b.weight_kg:
        reasons = [r] if r else []
        if b.lesion_suvpeak is None:
            reasons.append(
                Reason(
                    code="MISSING_REQUIRED_TAG",
                    field="baseline SULpeak",
                    detail="no measured baseline lesion SUVpeak",
                    confidence="CONFIRMED",
                )
            )
        return check(
            rule,
            "UNKNOWN",
            None,
            "SULpeak >= 1.5 x liver mean + 2 SD",
            reasons=reasons
            or [
                Reason(
                    code="ANTHROPOMETRICS_MISSING",
                    detail="SUL not available",
                    confidence="CONFIRMED",
                )
            ],
        )
    sulpeak = b.lesion_suvpeak * sul.lbm_kg / b.weight_kg  # type: ignore[operator]
    thr = rule.parameters["factor"] * lv.sul_mean + rule.parameters["sd_factor"] * lv.sul_sd
    return check(
        rule,
        "PASS" if sulpeak >= thr else "FAIL",
        {"baseline_sulpeak": sulpeak, "threshold": thr},
        "SULpeak >= 1.5 x liver mean + 2 SD",
    )


RULES = [
    (UPTAKE_WINDOW, uptake_window),
    (UPTAKE_DIFF, uptake_difference),
    (LIVER, liver_stability),
    (DOSE, dose_diff),
    (EQUIP, lambda r, c: same_system(r, c, software=True)),
    (MEASURABLE, baseline_measurable),
]
DOCUMENTED_NOT_IMPLEMENTED = [
    "Blood-pool fallback (descending aorta 1 cm x 2 cm): PERCIST 1.0 inconsistent on +2 SD",
    "Fasting >= 4-6 h, glucose < 200 mg/dL: not in image metadata",
    "Response categories (CMR/PMR/SMD/PMD, -30 % and 0.8 SUL): response-level, out of scope",
]
