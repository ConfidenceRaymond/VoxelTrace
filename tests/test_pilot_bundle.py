"""Whole-trial audit v2 orchestrator, evidence bundle, adjudication, site queries, versions."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import pytest
import yaml
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.bundle import verify_bundle
from voxeltrace.cli import main as cli
from voxeltrace.pilot import run_audit
from voxeltrace.trial.adjudication import (
    Adjudication,
    EvidenceItem,
    adjudication_status,
    append_adjudication,
    load_adjudications,
    result_sha256,
    verify_chain,
)
from voxeltrace.trial.audit import TrialAudit, run_trial_audit
from voxeltrace.trial.site_queries import LABEL, site_queries, site_queries_md
from voxeltrace.versions import SCHEMAS, rule_bundle

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


def trial(tmp_path, with_config=True):
    root = tmp_path / "trial"
    for tp in ("baseline", "followup"):
        write_image_series(
            root / "S1" / tp, modality="PT", study_uid=generate_uid(), pet_overrides=GOOD
        )
    cfg = {
        "trial_id": "T1",
        "ruleset": "qiba-fdg-1.14",
        "timepoint_order": ["baseline", "followup"],
        "reference_proposals": "off",
        "sites": {"S1": "SITE-A"},
    }
    if with_config:
        (root / "trial.yaml").write_text(yaml.safe_dump(cfg))
        return root, None
    c = tmp_path / "cfg" / "trial.yaml"
    c.parent.mkdir()
    c.write_text(yaml.safe_dump(cfg))
    return root, c


@pytest.fixture
def bundle(tmp_path):
    root, _ = trial(tmp_path)
    res = run_audit(root, tmp_path / "out")
    return root, tmp_path / "out" / "audit_bundle", res


def test_bundle_layout_manifest_and_verify(bundle):
    root, b, res = bundle
    for d in (
        "preflight",
        "protocol",
        "quantitative",
        "rules",
        "pair_verdicts",
        "reviews",
        "attestations",
        "adjudications",
        "reports",
    ):
        assert (b / d).is_dir(), d
    m = json.loads((b / "manifest.json").read_text())
    assert (
        m["schema_versions"] == SCHEMAS
        and m["rule_bundle_sha256"] == rule_bundle()["rule_bundle_sha256"]
    )
    assert m["inputs_sha256"] and m["input_files"] >= 6 and m["ai_components"].startswith("none")
    assert verify_bundle(b)["status"] == "OK"
    assert cli(["verify-bundle", str(b)]) == 0
    assert not os.access(b / "manifest.json", os.W_OK)  # read-only


def test_automated_verdicts_identical_to_direct_audit(bundle):
    root, b, res = bundle
    for rs in ("qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0"):
        direct = run_trial_audit(root, rs)
        packaged = TrialAudit.model_validate_json(
            (b / "rules" / rs / "trial_audit.json").read_text()
        )
        assert [p.verdict for p in packaged.pairs] == [p.verdict for p in direct.pairs]
        assert [[c.status for c in p.checks] for p in packaged.pairs] == [
            [c.status for c in p.checks] for p in direct.pairs
        ]


def test_report_keeps_evidence_classes_apart(bundle):
    _, b, _ = bundle
    md = (b / "reports" / "AUDIT_PACKAGE_REPORT.md").read_text()
    for h in (
        "REAL DATA",
        "SYNTHETIC TEST DATA",
        "HUMAN-REVIEWED EVIDENCE",
        "EXTERNALLY ATTESTED EVIDENCE",
        "IMAGE-DERIVED CORROBORATION",
        "UNRESOLVED EVIDENCE",
    ):
        assert h in md


@pytest.mark.parametrize("kind", ["modify", "delete", "add", "checksums"])
def test_tamper_detection(bundle, kind):
    _, b, _ = bundle
    for p in b.rglob("*"):
        if p.is_file():
            p.chmod(0o644)
    target = b / "pair_verdicts" / "qiba-fdg-1.14.csv"
    if kind == "modify":
        target.write_text(target.read_text().replace("ASSESSABLE", "NOT_ASSESSABLE"))
    elif kind == "delete":
        target.unlink()
    elif kind == "add":
        (b / "reports" / "extra.txt").write_text("x")
    else:
        ck = b / "checksums.sha256"
        ck.write_text(ck.read_text() + "\n")
    r = verify_bundle(b)
    assert r["status"] == "TAMPERED"
    assert cli(["verify-bundle", str(b)]) == 1


def test_output_never_overwritten_and_external_config(tmp_path):
    root, cfg = trial(tmp_path, with_config=False)
    run_audit(root, tmp_path / "o1", config=cfg, rulesets=("qiba-fdg-1.14",), hash_inputs=False)
    with pytest.raises(FileExistsError):
        run_audit(root, tmp_path / "o1", config=cfg, rulesets=("qiba-fdg-1.14",))
    assert not (root / "trial.yaml").exists()  # input left untouched


def test_cli_audit_summarize_list_reviews(tmp_path, capsys):
    root, _ = trial(tmp_path)
    assert (
        cli(
            [
                "audit",
                "--input",
                str(root),
                "--output",
                str(tmp_path / "o"),
                "--ruleset",
                "qiba-fdg-1.14",
                "--no-input-hashes",
            ]
        )
        == 0
    )
    b = tmp_path / "o" / "audit_bundle"
    assert cli(["summarize", str(b)]) == 0 and cli(["list-reviews", str(b)]) == 0
    assert "qiba-fdg-1.14" in capsys.readouterr().out


# ------------------------------------------------------------------ adjudication


def _adj(pair, **kw):
    base = dict(
        adjudication_id="A1",
        subject=pair.pair.subject_id,
        baseline=pair.pair.baseline,
        followup=pair.pair.followup,
        ruleset_id=pair.ruleset_id,
        automated_verdict=pair.verdict,
        automated_result_sha256=result_sha256(pair),
        action="CONFIRM_AUTOMATED_RESULT",
        reason="checked evidence",
        reviewer_id="phys-1",
        reviewer_role="PET_PHYSICIST",
        timestamp=datetime(2026, 10, 9, tzinfo=UTC),
        software_version="0.1.0",
        created_via="HUMAN_CLI",
        simulated=True,
    )
    base.update(kw)
    return Adjudication(**base)


def test_adjudication_rules_and_chain(tmp_path):
    root, _ = trial(tmp_path)
    a = run_trial_audit(root, "qiba-fdg-1.14")
    p = a.pairs[0]
    log = tmp_path / "adj.jsonl"
    with pytest.raises(PermissionError):
        append_adjudication(log, _adj(p), confirmed=False)
    append_adjudication(log, _adj(p), confirmed=True)
    with pytest.raises(ValueError):
        _adj(
            p, action="OVERRIDE_WITH_EVIDENCE", adjudicated_verdict="NOT_ASSESSABLE"
        )  # no evidence
    with pytest.raises(ValueError):
        _adj(p, created_via="AI_MODEL")
    with pytest.raises(ValueError):
        _adj(p, adjudicated_verdict="ASSESSABLE")  # only with OVERRIDE
    ov = _adj(
        p,
        adjudication_id="A2",
        action="OVERRIDE_WITH_EVIDENCE",
        adjudicated_verdict="NOT_ASSESSABLE",
        supplied_evidence=[EvidenceItem(description="site record", attachment_sha256="a" * 64)],
    )
    append_adjudication(log, ov, confirmed=True)
    recs, chain = load_adjudications(log, allow_simulated=True)
    assert chain["status"] == "OK" and len(recs) == 2
    assert load_adjudications(log)[0] == []  # simulated never used in production
    (row,) = adjudication_status(a.pairs, recs)
    assert (
        row["automated_verdict"] == p.verdict
        and row["adjudication_status"] == "OVERRIDDEN_BY_HUMAN"
    )
    assert row["human_verdict"] == "NOT_ASSESSABLE"
    assert p.verdict == row["automated_verdict"]  # automated result untouched
    # tampering: edit a stored line
    lines = log.read_text().splitlines()
    lines[0] = lines[0].replace("checked evidence", "edited later")
    log.write_text("\n".join(lines) + "\n")
    assert verify_chain(log)["status"] == "TAMPERED"
    with pytest.raises(ValueError):
        append_adjudication(log, _adj(p, adjudication_id="A3"), confirmed=True)


def test_adjudication_stale_when_result_changes(tmp_path):
    root, _ = trial(tmp_path)
    p = run_trial_audit(root, "qiba-fdg-1.14").pairs[0]
    stale = _adj(p, automated_result_sha256="b" * 64)
    (row,) = adjudication_status([p], [stale])
    assert row["adjudication_status"] == "NOT_ADJUDICATED" and row["stale_records"] == 1


def test_cli_adjudicate_requires_confirm(tmp_path):
    args = [
        "adjudicate",
        "--log",
        str(tmp_path / "a.jsonl"),
        "--id",
        "X",
        "--subject",
        "S1",
        "--baseline",
        "b",
        "--followup",
        "f",
        "--ruleset",
        "qiba-fdg-1.14",
        "--automated-verdict",
        "ASSESSABLE",
        "--result-sha256",
        "c" * 64,
        "--action",
        "CONFIRM_AUTOMATED_RESULT",
        "--reason",
        "r",
        "--reviewer",
        "me",
        "--role",
        "PET_PHYSICIST",
    ]
    assert cli(args) == 2 and not (tmp_path / "a.jsonl").exists()


# ------------------------------------------------------------------ site queries / versions


def test_site_queries_deterministic_and_labelled():
    items = [
        {
            "site": "A",
            "subject": "S1",
            "scan": "b",
            "reason_code": "MISSING_PATIENTSIZE",
            "field": "PatientSize",
            "evidence": "absent",
        },
        {
            "site": "A",
            "subject": "S1",
            "scan": "f",
            "reason_code": "MISSING_PATIENTSIZE",
            "field": "PatientSize",
            "evidence": "absent",
        },
        {
            "site": "A",
            "subject": "S1",
            "scan": "b",
            "reason_code": "NOT_A_TEMPLATE",
            "field": "",
            "evidence": "",
        },
    ]
    q = site_queries(items)
    assert (
        len(q) == 1
        and q[0]["label"] == LABEL
        and q[0]["sent"] is False
        and q[0]["scans"] == ["b", "f"]
    )
    md = site_queries_md(q)
    assert "MISSING_PATIENTSIZE" in md and LABEL in md and site_queries(items) == q


def test_rule_bundle_hash_tracks_thresholds(monkeypatch):
    from voxeltrace.rules import qiba

    h0 = rule_bundle()["rule_bundle_sha256"]
    monkeypatch.setitem(qiba.UPTAKE_WINDOW.parameters, "max_min", 80.0)
    assert rule_bundle()["rule_bundle_sha256"] != h0


def test_old_trial_audit_json_still_readable(bundle):
    _, b, _ = bundle
    d = json.loads((b / "rules" / "qiba-fdg-1.14" / "trial_audit.json").read_text())
    for k in ("recon_attestation_file", "recon_attestations"):
        d.pop(k, None)  # files written before these fields existed
    assert TrialAudit.model_validate(d).pairs


def test_input_paths_pseudonymized_by_default(tmp_path):
    from voxeltrace.bundle import inputs_manifest

    root, _ = trial(tmp_path)
    a = inputs_manifest(root)
    b = inputs_manifest(root, clear_paths=True)
    assert a["inputs_sha256"] == b["inputs_sha256"]
    assert all("path" not in f and len(f["path_sha256"]) == 64 for f in a["files"])
    assert all("path" in f for f in b["files"]) and not a["paths_in_clear"]


def test_audit_copies_review_and_adjudication_files_without_qc_images(tmp_path):
    """Regression: the copies used to fail unless --qc-images had created reviews/ first."""
    from voxeltrace.bundle import verify_bundle

    root, _ = trial(tmp_path)
    review = "schema: voxeltrace.reference-review/2\nreviews: {}\n"
    (root / "reference_review.yaml").write_text(review)
    adj = tmp_path / "adjudications.jsonl"
    adj.write_text("")
    run_audit(root, tmp_path / "out", hash_inputs=False, adjudications=adj)
    b = tmp_path / "out" / "audit_bundle"
    assert (b / "reviews" / "reference_review.yaml").exists()
    assert (b / "adjudications" / "adjudications.jsonl").exists()
    assert verify_bundle(b)["status"] == "OK"
