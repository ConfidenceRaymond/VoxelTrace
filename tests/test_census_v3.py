"""Census v3 (cross-collection): offline classification of sampled-header records."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pydicom
import pytest
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.rules.registry import get_ruleset

_spec = importlib.util.spec_from_file_location(
    "census_v3", Path(__file__).resolve().parents[1] / "scripts" / "census_v3_public_pet.py"
)
c3 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c3)
RULESETS = {rs: get_ruleset(rs) for rs in c3.RULESETS}
VERIFIED = {"FrameReferenceTime": "0", "DecayFactor": "1.0", "PatientSize": "1.75"}


def record(tmp_path, name, date, *, ct=True, tracer=None, **ov):
    study = generate_uid()
    uid, _ = write_image_series(tmp_path / name, modality="PT", study_uid=study, pet_overrides=ov)
    hs = [pydicom.dcmread(p, stop_before_pixels=True) for p in sorted((tmp_path / name).iterdir())]
    rec = c3.record_from_headers(
        {"SeriesInstanceUID": uid, "PatientID": "P1", "collection_id": "coll"}, hs, len(hs)
    )
    row = {
        "StudyInstanceUID": study,
        "StudyDate": date,
        "series_size_MB": "10",
        "license_short_name": "CC BY 4.0",
    }
    cts = {study: [{"frame_of_reference": rec["frame_of_reference"], "series_size_MB": 50.0}]}
    c3.enrich(rec, row, cts if ct else {})
    if tracer:
        rec["tracer_class"] = tracer
    return rec


def pair(tmp_path, b_kw=None, f_kw=None, segs=None):
    b = record(tmp_path, "b", "2020-01-01", **(b_kw or {}))
    f = record(tmp_path, "f", "2020-03-01", **(f_kw or {}))
    return c3.score_pair("coll", "P1", b, f, RULESETS, segs or {})


@pytest.mark.parametrize(
    ("name", "cls"),
    [
        ("Fluorodeoxyglucose", "FDG"),
        ("FDG -- fluorodeoxyglucose", "FDG"),
        ("68Ga-PSMA-11", "PSMA"),
        ("DCFPyL", "PSMA"),
        ("Florbetapir", "AMYLOID"),
        ("Flortaucipir", "TAU"),
        ("FLT", "OTHER"),
        ("Sodium Fluoride", "OTHER"),
        (None, "UNKNOWN"),
        ("", "UNKNOWN"),
    ],
)
def test_tracer_class(name, cls):
    assert c3.tracer_class(name) == cls


def test_architecture_vendor_and_seg_source():
    assert c3.architecture("uEXPLORER") == "TOTAL_BODY"
    assert c3.architecture("Biograph Vision Quadra") == "LONG_AFOV"
    assert c3.architecture("Biograph_mMR") == "PET_MR"
    assert c3.architecture("Biograph128_mCT") == "CONVENTIONAL_AFOV"
    assert c3.vendor("UIH / MIM Software") == "United Imaging"
    assert c3.vendor("CPS") == "Siemens"
    assert c3.seg_source("AIMI lung and FDG tumor AI segmentation", "bamf_aimi_annotations") == (
        "AI_UNREVIEWED"
    )
    assert c3.seg_source("AIMI x radiologist 1 corrected segmentation", "bamf") == (
        "HUMAN_CORRECTED_RADIOLOGIST"
    )
    assert c3.seg_source("Segmentation", "nan") == "COLLECTION_ANNOTATION"


def test_complete_fdg_pair_is_fully_decidable(tmp_path):
    r = pair(tmp_path, VERIFIED, VERIFIED)
    assert r["class"] == "FULLY_DECIDABLE_LIKELY" and r["predicted_assessable"]
    # sampled headers never give full geometry: raw verdict stays II until download
    assert r["qiba"] == "INSUFFICIENT_INFORMATION" and r["identity_unknown_fields"] == "voxel_size"
    assert r["voxel_header_proxy_same"] and r["qiba_if_voxel_confirmed"].startswith("ASSESSABLE")
    assert "voxel size: confirm on download" in r["main_blockers"]


def test_voxel_proxy_difference_is_not_decidable(tmp_path):
    r = pair(tmp_path, VERIFIED, {**VERIFIED, "SliceThickness": "5"})
    assert not r["voxel_header_proxy_same"] and r["class"] == "LIKELY_INSUFFICIENT"


def test_different_reconstruction_is_decided_not_assessable(tmp_path):
    r = pair(tmp_path, VERIFIED, {**VERIFIED, "ReconstructionMethod": "OTHER OSEM"})
    assert r["class"] == "FULLY_DECIDABLE_LIKELY" and not r["predicted_assessable"]
    assert r["qiba"] == "NOT_ASSESSABLE" and "VT-PROTOCOL-IDENTITY" in r["blocking_fail"]


def test_unverified_decay_factor_is_decidable_with_warning(tmp_path):
    kw = {"PatientSize": "1.75"}
    r = pair(tmp_path, kw, kw)
    assert r["class"] == "DECIDABLE_WITH_WARNING" and "UNVERIFIED" in r["decay_crosscheck"]


def test_missing_tracer_never_passes(tmp_path):
    r = pair(tmp_path, {**VERIFIED, "tracer": "UNKNOWN"}, VERIFIED)
    assert r["class"] == "LIKELY_INSUFFICIENT"


def test_non_fdg_requires_tracer_specific_ruleset(tmp_path):
    r = pair(tmp_path, {**VERIFIED, "tracer": "PSMA"}, {**VERIFIED, "tracer": "PSMA"})
    assert r["class"] == "REQUIRES_TRACER_SPECIFIC_RULESET"
    assert r["qiba"].startswith("NOT_EVALUATED")


def test_missing_reconstruction_is_not_a_pass(tmp_path):
    b = record(tmp_path, "b", "2020-01-01", **VERIFIED)
    f = record(tmp_path / "x", "f", "2020-03-01", **VERIFIED)
    for s in (b, f):  # simulate a vendor that encodes no reconstruction method (like GE 16.01)
        pj = __import__("json").loads(s["protocol_json"])
        pj["reconstruction"]["reconstruction_method"] = {"name": "reconstruction_method",
                                                         "status": "MISSING"}  # fmt: skip
        s["protocol_json"] = __import__("json").dumps(pj)
    r = c3.score_pair("coll", "P1", b, f, RULESETS, {})
    assert r["class"] == "LIKELY_INSUFFICIENT" and "VT-PROTOCOL-IDENTITY" in r["main_blockers"]
    assert r["qiba_attestation_path_possible"] is True  # a site attestation could close it


def test_percist_readiness_requires_height_ct_and_lesion(tmp_path):
    no_h = {"FrameReferenceTime": "0", "DecayFactor": "1.0"}
    assert pair(tmp_path / "a", no_h, no_h)["percist_readiness"] == "PERCIST_BLOCKED_BY_SUL"
    r = pair(tmp_path / "b", {**VERIFIED, "ct": False}, VERIFIED)
    assert r["percist_readiness"] == "PERCIST_BLOCKED_BY_REFERENCE"
    b = record(tmp_path / "c", "b", "2020-01-01", **VERIFIED)
    f = record(tmp_path / "c", "f", "2020-03-01", **VERIFIED)
    ai = {b["StudyInstanceUID"]: ["AI_UNREVIEWED"]}
    r = c3.score_pair("coll", "P1", b, f, RULESETS, ai)
    assert r["percist_readiness"] == "PERCIST_LIVER_READY_BUT_LESION_MISSING"
    manual = {b["StudyInstanceUID"]: ["COLLECTION_ANNOTATION"]}
    r = c3.score_pair("coll", "P1", b, f, RULESETS, manual)
    assert r["percist_readiness"].startswith("PERCIST_READY")
