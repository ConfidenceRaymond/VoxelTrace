"""Known-answer failure injection: one test per emittable reason code not covered elsewhere.

Coverage matrix: docs/failure_injection_coverage.md (scripts/reason_coverage.py).
"""

from __future__ import annotations

import pytest
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from test_preflight import codes, pet, scan_with_ct
from voxeltrace.evidence.fingerprint import build_fingerprint
from voxeltrace.ingest import discover_dicom
from voxeltrace.preflight import preflight_scan_dir, preflight_series_headers
from voxeltrace.trial.drift import ScanRecord, detect_drift

DF_300 = f"{2 ** (300 / 6586.2):.6f}"


@pytest.mark.parametrize(
    ("kw", "code", "state"),
    [
        (
            {"over": {"CorrectedImage": ["ATTN", "DECY"]}},
            "CORRECTIONS_NOT_DECLARED",
            "READY_WITH_WARNINGS",
        ),
        (
            {"drop": ("DecayFactor", "FrameReferenceTime")},
            "DECAY_FACTOR_UNVERIFIED",
            "READY_WITH_WARNINGS",
        ),
        (
            {"rp_overrides": {"RadiopharmaceuticalStartDateTime": None}},
            "INJECTION_DATE_FROM_SERIES",
            None,
        ),
        ({"rp_overrides": {"RadiopharmaceuticalStartDateTime": None}}, "ANONYMIZATION_LOSS", None),
        ({"over": {"TimezoneOffsetFromUTC": "+9999"}}, "INVALID_TIMEZONE", "DO_NOT_QUANTIFY"),
        ({"drop": ("DecayCorrection",)}, "MISSING_DECAYCORRECTION", "DO_NOT_QUANTIFY"),
        (
            {"rp_overrides": {"Radiopharmaceutical": "Unknown", "RadionuclideCodeSequence": None}},
            "RADIONUCLIDE_UNIDENTIFIED",
            None,
        ),
        (
            {
                "over": {
                    "SeriesTime": "101000",
                    "FrameReferenceTime": "300000",
                    "DecayFactor": DF_300,
                    "ActualFrameDuration": "120000",
                }
            },
            "SERIES_PRECEDES_ACQUISITION",
            "READY_WITH_WARNINGS",
        ),
        ({"over": {"SeriesTime": "102000"}}, "SERIES_TIME_AFTER_ACQUISITION", "DO_NOT_QUANTIFY"),
        ({"over": {"PatientWeight": "310"}}, "UNUSUAL_PATIENTWEIGHT", "READY_WITH_WARNINGS"),
        ({"drop": ("Manufacturer",)}, "SCANNER_UNKNOWN", "READY_WITH_WARNINGS"),
        ({"over": {"Manufacturer": "ACME"}}, "NO_VENDOR_PRIVATE_PARSER", "READY_TO_QUANTIFY"),
    ],
)
def test_preflight_injection(tmp_path, kw, code, state):
    sc = scan_with_ct(tmp_path, n_ct=25, **kw)
    assert code in codes(sc), codes(sc)
    if state:
        assert sc.series[0].state == state


def test_not_pet_and_no_pet_and_ct_ambiguous(tmp_path):
    uid, _ = write_image_series(
        tmp_path / "ct",
        modality="CT",
        study_uid=generate_uid(),
        rows=6,
        cols=6,
        slope=1.0,
        intercept=-1024.0,
    )
    (s,) = discover_dicom(tmp_path / "ct").series
    import pydicom

    h = [pydicom.dcmread(i.path, stop_before_pixels=True) for i in s.instances]
    r = preflight_series_headers(h)
    assert r.findings[0].reason_code == "NOT_PET_MODALITY" and r.state == "READY_TO_QUANTIFY"
    assert "NO_PET_SERIES" in codes(preflight_scan_dir(tmp_path / "ct"))
    for_uid = generate_uid()
    study = pet(tmp_path / "amb", for_uid=for_uid)
    for n in ("CT1", "CT2"):
        write_image_series(
            tmp_path / "amb" / n,
            modality="CT",
            study_uid=study,
            for_uid=for_uid,
            n_slices=25,
            rows=6,
            cols=6,
            slope=1.0,
            intercept=-1024.0,
        )
    assert "CT_FRAME_AMBIGUOUS" in codes(preflight_scan_dir(tmp_path / "amb"))


# ------------------------------------------------------------------ drift events


def _fp(tmp_path, name, rp=None, harmonization=None, rows=4, **ov):
    from test_fingerprint_drift import RECON
    from voxeltrace.evidence import extract_protocol
    from voxeltrace.quant.suv import audit_pet_headers, validate_suv_eligibility

    write_image_series(
        tmp_path / name,
        modality="PT",
        study_uid=generate_uid(),
        rows=rows,
        pet_overrides={**RECON, **ov},
        rp_overrides=rp,
    )
    (s,) = discover_dicom(tmp_path / name).series
    val, inputs = validate_suv_eligibility(audit_pet_headers(s))
    return build_fingerprint(extract_protocol(s, inputs, val), harmonization=harmonization)


@pytest.mark.parametrize(
    ("change", "event"),
    [
        ({"ManufacturerModelName": "Biograph64_mCT"}, "SCANNER_CHANGE"),
        ({"ReconstructionMethod": "PSF+TOF 3i21s"}, "RECONSTRUCTION_CHANGE"),
        ({"ConvolutionKernel": "XYZ Gauss5.00"}, "FILTER_CHANGE"),
        ({"SliceThickness": "5"}, "VOXEL_SIZE_CHANGE"),
        ({"rows": 6}, "MATRIX_CHANGE"),
        ({"CorrectedImage": ["NORM", "DTIM", "ATTN", "DECY", "RAN"]}, "CORRECTION_CHANGE"),
        ({"rp": {"Radiopharmaceutical": "Fluorothymidine"}}, "TRACER_CHANGE"),
        ({"Units": "CNTS"}, "QUANTITATIVE_STATE_CHANGE"),
        ({"harmonization": "EARL2"}, "HARMONIZATION_CHANGE"),
    ],
)
def test_drift_event_injection(tmp_path, change, event):
    base_h = "EARL1" if event == "HARMONIZATION_CHANGE" else None
    a = _fp(tmp_path, "a", harmonization=base_h)
    b = _fp(tmp_path, "b", **change)
    recs = [
        ScanRecord(site="A", subject=s, timepoint="b", scan_pseudonym=s, date=d, fingerprint=f)
        for s, d, f in (("S1", "2020-01-01", a), ("S2", "2020-02-01", b))
    ]
    ev = {e.event for e in detect_drift(recs).events}
    assert event in ev, ev


def test_dose_outlier_injection(tmp_path):
    fps = [_fp(tmp_path, f"d{i}") for i in range(3)]
    far = _fp(tmp_path, "far", rp={"RadionuclideTotalDose": "600000000"})
    recs = [
        ScanRecord(
            site="A",
            subject=f"S{i}",
            timepoint="b",
            scan_pseudonym=f"S{i}",
            date=f"2020-0{i + 1}-01",
            fingerprint=f,
        )
        for i, f in enumerate([*fps, far])
    ]
    out = [e for e in detect_drift(recs).events if e.event == "DOSE_OUTLIER"]
    assert len(out) == 1 and out[0].heuristic and out[0].new_value == 600.0


# ------------------------------------------------------------------ attestation / adjudication


def test_technologist_without_countersignature_reason(tmp_path):
    from test_qiba_attestation import att, scan
    from voxeltrace.evidence.attestation import validate_attestation

    _, facts = scan(tmp_path, "baseline")
    o = validate_attestation(
        att(facts, tmp_path, attestor_role="SITE_PET_TECHNOLOGIST"), facts, tmp_path
    )
    assert o.reasons == ["TECHNOLOGIST_REQUIRES_COUNTERSIGNATURE"]


def test_attestation_contradiction_reason_code(tmp_path):
    from test_qiba_attestation import identity, pair_ctx, scan, valid_outcomes

    (b, fb), (f, ff) = scan(tmp_path, "baseline"), scan(tmp_path, "followup")
    c, _ = identity(
        "qiba-fdg-1.14", pair_ctx(b, f, valid_outcomes(tmp_path, fb, ff, fkw={"subsets": 16}))
    )
    assert {r.code for r in c.reasons} == {"RECONSTRUCTION_ATTESTATION_CONTRADICTS"}


def test_confirmed_by_human_status(tmp_path):
    from test_pilot_bundle import _adj, trial
    from voxeltrace.trial.adjudication import adjudication_status
    from voxeltrace.trial.audit import run_trial_audit

    root, _ = trial(tmp_path)
    p = run_trial_audit(root, "qiba-fdg-1.14").pairs[0]
    (row,) = adjudication_status([p], [_adj(p)])
    assert (
        row["adjudication_status"] == "CONFIRMED_BY_HUMAN" and row["automated_verdict"] == p.verdict
    )


def test_reference_auto_not_found_without_ct(tmp_path):
    import yaml

    from voxeltrace.trial.audit import run_trial_audit

    root = tmp_path / "t"
    for tp in ("baseline", "followup"):
        pet(root / "S1" / tp)
    (root / "trial.yaml").write_text(
        yaml.safe_dump(
            {"trial_id": "T", "ruleset": "percist-1.0", "timepoint_order": ["baseline", "followup"]}
        )
    )
    a = run_trial_audit(root, "percist-1.0")
    reasons = {r.code for p in a.pairs for c in p.checks for r in c.reasons}
    assert "REFERENCE_AUTO_NOT_FOUND" in reasons


@pytest.mark.parametrize(
    ("field", "event"),
    [("time_of_flight", "TOF_CHANGE"), ("psf_resolution_modelling", "PSF_CHANGE")],
)
def test_tof_psf_change_needs_explicit_values(tmp_path, field, event):
    """Free text that omits TOF/PSF leaves them MISSING (never False): only explicit values
    can show a change; otherwise the engine reports UNKNOWN_PROTOCOL_DRIFT."""
    a = _fp(tmp_path, "a")
    b = a.model_copy(deep=True)
    b.fields[field] = b.fields[field].model_copy(update={"value": False, "trust": "LEVEL_A"})
    recs = [
        ScanRecord(site="A", subject=s, timepoint="b", scan_pseudonym=s, date=d, fingerprint=f)
        for s, d, f in (("S1", "2020-01-01", a), ("S2", "2020-02-01", b))
    ]
    ev = detect_drift(recs).events
    assert (
        [e.event for e in ev] == [event]
        and ev[0].previous_value is True
        and ev[0].new_value is False
    )
    c = _fp(tmp_path, "c", ReconstructionMethod="2i21s")  # no TOF/PSF words: MISSING, not False
    recs[1] = recs[1].model_copy(update={"fingerprint": c})
    assert "UNKNOWN_PROTOCOL_DRIFT" in {e.event for e in detect_drift(recs).events}


def test_private_start_agreeing_with_series_is_unknown_provenance():
    from test_vendors_anonymization import _ds
    from voxeltrace.trial.anonymization import audit_anonymization

    a = audit_anonymization(
        [
            _ds(
                private="20200102100000.000000",
                PatientSex="F",
                PatientSize="1.6",
                PatientWeight="60",
            )
        ]
    )
    (t,) = a.timing_crosschecks
    assert t.code == "UNKNOWN_PROVENANCE" and "no issue" in t.detail


def test_liver_without_sul_is_anthropometrics_missing():
    from test_trial_rules import ctx, tp
    from voxeltrace.quant.reference_region import ReferenceRegionResult
    from voxeltrace.rules import percist

    liver = ReferenceRegionResult(status="COMPUTED", region="LIVER", sul_mean=None, voxel_count=100)
    b, f = tp("B", 60, liver=liver), tp("F", 62, liver=liver)
    rule, fn = next(
        (r, fn) for r, fn in percist.RULES if r.rule_id == "PERCIST-LIVER-SUL-STABILITY"
    )
    c = fn(rule, ctx(b, f))
    assert c.status == "UNKNOWN" and {r.code for r in c.reasons} == {"ANTHROPOMETRICS_MISSING"}
