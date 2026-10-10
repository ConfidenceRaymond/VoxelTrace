"""Reviewer-form scoring safeguards, exercised ONLY with SYNTHETIC_TEST_ONLY forms written into
temporary directories. Nothing here is, or may be presented as, a real expert review."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
import yaml

from voxeltrace.expert_validation import SYNTHETIC_MARK, is_synthetic, score_responses

REPO = Path(__file__).resolve().parents[1]
RS = ["eanm-fdg-2.0", "percist-1.0", "qiba-fdg-1.14"]
KEY = {
    "CASE-001": {"pair": ["S1", "baseline", "followup"], "verdicts": {"qiba-fdg-1.14": "ASSESSABLE", "eanm-fdg-2.0": "ASSESSABLE_WITH_WARNINGS", "percist-1.0": "INSUFFICIENT_INFORMATION"}},
    "CASE-002": {"pair": ["S2", "baseline", "followup"], "verdicts": {"qiba-fdg-1.14": "NOT_ASSESSABLE", "eanm-fdg-2.0": "NOT_ASSESSABLE", "percist-1.0": "NOT_ASSESSABLE"}},
    "CASE-003": {"pair": ["S3", "baseline", "followup"], "verdicts": {"qiba-fdg-1.14": "INSUFFICIENT_INFORMATION", "eanm-fdg-2.0": "INSUFFICIENT_INFORMATION", "percist-1.0": "INSUFFICIENT_INFORMATION"}},
}  # fmt: skip


def pkg(tmp_path):
    p = tmp_path / "SYNTHETIC_TEST_ONLY_package"
    (p / "responses").mkdir(parents=True)
    (p / "COORDINATOR_ONLY_answer_key.json").write_text(json.dumps(KEY))
    return p


def form(p, name, case, verdicts, reviewer=f"{SYNTHETIC_MARK}-R1", **kw):
    f = {"schema": "VT-EXPERT-VALIDATION-1", "case_id": case, "reviewer_id": reviewer, "reviewer_role": "PET_PHYSICIST",
         "independent_verdicts": verdicts, "confidence": "medium", "review_time_min": 10, "simulated": True,
         "synthetic_test_only": True, **kw}  # fmt: skip
    (p / "responses" / f"{name}.response.yaml").write_text(yaml.safe_dump(f))


def all_rs(v):
    return dict.fromkeys(RS, v)


def test_exact_weighted_kappa_false_safe_and_ii(tmp_path):
    p = pkg(tmp_path)
    form(
        p,
        "a",
        "CASE-001",
        {
            "qiba-fdg-1.14": "NOT_ASSESSABLE",
            "eanm-fdg-2.0": "ASSESSABLE_WITH_WARNINGS",
            "percist-1.0": "INSUFFICIENT_INFORMATION",
        },
    )
    form(p, "b", "CASE-002", all_rs("NOT_ASSESSABLE"))
    form(p, "c", "CASE-003", all_rs("ASSESSABLE"))
    s = score_responses(p, allow_simulated=True)
    assert s["evidence_class"] == SYNTHETIC_MARK and s["responses_used"] == 3
    q = s["rulesets"]["qiba-fdg-1.14"]
    assert q["n"] == 3 and q["raw_agreement"] == round(1 / 3, 4)
    assert (
        q["false_safe"]["CRITICAL"] == 1 and q["false_safe"]["total"] == 1
    )  # VT ASSESSABLE vs expert NA
    assert q["false_unsafe_count"] == 1  # VT II vs expert ASSESSABLE
    assert q["cohens_kappa"] is not None and q["weighted_kappa_linear"] is not None
    assert 0 <= q["weighted_agreement"] <= 1
    e = s["rulesets"]["eanm-fdg-2.0"]
    assert e["ii_agreement"]["voxeltrace_only"] == 1
    assert s["rulesets"]["percist-1.0"]["ii_agreement"]["both"] == 1
    assert s["review_time_min"] == {"median": 10.0, "min": 10.0, "max": 10.0, "n": 3, "total": 30.0}
    assert s["confidence_counts"] == {"medium": 3}


def test_missing_duplicate_conflicting_malformed_and_abstention(tmp_path):
    p = pkg(tmp_path)
    form(p, "a", "CASE-001", all_rs("ASSESSABLE"))
    form(p, "a_copy", "CASE-001", all_rs("ASSESSABLE"))  # identical duplicate -> counted once
    form(p, "b1", "CASE-002", all_rs("NOT_ASSESSABLE"))
    form(p, "b2", "CASE-002", all_rs("ASSESSABLE"))  # same reviewer, different answer -> conflict
    (p / "responses" / "broken.response.yaml").write_text("case_id: [unclosed\n")
    form(p, "badverdict", "CASE-003", all_rs("MAYBE"), reviewer=f"{SYNTHETIC_MARK}-R2")
    form(p, "unknown", "CASE-999", all_rs("ASSESSABLE"), reviewer=f"{SYNTHETIC_MARK}-R3")
    form(
        p,
        "badconf",
        "CASE-003",
        all_rs("ASSESSABLE"),
        reviewer=f"{SYNTHETIC_MARK}-R4",
        confidence="certain",
    )
    form(p, "abst", "CASE-003", all_rs("UNABLE_TO_DECIDE"), reviewer=f"{SYNTHETIC_MARK}-R5")
    s = score_responses(p, allow_simulated=True)
    f = s["forms"]
    assert len(f["duplicates"]) == 1 and len(f["conflicts"]) == 1
    reasons = " ".join(r["reason"] for r in f["rejected"])
    for code in ("MALFORMED_YAML", "INVALID_VERDICT", "UNKNOWN_CASE", "INVALID_CONFIDENCE"):
        assert code in reasons
    assert s["responses_used"] == 2  # CASE-001 once + the abstaining CASE-003 form
    assert "CASE-002" in s["missing_cases"]  # the conflicting pair is not used
    q = s["rulesets"]["qiba-fdg-1.14"]
    assert q["n"] == 1 and q["abstentions"] == 1  # abstention never counts as agreement


def test_inter_reviewer_agreement(tmp_path):
    p = pkg(tmp_path)
    form(p, "r1", "CASE-002", all_rs("NOT_ASSESSABLE"))
    form(p, "r2", "CASE-002", all_rs("NOT_ASSESSABLE"), reviewer=f"{SYNTHETIC_MARK}-R2")
    form(p, "r3", "CASE-003", all_rs("INSUFFICIENT_INFORMATION"))
    form(p, "r4", "CASE-003", all_rs("ASSESSABLE"), reviewer=f"{SYNTHETIC_MARK}-R2")
    ir = score_responses(p, allow_simulated=True)["rulesets"]["qiba-fdg-1.14"]["inter_reviewer"]
    assert ir == {"cases_with_multiple_reviewers": 2, "unanimous": 1}


def test_synthetic_forms_are_never_scored_as_real(tmp_path):
    p = pkg(tmp_path)
    form(p, "a", "CASE-001", all_rs("ASSESSABLE"))
    s = score_responses(p)  # real scoring
    assert s["responses_used"] == 0 and s["evidence_class"] == "NONE"
    assert s["forms"]["synthetic_excluded"] == 1
    # a synthetic form without the simulated flag is still recognised by its reviewer id
    assert is_synthetic({"reviewer_id": f"{SYNTHETIC_MARK}-X"}) and not is_synthetic(
        {"reviewer_id": "R1"}
    )


def test_synthetic_and_real_forms_are_never_mixed(tmp_path):
    p = pkg(tmp_path)
    form(p, "syn", "CASE-001", all_rs("ASSESSABLE"))
    form(
        p,
        "real",
        "CASE-002",
        all_rs("NOT_ASSESSABLE"),
        reviewer="R-REAL",
        simulated=False,
        synthetic_test_only=False,
    )
    with pytest.raises(ValueError, match="together"):
        score_responses(p, allow_simulated=True)
    s = score_responses(p)
    assert s["evidence_class"] == "REAL_REVIEWER_FORMS" and s["responses_used"] == 1
    assert s["forms"]["synthetic_excluded"] == 1


def test_no_synthetic_form_in_real_validation_material():
    """Tracked real validation material, and the frozen blinded package if present, must not
    contain synthetic reviewer forms or filled forms of any kind."""
    tracked = subprocess.run(["git", "ls-files", "docs/external_validation", "docs/pilot/external_partner"],
                             cwd=REPO, capture_output=True, text=True, check=True).stdout.split()  # fmt: skip
    hits = [f for f in tracked if SYNTHETIC_MARK in (REPO / f).read_text(errors="ignore")
            and "SYNTHETIC_TEST_ONLY forms" not in (REPO / f).read_text(errors="ignore")]  # fmt: skip
    assert hits == []
    real = (
        REPO.parent / "outputs" / "external_validation_cohort_v1" / "package_blinded" / "responses"
    )
    if real.is_dir():
        for f in sorted(real.glob("*.response.yaml")):
            d = yaml.safe_load(f.read_text())
            assert not is_synthetic(d), f
            assert not d.get("reviewer_id") and not any(d["independent_verdicts"].values()), (
                f"{f} is filled"
            )
