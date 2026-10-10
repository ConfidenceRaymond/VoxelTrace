"""Partner intake contract VT-PARTNER-INTAKE-1."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.cli import main as cli
from voxeltrace.partner_intake import validate_partner_intake

TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "pilot"
    / "external_partner"
    / "partner_intake.yaml"
)


def pet(d, date="20200101", **ov):
    write_image_series(d, modality="PT", study_uid=generate_uid(), pet_overrides={
        "Manufacturer": "SIEMENS", "ManufacturerModelName": "Biograph128_mCT", "SoftwareVersions": "VG60A",
        "AcquisitionDate": date, "SeriesDate": date, **ov})  # fmt: skip


def entry(subj, tp, path, **kw):
    return {"site_id": "SITE-A", "subject_id": subj, "timepoint": tp, "tracer": "FDG", "expected_vendor": "SIEMENS",
            "expected_scanner_model": "Biograph128_mCT", "pet_path": path, "partner_review_required": True,
            "partner_reviewer_role": "PET_PHYSICIST", "notes": "", **kw}  # fmt: skip


def write(root, entries, **top):
    doc = {
        "schema": "VT-PARTNER-INTAKE-1",
        "organization_id": "ORG-X",
        "study_id": "STUDY-1",
        "entries": entries,
        **top,
    }
    p = root / "partner_intake.yaml"
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return p


def codes(r):
    return {f["code"] for f in r["findings"]}


def test_valid_intake(tmp_path):
    pet(tmp_path / "data" / "S1" / "bl")
    pet(tmp_path / "data" / "S1" / "fu", "20200301")
    r = validate_partner_intake(write(tmp_path, [entry("S1", "baseline", "data/S1/bl", expected_acquisition_date="2020-01-01"),
                                                 entry("S1", "followup", "data/S1/fu")]))  # fmt: skip
    assert r["status"] == "VALID", r["findings"]
    assert r["entries"] == 2 and r["review_required_entries"] == 2


def test_schema_paths_and_decisions_are_refused(tmp_path):
    pet(tmp_path / "data" / "S1" / "bl")
    p = write(tmp_path, [
        entry("S1", "baseline", "data/S1/bl", lesion_accepted=True),
        entry("S2", "baseline", "/abs/path"),
        entry("S3", "baseline", "../outside"),
        entry("S4", "baseline", "data/missing"),
        {"subject_id": "S5"},
        entry("S6", "baseline", "data/S1/bl", partner_review_required="yes", partner_reviewer_role="dr.x@hospital.org"),
    ], review_decision="ACCEPT")  # fmt: skip
    r = validate_partner_intake(p)
    assert r["status"] == "INVALID"
    assert {"HUMAN_DECISION_NOT_ACCEPTED", "PATH_ABSOLUTE", "PATH_ESCAPES_ROOT", "PATH_NOT_FOUND", "REQUIRED_FIELD_MISSING",
            "SCHEMA_INVALID", "PERSONAL_DATA_IN_ROLE", "SCAN_MAPPED_TO_MULTIPLE_SUBJECTS"} <= codes(r)  # fmt: skip


def test_duplicates_and_cross_entry_inconsistencies(tmp_path):
    pet(tmp_path / "data" / "S1" / "bl")
    pet(tmp_path / "data" / "S1" / "fu", "20200301")
    r = validate_partner_intake(write(tmp_path, [
        entry("S1", "baseline", "data/S1/bl"),
        entry("S1", "baseline", "data/S1/fu"),  # duplicate subject/timepoint
        entry("S1", "Follow-Up", "data/S1/fu", site_id="SITE-B", tracer="F-18 FLT"),  # same scan twice, other site
        entry("S1", "follow_up", "data/S1/fu"),
    ]))  # fmt: skip
    c = codes(r)
    assert {"DUPLICATE_ENTRY", "DUPLICATE_TIMEPOINT", "SCAN_MAPPED_TWICE", "SUBJECT_SITE_INCONSISTENT",
            "TRACER_NOT_RECOGNISED", "MIXED_TRACER"} <= c  # fmt: skip


def test_declared_vs_dicom_mismatch_and_not_pet(tmp_path):
    pet(tmp_path / "data" / "S1" / "bl", Manufacturer="GE MEDICAL SYSTEMS")
    write_image_series(tmp_path / "data" / "S1" / "ct", modality="CT", study_uid=generate_uid())
    r = validate_partner_intake(write(tmp_path, [
        entry("S1", "baseline", "data/S1/bl", expected_acquisition_date="2020-02-02", expected_software_version="VG70A"),
        entry("S1", "followup", "data/S1/ct"),
    ]))  # fmt: skip
    c = codes(r)
    assert {
        "VENDOR_MISMATCH",
        "ACQUISITION_DATE_MISMATCH",
        "SOFTWARE_VERSION_MISMATCH",
        "PET_PATH_NOT_PET",
    } <= c
    assert r["status"] == "INVALID"


def test_template_is_schema_valid_apart_from_placeholders():
    r = validate_partner_intake(TEMPLATE, check_dicom=False)
    c = codes(r)
    assert (
        "SCHEMA_INVALID" not in c
        and "HUMAN_DECISION_NOT_ACCEPTED" not in c
        and "REQUIRED_FIELD_MISSING" not in c
    )
    assert c <= {
        "PATH_NOT_FOUND",
        "TIMEPOINT_NAME_UNRECOGNISED",
        "SINGLE_TIMEPOINT",
        "POSSIBLE_IDENTIFIER",
        "UNKNOWN_FIELD",
    }


def test_cli_exit_codes(tmp_path, capsys):
    pet(tmp_path / "data" / "S1" / "bl")
    pet(tmp_path / "data" / "S1" / "fu", "20200301")
    ok = write(
        tmp_path, [entry("S1", "baseline", "data/S1/bl"), entry("S1", "followup", "data/S1/fu")]
    )
    assert cli(["validate-partner-intake", str(ok)]) == 0
    bad = write(tmp_path, [entry("S1", "baseline", "data/nope")])
    assert cli(["validate-partner-intake", str(bad), "--format", "json"]) == 3


def test_every_partner_intake_code_is_documented():
    import re

    from voxeltrace.remediation import remediation_matrix

    src = (
        Path(__file__).resolve().parents[1] / "src" / "voxeltrace" / "partner_intake.py"
    ).read_text()
    emitted = set(re.findall(r'add\(\s*"([A-Z_]+)"', src)) | {
        f"{a.upper()}_NOT_IN_DICOM"
        for a in ("Manufacturer", "ManufacturerModelName", "SoftwareVersions")
    }
    codes = {r["code"] for r in remediation_matrix()}
    assert emitted <= codes, emitted - codes
