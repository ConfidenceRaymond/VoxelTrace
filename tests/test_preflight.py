"""Quantitative Preflight (VT-PREFLIGHT-1): known-answer tests on synthetic DICOM."""

from __future__ import annotations

import json

import pytest
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.cli import main as cli
from voxeltrace.preflight import preflight_batch, preflight_scan_dir
from voxeltrace.preflight.reasons import CATALOG
from voxeltrace.preflight.schema import worst_state

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
    "CorrectedImage": ["NORM", "DTIM", "ATTN", "SCAT", "DECY", "RAN"],
}


def pet(root, name="PET", study=None, for_uid=None, **ov):
    study = study or generate_uid()
    write_image_series(
        root / name, modality="PT", study_uid=study, for_uid=for_uid,
        pet_overrides={**GOOD, **ov.pop("over", {})}, **ov,
    )  # fmt: skip
    return study


def codes(scan):
    return {f.reason_code for s in scan.series for f in s.findings} | {
        f.reason_code for f in scan.findings
    }


def scan_with_ct(tmp_path, n_ct=4, ct_for=None, **ov):
    for_uid = generate_uid()
    study = pet(tmp_path, for_uid=for_uid, **ov)
    write_image_series(
        tmp_path / "CT", modality="CT", study_uid=study, for_uid=ct_for or for_uid,
        n_slices=n_ct, rows=6, cols=6, pixel_spacing=(1.0, 1.0), slope=1.0, intercept=-1024.0,
    )  # fmt: skip
    return preflight_scan_dir(tmp_path)


def test_clean_scan_ready_or_only_expected_warnings(tmp_path):
    sc = scan_with_ct(tmp_path, n_ct=25)
    assert sc.series[0].facts["validator_eligible"]
    blocking = [f for s in sc.series for f in s.findings if f.severity == "BLOCKING"]
    assert not blocking and sc.state == "READY_TO_QUANTIFY"
    assert "CT_NOT_IN_PET_FRAME" not in codes(sc) and "CT_NOT_VOLUMETRIC" not in codes(sc)


@pytest.mark.parametrize(
    ("over", "code", "state"),
    [
        ({"Units": "CNTS"}, "UNSUPPORTED_UNITS", "DO_NOT_QUANTIFY"),
        ({"DecayCorrection": "NONE"}, "UNSUPPORTED_DECAY_CORRECTION", "DO_NOT_QUANTIFY"),
        ({"PatientWeight": "0"}, None, "DO_NOT_QUANTIFY"),
        ({"DecayFactor": "1.5"}, "DECAY_FACTOR_INCONSISTENT", "DO_NOT_QUANTIFY"),
        ({"PatientSize": ""}, "MISSING_PATIENTSIZE", None),
        ({"PatientSex": "O"}, "UNSUPPORTED_PATIENTSEX_FOR_SUL", None),
        ({"ImageType": ["DERIVED", "SECONDARY"]}, "DERIVED_IMAGE", None),
        ({"SOPClassUID": "1.2.840.10008.5.1.4.1.1.7"}, "SECONDARY_CAPTURE", "DO_NOT_QUANTIFY"),
        ({"ReconstructionMethod": ""}, "RECONSTRUCTION_INCOMPLETE", None),
        ({"SoftwareVersions": ""}, "SOFTWARE_UNKNOWN", None),
    ],
)  # fmt: skip
def test_known_answers(tmp_path, over, code, state):
    sc = scan_with_ct(tmp_path, n_ct=25, over=over)
    if code:
        assert code in codes(sc), codes(sc)
    if state:
        assert sc.series[0].state == state
    for s in sc.series:
        for f in s.findings:
            assert f.remediation and f.recoverable in ("YES", "NO", "MAYBE") and f.evidence


def test_missing_weight_is_blocking(tmp_path):
    sc = scan_with_ct(tmp_path, n_ct=25, drop=("PatientWeight",))
    assert sc.series[0].state == "DO_NOT_QUANTIFY"
    assert any(f.severity == "BLOCKING" for f in sc.series[0].findings)


def test_missing_tracer(tmp_path):
    sc = scan_with_ct(tmp_path, n_ct=25, rp_overrides={"Radiopharmaceutical": None})
    assert "TRACER_UNKNOWN" in codes(sc)


def test_ct_frame_checks(tmp_path):
    assert "CT_NOT_IN_PET_FRAME" in codes(scan_with_ct(tmp_path / "a", ct_for=generate_uid()))
    assert "CT_NOT_VOLUMETRIC" in codes(scan_with_ct(tmp_path / "b", n_ct=1))


def test_no_pet_and_multiple_pet(tmp_path):
    write_image_series(tmp_path / "x" / "CT", modality="CT", study_uid=generate_uid(),
                       rows=6, cols=6, slope=1.0, intercept=-1024.0)  # fmt: skip
    assert preflight_scan_dir(tmp_path / "x").state == "DO_NOT_QUANTIFY"
    pet(tmp_path / "y", "PET1")
    pet(tmp_path / "y", "PET2")
    sc = preflight_scan_dir(tmp_path / "y")
    assert "MULTIPLE_PET_SERIES" in codes(sc) and sc.state in ("NEEDS_REVIEW", "DO_NOT_QUANTIFY")


def test_batch_layouts_and_cli(tmp_path):
    for subj in ("S1", "S2"):
        for tp in ("baseline", "followup"):
            pet(tmp_path / "trial" / subj / tp)
    b = preflight_batch(tmp_path / "trial")
    assert b.summary["scans"] == 4 and {s.subject for s in b.scans} == {"S1", "S2"}
    single = preflight_batch(tmp_path / "trial" / "S1" / "baseline")
    assert single.summary["scans"] == 1
    assert cli(["preflight", str(tmp_path / "trial"), "--out", str(tmp_path / "o")]) == 0
    data = json.loads((tmp_path / "o" / "preflight.json").read_text())
    assert data["schema_version"] == "VT-PREFLIGHT-1" and len(data["scans"]) == 4
    assert (tmp_path / "o" / "preflight.csv").read_text().startswith("subject,scan,")
    assert cli(["preflight", str(tmp_path / "missing")]) == 2


def test_preflight_never_reports_suv_values(tmp_path):
    sc = scan_with_ct(tmp_path, n_ct=25)
    text = sc.model_dump_json()
    assert "suv_per_bqml" not in text and "suv_range" not in text


def test_state_precedence_and_catalog():
    from voxeltrace.preflight.checks import finding

    f = [
        finding("MISSING_PATIENTSIZE", "x", "t"),
        finding("UNSUPPORTED_UNITS", "y", "t", refusal=True),
    ]
    assert worst_state(f) == "DO_NOT_QUANTIFY"
    assert worst_state([finding("MULTIPLE_PET_SERIES", "z", "t")]) == "NEEDS_REVIEW"
    assert worst_state([]) == "READY_TO_QUANTIFY"
    assert all(s.remediation and s.recoverable in ("YES", "NO", "MAYBE") for s in CATALOG.values())
