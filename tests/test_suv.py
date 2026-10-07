"""SUVbw: hand-calculated oracles + strict refusal policy.

Oracle values are literal numbers computed by hand (see comments), not by the module.
"""

import math

import numpy as np
import pytest
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.ingest import discover_dicom
from voxeltrace.quant.suv import (
    apply_suv,
    audit_pet_headers,
    compute_suv_for_series,
    suv_scale_factors,
    validate_suv_eligibility,
)

REL = 1e-12  # float64 arithmetic on exactly representable inputs


def _pet(tmp_path, **kw):
    write_image_series(tmp_path, modality="PT", study_uid=generate_uid(), **kw)
    (s,) = discover_dicom(tmp_path).series
    return s


def _timing(series_t, inj_dt=None, inj_tm=None, series_d="20200101", acq_t=None, acq_d=None):
    rp = {}
    if inj_dt is not None:
        rp["RadiopharmaceuticalStartDateTime"] = inj_dt
        if inj_tm is None:  # keep the TM consistent with the DT (else: INJECTION_TIME_CONFLICT)
            inj_tm = inj_dt[8:]
    if inj_tm is not None:
        rp["RadiopharmaceuticalStartTime"] = inj_tm
    return {
        "pet_overrides": {
            "SeriesDate": series_d,
            "SeriesTime": series_t,
            "AcquisitionDate": acq_d or series_d,
            "AcquisitionTime": acq_t or series_t,
            "PatientWeight": "70",
        },
        "rp_overrides": {"RadionuclideTotalDose": "350000000", **rp},
    }


def _uniform(stored_value, n=3):
    return np.full((n, 4, 5), stored_value, dtype=np.uint16)


# ------------------------------------------------------------------ pure-formula oracles


def test_oracle_zero_interval():
    # W = 70 kg = 70000 g, D = 3.5e8 Bq, Δt = 0 → factor = 70000/3.5e8 = 2e-4 g/Bq
    s = suv_scale_factors(70.0, 3.5e8, 6586.2, 0.0)
    assert s.dose_decay_factor == 1.0
    assert s.suv_per_bqml == pytest.approx(2e-4, rel=REL)
    assert apply_suv(np.array([5000.0]), s)[0] == pytest.approx(1.0, rel=REL)


def test_oracle_one_half_life():
    # Δt = T½ → decayed dose = 1.75e8, factor = 70000/1.75e8 = 4e-4; 5000 Bq/mL → SUV 2.0
    s = suv_scale_factors(70.0, 3.5e8, 6586.2, 6586.2)
    assert s.dose_decay_factor == pytest.approx(0.5, rel=REL)
    assert s.decayed_dose_bq == pytest.approx(1.75e8, rel=REL)
    assert apply_suv(np.array([5000.0]), s)[0] == pytest.approx(2.0, rel=REL)


def test_oracle_two_half_lives_and_input_untouched():
    s = suv_scale_factors(80.0, 4.0e8, 6000.0, 12000.0)  # decayed 1e8 → factor 8e-4
    act = np.array([[1000.0, 2500.0]])
    before = act.copy()
    suv = apply_suv(act, s)
    np.testing.assert_allclose(suv, [[0.8, 2.0]], rtol=REL)
    np.testing.assert_array_equal(act, before)
    assert suv is not act


@pytest.mark.parametrize(
    "args",
    [
        (0, 1e8, 6586.2, 0),
        (70, 0, 6586.2, 0),
        (70, 1e8, 0, 0),
        (70, 1e8, 6586.2, -1),
        (math.nan, 1e8, 6586.2, 0),
        (70, math.inf, 6586.2, 0),
    ],
)
def test_scale_factor_rejects_bad_inputs(args):
    with pytest.raises(ValueError):
        suv_scale_factors(*args)


# ------------------------------------------------------------------ end-to-end oracles


def test_e2e_zero_interval_nonzero_intercept(tmp_path):
    # stored 2500, slope 2, intercept 100 → 5100 Bq/mL; factor 2e-4 → SUV 1.02
    s = _pet(
        tmp_path,
        stored=_uniform(2500),
        slope=2.0,
        intercept=100.0,
        **_timing("091500", inj_dt="20200101091500", inj_tm="091500"),
    )
    out = compute_suv_for_series(s)
    assert out.result is not None, out.refusal
    assert out.result.inputs.decay_interval_s == 0.0
    np.testing.assert_allclose(out.suv, 1.02, rtol=REL)
    assert any(w.code == "SHORT_DECAY_INTERVAL" for w in out.result.validation.warnings)


def test_e2e_one_half_life_fractional_seconds(tmp_path):
    # injection 09:00:00.000, scan 10:49:46.200 → Δt = 6586.2 s = T½; 5000 Bq/mL → SUV 2.0
    s = _pet(
        tmp_path,
        stored=_uniform(2500),
        slope=2.0,
        intercept=0.0,
        **_timing("104946.2", inj_dt="20200101090000.000", inj_tm="090000.000"),
    )
    out = compute_suv_for_series(s)
    assert out.result is not None, out.refusal
    assert out.result.inputs.decay_interval_s == pytest.approx(6586.2, abs=1e-6)
    np.testing.assert_allclose(out.suv, 2.0, rtol=1e-9)


def test_e2e_per_slice_slopes(tmp_path):
    # Δt = 0, factor 2e-4. stored 1000 on all slices:
    #   k0: 1000*1.0+0 = 1000 → 0.2 ; k1: 1000*0.5+0 = 500 → 0.1 ; k2: 1000*2+100 = 2100 → 0.42
    s = _pet(
        tmp_path,
        stored=_uniform(1000),
        slopes=[1.0, 0.5, 2.0],
        intercepts=[0, 0, 100],
        **_timing("091500", inj_dt="20200101091500"),
    )
    out = compute_suv_for_series(s)
    assert out.result is not None, out.refusal
    np.testing.assert_allclose(out.suv[:, 0, 0], [0.2, 0.1, 0.42], rtol=REL)
    r = out.result.rescale
    assert r.n_distinct_slopes == 3 and [p[2] for p in r.per_slice] == [1.0, 0.5, 2.0]
    assert [p[3] for p in r.per_slice] == [0.0, 0.0, 100.0]


def test_e2e_midnight_with_explicit_dates(tmp_path):
    # injection DT 2020-01-01 23:30:00, scan 2020-01-02 00:30:00 → Δt 3600 s
    # 2^(-3600/6586.2) = 0.68463291957200212 (hand, 40-digit decimal)
    # SUV = 5000*70000/(3.5e8*0.684632919572) = 1.4606367462218285
    s = _pet(
        tmp_path,
        stored=_uniform(2500),
        slope=2.0,
        intercept=0.0,
        **_timing("003000", series_d="20200102", inj_dt="20200101233000"),
    )
    out = compute_suv_for_series(s)
    assert out.result is not None, out.refusal
    assert out.result.inputs.decay_interval_s == 3600.0
    assert out.result.scale.dose_decay_factor == pytest.approx(0.68463291957200212, rel=1e-14)
    np.testing.assert_allclose(out.suv, 1.4606367462218285, rtol=1e-13)


def test_e2e_midnight_tm_only_documented_rule(tmp_path):
    s = _pet(
        tmp_path,
        stored=_uniform(2500),
        slope=2.0,
        intercept=0.0,
        drop=["RadiopharmaceuticalStartDateTime"],
        **_timing("003000", series_d="20200102", inj_tm="233000"),
    )
    out = compute_suv_for_series(s)
    assert out.result is not None, out.refusal
    assert out.result.inputs.decay_interval_s == 3600.0
    assert "previous day" in out.result.inputs.injection_datetime_source
    assert any(w.code == "INJECTION_DATE_ROLLOVER" for w in out.result.validation.warnings)
    np.testing.assert_allclose(out.suv, 1.4606367462218285, rtol=1e-13)


def test_e2e_series_precedes_acquisition_confirmed_by_frame_reference(tmp_path):
    # Series 10:00:00; slices acquired 10:00:30 with FrameReferenceTime 90 s (30 s + 60 s)
    per = {
        k: {
            "FrameReferenceTime": "90000",
            "ActualFrameDuration": "120000",
            "DecayFactor": f"{2 ** (90 / 6586.2):.8f}",
        }
        for k in range(3)
    }
    s = _pet(
        tmp_path,
        stored=_uniform(2500),
        slope=2.0,
        intercept=0.0,
        per_slice=per,
        **_timing("100000", acq_t="100030", inj_dt="20200101090000"),
    )
    out = compute_suv_for_series(s)
    assert out.result is not None, out.refusal
    assert out.result.inputs.decay_interval_s == 3600.0
    assert "FrameReferenceTime" in out.result.inputs.scan_reference_datetime_source


# ------------------------------------------------------------------ refusals


def _reasons(tmp_path, **kw):
    s = _pet(tmp_path, **kw)
    out = compute_suv_for_series(s)
    assert out.result is None and out.suv is None
    return {r.code for r in out.refusal.reasons}


@pytest.mark.parametrize(
    ("kw", "code"),
    [
        ({"pet_overrides": {"Units": "CNTS"}}, "UNSUPPORTED_UNITS"),
        ({"drop": ["Units"]}, "MISSING_UNITS"),
        ({"drop": ["PatientWeight"]}, "MISSING_PATIENTWEIGHT"),
        ({"drop": ["RadionuclideTotalDose"]}, "MISSING_RADIONUCLIDETOTALDOSE"),
        ({"drop": ["RadionuclideHalfLife"]}, "MISSING_RADIONUCLIDEHALFLIFE"),
        ({"pet_overrides": {"DecayCorrection": "ADMIN"}}, "UNSUPPORTED_DECAY_CORRECTION"),
        ({"pet_overrides": {"DecayCorrection": "NONE"}}, "UNSUPPORTED_DECAY_CORRECTION"),
        ({"pet_overrides": {"CorrectedImage": ["ATTN"]}}, "MISSING_CORRECTION"),
        ({"rp_overrides": {"RadionuclideTotalDose": "0"}}, "NONPOSITIVE_RADIONUCLIDETOTALDOSE"),
        ({"pet_overrides": {0x00101030: b"0   "}}, "NONPOSITIVE_PATIENTWEIGHT"),
        ({"pet_overrides": {0x00101030: b"-70 "}}, "NONPOSITIVE_PATIENTWEIGHT"),
        ({"pet_overrides": {0x00101030: b"NaN "}}, "INVALID_PATIENTWEIGHT"),
        ({"rp_overrides": {0x00181074: b"nan "}}, "INVALID_RADIONUCLIDETOTALDOSE"),
        ({"rp_overrides": {0x00181075: b"inf "}}, "INVALID_RADIONUCLIDEHALFLIFE"),
        ({"rp_overrides": {"RadionuclideHalfLife": "0"}}, "NONPOSITIVE_RADIONUCLIDEHALFLIFE"),
        ({"rp_overrides": {"RadionuclideHalfLife": "6000"}}, "HALF_LIFE_RADIONUCLIDE_MISMATCH"),
        ({"pet_overrides": {"PatientWeight": "70500"}}, "IMPLAUSIBLE_PATIENTWEIGHT"),
        ({"rp_overrides": {"RadionuclideTotalDose": "8.1"}}, "IMPLAUSIBLE_RADIONUCLIDETOTALDOSE"),
        (
            {"rp_overrides": {"RadiopharmaceuticalStartDateTime": "2020010109"}},
            "INVALID_INJECTION_TIME",
        ),
        pytest.param(
            {"rp_overrides": {"RadiopharmaceuticalStartTime": "09:15:00"}},
            "INVALID_INJECTION_TIME",
            marks=pytest.mark.filterwarnings("ignore"),
        ),
        ({"rp_overrides": {"RadiopharmaceuticalStartTime": "091501"}}, "INJECTION_TIME_CONFLICT"),
        (
            {"drop": ["RadiopharmaceuticalStartTime", "RadiopharmaceuticalStartDateTime"]},
            "MISSING_INJECTION_TIME",
        ),
        ({"pet_overrides": {"AcquisitionTime": "1015"}}, "INVALID_ACQUISITION_DATETIME"),
        ({"drop": ["AcquisitionTime"]}, "INVALID_ACQUISITION_DATETIME"),
        pytest.param(
            {"pet_overrides": {"SeriesTime": "1015xx"}},
            "INVALID_SERIES_DATETIME",
            marks=pytest.mark.filterwarnings("ignore"),
        ),
        (
            {
                "rp_overrides": {
                    "RadiopharmaceuticalStartDateTime": "20200101111500",
                    "RadiopharmaceuticalStartTime": "111500",
                }
            },
            "NEGATIVE_DECAY_INTERVAL",
        ),
        (
            {
                "rp_overrides": {
                    "RadiopharmaceuticalStartDateTime": "20191231091500",
                    "RadiopharmaceuticalStartTime": "091500",
                }
            },
            "IMPLAUSIBLE_DECAY_INTERVAL",
        ),
        ({"pet_overrides": {"SeriesTime": "101600"}}, "SERIES_TIME_AFTER_ACQUISITION"),
        ({"pet_overrides": {"SeriesTime": "101400"}}, "SCAN_REFERENCE_AMBIGUOUS"),
        ({"drop": ["RescaleSlope"]}, "MISSING_RESCALE"),
        ({"slope": 0.0}, "NONPOSITIVE_RESCALE_SLOPE"),
        ({"drop": ["RadiopharmaceuticalInformationSequence"]}, "RADIOPHARMACEUTICAL_ITEMS"),
        (
            {"rp_overrides": {"RadiopharmaceuticalStartDateTime": "20200101091500+0100"}},
            "TIMEZONE_AMBIGUOUS",
        ),
    ],
)
def test_refusals(tmp_path, kw, code):
    assert code in _reasons(tmp_path, **kw)


@pytest.mark.parametrize(
    ("field", "values", "code"),
    [
        ("PatientWeight", ["70", "71", "70"], "INCONSISTENT_PATIENTWEIGHT"),
        ("Units", ["BQML", "BQML", "CNTS"], "INCONSISTENT_UNITS"),
        ("DecayCorrection", ["START", "ADMIN", "START"], "INCONSISTENT_DECAYCORRECTION"),
        ("SeriesTime", ["101500", "101500", "101501"], "INCONSISTENT_SERIESTIME"),
    ],
)
def test_inconsistent_per_slice_metadata_refused(tmp_path, field, values, code):
    per = {k: {field: v} for k, v in enumerate(values)}
    assert code in _reasons(tmp_path, per_slice=per)


def test_inconsistent_per_slice_dose_refused(tmp_path):
    study, series, for_uid = generate_uid(), generate_uid(), generate_uid()
    write_image_series(
        tmp_path / "a",
        modality="PT",
        study_uid=study,
        series_uid=series,
        for_uid=for_uid,
        z_positions=[0.0, 4.0],
    )
    write_image_series(
        tmp_path / "b",
        modality="PT",
        study_uid=study,
        series_uid=series,
        for_uid=for_uid,
        z_positions=[8.0],
        rp_overrides={"RadionuclideTotalDose": "310000000"},
    )
    (s,) = discover_dicom(tmp_path).series
    out = compute_suv_for_series(s)
    assert "INCONSISTENT_RADIONUCLIDETOTALDOSE" in {r.code for r in out.refusal.reasons}


def test_decay_factor_inconsistency_refused(tmp_path):
    per = {
        k: {"FrameReferenceTime": "60000", "ActualFrameDuration": "120000", "DecayFactor": "1.5"}
        for k in range(3)
    }
    assert "DECAY_FACTOR_INCONSISTENT" in _reasons(tmp_path, per_slice=per)


def test_default_fixture_passes_and_audit_complete(tmp_path):
    s = _pet(tmp_path)
    audit = audit_pet_headers(s)
    val, inputs = validate_suv_eligibility(audit)
    assert val.eligible, val.reasons
    assert all(c.passed for c in val.checks)
    assert inputs.injection_datetime == "2020-01-01T09:15:00"
    assert inputs.scan_reference_datetime == "2020-01-01T10:15:00"
    assert inputs.decay_interval_s == 3600.0
    names = {f.name for f in inputs.fields}
    assert {
        "Units",
        "PatientWeight",
        "RadionuclideTotalDose",
        "RescaleSlope",
        "FrameReferenceTime",
    } <= names
