"""Assessability layers keep reference and protocol evidence separate."""

from voxeltrace.rules.schema import RuleCheck
from voxeltrace.trial.layers import assessability_layers, layer_of
from voxeltrace.trial.schema import PairAssessabilityResult, ScanPair


def check(rid, status, impact="blocking"):
    return RuleCheck(
        rule_id=rid,
        rule_version="1",
        standard="PERCIST_1.0",
        name=rid,
        impact=impact,
        status=status,
        expected="",
        source="",
    )


def result(verdict, checks):
    return PairAssessabilityResult(
        pair=ScanPair(subject_id="S", baseline="B", followup="F"),
        ruleset_id="percist-1.0",
        ruleset_version="1",
        standard="PERCIST_1.0",
        verdict=verdict,
        checks=checks,
    )


def test_layer_mapping():
    assert layer_of("PERCIST-LIVER-SUL-STABILITY") == "REFERENCE"
    assert layer_of("PERCIST-BASELINE-MEASURABLE") == "REFERENCE"
    assert layer_of("VT-PROTOCOL-IDENTITY") == "PROTOCOL"
    assert layer_of("QIBA-UPTAKE-DIFF") == "PROTOCOL"


def test_good_reference_does_not_hide_unknown_protocol():
    r = result(
        "INSUFFICIENT_INFORMATION",
        [
            check("PERCIST-LIVER-SUL-STABILITY", "PASS"),
            check("PERCIST-BASELINE-MEASURABLE", "PASS"),
            check("VT-PROTOCOL-IDENTITY", "UNKNOWN"),
            check("PERCIST-UPTAKE-DIFF", "PASS"),
            check("PERCIST-DOSE-DIFF", "UNKNOWN", impact="warning"),
        ],
    )
    layers = assessability_layers(r)
    assert layers["REFERENCE"]["status"] == "PASS"
    assert layers["PROTOCOL"]["status"] == "UNKNOWN"
    assert layers["PROTOCOL"]["unresolved"] == ["VT-PROTOCOL-IDENTITY"]
    assert layers["OVERALL"] == "INSUFFICIENT_INFORMATION"


def test_fail_dominates_unknown_and_no_reference_rules():
    r = result(
        "NOT_ASSESSABLE",
        [check("QIBA-UPTAKE-DIFF", "FAIL"), check("VT-PROTOCOL-IDENTITY", "UNKNOWN")],
    )
    layers = assessability_layers(r)
    assert layers["PROTOCOL"]["status"] == "FAIL"
    assert layers["REFERENCE"]["status"] == "NOT_APPLICABLE"
