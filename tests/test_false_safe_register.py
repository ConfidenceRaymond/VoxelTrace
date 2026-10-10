"""Executable entries of docs/validation/false_safe_risk_register.md.

FS-01 is a CHARACTERIZATION test: it pins current behaviour that is a documented false-safe
risk, so that any change to it is deliberate (a new rule version), and checks that the
delivery package discloses it. It does not endorse the behaviour."""

from __future__ import annotations

import csv

import yaml
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.delivery import build_delivery_package, reconstruction_evidence
from voxeltrace.pilot import run_audit

BASE = {"PatientSize": "1.75", "PatientSex": "M", "Manufacturer": "GE MEDICAL SYSTEMS", "PatientID": "P1",
        "ManufacturerModelName": "Discovery STE", "SoftwareVersions": "40.03", "FrameReferenceTime": "0",
        "DecayFactor": "1.0", "ConvolutionKernel": "STANDARD"}  # fmt: skip


def _pair(tmp_path, recon_a, recon_b):
    root = tmp_path / "trial"
    for i, (tp, date, rm) in enumerate(
        (("baseline", "20200101", recon_a), ("followup", "20200301", recon_b))
    ):
        write_image_series(root / "S1" / tp, modality="PT", study_uid=generate_uid(), slope=1.5 + i / 10,
                           pet_overrides={**BASE, "ReconstructionMethod": rm, "AcquisitionDate": date, "SeriesDate": date},
                           rp_overrides={"RadiopharmaceuticalStartDateTime": f"{date}091500"})  # fmt: skip
    (root / "trial.yaml").write_text(yaml.safe_dump({"trial_id": "FS", "ruleset": "qiba-fdg-1.14", "reference_proposals": "off",
                                                     "timepoint_order": ["baseline", "followup"]}))  # fmt: skip
    run_audit(root, tmp_path / "out", rulesets=("qiba-fdg-1.14",))
    return tmp_path / "out" / "audit_bundle"


def _identity(bundle):
    import json

    a = json.loads((bundle / "rules" / "qiba-fdg-1.14" / "trial_audit.json").read_text())
    return next(c for c in a["pairs"][0]["checks"] if c["rule_id"] == "VT-PROTOCOL-IDENTITY")


def test_fs01_identical_generic_text_implies_identical_parameters_and_is_disclosed(tmp_path):
    b = _pair(tmp_path, "OSEM", "OSEM")  # iterations / subsets / TOF / PSF not encoded
    c = _identity(b)
    # current behaviour (VT-PROTOCOL-IDENTITY v1): text identity -> parameters SAME -> PASS
    assert c["status"] == "PASS" and c["observed"]["iterations"] == "SAME"
    r = build_delivery_package(b, tmp_path / "pkg")
    assert r["status"] == "OK"
    rows = list(csv.DictReader((tmp_path / "pkg" / "pair_results.csv").open()))
    assert rows[0]["reconstruction_evidence"].startswith("TEXT_IMPLIED")
    assert "TEXT_IMPLIED" in (tmp_path / "pkg" / "README_FIRST.md").read_text()
    assert (
        "would not be detected" in (tmp_path / "pkg" / "methodology_and_limitations.md").read_text()
    )


def test_fs01_different_text_is_never_identity_pass(tmp_path):
    c = _identity(_pair(tmp_path, "OSEM 2i21s", "OSEM 3i21s"))
    assert c["status"] == "FAIL"


def test_reconstruction_evidence_labels():
    f = lambda text="OSEM", **t: {"fields": {k: {"trust": t.get(k, "LEVEL_A"),  # noqa: E731
                                                 "value": text if k == "reconstruction_method" else 1} for k in
                                ("reconstruction_method", "iterations", "subsets", "time_of_flight",
                                 "psf_resolution_modelling", "filter_kernel")}}  # fmt: skip
    assert (
        reconstruction_evidence({"S/a": f(), "S/b": f()}, "S", "a", "b") == "STRUCTURED (LEVEL_A)"
    )
    assert reconstruction_evidence(
        {"S/a": f(iterations="LEVEL_D"), "S/b": f()}, "S", "a", "b"
    ).startswith("FREE_TEXT")
    assert (
        reconstruction_evidence({"S/a": f(time_of_flight="NONE"), "S/b": f()}, "S", "a", "b")
        == "TEXT_IMPLIED: time_of_flight"
    )
    # a missing parameter without identical text is not text-implied: it is simply not established
    assert (
        reconstruction_evidence(
            {"S/a": f(time_of_flight="NONE"), "S/b": f(text="OSEM 2i")}, "S", "a", "b"
        )
        == "NOT_ESTABLISHED: time_of_flight"
    )
    assert (
        reconstruction_evidence(
            {"S/a": f(text=None, time_of_flight="NONE"), "S/b": f(text=None)}, "S", "a", "b"
        )
        == "NOT_ESTABLISHED: time_of_flight"
    )
    assert reconstruction_evidence({}, "S", "a", "b") == "NO_FINGERPRINT"
