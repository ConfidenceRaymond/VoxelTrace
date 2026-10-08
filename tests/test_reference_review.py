"""Human reference-region review: records, hash binding, OUTDATED/INVALID, audit consumption.

Every review in this file is SIMULATED (``simulated=True``) and written only under pytest's
temporary directory. Production audits refuse SIMULATED records.
"""

from pathlib import Path

import pytest
import yaml

from dicom_factory import build_pet_ct_seg_case
from voxeltrace.quant.reference_auto import ReferenceProposal
from voxeltrace.quant.reference_region import ReferenceRegionResult
from voxeltrace.rules import percist
from voxeltrace.trial.audit import run_trial_audit
from voxeltrace.trial.perturb import perturb_case
from voxeltrace.trial.reference import (
    InvalidReview,
    ReferenceReview,
    build_review,
    load_reviews,
    record_review,
    reference_reason,
    resolve_region,
    review_status,
)
from voxeltrace.trial.schema import PairContext, ScanPair, ScanTimepoint
from voxeltrace.trial.summary import review_worksheet

PROP = ReferenceProposal(
    region="LIVER",
    status="PROPOSED",
    method="SPHERE_AT_SUPPLIED_CENTRE",
    centre_patient_mm=(1.0, 2.0, 3.0),
    diameter_mm=30.0,
    pet_series_pseudonym="p",
)
BLOOD = ReferenceProposal(
    region="BLOOD_POOL",
    status="PROPOSED",
    method="CYLINDER_AT_SUPPLIED_CENTRE",
    centre_patient_mm=(4.0, 5.0, 6.0),
    diameter_mm=10.0,
    length_mm=20.0,
    pet_series_pseudonym="p",
)


def measured(spec):
    return ReferenceRegionResult(
        status="COMPUTED",
        region=spec.region,
        method=spec.method,
        provenance=spec.provenance,
        centre_patient_mm=spec.centre_patient_mm,
        diameter_mm=spec.diameter_mm,
        length_mm=spec.length_mm,
        suv_mean=2.0,
        sul_mean=1.5,
        sul_sd=0.2,
        voxel_count=100,
    )


def rv(decision, proposal=PROP, subject="S", timepoint="B", centre=None, **kw):
    return build_review(
        subject=subject,
        timepoint=timepoint,
        proposal=proposal,
        decision=decision,
        reviewer="core lab reader 1",
        adjusted_centre=centre,
        simulated=True,
        **kw,
    )


def resolve(review=None, proposal=PROP, measure=measured):
    return resolve_region(
        proposal.region,
        supplied=None,
        proposal=proposal,
        review=review,
        measure=measure,
        auto_enabled=True,
    )


# ------------------------------------------------------------------ decisions


def test_unreviewed_proposal_is_never_computed():
    r = resolve()
    assert r.status == "PROPOSED_REQUIRES_REVIEW" and r.suv_mean == 2.0  # preview only
    reason = reference_reason("B", r, "LIVER", subject="S")
    assert reason.code == "REFERENCE_REVIEW_REQUIRED"
    assert "S/B LIVER" in reason.detail and PROP.sha256 in reason.detail
    assert review_status(PROP.sha256, None) == "UNREVIEWED"


def test_accept_decision():
    review = rv("ACCEPT")
    assert review.final_geometry == review.proposal_geometry
    assert review.review_sha256 == review.content_sha256()
    assert review.rule_context.rule_ids == [
        "PERCIST-LIVER-SUL-STABILITY",
        "PERCIST-BASELINE-MEASURABLE",
    ]
    assert review.rule_context.ruleset_version == percist.V
    assert review.git_commit and review.software_version
    r = resolve(review)
    assert r.status == "COMPUTED" and r.review_decision == "ACCEPT"
    assert "accepted by core lab reader 1" in r.provenance
    assert reference_reason("B", r, "LIVER") is None
    assert review_status(PROP.sha256, review) == "ACCEPTED"


def test_adjust_decision_moves_centre_only_and_rehashes():
    acc, adj = rv("ACCEPT"), rv("ADJUST", centre=(5.04, 6.0, 7.0))
    assert adj.final_geometry.centre_patient_mm == (5.0, 6.0, 7.0)  # recorded at 0.1 mm
    assert adj.final_geometry.diameter_mm == 30.0  # size fixed by the rule
    assert adj.final_region_sha256 != acc.final_region_sha256
    r = resolve(adj)
    assert r.status == "COMPUTED" and r.centre_patient_mm == (5.0, 6.0, 7.0)
    assert review_status(PROP.sha256, adj) == "ADJUSTED"
    with pytest.raises(ValueError, match="ADJUST must move"):
        rv("ADJUST", centre=PROP.centre_patient_mm)
    with pytest.raises(ValueError, match="requires the adjusted centre"):
        rv("ADJUST")


def test_size_change_refused():
    d = rv("ADJUST", centre=(5.0, 6.0, 7.0)).model_dump()
    d["final_geometry"]["diameter_mm"] = 20.0
    d["review_sha256"] = None
    d["final_region_sha256"] = None
    with pytest.raises(ValueError, match="only the centre"):
        ReferenceReview.model_validate(d)


def test_reject_decision():
    review = rv("REJECT", note="sphere touches the liver edge")
    assert review.final_geometry is None
    r = resolve(review)
    assert r.status == "REJECTED_BY_REVIEWER" and "liver edge" in r.refusal
    assert reference_reason("B", r, "LIVER").code == "REFERENCE_REJECTED_BY_REVIEWER"
    assert review_status(PROP.sha256, review) == "REJECTED"


def test_proposal_hash_mismatch_is_outdated():
    review = rv("ACCEPT", proposal=PROP)
    other = PROP.model_copy(update={"pet_series_pseudonym": "another scan"})
    r = resolve(review, proposal=other)
    assert r.status == "REVIEW_OUTDATED" and "not reused" in r.refusal
    assert reference_reason("B", r, "LIVER").code == "REFERENCE_REVIEW_OUTDATED"
    assert review_status(other.sha256, review) == "OUTDATED"


@pytest.mark.parametrize(
    "change",
    [
        {"centre_patient_mm": (1.0, 2.0, 6.0)},
        {"algorithm_version": "vt-refauto-2"},
    ],
)
def test_changed_proposal_invalidates_old_review(change):
    old = rv("ADJUST", centre=(9.0, 9.0, 9.0))
    new = PROP.model_copy(update=change)
    assert new.sha256 != PROP.sha256
    r = resolve(old, proposal=new)
    assert r.status == "REVIEW_OUTDATED"
    assert r.suv_mean is None  # nothing measured from the outdated review


def test_accepted_region_failing_qc_is_actionable():
    def refused(spec):
        return ReferenceRegionResult(status="REFUSED", region="LIVER", refusal="overlaps a lesion")

    r = resolve(rv("ACCEPT"), measure=refused)
    assert reference_reason("B", r, "LIVER").code == "REFERENCE_QC_FAILED"


# ------------------------------------------------------------------ file records


def _write_entry(path: Path, key: str, region: str, entry: dict) -> None:
    path.write_text(yaml.safe_dump({"reviews": {key: {region: entry}}}))


def _entry(review: ReferenceReview) -> dict:
    import json

    return json.loads(review.model_dump_json())


def test_record_and_load_roundtrip(tmp_path):
    f = tmp_path / "reference_review.yaml"
    record_review(f, rv("ACCEPT"), confirmed=True)
    record_review(f, rv("REJECT", proposal=BLOOD), confirmed=True)
    got = load_reviews(f, allow_simulated=True)
    assert got["S/B"]["LIVER"].decision == "ACCEPT"
    assert got["S/B"]["BLOOD_POOL"].decision == "REJECT"


def test_record_requires_confirmation_and_explicit_replace(tmp_path):
    f = tmp_path / "reference_review.yaml"
    with pytest.raises(PermissionError):
        record_review(f, rv("ACCEPT"), confirmed=False)
    assert not f.exists()
    record_review(f, rv("ACCEPT"), confirmed=True)
    with pytest.raises(FileExistsError):
        record_review(f, rv("REJECT"), confirmed=True)
    record_review(f, rv("REJECT"), confirmed=True, replace=True)
    doc = yaml.safe_load(f.read_text())
    assert doc["reviews"]["S/B"]["LIVER"]["decision"] == "REJECT"
    assert doc["superseded"][0]["decision"] == "ACCEPT"


def test_review_from_different_subject_is_invalid(tmp_path):
    f = tmp_path / "r.yaml"
    _write_entry(f, "OTHER/B", "LIVER", _entry(rv("ACCEPT", subject="S")))
    got = load_reviews(f, allow_simulated=True)["OTHER/B"]["LIVER"]
    assert isinstance(got, InvalidReview) and "filed under OTHER/B" in got.error
    r = resolve(got)
    assert r.status == "REVIEW_INVALID"
    assert reference_reason("B", r, "LIVER").code == "REFERENCE_REVIEW_INVALID"


def test_review_for_wrong_region_type_is_invalid(tmp_path):
    f = tmp_path / "r.yaml"
    _write_entry(f, "S/B", "BLOOD_POOL", _entry(rv("ACCEPT")))  # a LIVER review
    got = load_reviews(f, allow_simulated=True)["S/B"]["BLOOD_POOL"]
    assert isinstance(got, InvalidReview) and "region LIVER" in got.error
    assert resolve(got, proposal=BLOOD).status == "REVIEW_INVALID"


def test_edited_record_is_invalid(tmp_path):
    e = _entry(rv("ACCEPT"))
    e["reviewer"] = "someone else"  # edited after saving
    f = tmp_path / "r.yaml"
    _write_entry(f, "S/B", "LIVER", e)
    got = load_reviews(f, allow_simulated=True)["S/B"]["LIVER"]
    assert isinstance(got, InvalidReview) and "review_sha256" in got.error


@pytest.mark.parametrize(
    "patch",
    [
        {"reviewer": ""},
        {"reviewed_at": "yesterday"},
        {"proposal_sha256": "abc"},
        {"decision": "ACCEPT", "final_geometry": None},
    ],
)
def test_incomplete_records_invalid(tmp_path, patch):
    e = {**_entry(rv("ACCEPT")), **patch, "review_sha256": None, "final_region_sha256": None}
    f = tmp_path / "r.yaml"
    _write_entry(f, "S/B", "LIVER", e)
    assert isinstance(load_reviews(f, allow_simulated=True)["S/B"]["LIVER"], InvalidReview)


def test_pending_entries_are_not_reviews(tmp_path):
    f = tmp_path / "r.yaml"
    _write_entry(f, "S/B", "LIVER", {"decision": "PENDING", "proposal_sha256": PROP.sha256})
    assert load_reviews(f) == {}


# ------------------------------------------------------------------ simulated reviews


def test_simulated_reviews_refused_by_production_loader(tmp_path):
    f = tmp_path / "r.yaml"
    record_review(f, rv("ACCEPT"), confirmed=True)
    got = load_reviews(f)["S/B"]["LIVER"]  # default: production
    assert isinstance(got, InvalidReview) and "SIMULATED" in got.error
    assert resolve(got).status == "REVIEW_INVALID"


def test_simulated_review_cannot_be_written_to_project_outputs():
    from voxeltrace.config import REPO_ROOT

    for tree in ("outputs", "data"):
        target = REPO_ROOT.parent / tree / "any_trial" / "reference_review.yaml"
        with pytest.raises(PermissionError, match="SIMULATED"):
            record_review(target, rv("ACCEPT"), confirmed=True)
        assert not target.exists()


def test_no_simulated_review_in_real_outputs():
    from voxeltrace.config import REPO_ROOT

    roots = [REPO_ROOT.parent / "outputs", REPO_ROOT.parent / "data"]
    files = [f for r in roots if r.exists() for f in r.rglob("reference_review*.yaml")]
    for f in files:
        doc = yaml.safe_load(f.read_text()) or {}
        for regions in (doc.get("reviews") or {}).values():
            for entry in (regions or {}).values():
                assert not (entry or {}).get("simulated"), f


def test_review_code_never_calls_a_model():
    src = Path(__file__).resolve().parents[1] / "src" / "voxeltrace"
    files = [
        src / "trial" / "reference.py",
        src / "trial" / "review.py",
        src / "visualization" / "reference_qc.py",
        Path(__file__).resolve().parents[1] / "app" / "pages" / "4_Reference_Review.py",
    ]
    for f in files:
        text = f.read_text()
        for banned in ("voxeltrace.ai", "transformers", "LocalAIClient", "qwen", "Qwen"):
            assert banned not in text, (f.name, banned)


# ------------------------------------------------------------------ worksheet


def test_worksheet_entries_are_pending_and_complete(tmp_path):
    from voxeltrace.trial.audit import TrialAudit

    t = ScanTimepoint(subject_id="S", timepoint="B", suv_status="PASS", liver=resolve())
    audit = TrialAudit(
        trial_id="T",
        ruleset_id="percist-1.0",
        ruleset_version="v",
        standard="PERCIST_1.0",
        timepoints=[t],
        pairs=[],
    )
    ws = review_worksheet(audit)
    e = ws["reviews"]["S/B"]["LIVER"]
    assert e["decision"] == "PENDING" and e["proposal_sha256"] == PROP.sha256
    f = tmp_path / "reference_review.yaml"
    f.write_text(yaml.safe_dump(ws))
    assert load_reviews(f) == {}
    e.update(decision="ACCEPT", reviewer="reader 2", reviewed_at="2026-10-09T10:00:00+00:00")
    f.write_text(yaml.safe_dump(ws))
    got = load_reviews(f)["S/B"]["LIVER"]  # a hand-completed worksheet entry is valid
    assert isinstance(got, ReferenceReview) and got.decision == "ACCEPT"
    assert review_status(PROP.sha256, got) == "ACCEPTED"


# ------------------------------------------------------------------ PERCIST rule + audit


def _ctx(liver_b, liver_f):
    def tp(name, liver):
        return ScanTimepoint(
            subject_id="S", timepoint=name, suv_status="PASS", uptake_s=3600, liver=liver
        )

    return PairContext(
        pair=ScanPair(subject_id="S", baseline="B", followup="F"),
        baseline=tp("B", liver_b),
        followup=tp("F", liver_f),
    )


def test_percist_liver_rule_ignores_unreviewed_proposals():
    rule, fn = percist.LIVER, percist.RULES[2][1]
    c = fn(rule, _ctx(resolve(), resolve()))
    assert c.status == "UNKNOWN"
    assert {r.code for r in c.reasons} == {"REFERENCE_REVIEW_REQUIRED"}
    ok = fn(rule, _ctx(resolve(rv("ACCEPT")), resolve(rv("ACCEPT", timepoint="F"))))
    assert ok.status == "PASS"


@pytest.fixture
def percist_trial(tmp_path, monkeypatch):
    """Synthetic DICOM trial (real baseline + identity copy) under PERCIST, with the proposer
    and region measurement replaced by fixed fakes (the real ones are tested elsewhere)."""
    from voxeltrace.trial import timepoint as tpmod

    base = tmp_path / "real"
    build_pet_ct_seg_case(base)
    perturb_case(base, tmp_path / "p" / "identity", "identity")
    t = tmp_path / "trial"
    (t / "S").mkdir(parents=True)
    (t / "S" / "BASELINE").symlink_to(base, target_is_directory=True)
    (t / "S" / "FOLLOWUP").symlink_to(tmp_path / "p" / "identity", target_is_directory=True)
    (t / "trial.yaml").write_text(
        yaml.safe_dump(
            {
                "trial_id": "T",
                "ruleset": "percist-1.0",
                "timepoint_order": ["BASELINE", "FOLLOWUP"],
            }
        )
    )

    def fake_proposals(case, run, tp, lesion_masks, qc_dir):
        props = {
            "LIVER": PROP.model_copy(update={"pet_series_pseudonym": tp.pet_series_pseudonym}),
            "BLOOD_POOL": BLOOD.model_copy(
                update={"pet_series_pseudonym": tp.pet_series_pseudonym}
            ),
        }
        return props, {}, None

    def fake_measure(suv, g, spec, **kw):
        return measured(spec)

    monkeypatch.setattr(tpmod, "_auto_proposals", fake_proposals)
    monkeypatch.setattr(tpmod, "measure_reference_region", fake_measure)
    return t


def _liver_check(audit):
    (pair,) = audit.pairs
    return pair, next(c for c in pair.checks if c.rule_id == "PERCIST-LIVER-SUL-STABILITY")


def test_audit_stays_insufficient_information_without_review(percist_trial):
    audit = run_trial_audit(percist_trial)
    pair, c = _liver_check(audit)
    assert pair.verdict == "INSUFFICIENT_INFORMATION"
    assert c.status == "UNKNOWN"
    details = [r.detail for r in c.reasons]
    assert {r.code for r in c.reasons} == {"REFERENCE_REVIEW_REQUIRED"}
    assert any("S/BASELINE LIVER" in d for d in details)
    assert any("S/FOLLOWUP LIVER" in d for d in details)
    assert audit.reference_reviews_applied == 0


def test_audit_consumes_valid_review(percist_trial):
    audit0 = run_trial_audit(percist_trial)
    f = percist_trial / "reference_review.yaml"
    for tp in audit0.timepoints:
        prop = PROP.model_copy(update={"pet_series_pseudonym": tp.pet_series_pseudonym})
        assert tp.liver.proposal_sha256 == prop.sha256
        record_review(
            f, rv("ACCEPT", proposal=prop, subject="S", timepoint=tp.timepoint), confirmed=True
        )
    # production mode refuses the SIMULATED records ...
    prod = run_trial_audit(percist_trial)
    _, c = _liver_check(prod)
    assert c.status == "UNKNOWN" and {r.code for r in c.reasons} == {"REFERENCE_REVIEW_INVALID"}
    # ... the test-only switch shows the audit consumes a valid review
    audit = run_trial_audit(percist_trial, allow_simulated_reviews=True)
    _, c = _liver_check(audit)
    assert c.status == "PASS" and not c.reasons
    assert audit.reference_reviews_applied == 2
    assert {tp.liver.status for tp in audit.timepoints} == {"COMPUTED"}
    assert {tp.blood_pool.status for tp in audit.timepoints} == {"PROPOSED_REQUIRES_REVIEW"}


def test_audit_marks_review_outdated_after_proposal_change(percist_trial, monkeypatch):
    from voxeltrace.trial import timepoint as tpmod

    audit0 = run_trial_audit(percist_trial)
    f = percist_trial / "reference_review.yaml"
    for tp in audit0.timepoints:
        prop = PROP.model_copy(update={"pet_series_pseudonym": tp.pet_series_pseudonym})
        record_review(f, rv("ACCEPT", proposal=prop, timepoint=tp.timepoint), confirmed=True)
    moved = PROP.model_copy(update={"centre_patient_mm": (1.0, 2.0, 9.0)})
    monkeypatch.setattr(
        tpmod,
        "_auto_proposals",
        lambda case, run, tp, lm, qc: (
            {"LIVER": moved.model_copy(update={"pet_series_pseudonym": tp.pet_series_pseudonym})},
            {},
            None,
        ),
    )
    audit = run_trial_audit(percist_trial, allow_simulated_reviews=True)
    _, c = _liver_check(audit)
    assert {r.code for r in c.reasons} == {"REFERENCE_REVIEW_OUTDATED"}
    assert audit.reference_reviews_applied == 0
