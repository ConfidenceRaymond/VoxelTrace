"""SUL (hand-calculated oracles) and reference-region measurement."""

import numpy as np
import pydicom
import pytest
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from test_lesions import geom
from voxeltrace.ingest import discover_dicom
from voxeltrace.quant.reference_region import ReferenceRegionSpec, measure_reference_region
from voxeltrace.quant.sul import apply_sul, compute_sul, lbm_kg
from voxeltrace.quant.suv import compute_suv_for_series


# W = 70 kg, H = 1.75 m (175 cm), BMI = 22.857142857
#   James M: 1.10*70 - 128*(70/175)^2 = 77 - 20.48 = 56.52
#   James F: 1.07*70 - 148*0.16 = 74.9 - 23.68 = 51.22
#   Janma M: 9270*70/(6680 + 216*22.857142857) = 648900/11617.142857 = 55.857107722577
#   Janma F: 648900/(8780 + 244*22.857142857) = 648900/14357.142857 = 45.197014925373
@pytest.mark.parametrize(
    ("formula", "sex", "expected"),
    [
        ("LBMJAMES128", "M", 56.52),
        ("LBMJAMES128", "F", 51.22),
        ("LBMJANMA", "M", 55.857107722577),
        ("LBMJANMA", "F", 45.197014925373),
    ],
)
def test_lbm_oracles(formula, sex, expected):
    assert lbm_kg(formula, sex, 70.0, 1.75) == pytest.approx(expected, rel=1e-12)


def test_james_refused_beyond_its_maximum():
    # male, 175 cm: maximum at W* = 1.10*175^2/256 = 131.59 kg
    lbm_kg("LBMJAMES128", "M", 131.0, 1.75)
    with pytest.raises(ValueError, match="James formula invalid"):
        lbm_kg("LBMJAMES128", "M", 132.0, 1.75)
    assert lbm_kg("LBMJANMA", "M", 160.0, 1.75) > 0  # Janmahasatian stays defined


def _suv_series(tmp_path, **pet_overrides):
    write_image_series(
        tmp_path,
        modality="PT",
        study_uid=generate_uid(),
        pet_overrides={"PatientWeight": "70", **pet_overrides},
    )
    (s,) = discover_dicom(tmp_path).series
    out = compute_suv_for_series(s)
    headers = [pydicom.dcmread(i.path, stop_before_pixels=True) for i in s.instances]
    return out, headers


def test_sul_end_to_end_and_suv_unchanged(tmp_path):
    out, headers = _suv_series(tmp_path, PatientSex="M", PatientSize="1.75")
    before = out.suv.copy()
    sul = compute_sul(out.result, headers, "LBMJAMES128")
    assert sul.status == "PASS" and sul.lbm_kg == pytest.approx(56.52, rel=1e-12)
    # SUL = SUV * LBM / W exactly
    sul_img = apply_sul(out.activity.array, sul)
    np.testing.assert_allclose(sul_img, out.suv * 56.52 / 70.0, rtol=1e-12)
    np.testing.assert_array_equal(out.suv, before)  # SUVbw untouched
    assert sul.height_source.startswith("(0010,1020)")


@pytest.mark.parametrize(
    ("over", "code"),
    [
        ({"PatientSex": "M"}, "MISSING_PATIENTSIZE"),
        ({"PatientSize": "1.75"}, "MISSING_PATIENTSEX"),
        ({"PatientSex": "O", "PatientSize": "1.75"}, "UNSUPPORTED_PATIENTSEX"),
        ({"PatientSex": "M", "PatientSize": "175"}, "AMBIGUOUS_PATIENTSIZE_UNIT"),
        ({"PatientSex": "M", "PatientSize": "0.2"}, "IMPLAUSIBLE_PATIENTSIZE"),
    ],
)
def test_sul_refusals(tmp_path, over, code):
    out, headers = _suv_series(tmp_path, **over)
    sul = compute_sul(out.result, headers, "LBMJANMA")
    assert sul.status == "REFUSED" and sul.refusals[0].code == code
    with pytest.raises(ValueError):
        apply_sul(out.activity.array, sul)


# ------------------------------------------------------------------ reference region


def test_reference_region_requires_supplied_region():
    g = geom((20, 20, 20), (2.0, 2.0, 2.0))
    r = measure_reference_region(np.ones((20, 20, 20)), g, None)
    assert r.status == "MANUAL_OR_REFERENCE_MASK_REQUIRED"


def test_sphere_reference_region_known_values():
    g = geom((30, 30, 30), (2.0, 2.0, 2.0))
    suv = np.full((30, 30, 30), 2.0)
    spec = ReferenceRegionSpec(
        region="LIVER",
        method="SPHERE_AT_SUPPLIED_CENTRE",
        centre_patient_mm=(30.0, 30.0, 30.0),
        diameter_mm=30.0,
        provenance="test",
    )
    r = measure_reference_region(suv, g, spec, sul=suv * 0.8)
    assert r.status == "COMPUTED"
    assert r.suv_mean == pytest.approx(2.0) and r.suv_sd == pytest.approx(0.0)
    assert r.sul_mean == pytest.approx(1.6) and r.cov == pytest.approx(0.0)
    # voxel-centre count within 15 mm on a 2 mm grid (independent brute force)
    n = sum(
        1
        for a in range(-8, 9)
        for b in range(-8, 9)
        for c in range(-8, 9)
        if (2 * a) ** 2 + (2 * b) ** 2 + (2 * c) ** 2 <= 225
    )
    assert r.voxel_count == n and r.volume_ml == pytest.approx(n * 0.008)


@pytest.mark.parametrize(
    ("centre", "lesion", "zero", "msg"),
    [
        ((2.0, 30.0, 30.0), False, False, "outside the image"),
        ((30.0, 30.0, 30.0), True, False, "overlaps"),
        ((30.0, 30.0, 30.0), False, True, "SUV exactly 0"),
    ],
)
def test_reference_region_qc_refusals(centre, lesion, zero, msg):
    g = geom((30, 30, 30), (2.0, 2.0, 2.0))
    suv = np.full((30, 30, 30), 2.0)
    if zero:
        suv[15, 15, 15] = 0.0
    les = np.zeros_like(suv, bool)
    if lesion:
        les[15, 15, 15] = True
    spec = ReferenceRegionSpec(
        region="LIVER",
        method="SPHERE_AT_SUPPLIED_CENTRE",
        centre_patient_mm=centre,
        diameter_mm=30.0,
        provenance="t",
    )
    r = measure_reference_region(suv, g, spec, lesion_masks=[les])
    assert r.status == "REFUSED" and msg in r.refusal
