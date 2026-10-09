"""Vendor knowledge base: schema and honesty constraints (nothing inferred)."""

from pathlib import Path

import yaml

KB = yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "configs" / "vendor_kb.yaml").read_text()
)
REQUIRED = {"vendor", "model", "architecture", "public_dicom_availability", "public_conformance_docs",
            "documented_private_fields", "observed_in_open_data", "timing_and_reconstruction_notes",
            "anonymization_risks", "parser_coverage", "validation_status"}  # fmt: skip


def test_schema_and_architecture():
    assert KB["schema"] == "VT-VENDOR-KB-1"
    for e in KB["entries"]:
        assert set(e) >= REQUIRED, e["model"]
        assert e["architecture"] in {"CONVENTIONAL_AFOV", "LONG_AFOV", "TOTAL_BODY", "PET_MR"}


def test_required_models_present():
    models = {(e["vendor"], e["model"]) for e in KB["entries"]}
    for want in [("SIEMENS", "Biograph mCT"), ("SIEMENS", "Biograph Vision"), ("SIEMENS", "Biograph Vision Quadra"),
                 ("GE", "Discovery LS"), ("GE", "Discovery MI"), ("GE", "Omni Legend"),
                 ("PHILIPS", "Ingenuity"), ("PHILIPS", "Vereos"), ("UNITED IMAGING", "uEXPLORER"),
                 ("UNITED IMAGING", "uMI Panorama"), ("UNITED IMAGING", "uMI 780"), ("UNITED IMAGING", "uPMR 790")]:  # fmt: skip
        assert want in models, want


def test_no_unearned_validation_claims():
    for e in KB["entries"]:
        observed = e["observed_in_open_data"]["series_sampled"]
        if observed == 0:
            assert e["validation_status"] == "NOT_VALIDATED", e["model"]
        if e["vendor"] == "UNITED IMAGING":
            assert e["validation_status"] == "NOT_VALIDATED"
            assert (
                "NO_OPEN_DICOM" in e["public_dicom_availability"]
                or "DERIVED" in e["public_dicom_availability"]
                or "GATED" in e["public_dicom_availability"]
            )
        if "VALIDATED" in e["validation_status"] and "NOT_VALIDATED" not in e["validation_status"]:
            assert "REAL_PAIR" in e["validation_status"]
