"""Reconstruction evidence trust model (reporting only)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydicom.dataset import Dataset

from voxeltrace.evidence import recon_trust as rt
from voxeltrace.evidence.recon_trust import (
    REQUIRED_PARAMETERS,
    EvidenceItem,
    ReconstructionAttestation,
    classify_identity,
    dicom_evidence,
    provenance_report_md,
)

VALUES = {
    "reconstruction_method": "OSEM",
    "iterations": 2,
    "subsets": 28,
    "post_filter": "GAUSS 6",
    "time_of_flight": False,
    "psf_resolution_modelling": False,
}


def items(tp, level="LEVEL_A", **override):
    vals = {**VALUES, **override}
    return [
        EvidenceItem(parameter=p, timepoint=tp, value=vals[p], trust_level=level, source="x")
        for p in REQUIRED_PARAMETERS
    ]


def header(**kw):
    ds = Dataset()
    for k, v in kw.items():
        setattr(ds, k, v)
    return ds


def attestation(tp, **kw):
    base = dict(
        subject_id="S1",
        study_pseudonym="st",
        series_pseudonym="se",
        timepoint=tp,
        scanner="GE Discovery LS",
        software_version="16.01",
        source_type="SCANNER_PROTOCOL_EXPORT",
        source_document="protocol_export.pdf",
        attestor="site physicist",
        attested_at=datetime(2026, 10, 8, tzinfo=UTC),
        confidence="CONFIRMED",
        attachment_sha256="a" * 64,
        rule_applicability=["percist-1.0"],
        simulated=False,
        **VALUES,
    )
    base.update(kw)
    return ReconstructionAttestation(**base)


def test_complete_structured_same_established():
    a = classify_identity(items("baseline"), items("followup"))
    assert a.classification == "ESTABLISHED" and a.unresolved == []
    assert a.highest_trust_level == "LEVEL_A"


def test_complete_structured_different_contradicted():
    a = classify_identity(items("baseline"), items("followup", iterations=3))
    assert a.classification == "CONTRADICTED"
    assert any("iterations: DIFFERENT" in r for r in a.reasons)


def test_standard_dicom_fields_extracted_as_level_a():
    hs = [
        header(ReconstructionMethod="OSEM", NumberOfIterations=2, NumberOfSubsets=28,
               ConvolutionKernel="GAUSS 6")
        for _ in range(3)
    ]  # fmt: skip
    ev = {i.parameter: i for i in dicom_evidence(hs, "baseline")}
    assert ev["iterations"].trust_level == "LEVEL_A" and ev["iterations"].value == "2"
    # TOF / PSF have no classic standard attribute: never filled from DICOM alone
    assert "time_of_flight" not in ev and "psf_resolution_modelling" not in ev


def test_standard_field_missing_on_one_slice_not_used():
    hs = [header(NumberOfIterations=2), header(NumberOfIterations=2), header()]
    assert not [i for i in dicom_evidence(hs, "baseline") if i.parameter == "iterations"]


def _private(value):
    ds = Dataset()
    ds.add_new(0x00110010, "LO", "ACME_RECON")
    ds.add_new(0x00111001, "LO", value)
    return ds


def test_vendor_private_documented_same_and_different(monkeypatch):
    monkeypatch.setitem(
        rt.DOCUMENTED_PRIVATE_TAGS, ("ACME_RECON", 0x0011, 0x01), ("iterations", "ACME DCS p.1")
    )
    b = [i for i in items("baseline", "LEVEL_B") if i.parameter != "iterations"]
    f = [i for i in items("followup", "LEVEL_B") if i.parameter != "iterations"]
    same = classify_identity(
        b + dicom_evidence([_private("2")], "baseline"),
        f + dicom_evidence([_private("2")], "followup"),
    )
    assert same.classification == "ESTABLISHED"
    diff = classify_identity(
        b + dicom_evidence([_private("2")], "baseline"),
        f + dicom_evidence([_private("4")], "followup"),
    )
    assert diff.classification == "CONTRADICTED"


def test_unsupported_private_tags_are_level_u_and_not_establishing():
    ev_b = dicom_evidence([_private("2")], "baseline")
    ev_f = dicom_evidence([_private("2")], "followup")
    assert {i.trust_level for i in ev_b} == {"LEVEL_U"}
    a = classify_identity(ev_b, ev_f)
    assert a.classification == "NOT_ESTABLISHED"
    assert a.highest_trust_level == "LEVEL_U"


def test_free_text_only_not_established():
    hs = [header(SeriesDescription="OSEM 2i28s", ProtocolName="WB")]
    a = classify_identity(dicom_evidence(hs, "baseline"), dicom_evidence(hs, "followup"))
    assert a.classification == "NOT_ESTABLISHED" and a.highest_trust_level == "LEVEL_D"
    # free text is never parsed into a parameter
    assert all(p.status == "NOT_ESTABLISHED" for p in a.parameters)


def test_free_text_level_d_parameter_items_not_establishing():
    a = classify_identity(items("baseline", "LEVEL_D"), items("followup", "LEVEL_D"))
    assert a.classification == "NOT_ESTABLISHED"


def test_image_derived_only_not_established():
    a = classify_identity(items("baseline", "LEVEL_E"), items("followup", "LEVEL_E"))
    assert a.classification == "NOT_ESTABLISHED"
    assert "ONLY_LEVEL_E_BASELINE" in a.parameters[0].reasons


def test_missing_both_not_established_with_remediation():
    a = classify_identity([], [])
    assert a.classification == "NOT_ESTABLISHED"
    assert a.unresolved == list(REQUIRED_PARAMETERS)
    assert a.remediation and "attestation" in a.remediation[0]


def test_attestation_only_established_with_warning_when_applicable():
    atts = (attestation("baseline"), attestation("followup", attachment_sha256="b" * 64))
    a = classify_identity([], [], ruleset="percist-1.0", attestations=atts)
    assert a.classification == "ESTABLISHED_WITH_WARNING"
    assert all(p.status == "SAME_WITH_WARNING" for p in a.parameters)


def test_attestation_not_applicable_to_ruleset_not_established():
    atts = (attestation("baseline"), attestation("followup"))
    a = classify_identity([], [], ruleset="qiba-fdg-1.14", attestations=atts)
    assert a.classification == "NOT_ESTABLISHED"
    assert any("ATTESTATION_NOT_APPLICABLE" in r for p in a.parameters for r in p.reasons)
    assert classify_identity([], [], attestations=atts).classification == "NOT_ESTABLISHED"


def test_attestation_validation():
    with pytest.raises(ValidationError):
        attestation("baseline", attachment_sha256="not-a-hash")
    with pytest.raises(ValidationError):
        attestation("baseline", attestor="")
    with pytest.raises(ValidationError):
        attestation("baseline", rule_applicability=[])
    with pytest.raises(ValueError, match="simulated"):
        classify_identity([], [], attestations=(attestation("baseline", simulated=True),))


def test_contradiction_across_establishing_levels():
    # LEVEL_A says 2 iterations, an attestation for the same series says 3
    atts = (attestation("baseline", iterations=3), attestation("followup"))
    a = classify_identity(
        items("baseline"), items("followup"), ruleset="percist-1.0", attestations=atts
    )
    assert a.classification == "CONTRADICTED"
    it = next(p for p in a.parameters if p.parameter == "iterations")
    assert it.status == "CONFLICT" and "EVIDENCE_CONFLICT_BASELINE" in it.reasons


def test_lower_trust_disagreement_downgrades_to_warning():
    b = items("baseline") + [
        EvidenceItem(parameter="iterations", timepoint="baseline", value=4,
                     trust_level="LEVEL_D", source="ImageComments")
    ]  # fmt: skip
    a = classify_identity(b, items("followup"))
    assert a.classification == "ESTABLISHED_WITH_WARNING"
    assert "iterations: LOWER_TRUST_EVIDENCE_DISAGREES" in a.reasons


def test_inputs_not_mutated_and_report_renders():
    b, f = [], []
    classify_identity(b, f, ruleset="percist-1.0",
                      attestations=(attestation("baseline"), attestation("followup")))  # fmt: skip
    assert b == [] and f == []
    md = provenance_report_md("S1", classify_identity([], []), {"baseline": [], "followup": []})
    assert "NOT_ESTABLISHED" in md and "What the site should provide" in md


def test_no_rule_reads_the_trust_model():
    src = Path(__file__).resolve().parents[1] / "src" / "voxeltrace"
    users = [
        p for p in src.rglob("*.py")
        if "recon_trust" in p.read_text() and p.name != "recon_trust.py"
    ]  # fmt: skip
    assert users == []
