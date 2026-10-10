"""Retrospective pilot hardening: pairing audit, site rollup, privacy scan, remediation matrix,
pilot acceptance contract (VT-PILOT-ACCEPTANCE-1), run-pilot and the delivery package."""

from __future__ import annotations

import csv
import json
import os
import shutil
from typing import get_args

import pytest
import yaml
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.cli import main as cli
from voxeltrace.delivery import build_delivery_package, verify_delivery
from voxeltrace.pilot import _hide_seg_name, run_audit
from voxeltrace.pilot_run import EXIT_CODES, STATUSES, audit_gate, run_pilot
from voxeltrace.privacy_scan import scan_directory, scan_text
from voxeltrace.remediation import NONE_ESTABLISHED, remediation_matrix
from voxeltrace.trial.pairing_audit import (
    PAIRING_CODES,
    ScanIdentity,
    audit_pairing,
    normalise_timepoint,
    pairing_status_by_subject,
)
from voxeltrace.trial.rollup import check_rollup

GOOD = {
    "FrameReferenceTime": "0",
    "DecayFactor": "1.0",
    "PatientSize": "1.75",
    "PatientSex": "M",
    "Manufacturer": "SIEMENS",
    "ManufacturerModelName": "Biograph128_mCT",
    "SoftwareVersions": "VG60A",
    "ReconstructionMethod": "PSF+TOF 2i21s",
    "ConvolutionKernel": "XYZ Gauss2.00",
}
DATES = {"baseline": "20200101", "followup": "20200301"}


_SLOPE = iter(1.5 + 0.01 * k for k in range(10_000))


def _scan(root, subj, tp, **over):
    """Distinct voxel content per scan (identical content is a duplicate-scan finding)."""
    date = DATES.get(tp, "20200501")
    ov = {**GOOD, "SeriesDate": date, "AcquisitionDate": date, "PatientID": f"PID-{subj}", **over}
    rp = {"RadiopharmaceuticalStartDateTime": f"{date}091500"}
    write_image_series(root / subj / tp, modality="PT", study_uid=generate_uid(), pet_overrides=ov,
                       rp_overrides=rp, slope=next(_SLOPE))  # fmt: skip


def make_trial(tmp_path, subjects=("S1", "S2"), config=True, sites=None):
    root = tmp_path / "trial"
    for s in subjects:
        for tp in ("baseline", "followup"):
            _scan(root, s, tp)
    if config:
        cfg = {"trial_id": "T-PILOT", "ruleset": "qiba-fdg-1.14",
               "timepoint_order": ["baseline", "followup"], "reference_proposals": "off",
               "sites": sites or {"S1": "SITE-A", "S2": "SITE-B"}}  # fmt: skip
        (root / "trial.yaml").write_text(yaml.safe_dump(cfg))
    return root


# ---------------------------------------------------------------- pairing audit


def _ids(*rows):
    return [ScanIdentity(**r) for r in rows]


def test_pairing_ok_layout_has_no_findings():
    r = audit_pairing(
        _ids(
            dict(
                subject="S1",
                timepoint="baseline",
                patient_id_sha256="p1",
                pet_series_pseudonym="a",
                acquisition_date="2020-01-01",
                tracer="FDG",
            ),
            dict(
                subject="S1",
                timepoint="followup",
                patient_id_sha256="p1",
                pet_series_pseudonym="b",
                acquisition_date="2020-03-01",
                tracer="FDG",
            ),
        ),  # fmt: skip
        ["baseline", "followup"],
    )
    assert r["status"] == "OK" and r["findings"] == []


@pytest.mark.parametrize(
    "rows,order,code,severity",
    [
        ([("S1", "baseline", "p", "a", "2020-01-01"), ("S1", "Baseline", "p", "b", "2020-02-01")],
         ["baseline", "Baseline"], "DUPLICATE_TIMEPOINT", "BLOCKING"),
        ([("S1", "baseline", "p", "a", "2020-01-01"), ("S1", "followup", "p", "a", "2020-02-01")],
         ["baseline", "followup"], "SAME_SCAN_LINKED_TWICE", "BLOCKING"),
        ([("S1", "baseline", "p", "a", "2020-01-01"), ("S2", "baseline", "q", "a", "2020-02-01")],
         ["baseline"], "SCAN_LINKED_TO_MULTIPLE_SUBJECTS", "BLOCKING"),
        ([("S1", "baseline", "p", "a", "2020-05-01"), ("S1", "followup", "p", "b", "2020-02-01")],
         ["baseline", "followup"], "TIMEPOINT_ORDER_ANOMALY", "BLOCKING"),
        ([("S1", "pre", "p", "a", "2020-01-01"), ("S1", "post", "p", "b", "2020-02-01")],
         [], "TIMEPOINT_ORDER_UNDECLARED", "NEEDS_REVIEW"),
        ([("S1", "baseline", "p", "a", "2020-01-01"), ("S1", "week6", "p", "b", "2020-02-01")],
         ["baseline", "followup"], "UNDECLARED_TIMEPOINT", "NEEDS_REVIEW"),
        ([("S1", "baseline", "p", "a", "2020-01-01"), ("S1", "followup", "q", "b", "2020-02-01")],
         ["baseline", "followup"], "INCONSISTENT_SUBJECT_PSEUDONYM", "NEEDS_REVIEW"),
        ([("S1", "baseline", "p", "a", "2020-01-01"), ("S2", "baseline", "p", "b", "2020-02-01")],
         ["baseline"], "SUBJECT_PSEUDONYM_SHARED", "NEEDS_REVIEW"),
        ([("S1", "baseline", "p", "a", "2020-01-01"), ("S1", "followup", "p", "b", "2020-01-01")],
         ["baseline", "followup"], "SAME_DAY_TIMEPOINTS", "NEEDS_REVIEW"),
        ([("S1", "baseline", "p", "a", "2020-01-01")], ["baseline", "followup"], "MISSING_TIMEPOINT", "WARNING"),
        ([("S1", "baseline", "p", "a", None), ("S1", "followup", "p", "b", "2020-02-01")],
         ["baseline", "followup"], "ACQUISITION_DATE_UNKNOWN", "WARNING"),
    ],
)  # fmt: skip
def test_pairing_findings(rows, order, code, severity):
    scans = [ScanIdentity(subject=s, timepoint=t, patient_id_sha256=p, pet_series_pseudonym=u,
                          acquisition_date=d) for s, t, p, u, d in rows]  # fmt: skip
    r = audit_pairing(scans, order)
    hits = [f for f in r["findings"] if f["code"] == code]
    assert hits and all(f["severity"] == severity for f in hits)
    assert PAIRING_CODES[code][0] == severity
    assert r["status"] == {"BLOCKING": "BLOCKED", "NEEDS_REVIEW": "NEEDS_REVIEW"}.get(
        max((f["severity"] for f in r["findings"]), key=["INFO", "WARNING", "NEEDS_REVIEW", "BLOCKING"].index),
        "OK",
    )  # fmt: skip


def test_mixed_tracer_and_synthetic_downgrade():
    r = audit_pairing(
        _ids(
            dict(
                subject="S1",
                timepoint="baseline",
                pet_series_pseudonym="a",
                tracer="FDG",
                acquisition_date="2020-01-01",
            ),
            dict(
                subject="S1",
                timepoint="followup",
                pet_series_pseudonym="b",
                tracer="FLT",
                acquisition_date="2020-02-01",
            ),
            dict(
                subject="SYN",
                timepoint="baseline",
                pet_series_pseudonym="a",
                synthetic=True,
                acquisition_date="2020-01-01",
            ),
        ),  # fmt: skip
        ["baseline", "followup"],
    )
    codes = {(f["code"], f["severity"]) for f in r["findings"]}
    assert ("MIXED_TRACER", "WARNING") in codes
    assert ("SCAN_LINKED_TO_MULTIPLE_SUBJECTS", "INFO") in codes  # declared synthetic reuse
    assert r["status"] == "OK"


def test_pairing_status_by_subject_and_normalisation():
    assert normalise_timepoint("Follow-Up") == normalise_timepoint("follow_up") == "followup"
    rep = {"findings": [{"subject": "*", "severity": "NEEDS_REVIEW"},
                        {"subject": "S1", "severity": "BLOCKING"},
                        {"subject": "S2", "severity": "WARNING"}]}  # fmt: skip
    st = pairing_status_by_subject(rep)
    assert st == {"S1": "BLOCKING", "S2": "NEEDS_REVIEW", "*": "NEEDS_REVIEW"}


# ---------------------------------------------------------------- audit outputs


@pytest.fixture(scope="module")
def audited(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pilot")
    root = make_trial(tmp)
    res = run_audit(root, tmp / "out")
    return root, tmp / "out" / "audit_bundle", res


def test_bundle_has_pairing_and_site_rollup(audited):
    _, b, _ = audited
    pairing = json.loads((b / "pairing" / "pairing_audit.json").read_text())
    assert pairing["schema"] == "VT-PAIRING-AUDIT-1" and pairing["status"] == "OK", pairing
    rows = list(csv.DictReader((b / "reports" / "site_summary.csv").open()))
    site = [r for r in rows if r["level"] == "SITE" and r["ruleset"] == "qiba-fdg-1.14"]
    assert {r["site"] for r in site} == {"SITE-A", "SITE-B"}
    assert sum(int(r["scans_total"]) for r in site) == 4
    assert sum(int(r["pairs_total"]) for r in site) == 2
    verdicts = list(csv.DictReader((b / "pair_verdicts" / "qiba-fdg-1.14.csv").open()))
    for v in (
        "ASSESSABLE",
        "ASSESSABLE_WITH_WARNINGS",
        "NOT_ASSESSABLE",
        "INSUFFICIENT_INFORMATION",
    ):
        assert sum(int(r[f"pairs_{v.lower()}"]) for r in site) == sum(
            x["verdict"] == v for x in verdicts
        )
    page = (b / "reports" / "EXECUTIVE_SUMMARY.md").read_text()
    assert "## At a glance" in page and "Sites requiring action" in page


def test_check_rollup_detects_inconsistency():
    class PF:
        scans = [object(), object()]

    class A:
        pairs: list = []

    good = [{"level": "SITE", "site": "X", "scanner": "*", "ruleset": "r", "scans_total": 2,
             "scans_ready_to_quantify": 2, "scans_ready_with_warnings": 0, "scans_do_not_quantify": 0,
             "scans_needs_review": 0, "pairs_total": 0, "pairs_assessable": 0,
             "pairs_assessable_with_warnings": 0, "pairs_not_assessable": 0,
             "pairs_insufficient_information": 0, "drift_events": 0}]  # fmt: skip
    good.append({**good[0], "level": "SCANNER", "scanner": "M"})
    assert check_rollup(good, PF, {"r": A}) == []
    bad = [dict(good[0], scans_total=3), good[1]]
    assert check_rollup(bad, PF, {"r": A})


def test_segmentation_file_names_are_hashed_unless_clear():
    e = {"source_provenance": {"seg_file": "1.2.840.113619.2.55.3.1234.dcm", "basis": "x"}}
    h = _hide_seg_name(e)
    assert h["source_provenance"]["seg_file"].startswith("sha256:")
    assert "1.2.840" not in json.dumps(h) and e["source_provenance"]["seg_file"].startswith("1.2")


def test_discovery_ignores_hidden_directories(tmp_path):
    from voxeltrace.trial.discovery import discover_trial

    root = make_trial(tmp_path, subjects=("S1",))
    (root / ".git" / "objects").mkdir(parents=True)
    (root / "S1" / ".cache").mkdir()
    lay = discover_trial(root)
    assert list(lay.scans) == ["S1"] and set(lay.scans["S1"]) == {"baseline", "followup"}


# ---------------------------------------------------------------- privacy scan


@pytest.mark.parametrize(
    "text,cat",
    [
        ('"PatientName": "DOE^JANE"', "DICOM_IDENTIFIER_ATTRIBUTE"),
        ("PatientID", "DICOM_IDENTIFIER_ATTRIBUTE"),
        ("AccessionNumber=123", "DICOM_IDENTIFIER_ATTRIBUTE"),
        ("(0010,0020)", "DICOM_IDENTIFIER_ATTRIBUTE"),
        ('"InstitutionName": "General Hospital"', "DICOM_IDENTIFIER_ATTRIBUTE"),
        ("seg 1.3.6.1.4.1.14519.5.2.1.4486875521317 x", "DICOM_UID"),
        ("/home/mindlab/voxeltrace_hackathon/data/x", "LOCAL_PATH"),
        ("see /home/dell/foo", "LOCAL_PATH"),
        ("/Users/alice/Desktop/trial", "LOCAL_PATH"),
        (r"C:\Users\bob\pet", "LOCAL_PATH"),
        ("in voxeltrace_hackathon/outputs", "WORKSPACE_NAME"),
        ("contact jane.doe@hospital.org", "EMAIL"),
        ("token hf_" + "a" * 34, "SECRET"),
        ("ghp_" + "B" * 36, "SECRET"),
        ("api_key = abcdefgh12345678", "SECRET"),
        ("-----BEGIN RSA PRIVATE KEY-----", "SECRET"),
        ("operator mindlab ran it", "LOCAL_ACCOUNT"),
    ],
)
def test_privacy_scan_flags(text, cat):
    assert cat in {f["category"] for f in scan_text(text)}


@pytest.mark.parametrize(
    "text",
    [
        "pet_4ef5a6f7ae173fea",
        "sha256 413186131a357163959cb161358e9193899c9675278bcc1a8a8c8d194f9d411d",
        "qiba-fdg-1.14 QIBA-FDG-PETCT-1.14 percist-1.0",
        "StationName absent although the declared profile retains device identity",
        "acquired 2020-01-01",
        "voxeltrace 0.3.0; Boellaard R et al. EJNMMI 2015;42:328-354",
        "ACRIN-NSCLC-FDG-PET-050,baseline,followup",
    ],
)
def test_privacy_scan_does_not_flag_pseudonyms_and_versions(text):
    assert scan_text(text) == []


def test_privacy_scan_directory_hidden_and_dicom_files(tmp_path):
    (tmp_path / "ok.md").write_text("fine\n")
    (tmp_path / ".hidden").write_text("x")
    (tmp_path / "x.dcm").write_bytes(b"\0" * 128 + b"DICM")
    r = scan_directory(tmp_path)
    assert r["status"] == "FINDINGS"
    assert {"HIDDEN_FILE", "DICOM_FILE"} <= set(r["categories"])


# ---------------------------------------------------------------- remediation matrix


def test_remediation_matrix_covers_every_reason_code():
    from voxeltrace.preflight.reasons import CATALOG as PF
    from voxeltrace.trial.reasons import ReasonCode

    rows = remediation_matrix()
    codes = {r["code"] for r in rows}
    assert set(get_args(ReasonCode)) <= codes
    assert set(PF) <= codes
    assert set(PAIRING_CODES) <= codes
    assert {
        "NON_FDG_TRACER",
        "TRACER_NOT_RECOGNISED",
        "NO_SCANS_FOUND",
        "TRIAL_CONFIG_INVALID",
    } <= codes
    for r in rows:
        for k in ("reexport_can_fix", "documentation_can_fix", "human_review_can_fix", "permanent"):
            assert r[k] in ("YES", "NO", "MAYBE"), (r["code"], k)
        assert r["remediation"].strip() and r["customer_wording"].strip()
        assert (
            not r["remediation"].lower().startswith("none") or r["remediation"] == NONE_ESTABLISHED
        )


# ---------------------------------------------------------------- acceptance + run-pilot


def test_audit_gate_policy():
    ok = {"layout": [], "decision": "NEEDS_REEXPORT",
          "scans": [{"decision": "ACCEPT_FOR_AUDIT"}, {"decision": "NEEDS_REEXPORT"}]}  # fmt: skip
    assert audit_gate(ok, strict=False) == (True, None)
    assert audit_gate(ok, strict=True) == (False, "NEEDS_REEXPORT")
    assert audit_gate({**ok, "scans": [{"decision": "UNSUPPORTED"}]}, False) == (
        False,
        "UNSUPPORTED",
    )
    assert audit_gate({**ok, "scans": []}, False) == (False, "NEEDS_REEXPORT")
    blk = {**ok, "layout": [{"code": "TRIAL_CONFIG_INVALID", "severity": "BLOCKING"}]}
    assert audit_gate(blk, False) == (False, "NEEDS_REEXPORT")
    assert set(EXIT_CODES) <= set(STATUSES)


@pytest.fixture(scope="module")
def pilot(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("runpilot")
    root = make_trial(tmp, config=False)
    res = run_pilot(root, tmp / "p1", trial_id="T-PILOT", timepoints=["baseline", "followup"])
    return tmp, root, res


def test_run_pilot_writes_contract_and_package(pilot):
    tmp, root, res = pilot
    out = tmp / "p1"
    acc = json.loads((out / "pilot_acceptance.json").read_text())
    assert acc["schema"] == "VT-PILOT-ACCEPTANCE-1"
    assert acc["status"] in ("AUDIT_COMPLETE", "AUDIT_COMPLETE_WITH_REVIEW_PENDING")
    assert acc["intake_status"] in ("ACCEPTED_FOR_AUDIT", "ACCEPTED_WITH_WARNINGS")
    for k in ("dataset", "software", "preflight_summary", "review_requirements", "unsupported_features",
              "output", "pairing", "verdicts"):  # fmt: skip
        assert k in acc
    assert len(acc["dataset"]["inputs_sha256"]) == 64
    assert (
        acc["output"]["bundle"] == "audit/audit_bundle"
        and acc["output"]["verification_status"] == "OK"
    )
    assert acc["software"]["rule_bundle_sha256"] and acc["software"]["rule_versions"]
    assert not (root / "trial.yaml").exists()  # input never written; config goes to the output
    assert (out / "config" / "trial.yaml").exists()
    assert res["delivery"]["status"] == "OK"
    assert "/" not in acc["output"]["bundle"][:1] and str(tmp) not in json.dumps(acc)


def test_acceptance_is_deterministic(pilot, tmp_path):
    tmp, root, res = pilot
    res2 = run_pilot(
        root, tmp_path / "p2", config=tmp / "p1" / "config" / "trial.yaml", delivery=False
    )
    assert res2["acceptance"] == res["acceptance"]


def test_delivery_package_contents_and_verification(pilot):
    tmp, _, res = pilot
    pkg = tmp / "p1" / "delivery_package"
    for name in ("README_FIRST.md", "executive_summary.pdf", "executive_summary.json", "pair_results.csv",
                 "scan_preflight.csv", "site_summary.csv", "protocol_drift.csv", "unresolved_items.csv",
                 "recommended_site_queries/site_queries.md", "evidence_bundle/manifest.json",
                 "verification_report.json", "methodology_and_limitations.md", "software_version.txt",
                 "pilot_acceptance.json", "remediation_matrix.csv", "privacy_scan.json",
                 "DELIVERY_CHECKSUMS.sha256", "DELIVERY_MANIFEST.json"):  # fmt: skip
        assert (pkg / name).exists(), name
    assert not list(pkg.rglob("*.dcm")) and not [p for p in pkg.rglob(".*")]
    v = verify_delivery(pkg)
    assert v["status"] == "OK" and v["evidence_bundle"] == "OK" and v["privacy_scan"] == "CLEAN", v
    assert json.loads((pkg / "verification_report.json").read_text())["bundle"] == "evidence_bundle"
    rows = list(csv.DictReader((pkg / "pair_results.csv").open()))
    assert rows and all(r["pairing_status"] == "OK" for r in rows)
    text = "".join(p.read_text(errors="ignore") for p in pkg.rglob("*") if p.is_file())
    assert str(tmp) not in text


def test_delivery_detects_tampering_and_extra_files(pilot, tmp_path):
    tmp, _, _ = pilot
    pkg = tmp_path / "copy"
    shutil.copytree(tmp / "p1" / "delivery_package", pkg)
    for p in pkg.rglob("*"):
        os.chmod(p, 0o755 if p.is_dir() else 0o644)
    (pkg / "pair_results.csv").write_text("changed\n")
    assert verify_delivery(pkg)["status"] == "TAMPERED"
    (pkg / ".DS_Store").write_text("x")
    v = verify_delivery(pkg)
    assert ".DS_Store" in v["unlisted"] and v["privacy_scan"] == "FINDINGS"


def test_delivery_refuses_tampered_bundle_and_never_overwrites(audited, tmp_path):
    _, b, _ = audited
    bad = tmp_path / "bundle"
    shutil.copytree(b, bad)
    os.chmod(bad / "reports" / "summary.json", 0o644)
    (bad / "reports" / "summary.json").write_text("{}")
    with pytest.raises(ValueError, match="TAMPERED"):
        build_delivery_package(bad, tmp_path / "pkg")
    assert build_delivery_package(b, tmp_path / "pkg2")["status"] == "OK"
    with pytest.raises(FileExistsError):
        build_delivery_package(b, tmp_path / "pkg2")


def test_delivery_rejects_privacy_findings(audited, tmp_path):
    from voxeltrace.bundle import finalize_bundle

    _, b, _ = audited
    leaky = tmp_path / "leaky"
    shutil.copytree(b, leaky)
    for p in leaky.rglob("*"):
        os.chmod(p, 0o755 if p.is_dir() else 0o644)
    (leaky / "reports" / "note.md").write_text("input was /home/alice/site_export/PatientX\n")
    (leaky / "checksums.sha256").unlink()
    manifest = json.loads((leaky / "manifest.json").read_text())
    (leaky / "manifest.json").unlink()
    finalize_bundle(leaky, manifest)
    r = build_delivery_package(leaky, tmp_path / "pkg")
    assert r["status"] == "REJECTED_PRIVACY" and "LOCAL_PATH" in r["categories"]
    assert not (tmp_path / "pkg").exists() and (tmp_path / "pkg.privacy_findings.json").exists()


def test_pairing_block_makes_audit_blocked_and_refuses_delivery(tmp_path):
    root = make_trial(tmp_path, subjects=("S1",))
    shutil.rmtree(root / "S1" / "followup")
    shutil.copytree(root / "S1" / "baseline", root / "S1" / "followup")  # same scan twice
    res = run_pilot(root, tmp_path / "out")
    acc = res["acceptance"]
    assert acc["status"] == "AUDIT_BLOCKED" and acc["pairing"]["status"] == "BLOCKED"
    assert res["delivery"] is None and not (tmp_path / "out" / "delivery_package").exists()
    assert EXIT_CODES[acc["status"]] == 1


def test_unsupported_tracer_is_not_audited(tmp_path):
    root = tmp_path / "trial"
    for tp in ("baseline", "followup"):
        write_image_series(root / "S1" / tp, modality="PT", study_uid=generate_uid(), slope=next(_SLOPE),
                           pet_overrides=GOOD, rp_overrides={"Radiopharmaceutical": "PSMA-11"})  # fmt: skip
    res = run_pilot(root, tmp_path / "out", trial_id="T", timepoints=["baseline", "followup"])
    acc = res["acceptance"]
    assert acc["status"] == "UNSUPPORTED" and acc["audit_status"] == "NOT_RUN"
    assert "NON_FDG_TRACER" in acc["unsupported_features"]
    assert not (tmp_path / "out" / "audit").exists()


def test_strict_intake_blocks_reexport_but_default_audits(tmp_path):
    root = tmp_path / "trial"
    _scan(root, "S1", "baseline")
    write_image_series(root / "S1" / "followup", modality="PT", study_uid=generate_uid(),
                       pet_overrides={**GOOD, "AcquisitionDate": "20200301", "SeriesDate": "20200301"},
                       drop=("PatientWeight",), slope=next(_SLOPE))  # fmt: skip
    strict = run_pilot(root, tmp_path / "strict", trial_id="T", timepoints=["baseline", "followup"],
                       strict_intake=True)  # fmt: skip
    assert strict["acceptance"]["status"] == "NEEDS_REEXPORT"
    default = run_pilot(root, tmp_path / "default", trial_id="T", timepoints=["baseline", "followup"],
                        delivery=False)  # fmt: skip
    assert default["acceptance"]["intake_status"] == "NEEDS_REEXPORT"
    assert default["acceptance"]["audit_status"].startswith("AUDIT_")


def test_run_pilot_cli_exit_codes_and_refusals(tmp_path, capsys):
    root = make_trial(tmp_path, subjects=("S1",))
    assert cli(["run-pilot", "--input", str(root), "--output", str(tmp_path / "o"), "--no-delivery",
                "--format", "json"]) == 0  # fmt: skip
    out = json.loads(capsys.readouterr().out)
    assert out["acceptance"]["schema"] == "VT-PILOT-ACCEPTANCE-1"
    assert (
        cli(["run-pilot", "--input", str(root), "--output", str(tmp_path / "o")]) == 2
    )  # never overwrite
    bare = tmp_path / "bare"
    _scan(bare, "S1", "baseline")
    _scan(bare, "S1", "followup")
    assert (
        cli(["run-pilot", "--input", str(bare), "--output", str(tmp_path / "o2")]) == 2
    )  # no trial-id
    assert cli(["remediation-matrix", "--format", "json"]) == 0
    assert cli(["deliver", str(tmp_path / "o"), "--out", str(tmp_path / "pkg")]) == 0
    assert cli(["verify-delivery", str(tmp_path / "pkg")]) == 0


# ---------------------------------------------------------------- evidence trust trace


def test_evidence_trace_links_verdict_to_field_trust_and_source(tmp_path):
    from voxeltrace.trace import evidence_trace, explain_pair

    root = tmp_path / "trial"
    for i, (tp, date) in enumerate((("baseline", "20200101"), ("followup", "20200301"))):
        ov = {**GOOD, "AcquisitionDate": date, "SeriesDate": date, "PatientID": "P1"}
        ov.pop("ConvolutionKernel")  # filter unknown -> VT-PROTOCOL-IDENTITY UNKNOWN
        write_image_series(root / "S1" / tp, modality="PT", study_uid=generate_uid(), slope=2.0 + i / 10,
                           pet_overrides=ov, rp_overrides={"RadiopharmaceuticalStartDateTime": f"{date}091500"})  # fmt: skip
    (root / "trial.yaml").write_text(yaml.safe_dump({"trial_id": "T", "ruleset": "qiba-fdg-1.14", "timepoint_order": ["baseline", "followup"],
                                                     "reference_proposals": "off"}))  # fmt: skip
    run_audit(root, tmp_path / "out", rulesets=("qiba-fdg-1.14",))
    b = tmp_path / "out" / "audit_bundle"
    rows = [r for r in evidence_trace(b) if r["rule_id"] == "VT-PROTOCOL-IDENTITY"]
    assert rows and rows[0]["verdict"] == "INSUFFICIENT_INFORMATION"
    assert rows[0]["reason_code"] == "AMBIGUOUS_RECONSTRUCTION"
    assert (
        "filter_kernel" in rows[0]["baseline_evidence"]
        and "trust NONE" in rows[0]["baseline_evidence"]
    )
    assert "ConvolutionKernel" in rows[0]["baseline_evidence"]
    assert rows[0]["plain_language"] and rows[0]["remediation"]
    text = explain_pair(b, "S1")
    assert (
        "VT-PROTOCOL-IDENTITY" in text and "in plain language" in text and "what can fix it" in text
    )
    assert "no pair" in explain_pair(b, "NOPE")


def test_delivery_contains_evidence_trace(pilot):
    tmp, _, _ = pilot
    p = tmp / "p1" / "delivery_package" / "pair_evidence_trace.csv"
    assert p.exists() and p.read_text().startswith("ruleset,subject")
