"""Audit top page, deterministic executive summary and reproducible PDF."""

from __future__ import annotations

import json
import re

from test_pilot_bundle import trial
from voxeltrace.executive import executive_summary
from voxeltrace.pdf import markdown_to_pdf
from voxeltrace.pilot import run_audit


def test_bundle_has_top_page_summary_and_reproducible_pdf(tmp_path):
    root, _ = trial(tmp_path)
    run_audit(root, tmp_path / "a", hash_inputs=False)
    run_audit(root, tmp_path / "b", hash_inputs=False)
    ra, rb = (
        tmp_path / "a" / "audit_bundle" / "reports",
        tmp_path / "b" / "audit_bundle" / "reports",
    )
    page = json.loads((ra / "executive_summary.json").read_text())
    assert page["pairs"] >= 1 and set(page["verdicts"]) >= {"qiba-fdg-1.14"}
    for t in page["top_failure_reasons"]:
        assert t["recommendation"] and t["pairs_affected"] >= 1
    report = (ra / "AUDIT_PACKAGE_REPORT.md").read_text()
    assert report.startswith(f"# Audit summary: {page['trial_id']}")  # counts come first
    pdf = (ra / "AUDIT_PACKAGE_REPORT.pdf").read_bytes()
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert pdf == (rb / "AUDIT_PACKAGE_REPORT.pdf").read_bytes()  # byte-reproducible
    assert (ra / "EXECUTIVE_SUMMARY.md").read_text() == (rb / "EXECUTIVE_SUMMARY.md").read_text()


def test_recommendations_follow_reason_codes_only():
    page = {"trial_id": "T", "pairs": 2, "subjects": 2, "scans": 4, "real_pairs": 2, "scan_states": {},
            "verdicts": {"qiba-fdg-1.14": {"INSUFFICIENT_INFORMATION": 2}}, "pending_reference_reviews": 0,
            "top_failure_reasons": [{"reason_code": "AMBIGUOUS_RECONSTRUCTION", "pairs_affected": 2,
                                     "rulesets": ["qiba-fdg-1.14"], "site_can_fix": "MAYBE",
                                     "recommendation": "R1"}]}  # fmt: skip
    text = "\n".join(executive_summary(page))
    assert "AMBIGUOUS_RECONSTRUCTION (2 pair(s); site can fix: MAYBE): R1." in text
    assert executive_summary(page) == executive_summary(page)
    page["top_failure_reasons"] = []
    assert "No blocking reason occurred." in executive_summary(page)


def test_pdf_escapes_and_paginates():
    md = "# Title (x)\n" + "\n".join(f"line {i} with \\ and (paren) and µ" for i in range(200))
    pdf = markdown_to_pdf(md, title="t")
    assert b"\\(paren\\)" in pdf
    assert int(re.search(rb"/Count (\d+)", pdf).group(1)) >= 3  # 200 lines do not fit one page
    assert markdown_to_pdf(md, title="t") == pdf


def test_version_flag_reports_code_rules_and_schemas(capsys):
    import pytest

    import voxeltrace
    from voxeltrace.cli import main

    with pytest.raises(SystemExit) as e:
        main(["--version"])
    out = capsys.readouterr().out
    assert e.value.code == 0 and f"voxeltrace {voxeltrace.__version__}" in out
    for token in (
        "percist-1.0",
        "rule bundle sha256",
        "VT-EXECUTIVE-SUMMARY-2",
        "voxeltrace.lesion-review/1",
    ):
        assert token in out


def test_decided_failures_without_reason_codes_are_listed():
    from types import SimpleNamespace as NS

    from voxeltrace.executive import top_page

    chk = NS(
        rule_id="QIBA-UPTAKE-WINDOW",
        impact="blocking",
        status="FAIL",
        reasons=[],
        expected="55-75 min",
    )
    pair = NS(pair=NS(subject_id="S1", baseline="b", followup="f"), synthetic_perturbation=None,
              verdict="NOT_ASSESSABLE", checks=[chk])  # fmt: skip
    audit = NS(pairs=[pair], timepoints=[NS(subject_id="S1"), NS(subject_id="S2")])
    page = top_page("T", {"preflight": {"scans": 3}}, {"qiba-fdg-1.14": audit})
    assert page["subjects"] == 2  # single-timepoint subjects are counted too
    (t,) = page["top_failure_reasons"]
    assert (
        t["reason_code"] == "QIBA-UPTAKE-WINDOW FAIL"
        and t["site_can_fix"] == "NO"
        and "55-75 min" in t["recommendation"]
    )
