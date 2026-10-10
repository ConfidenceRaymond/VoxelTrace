"""Partner-drop intake mapping (VT-INTAKE-MAPPING-1) and staging."""

from __future__ import annotations

import json

import pytest
from pydicom.uid import generate_uid

from dicom_factory import write_image_series
from voxeltrace.cli import main as cli
from voxeltrace.intake import canonical_timepoint, map_intake, stage_intake

GOOD = {"FrameReferenceTime": "0", "DecayFactor": "1.0", "PatientSize": "1.75", "PatientSex": "M",
        "Manufacturer": "SIEMENS", "ManufacturerModelName": "Biograph128_mCT", "SoftwareVersions": "VG60A",
        "ReconstructionMethod": "PSF+TOF 2i21s", "ConvolutionKernel": "XYZ Gauss2.00"}  # fmt: skip
_SLOPE = iter(1.5 + 0.01 * k for k in range(10_000))


def pet(d, pid, date, for_uid=None, **over):
    ov = {**GOOD, "PatientID": pid, "AcquisitionDate": date, "SeriesDate": date, **over}
    write_image_series(d, modality="PT", study_uid=generate_uid(), for_uid=for_uid, pet_overrides=ov,
                       rp_overrides={"RadiopharmaceuticalStartDateTime": f"{date}091500"}, slope=next(_SLOPE))  # fmt: skip


def ct(d, for_uid, pid, n=3):
    write_image_series(d, modality="CT", study_uid=generate_uid(), for_uid=for_uid, n_slices=n,
                       per_slice={k: {"PatientID": pid} for k in range(n)})  # fmt: skip


@pytest.fixture
def drop(tmp_path):
    """A realistic, messy core-lab drop."""
    r = tmp_path / "PartnerDrop"
    # SiteA/Subject001: clean baseline + follow-up with CT, protocol PDF, sidecar
    for tp, date in (("Baseline", "20200101"), ("Follow-Up", "20200301")):
        f = generate_uid()
        pet(r / "SiteA" / "Subject001" / tp / "PET_AC", "P001", date, for_uid=f)
        ct(r / "SiteA" / "Subject001" / tp / "CT", f, "P001")
    (r / "SiteA" / "Subject001" / "Baseline" / "protocol.pdf").write_bytes(b"%PDF-1.4 placeholder")
    (r / "SiteA" / "Subject001" / "Baseline" / "metadata.json").write_text('{"note": "sidecar"}')
    (r / "SiteA" / "README.txt").write_text("site notes")
    (r / "SiteA" / ".DS_Store").write_bytes(b"x")
    (r / "__MACOSX" / "junk").mkdir(parents=True)
    # SiteA/Subject002: follow-up has AC + NAC PET (R1 resolves) and two SEG (ambiguous); no CT
    pet(r / "SiteA" / "Subject002" / "BL" / "pet", "P002", "20200105")
    pet(r / "SiteA" / "Subject002" / "FU1" / "ac", "P002", "20200310")
    pet(r / "SiteA" / "Subject002" / "FU1" / "nac", "P002", "20200310", CorrectedImage=["DECY"])
    # SiteB/Subject003: two attenuation-corrected BQML PET series at follow-up -> NEEDS_REVIEW
    pet(r / "SiteB" / "Subject003" / "pre" / "s1", "P003", "20200110")
    pet(r / "SiteB" / "Subject003" / "post" / "recon_a", "P003", "20200401")
    pet(r / "SiteB" / "Subject003" / "post" / "recon_b", "P003", "20200401")
    # SiteB/Subject004: unrecognised timepoint name -> NEEDS_REVIEW
    pet(r / "SiteB" / "Subject004" / "baseline" / "x", "P004", "20200111")
    pet(r / "SiteB" / "Subject004" / "week 6" / "x", "P004", "20200220")
    return r


def by(m, subject, tp_raw):
    return next(s for s in m["scans"] if s["subject"] == subject and s["timepoint_raw"] == tp_raw)


def test_timepoint_aliases():
    assert (
        canonical_timepoint("Baseline")
        == canonical_timepoint("BL")
        == canonical_timepoint("pre")
        == "baseline"
    )
    assert canonical_timepoint("Follow-Up") == canonical_timepoint("post") == "followup"
    assert canonical_timepoint("FU1") == canonical_timepoint("T1") == "followup"
    assert canonical_timepoint("followup_2") == canonical_timepoint("FU2") == "followup2"
    assert canonical_timepoint("fu0") is None
    assert canonical_timepoint("week 6") is None
    assert canonical_timepoint("week 6", {"week 6": "followup"}) == "followup"


def test_mapping_interprets_messy_drop(drop):
    m = map_intake(drop)
    assert m["schema"] == "VT-INTAKE-MAPPING-1" and m["status"] == "NEEDS_REVIEW"
    s1b = by(m, "Subject001", "Baseline")
    assert s1b["status"] == "MAPPED" and s1b["site"] == "SiteA" and s1b["timepoint"] == "baseline"
    assert s1b["pet_selected"] and s1b["ct_selected"] and s1b["segmentation_selected"] is None
    assert by(m, "Subject001", "Follow-Up")["timepoint"] == "followup"
    fu = by(m, "Subject002", "FU1")
    assert fu["pet_selected"] and {x["excluded_by"] for x in fu["pet_selection"]} == {
        "R1_NAC",
        None,
    }
    assert fu["status"] == "MAPPED_WITH_WARNINGS"  # no CT
    amb = by(m, "Subject003", "post")
    assert amb["status"] == "NEEDS_REVIEW" and amb["pet_selected"] is None
    assert {f["code"] for f in amb["findings"]} >= {"MULTIPLE_PET_CANDIDATES"}
    wk = by(m, "Subject004", "week 6")
    assert wk["status"] == "NEEDS_REVIEW" and wk["timepoint"] is None
    reasons = {i["path"]: i["reason"] for i in m["ignored_files"]}
    assert "not DICOM" in reasons["SiteA/Subject001/Baseline/protocol.pdf"]
    assert "not DICOM" in reasons["SiteA/Subject001/Baseline/metadata.json"]
    assert "above" in reasons["SiteA/README.txt"] and "hidden" in reasons["SiteA/.DS_Store"]
    assert any(p.startswith("__MACOSX") for p in reasons)
    text = json.dumps(m)
    assert "P001" not in text  # patient identifiers only as sha256


def test_mapping_is_deterministic(drop):
    assert json.dumps(map_intake(drop), sort_keys=True) == json.dumps(
        map_intake(drop), sort_keys=True
    )


def test_duplicate_timepoints_and_mixed_patient(tmp_path):
    r = tmp_path / "d"
    pet(r / "A" / "S1" / "baseline" / "x", "P1", "20200101")
    pet(r / "A" / "S1" / "BL" / "x", "P1", "20200102")
    pet(r / "A" / "S2" / "baseline" / "x", "P2", "20200101")
    pet(r / "A" / "S2" / "baseline" / "y", "OTHER", "20200101", CorrectedImage=["DECY"])
    m = map_intake(r)
    codes = {(s["subject"], f["code"]) for s in m["scans"] for f in s["findings"]}
    assert ("S1", "DUPLICATE_TIMEPOINT") in codes and ("S2", "MIXED_PATIENT_IN_SCAN") in codes


def test_subject_name_collision_across_sites_is_prefixed(tmp_path):
    r = tmp_path / "d"
    for site, pid in (("A", "P1"), ("B", "P2")):
        pet(r / site / "001" / "baseline" / "x", pid, "20200101")
        pet(r / site / "001" / "followup" / "x", pid, "20200301")
    m = map_intake(r)
    assert {s["staged_subject"] for s in m["scans"]} == {"A-001", "B-001"}
    assert m["status"] == "MAPPED_WITH_WARNINGS"  # no CT anywhere


def test_stage_and_audit_the_mapped_scans(drop, tmp_path):
    m = map_intake(drop)
    out = tmp_path / "staged"
    r = stage_intake(m, drop, out, trial_id="DRY")
    assert "Subject001/baseline" in r["staged"] and "Subject002/followup" in r["staged"]
    assert {x["scan"] for x in r["skipped"]} == {"Subject003/post", "Subject004/week 6"}
    assert (out / "Subject001" / "baseline" / "PET").is_dir() and (
        out / "Subject001" / "baseline" / "CT"
    ).is_dir()
    assert not (out / "Subject002" / "followup" / "CT").exists()
    import yaml

    cfg = yaml.safe_load((out / "trial.yaml").read_text())
    assert cfg["sites"]["Subject001"] == "SiteA" and cfg["timepoint_order"][0] == "baseline"
    from voxeltrace.validate_input import validate_input

    v = validate_input(out)
    assert v["decision"] in ("ACCEPT_FOR_AUDIT", "ACCEPT_WITH_WARNINGS", "NEEDS_REEXPORT")
    with pytest.raises(FileExistsError):
        stage_intake(m, drop, out, trial_id="DRY")


def test_intake_map_cli(drop, tmp_path, capsys):
    rc = cli(["intake-map", str(drop), "--out", str(tmp_path / "m.json"), "--stage", str(tmp_path / "st"),
              "--trial-id", "X", "--timepoint-map", "week 6=followup"])  # fmt: skip
    assert rc == 2  # Subject003 remains ambiguous
    m = json.loads((tmp_path / "m.json").read_text())
    assert by(m, "Subject004", "week 6")["timepoint"] == "followup"
    assert (tmp_path / "st" / "Subject004" / "followup" / "PET").is_dir()
    assert cli(["intake-map", str(drop), "--out", str(tmp_path / "m.json")]) == 2  # never overwrite
