"""Expert validation package: blinding, empty forms, metrics (simulated responses only)."""

from __future__ import annotations

import json

import pytest
import yaml

from test_pilot_bundle import trial
from voxeltrace.expert_validation import _kappa, export_package, score_responses
from voxeltrace.pilot import run_audit


@pytest.fixture
def package(tmp_path):
    root, _ = trial(tmp_path)
    run_audit(root, tmp_path / "out", hash_inputs=False)
    export_package(tmp_path / "out" / "audit_bundle", tmp_path / "pkg", mode="BLINDED")
    return tmp_path / "pkg"


def test_blinded_packets_hide_verdicts_and_forms_are_empty(package):
    (case,) = sorted((package / "cases").glob("*.json"))
    text = case.read_text()
    assert "voxeltrace_verdicts" not in text
    for v in ("ASSESSABLE_WITH_WARNINGS", "INSUFFICIENT_INFORMATION", "NOT_ASSESSABLE"):
        assert v not in text  # no verdict strings leak into blinded evidence
    form = yaml.safe_load((package / "responses" / "CASE-001.response.yaml").read_text())
    assert form["reviewer_id"] == "" and not any(form["independent_verdicts"].values())
    assert score_responses(package)["responses_used"] == 0  # empty forms never count


def test_unblinded_contains_verdicts(tmp_path):
    root, _ = trial(tmp_path)
    run_audit(root, tmp_path / "o", hash_inputs=False, rulesets=("qiba-fdg-1.14",))
    export_package(tmp_path / "o" / "audit_bundle", tmp_path / "u", mode="UNBLINDED")
    case = json.loads((tmp_path / "u" / "cases" / "CASE-001.json").read_text())
    assert "qiba-fdg-1.14" in case["voxeltrace_verdicts"]


def test_scoring_metrics_with_simulated_responses(package):
    key = json.loads((package / "COORDINATOR_ONLY_answer_key.json").read_text())
    vt = key["CASE-001"]["verdicts"]
    form = yaml.safe_load((package / "responses" / "CASE-001.response.yaml").read_text())
    form.update(
        reviewer_id="sim-1",
        reviewer_role="PET_PHYSICIST",
        simulated=True,
        review_time_min=12,
        independent_verdicts={rs: "NOT_ASSESSABLE" for rs in vt},
        rules_disagreed=["VT-PROTOCOL-IDENTITY"],
    )
    (package / "responses" / "CASE-001.response.yaml").write_text(yaml.safe_dump(form))
    assert score_responses(package)["responses_used"] == 0  # simulated excluded by default
    s = score_responses(package, allow_simulated=True)
    assert s["responses_used"] == 1 and s["rule_level_disagreement"] == {"VT-PROTOCOL-IDENTITY": 1}
    for rs, m in s["rulesets"].items():
        assert m["n"] == 1 and m["raw_agreement"] == (1.0 if vt[rs] == "NOT_ASSESSABLE" else 0.0)
        if vt[rs] in ("ASSESSABLE", "ASSESSABLE_WITH_WARNINGS"):
            assert m["false_safe_rate"] == 1.0
    assert s["review_time_min"]["median"] == 12


def test_kappa():
    assert _kappa([("A", "A"), ("B", "B")]) == 1.0
    assert _kappa([("A", "B"), ("B", "A")]) == -1.0
    assert _kappa([("A", "A")]) is None
