"""QIBA-only reconstruction attestation (LEVEL_C): roles, charter, binding, rule integration.

All attestations here are SIMULATED test fixtures. No production attestation exists.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest
import yaml
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.evidence import extract_protocol
from voxeltrace.evidence.attestation import (
    SCHEMA,
    ReconstructionAttestation,
    ScanFacts,
    load_attestations,
    validate_attestation,
)
from voxeltrace.ingest import discover_dicom
from voxeltrace.quant.suv import audit_pet_headers, validate_suv_eligibility
from voxeltrace.rules.qiba_identity import WARNING, protocol_identity
from voxeltrace.rules.registry import assess_pair, get_ruleset
from voxeltrace.trial.audit import run_trial_audit
from voxeltrace.trial.export import export_audit
from voxeltrace.trial.layers import assessability_layers
from voxeltrace.trial.schema import PairContext, ScanPair, ScanTimepoint
from voxeltrace.trial.summary import attestation_rows, audit_report_md

SCANNER = {
    "Manufacturer": "GE MEDICAL SYSTEMS",
    "ManufacturerModelName": "Discovery LS",
    "SoftwareVersions": "16.01",
    "CorrectedImage": ["DECY", "ATTN", "SCAT", "DTIM", "RAN", "NORM"],
}
NO_RECON = ("ReconstructionMethod", "ConvolutionKernel")  # like ACRIN 168
RECON_VALUES = dict(
    reconstruction_method="OSEM",
    iterations=2,
    subsets=28,
    post_filter="GAUSS 6",
    time_of_flight=False,
    psf_resolution_modelling=False,
)


def scan(tmp_path, name, *, overrides=None, drop=NO_RECON):
    study = generate_uid()
    series, _ = write_image_series(
        tmp_path / name,
        modality="PT",
        study_uid=study,
        pet_overrides={**SCANNER, **(overrides or {})},
        drop=drop,
    )
    (s,) = discover_dicom(tmp_path / name).series
    val, inputs = validate_suv_eligibility(audit_pet_headers(s))
    tp = ScanTimepoint(
        subject_id="S1",
        timepoint=name,
        suv_status="PASS",
        protocol=extract_protocol(s, inputs, val),
    )
    facts = ScanFacts(
        subject_id="S1",
        timepoint=name,
        study_instance_uid=study,
        series_instance_uid=series,
        manufacturer=SCANNER["Manufacturer"],
        manufacturer_model_name=SCANNER["ManufacturerModelName"],
        software_versions=[SCANNER["SoftwareVersions"]],
    )
    return tp, facts


def doc(tmp_path, name="protocol_export.pdf", content=b"scanner protocol export"):
    p = tmp_path / "docs" / name
    p.parent.mkdir(exist_ok=True)
    p.write_bytes(content)
    return {"path": f"docs/{name}", "sha256": hashlib.sha256(content).hexdigest()}


def att(facts, tmp_path, **kw):
    base = dict(
        attestation_id=f"ATT-{facts.timepoint}",
        subject_id=facts.subject_id,
        timepoint=facts.timepoint,
        study_instance_uid=facts.study_instance_uid,
        series_instance_uid=facts.series_instance_uid,
        manufacturer=facts.manufacturer,
        manufacturer_model_name=facts.manufacturer_model_name,
        software_version="16.01",
        source={"source_type": "SCANNER_PROTOCOL_EXPORT", **doc(tmp_path)},
        attestor_id="physicist-01",
        attestor_role="QUALIFIED_PET_PHYSICIST",
        attested_at=datetime(2026, 10, 8, tzinfo=UTC),
        rule_scope=["qiba-fdg-1.14"],
        confidence="CONFIRMED",
        simulated=True,
        **RECON_VALUES,
    )
    base.update(kw)
    return ReconstructionAttestation.model_validate(base)


def pair_ctx(b, f, outcomes=None):
    return PairContext(
        pair=ScanPair(subject_id="S1", baseline=b.timepoint, followup=f.timepoint),
        baseline=b,
        followup=f,
        recon_attestations=outcomes or {},
    )


def identity(rs, ctx):
    res = assess_pair(get_ruleset(rs), ctx)
    return next(c for c in res.checks if c.rule_id == "VT-PROTOCOL-IDENTITY"), res


@pytest.fixture
def pair(tmp_path):
    (b, fb), (f, ff) = scan(tmp_path, "baseline"), scan(tmp_path, "followup")
    return tmp_path, b, fb, f, ff


def valid_outcomes(tmp_path, fb, ff, bkw=None, fkw=None):
    return {
        "baseline": [validate_attestation(att(fb, tmp_path, **(bkw or {})), fb, tmp_path)],
        "followup": [validate_attestation(att(ff, tmp_path, **(fkw or {})), ff, tmp_path)],
    }


# ------------------------------------------------------------------ roles (Part 2)


@pytest.mark.parametrize(
    ("role", "kw", "ok"),
    [
        ("QUALIFIED_PET_PHYSICIST", {}, True),
        ("NUCLEAR_MEDICINE_PHYSICIST", {}, True),
        ("IMAGING_CORE_QC_LEAD", {"attestor_qc_responsibility_documented": True}, True),
        ("IMAGING_CORE_QC_LEAD", {}, False),  # QC responsibility not documented
        ("SITE_PET_TECHNOLOGIST", {}, False),  # no countersignature
        ("INVESTIGATOR", {}, False),
        ("RADIOLOGIST", {}, False),
        ("STUDY_COORDINATOR", {}, False),
        ("VENDOR_REPRESENTATIVE", {}, False),
        ("OTHER", {}, False),
    ],
)
def test_attestor_roles(pair, role, kw, ok):
    tmp_path, _, fb, _, _ = pair
    o = validate_attestation(att(fb, tmp_path, attestor_role=role, **kw), fb, tmp_path)
    assert (o.status == "VALID") is ok, o.reasons


@pytest.mark.parametrize(
    ("signer_role", "qc_doc", "same_person", "ok"),
    [
        ("QUALIFIED_PET_PHYSICIST", False, False, True),
        ("NUCLEAR_MEDICINE_PHYSICIST", False, False, True),
        ("IMAGING_CORE_QC_LEAD", True, False, True),
        ("IMAGING_CORE_QC_LEAD", False, False, False),
        ("RADIOLOGIST", False, False, False),
        ("INVESTIGATOR", False, False, False),
        ("SITE_PET_TECHNOLOGIST", False, False, False),
        ("QUALIFIED_PET_PHYSICIST", False, True, False),  # self-countersignature
    ],
)
def test_technologist_countersignature(pair, signer_role, qc_doc, same_person, ok):
    tmp_path, _, fb, _, _ = pair
    cs = {
        "signer_id": "tech-01" if same_person else "phys-02",
        "signer_role": signer_role,
        "signed_at": "2026-10-08T12:00:00Z",
        "qc_responsibility_documented": qc_doc,
    }
    a = att(fb, tmp_path, attestor_role="SITE_PET_TECHNOLOGIST", attestor_id="tech-01",
            countersignature=cs)  # fmt: skip
    assert (validate_attestation(a, fb, tmp_path).status == "VALID") is ok


def test_unsigned_note_believed_and_unsigned_attestor_rejected(pair):
    tmp_path, _, fb, _, _ = pair
    note = att(fb, tmp_path, source={"source_type": "UNSIGNED_NOTE", **doc(tmp_path)})
    assert "UNSIGNED_NOTE_NOT_ACCEPTED" in validate_attestation(note, fb, tmp_path).reasons
    believed = att(fb, tmp_path, confidence="BELIEVED")
    assert validate_attestation(believed, fb, tmp_path).status == "INVALID"
    with pytest.raises(ValueError):
        att(fb, tmp_path, attestor_id="")  # unsigned: no attestor
    with pytest.raises(ValueError):
        att(fb, tmp_path, series_instance_uid="")  # unbound protocol document
    with pytest.raises(ValueError):
        att(fb, tmp_path, rule_scope=[])


# ------------------------------------------------------------------ charter (Part 3)


def test_charter_alone_is_expected_protocol_only(pair):
    tmp_path, _, fb, _, _ = pair
    ch = {"source_type": "TRIAL_IMAGING_CHARTER", **doc(tmp_path, "charter.pdf", b"charter")}
    o = validate_attestation(att(fb, tmp_path, source=ch), fb, tmp_path)
    assert o.status == "EXPECTED_PROTOCOL_ONLY"
    binding = {
        "site": "SITE-1",
        "scanner_model": "Discovery LS",
        "software_version_or_period": "16.01",
        "scan_level_applicability": "series listed in charter annex 2",
    }
    o = validate_attestation(att(fb, tmp_path, source=ch, charter_binding=binding), fb, tmp_path)
    assert o.status == "EXPECTED_PROTOCOL_ONLY"  # bound, but no scan-level corroboration
    corr = [{"source_type": "SITE_PROTOCOL_RECORD", **doc(tmp_path, "rec.pdf", b"record")}]
    o = validate_attestation(
        att(fb, tmp_path, source=ch, charter_binding=binding, corroborating_sources=corr),
        fb,
        tmp_path,
    )
    assert o.status == "VALID"


# ------------------------------------------------------------------ binding (Part 7)


def test_hash_binding_stale_and_missing(pair):
    tmp_path, _, fb, _, _ = pair
    a = att(fb, tmp_path)
    assert validate_attestation(a, fb, tmp_path).status == "VALID"
    (tmp_path / a.source.path).write_bytes(b"edited after signing")
    o = validate_attestation(a, fb, tmp_path)
    assert o.status == "STALE" and o.reasons[0].startswith("SOURCE_DOCUMENT_CHANGED")
    (tmp_path / a.source.path).unlink()
    assert validate_attestation(a, fb, tmp_path).status == "INVALID"


@pytest.mark.parametrize(
    ("change", "status", "reason"),
    [
        ({"series_instance_uid": "1.2.3"}, "STALE", "SERIES_CHANGED"),
        ({"study_instance_uid": "1.2.3"}, "STALE", "STUDY_CHANGED"),
        ({"manufacturer": "SIEMENS"}, "STALE", "MANUFACTURER_CHANGED"),
        ({"manufacturer_model_name": "Discovery ST"}, "STALE", "MODEL_CHANGED"),
        ({"software_version": "17.00"}, "STALE", "SOFTWARE_CHANGED"),
        ({"timepoint": "followup"}, "INVALID", "TIMEPOINT_MISMATCH"),
        ({"subject_id": "S2"}, "INVALID", "SUBJECT_MISMATCH"),
    ],
)
def test_scan_binding(pair, change, status, reason):
    tmp_path, _, fb, _, _ = pair
    o = validate_attestation(att(fb, tmp_path, **change), fb, tmp_path)
    assert o.status == status and reason in o.reasons


def test_unverifiable_scan_is_invalid(pair):
    tmp_path, _, fb, _, _ = pair
    blind = fb.model_copy(update={"software_versions": None, "study_instance_uid": None})
    o = validate_attestation(att(fb, tmp_path), blind, tmp_path)
    assert o.status == "INVALID"
    assert {"SOFTWARE_UNVERIFIABLE", "STUDY_UNVERIFIABLE"} <= set(o.reasons)


def test_loader_rejects_simulated_in_production_and_bad_schema(pair):
    tmp_path, _, fb, _, _ = pair
    a = att(fb, tmp_path)
    f = tmp_path / "att.yaml"
    f.write_text(yaml.safe_dump({"schema": SCHEMA, "attestations": [a.model_dump(mode="json")]}))
    good, rejected = load_attestations(f)
    assert good == {} and rejected[0].reasons == ["SIMULATED_NOT_ALLOWED_IN_PRODUCTION"]
    good, rejected = load_attestations(f, allow_simulated=True)
    assert list(good) == ["S1/baseline"] and not rejected
    f.write_text(yaml.safe_dump({"schema": "other", "attestations": []}))
    with pytest.raises(ValueError):
        load_attestations(f)
    assert load_attestations(tmp_path / "absent.yaml") == ({}, [])


# ------------------------------------------------------------------ rule integration (Part 5)


def test_no_attestation_is_byte_identical_and_not_established(pair):
    _, b, _, f, _ = pair
    for rs in ("qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0"):
        c, _ = identity(rs, pair_ctx(b, f))
        assert c.status == "UNKNOWN" and protocol_identity(c) == "NOT_ESTABLISHED"
        assert "protocol_identity" not in c.observed and c.rule_version == "1"


def test_valid_attestations_establish_with_warning_for_qiba_only(pair):
    tmp_path, b, fb, f, ff = pair
    outs = valid_outcomes(tmp_path, fb, ff)
    c, res = identity("qiba-fdg-1.14", pair_ctx(b, f, outs))
    assert c.status == "PASS_WITH_WARNING"
    assert protocol_identity(c) == "ESTABLISHED_WITH_WARNING"
    assert c.observed["warning"] == WARNING and WARNING in c.message
    ev = c.observed["attestation_evidence"]
    assert {e["attestation_id"] for e in ev if e["used"]} == {"ATT-baseline", "ATT-followup"}
    assert all(e["trust_level"] == "LEVEL_C" and len(e["source_sha256"]) == 64 for e in ev)
    assert {e["attestor_role"] for e in ev} == {"QUALIFIED_PET_PHYSICIST"}
    assert c.reasons[0].code == "EXTERNAL_RECONSTRUCTION_ATTESTATION"
    assert c.rule_version.endswith("+qiba-attestation-1")
    assert res.verdict != "ASSESSABLE"  # never silently fully verified
    assert assessability_layers(res)["PROTOCOL"]["checks"]["VT-PROTOCOL-IDENTITY"] == (
        "PASS_WITH_WARNING"
    )
    for rs in ("eanm-fdg-2.0", "percist-1.0"):  # unchanged: attestations ignored
        c2, _ = identity(rs, pair_ctx(b, f, outs))
        c0, _ = identity(rs, pair_ctx(b, f))
        assert c2 == c0 and c2.status == "UNKNOWN"


def test_out_of_scope_attestation_not_used(pair):
    tmp_path, b, fb, f, ff = pair
    scope = {"rule_scope": ["eanm-fdg-2.0", "percist-1.0"]}
    outs = valid_outcomes(tmp_path, fb, ff, scope, scope)
    c, _ = identity("qiba-fdg-1.14", pair_ctx(b, f, outs))
    assert c.status == "UNKNOWN" and protocol_identity(c) == "NOT_ESTABLISHED"
    assert {r.code for r in c.reasons} >= {"RECONSTRUCTION_ATTESTATION_NOT_USABLE"}
    assert not any(e["used"] for e in c.observed["attestation_evidence"])
    for rs in ("eanm-fdg-2.0", "percist-1.0"):
        assert identity(rs, pair_ctx(b, f, outs))[0].status == "UNKNOWN"


def test_one_timepoint_only_or_incomplete_is_not_established(pair):
    tmp_path, b, fb, f, ff = pair
    outs = valid_outcomes(tmp_path, fb, ff)
    c, _ = identity("qiba-fdg-1.14", pair_ctx(b, f, {"baseline": outs["baseline"]}))
    assert c.status == "UNKNOWN"
    outs = valid_outcomes(tmp_path, fb, ff, fkw={"time_of_flight": None})
    c, _ = identity("qiba-fdg-1.14", pair_ctx(b, f, outs))
    assert c.status == "UNKNOWN" and "time_of_flight" in c.message


def test_stale_attestation_not_used(pair):
    tmp_path, b, fb, f, ff = pair
    outs = valid_outcomes(tmp_path, fb, ff, fkw={"software_version": "17.00"})
    assert outs["followup"][0].status == "STALE"
    c, _ = identity("qiba-fdg-1.14", pair_ctx(b, f, outs))
    assert c.status == "UNKNOWN"


def test_attested_values_differ_between_timepoints_is_contradicted(pair):
    tmp_path, b, fb, f, ff = pair
    outs = valid_outcomes(tmp_path, fb, ff, fkw={"iterations": 3})
    c, res = identity("qiba-fdg-1.14", pair_ctx(b, f, outs))
    assert c.status == "FAIL" and protocol_identity(c) == "CONTRADICTED"
    assert res.verdict == "NOT_ASSESSABLE"


def test_attestation_contradicting_dicom_is_contradicted(tmp_path):
    recon = {"ReconstructionMethod": "OSEM 2i28s", "ConvolutionKernel": "GAUSS 6"}
    (b, fb), (f, ff) = (
        scan(tmp_path, n, overrides=recon, drop=()) for n in ("baseline", "followup")
    )
    outs = valid_outcomes(tmp_path, fb, ff, bkw={"iterations": 4})
    c, _ = identity("qiba-fdg-1.14", pair_ctx(b, f, outs))
    assert c.status == "FAIL" and "DICOM" in c.message


def test_two_attestations_disagree_is_contradicted(pair):
    tmp_path, b, fb, f, ff = pair
    outs = valid_outcomes(tmp_path, fb, ff)
    other = att(fb, tmp_path, attestation_id="ATT-b2", subsets=16)
    outs["baseline"].append(validate_attestation(other, fb, tmp_path))
    c, _ = identity("qiba-fdg-1.14", pair_ctx(b, f, outs))
    assert c.status == "FAIL" and "attestations disagree" in c.message


def test_attestation_cannot_fill_non_reconstruction_unknowns(tmp_path):
    (b, fb), (f, ff) = (
        scan(tmp_path, n, drop=(*NO_RECON, "CorrectedImage")) for n in ("baseline", "followup")
    )
    outs = valid_outcomes(tmp_path, fb, ff)
    c, _ = identity("qiba-fdg-1.14", pair_ctx(b, f, outs))
    assert c.status == "UNKNOWN" and "non-reconstruction" in c.message


# ------------------------------------------------------------------ end-to-end audit + report


def _trial(tmp_path):
    root = tmp_path / "trial"
    facts = {}
    for name in ("baseline", "followup"):
        study = generate_uid()
        series, _ = write_image_series(
            root / "S1" / name, modality="PT", study_uid=study, pet_overrides=SCANNER, drop=NO_RECON
        )
        facts[name] = ScanFacts(
            subject_id="S1",
            timepoint=name,
            study_instance_uid=study,
            series_instance_uid=series,
            manufacturer=SCANNER["Manufacturer"],
            manufacturer_model_name=SCANNER["ManufacturerModelName"],
            software_versions=["16.01"],
        )
    (root / "trial.yaml").write_text(
        yaml.safe_dump(
            {
                "trial_id": "T",
                "ruleset": "qiba-fdg-1.14",
                "timepoint_order": list(facts),
                "reference_proposals": "off",
            }  # fmt: skip
        )
    )
    adir = tmp_path / "attest"
    adir.mkdir()
    atts = [att(fx, adir).model_dump(mode="json") for fx in facts.values()]
    (adir / "att.yaml").write_text(yaml.safe_dump({"schema": SCHEMA, "attestations": atts}))
    return root, adir / "att.yaml"


def test_audit_end_to_end_report_and_export(tmp_path):
    root, afile = _trial(tmp_path)
    plain = run_trial_audit(root, "qiba-fdg-1.14")
    assert plain.recon_attestations == []
    prod = run_trial_audit(root, "qiba-fdg-1.14", attestations_file=afile)
    assert {o.status for o in prod.recon_attestations} == {"INVALID"}  # simulated: refused
    test = run_trial_audit(
        root, "qiba-fdg-1.14", attestations_file=afile, allow_simulated_attestations=True
    )
    c = next(c for c in test.pairs[0].checks if c.rule_id == "VT-PROTOCOL-IDENTITY")
    assert c.status == "PASS_WITH_WARNING"
    rows = attestation_rows(test)
    assert {r["status"] for r in rows} == {"VALID"}
    assert all(r["affected_rule_set"] == "qiba-fdg-1.14" for r in rows)
    md = audit_report_md(test)
    assert "EXTERNAL RECONSTRUCTION ATTESTATION USED" in md
    paths = {p.name for p in export_audit(test, tmp_path / "out")}
    assert "reconstruction_attestations.csv" in paths
    assert "PASS_WITH_WARNING" in (tmp_path / "out" / "rule_summary.csv").read_text()
    # no attestations -> no new keys / files
    export_audit(plain, tmp_path / "plain")
    assert "recon_attestation" not in (tmp_path / "plain" / "trial_audit.json").read_text()
    assert not (tmp_path / "plain" / "reconstruction_attestations.csv").exists()
    for rs in ("eanm-fdg-2.0", "percist-1.0"):
        a0 = run_trial_audit(root, rs)
        a1 = run_trial_audit(root, rs, attestations_file=afile, allow_simulated_attestations=True)
        assert [c.model_dump() for c in a0.pairs[0].checks] == [
            c.model_dump() for c in a1.pairs[0].checks
        ]


def test_report_view_from_exported_json(tmp_path):
    import json

    from voxeltrace.trial.attestation_report import attestation_table, banner_needed, identity_rows

    root, afile = _trial(tmp_path)
    test = run_trial_audit(
        root, "qiba-fdg-1.14", attestations_file=afile, allow_simulated_attestations=True
    )
    export_audit(test, tmp_path / "o")
    d = json.loads((tmp_path / "o" / "trial_audit.json").read_text())
    assert banner_needed(d)
    (row,) = identity_rows(d)
    assert (
        row["protocol_identity"] == "ESTABLISHED_WITH_WARNING" and row["trust_level"] == "LEVEL_C"
    )
    t = attestation_table(d)
    assert {r["attestor_role"] for r in t} == {"QUALIFIED_PET_PHYSICIST"}
    assert all(len(r["source_sha256"]) == 64 for r in t)
    plain = run_trial_audit(root, "qiba-fdg-1.14")
    export_audit(plain, tmp_path / "p")
    d = json.loads((tmp_path / "p" / "trial_audit.json").read_text())
    assert not banner_needed(d) and attestation_table(d) == []
    assert identity_rows(d)[0]["protocol_identity"] == "NOT_ESTABLISHED"
