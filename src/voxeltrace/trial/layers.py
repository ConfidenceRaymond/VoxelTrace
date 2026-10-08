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
