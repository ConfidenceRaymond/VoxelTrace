import json

import pytest
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.evidence import (
    assess_protocol_qc,
    compare_protocols,
    extract_protocol,
)
from voxeltrace.evidence.reconstruction import parse_iterations_subsets
from voxeltrace.ingest import discover_dicom
from voxeltrace.quant.suv import audit_pet_headers, validate_suv_eligibility

RECON = {
    "ReconstructionMethod": "PSF+TOF 2i21s",
    "ConvolutionKernel": "XYZ Gauss2.00",
    "ActualFrameDuration": "120000",
    "SeriesType": ["WHOLE BODY", "IMAGE"],
    "ManufacturerModelName": "Biograph128_mCT",
    "Manufacturer": "SIEMENS",
    "CorrectedImage": ["NORM", "DTIM", "ATTN", "SCAT", "DECY", "RAN"],
}


def protocol(tmp_path, name="a", *, overrides=None, drop=(), **kw):
    ov = {**RECON, **(overrides or {})}
    write_image_series(
        tmp_path / name, modality="PT", study_uid=generate_uid(), pet_overrides=ov, drop=drop, **kw
    )
    (s,) = discover_dicom(tmp_path / name).series
    val, inputs = validate_suv_eligibility(audit_pet_headers(s))
    return extract_protocol(s, inputs, val), val


# ---------------------------------------------------------------- extraction


def test_real_like_extraction_and_free_text_parsing(tmp_path):
    p, _ = protocol(tmp_path)
    r = p.reconstruction
    assert r.reconstruction_method.value == "PSF+TOF 2i21s"
    assert (r.iterations.value, r.subsets.value) == (2, 21)
    assert r.iterations.derivation == "free_text_pattern"
    assert r.time_of_flight.value is True and r.psf_resolution_modelling.value is True
    assert r.post_filter_gaussian_width.value == 2.0
    assert r.post_filter_gaussian_width.status == "PRESENT_BUT_AMBIGUOUS"  # unit not stated
    assert r.algorithm_family.status == "MISSING"  # OSEM not stated -> not inferred
    assert r.voxel_size_mm.value == [3.0, 2.0, 4.0]
    a = p.acquisition
    assert a.uptake_interval_s.value == 3600.0
    assert a.uptake_interval_s.derivation == "validated_suv_input"
    assert a.number_of_bed_positions.status == "MISSING"
    assert a.is_dynamic.value is False and a.bed_duration_s.value == 120.0
    c = p.corrections
    assert {k for k, f in c.applied.items() if f.value is True} == {
        "attenuation",
        "scatter",
        "randoms",
        "decay",
        "normalization",
        "dead_time",
    }
    assert c.applied["sensitivity"].status == "MISSING"


def test_absent_tokens_mean_unknown_not_false(tmp_path):
    p, _ = protocol(tmp_path, overrides={"ReconstructionMethod": "OSEM3D 4i8s"})
    r = p.reconstruction
    assert r.algorithm_family.value == "OSEM"
    assert r.time_of_flight.status == "MISSING" and r.time_of_flight.value is None
    assert r.psf_resolution_modelling.status == "MISSING"


def test_structured_attributes_take_precedence(tmp_path):
    p, _ = protocol(
        tmp_path,
        overrides={
            "NumberOfIterations": 3,
            "NumberOfSubsets": 12,
            "TimeOfFlightInformationUsed": "NO",
        },
    )
    r = p.reconstruction
    assert (r.iterations.value, r.subsets.value) == (3, 12)
    assert r.iterations.derivation == "standard_tag"
    assert r.time_of_flight.value is False and r.time_of_flight.derivation == "standard_tag"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("PSF+TOF 2i21s", (2, 21)),
        ("OSEM 3i 24s", (3, 24)),
        ("FBP", None),
        (None, None),
        ("2i21s then 3i21s", "AMBIGUOUS"),
        ("v2.1i5s", None),
    ],
)
def test_iteration_subset_pattern(text, expected):
    assert parse_iterations_subsets(text) == expected


def test_missing_scanner_metadata(tmp_path):
    p, val = protocol(tmp_path, drop=["Manufacturer", "ManufacturerModelName"])
    assert p.scanner.manufacturer_model_name.status == "MISSING"
    qc = assess_protocol_qc(p, val.eligible)
    codes = {i.code for i in qc.items}
    assert {"MISSING_SCANNER_MODEL", "MISSING_MANUFACTURER"} <= codes
    assert qc.usable_for == {
        "suv": True,
        "lesion_metrics": True,
        "cross_scan_comparison": False,
    }  # case not failed as a whole


def test_missing_reconstruction_info(tmp_path):
    p, val = protocol(
        tmp_path,
        drop=["ReconstructionMethod", "ConvolutionKernel"],
        per_slice={k: {} for k in range(3)},
    )
    qc = assess_protocol_qc(p, val.eligible)
    assert p.reconstruction.iterations.status == "MISSING"
    assert "MISSING_RECONSTRUCTION_ALGORITHM" in {i.code for i in qc.items}


def test_corrected_image_absent_is_unknown_not_false(tmp_path):
    p, val = protocol(tmp_path, drop=["CorrectedImage"])
    assert all(f.status == "MISSING" and f.value is None for f in p.corrections.applied.values())
    assert p.corrections.applied_set() is None
    qc = assess_protocol_qc(p, val.eligible)
    assert not qc.usable_for["suv"] and "corrected_image" in qc.blocked_by["suv"]


def test_unlisted_flag_is_false(tmp_path):
    p, _ = protocol(tmp_path, overrides={"CorrectedImage": ["ATTN", "DECY"]})
    assert p.corrections.applied["scatter"].value is False
    assert "not declared" in p.corrections.applied["scatter"].note


def test_identifiers_never_copied(tmp_path):
    p, _ = protocol(
        tmp_path,
        overrides={
            "DeviceSerialNumber": "SN-12345",
            "InstitutionName": "Secret Hospital",
            "StationName": "PETCT01",
        },
    )
    assert set(p.scanner.identifying_attributes_recorded) == {
        "DeviceSerialNumber",
        "InstitutionName",
        "StationName",
    }
    blob = json.dumps(p.model_dump(mode="json"))
    assert "SN-12345" not in blob and "Secret Hospital" not in blob and "PETCT01" not in blob


def test_uptake_outside_qiba_window(tmp_path):
    p, val = protocol(
        tmp_path,
        rp_overrides={
            "RadiopharmaceuticalStartDateTime": "20200101084500",
            "RadiopharmaceuticalStartTime": "084500",
        },
    )
    assert p.acquisition.uptake_interval_s.value == 5400.0
    assert "UPTAKE_OUTSIDE_QIBA_WINDOW" in {i.code for i in assess_protocol_qc(p, True).items}


# ---------------------------------------------------------------- comparability


def test_same_scanner_same_reconstruction_comparable(tmp_path):
    a, _ = protocol(tmp_path, "a")
    b, _ = protocol(tmp_path, "b")
    r = compare_protocols(a, b)
    assert r.category == "COMPARABLE", r.statement
    assert not r.blocking_differences and not r.blocking_unknowns


def test_different_scanner_not_comparable(tmp_path):
    a, _ = protocol(tmp_path, "a")
    b, _ = protocol(
        tmp_path,
        "b",
        overrides={"ManufacturerModelName": "Discovery MI", "Manufacturer": "GE MEDICAL SYSTEMS"},
    )
    r = compare_protocols(a, b)
    assert r.category == "NOT_COMPARABLE"
    assert {"manufacturer", "scanner_model"} <= set(r.blocking_differences)
    assert "biological" in r.scope_note


def test_changed_voxel_size_not_comparable(tmp_path):
    a, _ = protocol(tmp_path, "a")
    b, _ = protocol(tmp_path, "b", pixel_spacing=(4.0, 4.0))
    r = compare_protocols(a, b)
    assert r.category == "NOT_COMPARABLE" and "voxel_size" in r.blocking_differences


def test_changed_filter_not_comparable(tmp_path):
    a, _ = protocol(tmp_path, "a")
    b, _ = protocol(tmp_path, "b", overrides={"ConvolutionKernel": "XYZ Gauss5.00"})
    r = compare_protocols(a, b)
    assert r.blocking_differences == ["post_filter"]


def test_changed_iterations_not_comparable(tmp_path):
    a, _ = protocol(tmp_path, "a")
    b, _ = protocol(tmp_path, "b", overrides={"ReconstructionMethod": "PSF+TOF 3i21s"})
    r = compare_protocols(a, b)
    assert set(r.blocking_differences) == {"reconstruction_method", "iterations"}


@pytest.mark.parametrize(
    ("inj", "category"),
    [
        ("091000", "COMPARABLE"),  # uptake 65 min vs 60 min: within ±10 min
        ("085500", "NOT_COMPARABLE"),  # 80 min vs 60 min
    ],
)
def test_changed_uptake_time(tmp_path, inj, category):
    a, _ = protocol(tmp_path, "a")
    b, _ = protocol(
        tmp_path,
        "b",
        rp_overrides={
            "RadiopharmaceuticalStartDateTime": "20200101" + inj,
            "RadiopharmaceuticalStartTime": inj,
        },
    )
    r = compare_protocols(a, b)
    assert r.category == category
    up = next(c for c in r.checks if c.name == "uptake_interval")
    assert up.result == ("WITHIN_TOLERANCE" if category == "COMPARABLE" else "DIFFERENT")


def test_correction_mismatch_not_comparable(tmp_path):
    a, _ = protocol(tmp_path, "a")
    b, _ = protocol(
        tmp_path, "b", overrides={"CorrectedImage": ["ATTN", "DECY", "NORM", "DTIM", "RAN"]}
    )
    r = compare_protocols(a, b)
    chk = next(c for c in r.checks if c.name == "correction_state")
    assert chk.result == "DIFFERENT" and chk.difference == ["scatter"]
    assert r.category == "NOT_COMPARABLE"


def test_insufficient_information(tmp_path):
    a, _ = protocol(tmp_path, "a")
    b, _ = protocol(tmp_path, "b", drop=["ReconstructionMethod", "ManufacturerModelName"])
    r = compare_protocols(a, b)
    assert r.category == "INSUFFICIENT_INFORMATION"
    assert {"scanner_model", "reconstruction_method"} <= set(r.blocking_unknowns)


def test_software_and_activity_differences_are_warnings(tmp_path):
    a, _ = protocol(tmp_path, "a")
    b, _ = protocol(
        tmp_path,
        "b",
        overrides={"SoftwareVersions": "VG70A"},
        rp_overrides={"RadionuclideTotalDose": "400000000"},
    )
    r = compare_protocols(a, b)
    assert r.category == "COMPARABLE_WITH_WARNINGS"
    assert {"software_version", "injected_activity"} <= set(r.warnings)
