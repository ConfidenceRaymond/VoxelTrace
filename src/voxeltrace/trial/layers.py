"""Assessability layers of a pair result (reporting only; verdict logic is unchanged).

A pair verdict mixes rules of different kinds. To keep a good reference result from looking
like full assessability, the checks are reported in three layers:

  REFERENCE   rules that need a reviewed reference region (PERCIST liver rules)
  PROTOCOL    every other rule: quantitative eligibility, tracer, protocol identity,
              timing, dose, system/software, harmonisation
  OVERALL     the unchanged pair verdict (all blocking rules together)

Layer status: FAIL if any blocking check FAILs, else UNKNOWN if any blocking check is
UNKNOWN, else PASS_WITH_WARNING if a blocking check passed only on external attestation
(QIBA), else PASS (warning-level checks are listed but do not set the layer status).
"""

from __future__ import annotations

from typing import Any

REFERENCE_RULES = frozenset({"PERCIST-LIVER-SUL-STABILITY", "PERCIST-BASELINE-MEASURABLE"})


def layer_of(rule_id: str) -> str:
    return "REFERENCE" if rule_id in REFERENCE_RULES else "PROTOCOL"


def layer_status(checks: list[Any]) -> str:
    blocking = [c for c in checks if c.impact == "blocking"]
    if any(c.status == "FAIL" for c in blocking):
        return "FAIL"
    if any(c.status == "UNKNOWN" for c in blocking):
        return "UNKNOWN"
    if any(c.status == "PASS_WITH_WARNING" for c in blocking):
        return "PASS_WITH_WARNING"
    return "PASS"


def assessability_layers(pair_result: Any) -> dict[str, Any]:
    """{'REFERENCE': {...}, 'PROTOCOL': {...}, 'OVERALL': verdict} for one pair result."""
    out: dict[str, Any] = {}
    for layer in ("REFERENCE", "PROTOCOL"):
        cs = [c for c in pair_result.checks if layer_of(c.rule_id) == layer]
        out[layer] = {
            "status": layer_status(cs) if cs else "NOT_APPLICABLE",
            "checks": {c.rule_id: c.status for c in cs},
            "unresolved": sorted(
                c.rule_id
                for c in cs
                if c.impact == "blocking" and c.status not in ("PASS", "PASS_WITH_WARNING")
            ),
        }
    out["OVERALL"] = pair_result.verdict
    return out


# ------------------------------------------------------------------ PERCIST readiness layers
PERCIST_LAYERS = {
    "QUANTITATIVE": ("VT-SUV-BOTH",),
    "REFERENCE": ("PERCIST-LIVER-SUL-STABILITY",),
    "TARGET": ("PERCIST-BASELINE-MEASURABLE",),
    "PROTOCOL": (
        "VT-TRACER-SAME", "VT-PROTOCOL-IDENTITY", "PERCIST-UPTAKE-WINDOW", "PERCIST-UPTAKE-DIFF",
        "PERCIST-DOSE-DIFF", "PERCIST-SAME-SCANNER-SOFTWARE",
    ),
}  # fmt: skip


def _status(statuses: list[str]) -> str:
    if not statuses:
        return "NOT_APPLICABLE"
    if "FAIL" in statuses:
        return "FAIL"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    return "PASS"


def percist_readiness(pair_result: Any, baseline: Any, followup: Any) -> dict[str, Any]:
    """Separate PERCIST components (reporting only): QUANTITATIVE (strict SUV + SUL at both
    timepoints), REFERENCE (human-reviewed liver + liver stability), TARGET (human-reviewed
    baseline lesion + measurability), PROTOCOL (tracer, reconstruction identity, uptake, dose,
    scanner), OVERALL (the unchanged verdict). Each layer reports its own unresolved items so
    one layer never hides another."""
    if not pair_result.ruleset_id.startswith("percist"):
        return {"OVERALL": pair_result.verdict, "note": "not a PERCIST rule set"}
    checks = {c.rule_id: c for c in pair_result.checks}
    out: dict[str, Any] = {}
    for layer, rules in PERCIST_LAYERS.items():
        present = [checks[r] for r in rules if r in checks]
        detail = {c.rule_id: c.status for c in present}
        unresolved = {
            c.rule_id: sorted({r.code for r in c.reasons}) for c in present if c.status != "PASS"
        }
        extra: dict[str, Any] = {}
        statuses = [c.status for c in present if c.impact == "blocking"]
        if layer == "QUANTITATIVE":
            sul = {tp.timepoint: (tp.sul.get("LBMJAMES128").status if tp.sul.get("LBMJAMES128") else "NOT_COMPUTED")
                   for tp in (baseline, followup)}  # fmt: skip
            extra["sul_james"] = sul
            if any(v != "PASS" for v in sul.values()):
                statuses.append("UNKNOWN")
                unresolved["SUL"] = [f"{k}: {v}" for k, v in sul.items() if v != "PASS"]
        if layer == "REFERENCE":
            extra["liver_review"] = {
                tp.timepoint: (tp.liver.review_decision if tp.liver else None)
                for tp in (baseline, followup)
            }
            extra["liver_status"] = {
                tp.timepoint: (tp.liver.status if tp.liver else None) for tp in (baseline, followup)
            }
        if layer == "TARGET":
            extra["baseline_target_status"] = baseline.lesion_target_status or "NO_LESION_SUPPLIED"
            extra["lesion_segments"] = [
                {"segment": e.candidate.segment_number, "source_type": e.candidate.source_type,
                 "review_status": e.review_status, "target_eligible": e.candidate.target_eligible,
                 "used_as_target": e.used_as_target}
                for e in baseline.lesion_evidence
            ]  # fmt: skip
        out[layer] = {
            "status": _status(statuses),
            "checks": detail,
            "unresolved": unresolved,
            **extra,
        }
    out["OVERALL"] = pair_result.verdict
    out["all_rules_executed_with_evidence"] = all(
        c.status in ("PASS", "FAIL") for c in pair_result.checks if c.impact == "blocking"
    )
    return out
