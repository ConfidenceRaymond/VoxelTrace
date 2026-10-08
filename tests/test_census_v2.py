"""Census v2 sampled prediction: identical audit to the strict validator; catches the
decay-factor patterns that a one-header census missed."""

import pydicom
import pytest
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.census.sampled import predict_pet, sampled_header_audit
from voxeltrace.ingest import discover_dicom
from voxeltrace.quant.suv import audit_pet_headers, validate_suv_eligibility


def series(tmp_path, per_slice=None, **over):
    write_image_series(
        tmp_path,
        modality="PT",
        study_uid=generate_uid(),
        n_slices=5,
        pet_overrides={"PatientWeight": "70", **over},
        per_slice=per_slice,
    )
    (s,) = discover_dicom(tmp_path).series
    headers = [pydicom.dcmread(i.path, stop_before_pixels=True) for i in s.instances]
    return s, headers


def test_mirror_audit_identical_to_validator_audit(tmp_path):
    s, headers = series(tmp_path)
    full = audit_pet_headers(s)
    mine = sampled_header_audit(s.series_uid, headers)
    assert {k: v.model_dump() for k, v in full.fields.items()} == {
        k: v.model_dump() for k, v in mine.fields.items()
    }
    a, _ = validate_suv_eligibility(full)
    b, _ = validate_suv_eligibility(mine)
    assert a.eligible == b.eligible and [r.code for r in a.reasons] == [r.code for r in b.reasons]


def test_prediction_matches_full_series_when_consistent(tmp_path):
    s, headers = series(tmp_path)
    p = predict_pet(s.series_uid, headers[::2])
    full, _ = validate_suv_eligibility(audit_pet_headers(s))
    assert p["suv_eligible"] == full.eligible


def test_decay_factor_inconsistency_detected_from_sample(tmp_path):
    # GE-like: FrameReferenceTime holds frame starts while DecayFactor is mid-frame
    per = {k: {"FrameReferenceTime": str(300000 * k), "DecayFactor": "1.5"} for k in range(5)}
    s, headers = series(tmp_path, per_slice=per, DecayCorrection="START")
    full, _ = validate_suv_eligibility(audit_pet_headers(s))
    p = predict_pet(s.series_uid, [headers[0], headers[2], headers[4]])
    assert [r.code for r in full.reasons] == ["DECAY_FACTOR_INCONSISTENT"]
    assert "DECAY_FACTOR_INCONSISTENT" in p["refusal_codes"]
    assert p["distinct_frame_reference_times"] == 3 and p["multi_bed_detected"]


def test_frt_zero_with_decay_factor_flag(tmp_path):
    per = {k: {"FrameReferenceTime": "0", "DecayFactor": str(1.0 + 0.02 * k)} for k in range(5)}
    s, headers = series(tmp_path, per_slice=per)
    p = predict_pet(s.series_uid, headers)
    assert p["frt_zero_with_decay_factor"] is True
    assert not p["suv_eligible"]


@pytest.mark.parametrize(("field", "key"), [("PatientSize", "height_present")])
def test_presence_flags(tmp_path, field, key):
    s, headers = series(tmp_path)
    assert predict_pet(s.series_uid, headers)[key] is False
    s2, headers2 = series(tmp_path / "b", **{field: "1.7"})
    assert predict_pet(s2.series_uid, headers2)[key] is True
