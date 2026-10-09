"""PERCIST readiness layers are reporting only: they never change the verdict."""

from types import SimpleNamespace as NS

from voxeltrace.trial.layers import percist_readiness


def _check(rule, status, code=None):
    return NS(
        rule_id=rule, status=status, impact="blocking", reasons=[NS(code=code)] if code else []
    )


def _tp(name, sul="PASS", target=None):
    return NS(timepoint=name, sul={"LBMJAMES128": NS(status=sul)}, liver=NS(review_decision="ACCEPT", status="PASS"),
              lesion_target_status=target, lesion_evidence=[])  # fmt: skip


def _pair(checks, verdict):
    return NS(ruleset_id="percist-1.0", checks=checks, verdict=verdict)


ALL_PASS = [
    _check(r, "PASS")
    for r in ("VT-SUV-BOTH", "PERCIST-LIVER-SUL-STABILITY", "PERCIST-BASELINE-MEASURABLE", "VT-TRACER-SAME",
              "VT-PROTOCOL-IDENTITY", "PERCIST-UPTAKE-WINDOW", "PERCIST-UPTAKE-DIFF", "PERCIST-DOSE-DIFF")
]  # fmt: skip


def test_all_layers_pass_and_overall_is_unchanged_verdict():
    r = percist_readiness(
        _pair(ALL_PASS, "ASSESSABLE"), _tp("baseline", target="REVIEWED_TARGET"), _tp("followup")
    )
    assert [r[k]["status"] for k in ("QUANTITATIVE", "REFERENCE", "TARGET", "PROTOCOL")] == [
        "PASS"
    ] * 4
    assert r["OVERALL"] == "ASSESSABLE" and r["all_rules_executed_with_evidence"]


def test_unreviewed_target_is_isolated_to_target_layer():
    checks = [c for c in ALL_PASS if c.rule_id != "PERCIST-BASELINE-MEASURABLE"]
    checks.append(_check("PERCIST-BASELINE-MEASURABLE", "UNKNOWN", "LESION_REVIEW_REQUIRED"))
    r = percist_readiness(
        _pair(checks, "INSUFFICIENT_INFORMATION"),
        _tp("baseline", target="LESION_REVIEW_REQUIRED:UNREVIEWED"),
        _tp("followup"),
    )
    assert r["TARGET"]["status"] == "UNKNOWN" and r["PROTOCOL"]["status"] == "PASS"
    assert r["TARGET"]["unresolved"] == {"PERCIST-BASELINE-MEASURABLE": ["LESION_REVIEW_REQUIRED"]}
    assert r["OVERALL"] == "INSUFFICIENT_INFORMATION" and not r["all_rules_executed_with_evidence"]


def test_fail_dominates_and_missing_sul_makes_quantitative_unknown():
    checks = [c for c in ALL_PASS if c.rule_id != "PERCIST-UPTAKE-DIFF"] + [
        _check("PERCIST-UPTAKE-DIFF", "FAIL", "X")
    ]
    r = percist_readiness(
        _pair(checks, "NOT_ASSESSABLE"), _tp("baseline", sul="REFUSED"), _tp("followup")
    )
    assert r["PROTOCOL"]["status"] == "FAIL" and r["QUANTITATIVE"]["status"] == "UNKNOWN"
    assert r["OVERALL"] == "NOT_ASSESSABLE"


def test_non_percist_ruleset_reports_overall_only():
    r = percist_readiness(
        NS(ruleset_id="qiba-fdg-1.14", checks=[], verdict="ASSESSABLE"), None, None
    )
    assert r == {"OVERALL": "ASSESSABLE", "note": "not a PERCIST rule set"}
