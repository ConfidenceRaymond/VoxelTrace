"""Bounded-download guards and blocked-by classification for the real ACRIN analysis."""

import importlib.util
import json
from pathlib import Path

import pytest

from voxeltrace.rules.schema import RuleCheck
from voxeltrace.trial.reasons import Reason

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def fetch(monkeypatch):
    mod = load("fetch_acrin_series")
    calls = []

    def fake_list(bucket, uuid):
        calls.append(uuid)
        return [{"key": f"{uuid}/{i}.dcm", "size": 1_000_000, "etag": "e"} for i in range(10)]

    def no_get(url):
        raise AssertionError(f"download attempted: {url}")

    monkeypatch.setattr(mod, "list_series", fake_list)
    monkeypatch.setattr(mod, "_get", no_get)
    return mod, calls


def allow(tmp_path, **over):
    s = {
        "collection": "ACRIN-NSCLC-FDG-PET",
        "PatientID": "SUBJ-1",
        "timepoint": "baseline",
        "modality": "PET",
        "StudyInstanceUID": "1",
        "SeriesInstanceUID": "2",
        "SeriesDescription": "PET",
        "expected_instances": 10,
        "expected_MB": 10.0,
        "aws_bucket": "b",
        "crdc_series_uuid": "u",
        "license": "CC BY 3.0",
        **over,
    }
    p = tmp_path / "allow.json"
    p.write_text(json.dumps({"approved_subjects": ["SUBJ-1"], "series": [s]}))
    return str(p)


def test_plan_only_never_downloads(fetch, tmp_path):
    mod, calls = fetch
    assert mod.main(["x", allow(tmp_path), "--plan-only"]) == 0
    assert calls == ["u"]  # only the series' own prefix is listed


def test_unapproved_subject_stops_before_listing(fetch, tmp_path):
    mod, calls = fetch
    assert mod.main(["x", allow(tmp_path, PatientID="OTHER")]) == 2
    assert calls == []


@pytest.mark.parametrize(("over"), [{"expected_instances": 11}, {"expected_MB": 20.0}])
def test_count_or_size_mismatch_stops_before_download(fetch, tmp_path, over):
    mod, _ = fetch
    assert mod.main(["x", allow(tmp_path, **over)]) == 2  # no _get call (would assert)


def test_software_versions_single_value_not_split():
    mod = load("fetch_acrin_series")
    assert mod.software_versions({"SoftwareVersions": "16.01"}) == ["16.01"]
    assert mod.software_versions({"SoftwareVersions": ["a", "b"]}) == ["a", "b"]
    assert mod.software_versions({}) is None


def _check(status, *codes, detail="x"):
    return RuleCheck(
        rule_id="R",
        rule_version="1",
        standard="VOXELTRACE",
        name="R",
        impact="blocking",
        status=status,
        expected="",
        source="",
        reasons=[Reason(code=c, detail=detail, confidence="CONFIRMED") for c in codes],
    )


def test_blocked_by_separates_suv_from_review():
    mod = load("analyze_acrin_longitudinal")
    assert mod.blocked_by(_check("PASS")) == ""
    assert mod.blocked_by(_check("UNKNOWN", "SUV_REFUSED")) == "SUV_REFUSED"
    # region not evaluated because SUV was refused: not a pending review
    not_eval = _check(
        "UNKNOWN",
        "MANUAL_OR_REFERENCE_MASK_REQUIRED",
        detail="S/F LIVER: reference region not evaluated (no quantitative SUV)",
    )
    assert mod.blocked_by(not_eval) == "SUV_REFUSED"
    assert mod.blocked_by(_check("UNKNOWN", "REFERENCE_REVIEW_REQUIRED")) == "REFERENCE_REVIEW"
    assert mod.blocked_by(_check("UNKNOWN", "AMBIGUOUS_RECONSTRUCTION")).startswith("OWN_EVIDENCE")


def test_existing_manifest_never_overwritten(fetch, tmp_path, monkeypatch):
    mod, _ = fetch
    monkeypatch.setattr(mod, "DEST", tmp_path)
    (tmp_path / "provenance_manifest.json").write_text("{}")
    assert mod.main(["x", allow(tmp_path)]) == 2
    assert (tmp_path / "provenance_manifest.json").read_text() == "{}"


def test_existing_subject_directory_stops(fetch, tmp_path, monkeypatch):
    mod, calls = fetch
    monkeypatch.setattr(mod, "DEST", tmp_path)
    (tmp_path / "SUBJ-1").mkdir()
    assert mod.main(["x", allow(tmp_path), "--manifest", "m2.json"]) == 2
    assert not (tmp_path / "m2.json").exists()
