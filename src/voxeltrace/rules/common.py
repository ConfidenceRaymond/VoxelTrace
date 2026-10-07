"""Shared deterministic checks used by the standard-specific rule modules."""

from __future__ import annotations

from voxeltrace.evidence.comparability import compare_protocols
from voxeltrace.rules.schema import CheckStatus, Rule, RuleCheck
from voxeltrace.trial.reasons import Reason
from voxeltrace.trial.schema import PairContext, ScanTimepoint


def check(
    rule: Rule,
    status: CheckStatus,
    observed,
    expected: str,
    message: str = "",
    reasons: list[Reason] | None = None,
) -> RuleCheck:
    src = "; ".join(f"{s.citation} [{s.locator}]" for s in rule.sources)
    return RuleCheck(
        rule_id=rule.rule_id,
        rule_version=rule.version,
        standard=rule.standard,
        name=rule.name,
        impact=rule.impact,
        status=status,
        observed=observed,
        expected=expected,
        source=src,
        message=message,
        reasons=reasons or [],
    )


def _uptake_missing(tp: ScanTimepoint) -> Reason:
    if tp.suv_status == "REFUSED":
        return Reason(
            code="SUV_REFUSED",
            field=f"{tp.timepoint}.uptake",
            detail="strict SUV/timing refused: " + ", ".join(tp.suv_refusal_codes),
            confidence="CONFIRMED",
            evidence_basis="strict SUV validator",
        )
    return Reason(
        code="AMBIGUOUS_TIMING",
        field=f"{tp.timepoint}.uptake",
        detail="validated uptake interval unavailable",
        confidence="CONFIRMED",
        evidence_basis="strict SUV timing validator",
    )


def uptake_window(rule: Rule, ctx: PairContext) -> RuleCheck:
    lo, hi = rule.parameters["min_min"], rule.parameters["max_min"]
    obs, missing, out = {}, [], []
    for tp in (ctx.baseline, ctx.followup):
        if tp.uptake_s is None:
            missing.append(_uptake_missing(tp))
            continue
        m = tp.uptake_s / 60.0
        obs[tp.timepoint] = round(m, 2)
        if not lo <= m <= hi:
            out.append(tp.timepoint)
    exp = f"{lo} <= uptake <= {hi} min at every timepoint"
    if out:
        return check(rule, "FAIL", obs, exp, f"outside window: {out}")
    if missing:
        return check(rule, "UNKNOWN", obs, exp, reasons=missing)
    return check(rule, "PASS", obs, exp)


def uptake_difference(rule: Rule, ctx: PairContext) -> RuleCheck:
    max_d = rule.parameters["max_diff_min"]
    min_start = rule.parameters.get("min_start_min")
    b, f = ctx.baseline, ctx.followup
    exp = f"|follow-up - baseline| <= {max_d} min" + (
        f" and every scan >= {min_start} min" if min_start else ""
    )
    if b.uptake_s is None or f.uptake_s is None:
        return check(
            rule,
            "UNKNOWN",
            None,
            exp,
            reasons=[_uptake_missing(t) for t in (b, f) if t.uptake_s is None],
        )
    d = (f.uptake_s - b.uptake_s) / 60.0
    obs = {
        "difference_min": round(d, 2),
        "baseline_min": round(b.uptake_s / 60, 2),
        "followup_min": round(f.uptake_s / 60, 2),
    }
    if abs(d) > max_d or (min_start and min(b.uptake_s, f.uptake_s) / 60.0 < min_start):
        return check(rule, "FAIL", obs, exp)
    return check(rule, "PASS", obs, exp)


def same_system(rule: Rule, ctx: PairContext, *, software: bool) -> RuleCheck:
    b, f = ctx.baseline, ctx.followup
    if b.protocol is None or f.protocol is None:
        return check(
            rule,
            "UNKNOWN",
            None,
            "same scanner",
            reasons=[
                Reason(
                    code="MISSING_REQUIRED_TAG",
                    detail="protocol evidence unavailable",
                    confidence="CONFIRMED",
                )
            ],
        )
    keys = [("manufacturer", "scanner.manufacturer"), ("manufacturer_model_name", "scanner.model")]
    obs, unknown, diff = {}, [], []
    for attr, label in keys:
        fa, fb = getattr(b.protocol.scanner, attr), getattr(f.protocol.scanner, attr)
        obs[label] = [fa.value, fb.value]
        if not (fa.known and fb.known):
            unknown.append(label)
        elif str(fa.value).casefold() != str(fb.value).casefold():
            diff.append(label)
    if software:
        sa, sb = b.protocol.scanner.software_versions, f.protocol.scanner.software_versions
        obs["software"] = [sa.value, sb.value]
        if not (sa.known and sb.known):
            unknown.append("software")
        elif sa.value != sb.value:
            diff.append("software")
    exp = "same scanner manufacturer/model" + (" and software version" if software else "")
    if diff:
        return check(rule, "FAIL", obs, exp, f"differs: {diff}")
    if unknown:
        return check(
            rule,
            "UNKNOWN",
            obs,
            exp,
            reasons=[
                Reason(
                    code="MISSING_REQUIRED_TAG",
                    field=u,
                    detail=f"{u} unknown",
                    confidence="CONFIRMED",
                )
                for u in unknown
            ],
        )
    return check(rule, "PASS", obs, exp)


RECON_CHECKS = (
    "manufacturer",
    "scanner_model",
    "image_units",
    "decay_correction",
    "correction_state",
    "voxel_size",
    "reconstruction_method",
    "iterations",
    "subsets",
    "time_of_flight",
    "psf_resolution_modelling",
    "post_filter",
)


def reconstruction_identity(rule: Rule, ctx: PairContext) -> RuleCheck:
    b, f = ctx.baseline, ctx.followup
    exp = "identical acquisition/reconstruction/correction settings: " + ", ".join(RECON_CHECKS)
    if b.protocol is None or f.protocol is None:
        return check(
            rule,
            "UNKNOWN",
            None,
            exp,
            reasons=[
                Reason(
                    code="MISSING_REQUIRED_TAG",
                    detail="protocol evidence unavailable",
                    confidence="CONFIRMED",
                )
            ],
        )
    cmp = compare_protocols(b.protocol, f.protocol)
    sel = [c for c in cmp.checks if c.name in RECON_CHECKS]
    obs = {c.name: c.result for c in sel}
    diff = [c.name for c in sel if c.result == "DIFFERENT"]
    unk = [c.name for c in sel if c.result == "UNKNOWN"]
    if diff:
        return check(rule, "FAIL", obs, exp, f"differs: {diff}")
    if unk:
        code = (
            "AMBIGUOUS_RECONSTRUCTION"
            if any(
                u
                in (
                    "reconstruction_method",
                    "iterations",
                    "subsets",
                    "time_of_flight",
                    "psf_resolution_modelling",
                    "post_filter",
                )
                for u in unk
            )
            else "MISSING_REQUIRED_TAG"
        )
        return check(
            rule,
            "UNKNOWN",
            obs,
            exp,
            f"unknown: {unk}",
            reasons=[
                Reason(
                    code=code,
                    field=u,
                    detail=f"{u} unknown on at least one timepoint",
                    confidence="CONFIRMED",
                )
                for u in unk
            ],
        )
    return check(rule, "PASS", obs, exp)
