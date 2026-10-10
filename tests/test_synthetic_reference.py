"""SYNTHETIC_INHERITED_REFERENCE: allowed only for synthetic test fixtures whose CT is the
unchanged parent CT; never for real scans; provenance names the source review."""

import hashlib
import json

import pydicom
import pytest
import yaml

from dicom_factory import build_pet_ct_seg_case
from test_reference_review import BLOOD, PROP, measured, rv
from voxeltrace.quant.reference_region import ReferenceRegionResult
from voxeltrace.rules import percist
from voxeltrace.trial.audit import run_trial_audit
from voxeltrace.trial.perturb import CT_LABEL, perturb_case
from voxeltrace.trial.reference import record_review, reference_reason
from voxeltrace.trial.schema import PairContext, ScanPair, ScanTimepoint
from voxeltrace.trial.summary import review_status_of
from voxeltrace.trial.synthetic_reference import (
    FIXTURE_FILE,
    InheritanceRequest,
    SyntheticFixtureManifest,
    inherit_region,
    refusal_reason,
)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture
def trial(tmp_path, monkeypatch):
    """Real-like baseline + identity synthetic follow-up WITH copied CT; proposer and
    measurement replaced by fixed fakes; baseline reviews SIMULATED (tests only)."""
    from voxeltrace.trial import timepoint as tpmod

    base = tmp_path / "real"
    build_pet_ct_seg_case(base)
    fu = perturb_case(base, tmp_path / "p" / "identity", "identity", with_ct=True)
    t = tmp_path / "trial"
    (t / "S").mkdir(parents=True)
    (t / "S" / "BASELINE").symlink_to(base, target_is_directory=True)
    (t / "S" / "FOLLOWUP").symlink_to(fu, target_is_directory=True)
    cfg = {
        "trial_id": "T",
        "ruleset": "percist-1.0",
        "timepoint_order": ["BASELINE", "FOLLOWUP"],
        "synthetic_perturbations": {"S/FOLLOWUP": "SYNTHETIC_PERTURBATION identity"},
        "synthetic_reference_inheritance": {"S/FOLLOWUP": {"parent": "S/BASELINE"}},
    }
    (t / "trial.yaml").write_text(yaml.safe_dump(cfg))

    def fake_proposals(case, run, tp, lesion_masks, qc_dir):
        tpmod._ct_fingerprint(case, run, tp)
        upd = {"pet_series_pseudonym": tp.pet_series_pseudonym}
        return (
            {"LIVER": PROP.model_copy(update=upd), "BLOOD_POOL": BLOOD.model_copy(update=upd)},
            {},
            None,
        )

    monkeypatch.setattr(tpmod, "_auto_proposals", fake_proposals)
    monkeypatch.setattr(tpmod, "measure_reference_region", lambda s, g, spec, **k: measured(spec))
    a0 = run_trial_audit(t)
    b = next(x for x in a0.timepoints if x.timepoint == "BASELINE")
    upd = {"pet_series_pseudonym": b.pet_series_pseudonym}
    for p in (PROP, BLOOD):
        record_review(
            t / "reference_review.yaml",
            rv("ACCEPT", proposal=p.model_copy(update=upd), timepoint="BASELINE"),
            confirmed=True,
        )
    return t, base, fu, cfg


def audit(t):
    return run_trial_audit(t, allow_simulated_reviews=True)


def fu_tp(a):
    return next(x for x in a.timepoints if x.timepoint == "FOLLOWUP")


def test_fixture_is_labelled_and_ct_unchanged(trial):
    _, base, fu, _ = trial
    m = SyntheticFixtureManifest.load(fu)
    assert m and set(m.labels) == {"SYNTHETIC_PERTURBATION", "CT_COPIED_UNCHANGED_FROM_BASELINE"}
    assert m.ct_copied_unchanged and m.perturbation == "identity"
    ds = pydicom.dcmread(next((fu / "CT").glob("*.dcm")))
    assert ds.SeriesDescription == CT_LABEL and "NOT a real follow-up CT" in ds.ImageComments
    orig = pydicom.dcmread(next((base / "b_ct").glob("*.dcm")))
    assert ds.FrameOfReferenceUID != orig.FrameOfReferenceUID  # the synthetic case's frame


def test_inherited_reference_for_synthetic_fixture(trial):
    t, *_ = trial
    a = audit(t)
    b = next(x for x in a.timepoints if x.timepoint == "BASELINE")
    f = fu_tp(a)
    for parent, child in ((b.liver, f.liver), (b.blood_pool, f.blood_pool)):
        assert parent.status == "COMPUTED" and parent.review_decision == "ACCEPT"
        assert child.status == "SYNTHETIC_INHERITED_REFERENCE"  # never COMPUTED / ACCEPTED
        assert child.source == "SYNTHETIC_INHERITED" and child.review_decision is None
        g = child.inherited_from["geometry"]
        assert (g["method"], tuple(g["centre_patient_mm"]), g["diameter_mm"], g["length_mm"]) == (
            parent.method,
            parent.centre_patient_mm,
            parent.diameter_mm,
            parent.length_mm,
        )
        assert child.centre_patient_mm == parent.centre_patient_mm
    reviews = yaml.safe_load((t / "reference_review.yaml").read_text())["reviews"]
    assert (
        f.liver.inherited_from["source_review_sha256"]
        == (reviews["S/BASELINE"]["LIVER"]["review_sha256"])
    )
    assert review_status_of(f.liver) == "SYNTHETIC_INHERITED_REFERENCE"
    (pair,) = a.pairs
    c = next(c for c in pair.checks if c.rule_id == "PERCIST-LIVER-SUL-STABILITY")
    assert c.status == "PASS"  # the liver rule now executes on the synthetic pair


def test_rejected_for_real_scan(trial):
    t, base, _, cfg = trial
    # a REAL copy of the baseline declared as an inheriting follow-up, not declared synthetic
    cfg["synthetic_perturbations"] = {}
    (t / "trial.yaml").write_text(yaml.safe_dump(cfg))
    f = fu_tp(audit(t))
    assert f.liver.status == "INHERITANCE_REFUSED"
    assert "not declared SYNTHETIC_PERTURBATION" in f.liver.refusal
    assert reference_reason("FOLLOWUP", f.liver, "LIVER").code == "REFERENCE_INHERITANCE_REFUSED"


def test_rejected_without_dicom_synthetic_label(trial, tmp_path):
    t, base, _, cfg = trial
    real_copy = tmp_path / "realcopy"
    import shutil

    shutil.copytree(base, real_copy)
    (t / "S" / "FOLLOWUP").unlink()
    (t / "S" / "FOLLOWUP").symlink_to(real_copy, target_is_directory=True)
    f = fu_tp(audit(t))  # declared synthetic in yaml, but the DICOM is not labelled
    assert f.liver.status == "INHERITANCE_REFUSED" and "DICOM label" in f.liver.refusal


def test_parent_scan_hash_must_match(trial):
    t, _, fu, _ = trial
    p = fu / FIXTURE_FILE
    m = json.loads(p.read_text())
    m["parent_pet_content_sha256"] = "0" * 64
    p.write_text(json.dumps(m))
    f = fu_tp(audit(t))
    assert f.liver.status == "INHERITANCE_REFUSED" and "parent PET content hash" in f.liver.refusal


@pytest.mark.parametrize(
    ("attr", "msg"),
    [("ImagePositionPatient", "geometry"), ("PixelData", "pixel data")],
)
def test_ct_geometry_and_pixels_must_match(trial, attr, msg):
    t, _, fu, _ = trial
    files = sorted((fu / "CT").glob("*.dcm"))
    ds = pydicom.dcmread(files[0])
    if attr == "ImagePositionPatient":
        for f in files:  # shift the whole CT 1 mm: geometry differs, pixels identical
            d = pydicom.dcmread(f)
            d.ImagePositionPatient = [float(v) + 1.0 for v in d.ImagePositionPatient]
            d.save_as(f)
    else:
        arr = ds.pixel_array.copy()
        arr[0, 0] += 1
        ds.PixelData = arr.tobytes()
        ds.save_as(files[0])
    f = fu_tp(audit(t))
    assert f.liver.status == "INHERITANCE_REFUSED" and msg in f.liver.refusal


def test_parent_needs_accepted_region(trial):
    t, *_ = trial
    (t / "reference_review.yaml").unlink()  # parent unreviewed
    f = fu_tp(audit(t))
    assert f.liver.status == "INHERITANCE_REFUSED" and "not COMPUTED" in f.liver.refusal


def test_inherited_region_rejected_on_real_scan_by_rules():
    inherited = ReferenceRegionResult(
        status="SYNTHETIC_INHERITED_REFERENCE",
        region="LIVER",
        source="SYNTHETIC_INHERITED",
        inherited_from={"parent_key": "S/B"},
        sul_mean=1.5,
        sul_sd=0.2,
    )
    assert reference_reason("F", inherited, "LIVER", synthetic=True) is None
    r = reference_reason("F", inherited, "LIVER", synthetic=False)
    assert r.code == "REFERENCE_INHERITANCE_REFUSED" and "real scan" in r.detail

    def tp(name, synthetic):
        return ScanTimepoint(
            subject_id="S",
            timepoint=name,
            suv_status="PASS",
            liver=inherited,
            synthetic_perturbation="SYNTHETIC_PERTURBATION x" if synthetic else None,
        )

    def ctx(synthetic):
        return PairContext(
            pair=ScanPair(subject_id="S", baseline="B", followup="F"),
            baseline=tp("B", synthetic),
            followup=tp("F", synthetic),
        )

    rule, fn = percist.LIVER, percist.RULES[2][1]
    assert fn(rule, ctx(True)).status == "PASS"
    real = fn(rule, ctx(False))
    assert real.status == "UNKNOWN"
    assert {x.code for x in real.reasons} == {"REFERENCE_INHERITANCE_REFUSED"}


def test_refusal_reasons_unit():
    good = InheritanceRequest(
        child_key="S/F",
        parent_key="S/B",
        declared_synthetic=True,
        dicom_synthetic_label=True,
        fixture=SyntheticFixtureManifest(
            labels=["SYNTHETIC_PERTURBATION", "CT_COPIED_UNCHANGED_FROM_BASELINE"],
            perturbation="identity",
            parent_case_dir="/x",
            parent_pet_content_sha256="p",
            ct_copied_unchanged=True,
            ct_geometry_sha256="g",
            ct_pixel_sha256="c",
        ),
        parent_pet_content_sha256="p",
        parent_ct_geometry_sha256="g",
        parent_ct_pixel_sha256="c",
        child_ct_geometry_sha256="g",
        child_ct_pixel_sha256="c",
        parent_fixture_match=True,
    )
    assert refusal_reason(good) is None
    assert "labels" in refusal_reason(
        good.model_copy(update={"fixture": good.fixture.model_copy(update={"labels": ["X"]})})
    )
    assert "parent recorded" in refusal_reason(
        good.model_copy(update={"parent_fixture_match": False})
    )
    parent = ReferenceRegionResult(
        status="COMPUTED",
        region="LIVER",
        source="AUTO_PROPOSAL",
        review_decision="ACCEPT",
        method="SPHERE_AT_SUPPLIED_CENTRE",
        centre_patient_mm=(1.0, 2.0, 3.0),
        diameter_mm=30.0,
    )
    no_review = inherit_region("LIVER", good, parent, None, measured)
    assert no_review.status == "INHERITANCE_REFUSED" and "human review" in no_review.refusal
    ok = inherit_region("LIVER", good, parent, "r" * 64, measured)
    assert ok.status == "SYNTHETIC_INHERITED_REFERENCE"
    assert ok.inherited_from["source_review_sha256"] == "r" * 64


def test_production_review_file_untouched(trial):
    from voxeltrace.config import REPO_ROOT

    prod = REPO_ROOT.parent / "outputs" / "synthetic_comparability" / "trial_demo"
    prod_file = prod / "reference_review.yaml"
    before = sha(prod_file) if prod_file.exists() else None
    t, *_ = trial
    local = t / "reference_review.yaml"
    local_before = sha(local)
    audit(t)
    assert sha(local) == local_before  # auditing never writes reviews
    assert (sha(prod_file) if prod_file.exists() else None) == before


def test_fixture_parent_matches_after_workspace_relocation(tmp_path):
    """Regression (2026-10-10): fixture manifests record absolute parent paths; after the
    workspace moved machines, inheritance was refused. Same workspace-relative location
    matches; any other location does not."""
    from voxeltrace.trial.synthetic_reference import same_case_dir

    ws = tmp_path / "ws"
    parent = ws / "data" / "coll" / "CASE1" / "dicom"
    parent.mkdir(parents=True)
    assert same_case_dir(parent, parent, ws)
    assert same_case_dir("/home/olduser/old_ws/data/coll/CASE1/dicom", parent, ws)
    assert not same_case_dir("/home/olduser/old_ws/data/coll/CASE2/dicom", parent, ws)
    assert not same_case_dir("/home/olduser/old_ws/other/coll/CASE1/dicom", parent, ws)
    outside = tmp_path / "elsewhere" / "dicom"
    outside.mkdir(parents=True)
    assert not same_case_dir("/x/elsewhere/dicom", outside, ws)
