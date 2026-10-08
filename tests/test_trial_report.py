"""Audit report tables: REAL and SYNTHETIC kept separate; failing fields visible."""

from voxeltrace.rules.schema import RuleCheck
from voxeltrace.trial.audit import TrialAudit
from voxeltrace.trial.reasons import Reason
from voxeltrace.trial.schema import PairAssessabilityResult, ScanPair, ScanTimepoint
from voxeltrace.trial.summary import (
    audit_report_md,
    compact_observed,
    failure_rows,
    pair_rows,
    rule_rows,
)


def check(rid, status, observed=None, reasons=()):
    return RuleCheck(
        rule_id=rid,
        rule_version="1",
        standard="VOXELTRACE",
        name=rid,
        impact="blocking",
        status=status,
        observed=observed,
        expected="cond",
        source="s",
        reasons=list(reasons),
    )


def pair(subject, verdict, checks, synthetic):
    return PairAssessabilityResult(
        pair=ScanPair(subject_id=subject, baseline="B", followup="F"),
        ruleset_id="r",
        ruleset_version="1",
        standard="QIBA_FDG_1.14",
        verdict=verdict,
        checks=checks,
        synthetic_perturbation=synthetic,
    )


R = Reason(code="AMBIGUOUS_RECONSTRUCTION", detail="x", confidence="CONFIRMED")
AUDIT = TrialAudit(
    trial_id="T",
    ruleset_id="r",
    ruleset_version="1",
    standard="QIBA_FDG_1.14",
    timepoints=[
        ScanTimepoint(subject_id="REAL1", timepoint="B", suv_status="PASS"),
        ScanTimepoint(subject_id="REAL1", timepoint="F", suv_status="PASS"),
        ScanTimepoint(subject_id="SYN1", timepoint="B", suv_status="PASS"),
        ScanTimepoint(
            subject_id="SYN1",
            timepoint="F",
            suv_status="PASS",
            synthetic_perturbation="SYNTHETIC_PERTURBATION blur",
        ),
    ],
    pairs=[
        pair("REAL1", "ASSESSABLE", [check("VT-A", "PASS")], False),
        pair(
            "SYN1",
            "NOT_ASSESSABLE",
            [
                check("VT-A", "FAIL", {"scanner": "SAME", "post_filter": "DIFFERENT"}),
                check("VT-B", "UNKNOWN", None, [R, R, R]),
            ],
            True,
        ),
    ],
)


def test_compact_observed_keeps_only_differences():
    assert compact_observed({"a": "SAME", "b": "DIFFERENT"}) == '{"b": "DIFFERENT"}'
    assert compact_observed({"x": 1.0}) == '{"x": 1.0}'


def test_pair_and_rule_rows_separate_origins():
    rows = {r["subject"]: r for r in pair_rows(AUDIT)}
    assert rows["REAL1"]["data_origin"] == "REAL"
    assert rows["SYN1"]["data_origin"] == "SYNTHETIC_PERTURBATION"
    assert rows["SYN1"]["synthetic_perturbation"] == "SYNTHETIC_PERTURBATION blur"
    assert rows["SYN1"]["blocking_fail"] == "VT-A" and rows["SYN1"]["blocking_unknown"] == "VT-B"
    rules = {(r["rule_id"], r["data_origin"]): r for r in rule_rows(AUDIT)}
    assert rules[("VT-A", "REAL")]["PASS"] == 1 and rules[("VT-A", "REAL")]["FAIL"] == 0
    assert rules[("VT-A", "SYNTHETIC_PERTURBATION")]["FAIL"] == 1  # never pooled with REAL


def test_failure_rows_classify_and_dedupe():
    rows = failure_rows(AUDIT)
    assert [r["failure_class"] for r in rows] == ["TECHNICAL", "MISSING_DATA"]
    assert rows[0]["observed"] == '{"post_filter": "DIFFERENT"}'
    assert rows[1]["reason_codes"] == "AMBIGUOUS_RECONSTRUCTION"
    assert all(r["data_origin"] == "SYNTHETIC_PERTURBATION" for r in rows)


def test_report_has_separate_sections():
    md = audit_report_md(AUDIT)
    real, syn = md.split("## REAL DATA FINDINGS")[1].split("## SYNTHETIC_PERTURBATION FINDINGS")
    # pairs never mix; a real baseline of a synthetic pair is still listed as a real scan
    assert "| REAL1 |" in real and "| SYN1 |" not in real
    assert "- SYN1/B:" in real and "- SYN1/F:" not in real
    assert "| SYN1 |" in syn and "| REAL1 |" not in syn
