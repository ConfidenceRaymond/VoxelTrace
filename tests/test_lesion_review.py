"""Lesion review gate: no supplied mask is quantitative ground truth without a human ACCEPT."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import numpy as np
import pydicom
import pytest
import yaml
from pydicom.uid import generate_uid

from dicom_factory import write_image_series, write_seg
from voxeltrace.trial.audit import run_trial_audit
from voxeltrace.trial.discovery import discover_trial
from voxeltrace.trial.lesion_review import (
    LesionReview,
    append_review,
    classify_source,
    load_reviews,
    verify_log,
)
from voxeltrace.trial.timepoint import build_timepoint

Z = [float(2 * k) for k in range(9)]
PET_OV = {"FrameReferenceTime": "0", "DecayFactor": "1.0", "PatientSize": "1.75", "PatientSex": "M"}


def make_scan(d, *, ai=False, corrected=False, shift=0):
    study, for_uid = generate_uid(), generate_uid()
    stored = np.full((9, 12, 12), 10.0)
    stored[3:6, 4:8, 4:8] = 200.0
    pet_uid, _ = write_image_series(d / "PET", modality="PT", study_uid=study, for_uid=for_uid, n_slices=9,
                                    rows=12, cols=12, pixel_spacing=(2.0, 2.0), z_positions=Z,
                                    pet_overrides=PET_OV, stored=stored, slope=1.0, intercept=0.0)  # fmt: skip
    mask = np.zeros((12, 12), dtype=np.uint8)
    mask[4 + shift : 8, 4:8] = 1
    seg = write_seg(d / "SEG" / "seg.dcm", study_uid=study, for_uid=for_uid, referenced_series_uid=pet_uid,
                    rows=12, cols=12, pixel_spacing=(2.0, 2.0), frames=[(1, Z[k], mask) for k in (3, 4, 5)])  # fmt: skip
    if ai or corrected:
        ds = pydicom.dcmread(seg)
        ds.SeriesDescription = ("AIMI lung and FDG tumor AI segmentation" if ai
                                else "AIMI tumor radiologist 1 corrected segmentation")  # fmt: skip
        ds.SegmentSequence[0].SegmentAlgorithmType = "AUTOMATIC" if ai else "SEMIAUTOMATIC"
        ds.SegmentSequence[0].SegmentAlgorithmName = "nnU-Net"
        ds.save_as(seg)
    return d


def tp_of(d, subject="S1", timepoint="baseline", reviews=None, policy="REVIEW_REQUIRED"):
    return build_timepoint(d, subject=subject, timepoint=timepoint, auto_reference=False,
                           lesion_reviews=reviews, lesion_policy=policy)  # fmt: skip


def review_for(cand, decision="ACCEPT", **kw):
    base = dict(subject=cand.subject, timepoint=cand.timepoint, study_hash=cand.study_hash,
                pet_series_hash=cand.pet_series_hash, seg_series_hash=cand.seg_series_hash,
                seg_file_sha256=cand.seg_file_sha256, segment_number=cand.segment_number,
                segment_label=cand.segment_label, mask_sha256=cand.mask_sha256,
                source_type=cand.source_type, source_provenance=cand.source_provenance,
                reviewer_id="phys-1", reviewer_role="PET_PHYSICIST", decision=decision,
                timestamp=datetime(2026, 10, 9, tzinfo=UTC), software_version="0.1.0",
                created_via="HUMAN_UI", simulated=True)  # fmt: skip
    base.update(kw)
    return LesionReview(**base)


def log_with(tmp_path, *reviews, name="lr.jsonl"):
    p = tmp_path / name
    for r in reviews:
        append_review(p, r, confirmed=True)
    return p


@pytest.fixture
def ai_scan(tmp_path):
    return make_scan(tmp_path / "scan", ai=True)


def test_unreviewed_ai_cannot_be_target(ai_scan):
    tp = tp_of(ai_scan)
    (ev,) = tp.lesion_evidence
    assert ev.candidate.source_type == "AI_GENERATED" and ev.review_status == "UNREVIEWED"
    assert (
        tp.lesion_suvpeak is None and tp.lesion_target_status == "LESION_REVIEW_REQUIRED:UNREVIEWED"
    )
    assert (
        ev.candidate.suv_peak is not None and ev.candidate.voxel_count == 48
    )  # measured, not used


def test_accepted_ai_is_reviewed_evidence_and_source_preserved(ai_scan, tmp_path):
    cand = tp_of(ai_scan).lesion_evidence[0].candidate
    log = log_with(tmp_path, review_for(cand))
    tp = tp_of(ai_scan, reviews=load_reviews(log, allow_simulated=True))
    (ev,) = tp.lesion_evidence
    assert ev.review_status == "ACCEPTED" and ev.used_as_target
    assert ev.candidate.source_type == "AI_GENERATED"  # never relabelled as human
    assert "AI_GENERATED accepted" in ev.evidence_label
    assert (
        tp.lesion_suvpeak == pytest.approx(cand.suv_peak)
        and tp.lesion_target_status == "REVIEWED_TARGET"
    )
    assert "AUTOMATIC" in ev.candidate.source_provenance["basis"]


@pytest.mark.parametrize(
    ("decision", "reason"),
    [("REJECT", []), ("REJECT_AND_REPLACE_REQUIRED", ["REPLACEMENT_MASK_REQUIRED"])],
)
def test_rejected_cannot_be_used(ai_scan, tmp_path, decision, reason):
    cand = tp_of(ai_scan).lesion_evidence[0].candidate
    tp = tp_of(
        ai_scan,
        reviews=load_reviews(log_with(tmp_path, review_for(cand, decision)), allow_simulated=True),
    )
    (ev,) = tp.lesion_evidence
    assert ev.review_status == "REJECTED" and ev.reasons == reason and tp.lesion_suvpeak is None


def test_changed_mask_makes_review_outdated(tmp_path):
    a = make_scan(tmp_path / "a", ai=True)
    cand = tp_of(a).lesion_evidence[0].candidate
    log = log_with(tmp_path, review_for(cand, mask_sha256="f" * 64))
    (ev,) = tp_of(a, reviews=load_reviews(log, allow_simulated=True)).lesion_evidence
    assert ev.review_status == "OUTDATED" and ev.reasons == ["MASK_CHANGED_SINCE_REVIEW"]


def test_wrong_subject_review_not_applied(ai_scan, tmp_path):
    cand = tp_of(ai_scan).lesion_evidence[0].candidate
    log = log_with(tmp_path, review_for(cand, subject="S2"))
    (ev,) = tp_of(ai_scan, reviews=load_reviews(log, allow_simulated=True)).lesion_evidence
    assert ev.review_status == "UNREVIEWED"


def test_wrong_series_review_invalid(ai_scan, tmp_path):
    cand = tp_of(ai_scan).lesion_evidence[0].candidate
    log = log_with(tmp_path, review_for(cand, pet_series_hash="pet_0000000000000000"))
    (ev,) = tp_of(ai_scan, reviews=load_reviews(log, allow_simulated=True)).lesion_evidence
    assert ev.review_status == "INVALID" and ev.reasons == ["REVIEW_FOR_DIFFERENT_SERIES"]


def test_simulated_review_rejected_in_production(ai_scan, tmp_path):
    cand = tp_of(ai_scan).lesion_evidence[0].candidate
    log = log_with(tmp_path, review_for(cand))
    tp = tp_of(ai_scan, reviews=load_reviews(log))  # production: allow_simulated False
    (ev,) = tp.lesion_evidence
    assert ev.review_status == "UNREVIEWED" and ev.reasons == ["SIMULATED_REVIEW_REJECTED"]
    assert tp.lesion_suvpeak is None


def test_tampered_log_detected(ai_scan, tmp_path):
    cand = tp_of(ai_scan).lesion_evidence[0].candidate
    log = log_with(tmp_path, review_for(cand, decision="REJECT"))
    log.write_text(log.read_text().replace('"REJECT"', '"ACCEPT"'))
    assert verify_log(log)["status"] == "TAMPERED"
    (ev,) = tp_of(ai_scan, reviews=load_reviews(log, allow_simulated=True)).lesion_evidence
    assert ev.review_status == "INVALID" and ev.reasons == ["REVIEW_LOG_TAMPERED"]
    with pytest.raises(ValueError):
        append_review(log, review_for(cand), confirmed=True)
    with pytest.raises(PermissionError):
        append_review(tmp_path / "x.jsonl", review_for(cand), confirmed=False)


def test_source_classification_and_provenance(tmp_path):
    manual = tp_of(make_scan(tmp_path / "m")).lesion_evidence[0].candidate
    corrected = tp_of(make_scan(tmp_path / "c", corrected=True)).lesion_evidence[0].candidate
    assert manual.source_type == "HUMAN_MANUAL" and corrected.source_type == "HUMAN_CORRECTED"
    assert (
        manual.source_provenance["seg_file"] == "seg.dcm"
        and corrected.source_provenance["seg_series_description"]
    )
    assert classify_source(None, None, None)[0] == "UNKNOWN"
    assert classify_source("x", "AUTOMATIC", "threshold 41%")[0] == "ALGORITHM_GENERATED"
    assert classify_source("x", "SEMIAUTOMATIC", None)[0] == "ALGORITHM_GENERATED"


def test_review_source_type_must_match(ai_scan, tmp_path):
    cand = tp_of(ai_scan).lesion_evidence[0].candidate
    log = log_with(tmp_path, review_for(cand, source_type="HUMAN_MANUAL"))
    (ev,) = tp_of(ai_scan, reviews=load_reviews(log, allow_simulated=True)).lesion_evidence
    assert ev.review_status == "INVALID" and ev.reasons == ["SOURCE_TYPE_MISMATCH"]


def _trial(tmp_path, *, seg=True, policy=None, synthetic=False):
    root = tmp_path / "trial"
    for tp in ("baseline", "followup"):
        if seg:
            make_scan(root / "S1" / tp, ai=True)
        else:
            write_image_series(
                root / "S1" / tp / "PET",
                modality="PT",
                study_uid=generate_uid(),
                pet_overrides=PET_OV,
            )
    cfg = {"trial_id": "T", "ruleset": "percist-1.0", "timepoint_order": ["baseline", "followup"],
           "reference_proposals": "off"}  # fmt: skip
    if policy:
        cfg["lesion_evidence_policy"] = policy
    if synthetic:
        cfg["synthetic_perturbations"] = {"S1/followup": "SYNTHETIC_PERTURBATION identity"}
    (root / "trial.yaml").write_text(yaml.safe_dump(cfg))
    return root


def test_audit_reports_lesion_review_required_and_exports(tmp_path):
    from voxeltrace.trial.export import export_audit

    root = _trial(tmp_path)
    a = run_trial_audit(root, "percist-1.0")
    c = next(c for c in a.pairs[0].checks if c.rule_id == "PERCIST-BASELINE-MEASURABLE")
    assert c.status == "UNKNOWN" and "LESION_REVIEW_REQUIRED" in {r.code for r in c.reasons}
    assert {r["review_status"] for r in a.lesion_evidence} == {"UNREVIEWED"} and len(
        a.lesion_evidence
    ) == 2
    names = {p.name for p in export_audit(a, tmp_path / "o")}
    assert "lesion_review_status.csv" in names
    assert '"lesion_evidence"' in (tmp_path / "o" / "trial_audit.json").read_text()


def test_no_seg_trial_output_unchanged_shape(tmp_path):
    from voxeltrace.trial.export import export_audit

    a = run_trial_audit(_trial(tmp_path, seg=False), "percist-1.0")
    export_audit(a, tmp_path / "o")
    text = (tmp_path / "o" / "trial_audit.json").read_text()
    assert "lesion_evidence" not in text and "lesion_target_status" not in text
    c = next(c for c in a.pairs[0].checks if c.rule_id == "PERCIST-BASELINE-MEASURABLE")
    assert "MISSING_REQUIRED_TAG" in {r.code for r in c.reasons}  # historical reason kept


def test_legacy_policy_only_for_synthetic_trials(tmp_path):
    with pytest.raises(ValueError, match="synthetic"):
        discover_trial(_trial(tmp_path / "real", policy="LEGACY_UNREVIEWED_ALLOWED"))
    root = _trial(tmp_path / "syn", policy="LEGACY_UNREVIEWED_ALLOWED", synthetic=True)
    a = run_trial_audit(root, "percist-1.0")
    rows = [r for r in a.lesion_evidence if r["used_as_target"]]
    assert rows and all("UNREVIEWED_LEGACY_POLICY" in r["evidence_label"] for r in rows)
    assert json.dumps(a.lesion_evidence_policy) == '"LEGACY_UNREVIEWED_ALLOWED"'


def test_context_renders_and_build_review_requires_human_input(ai_scan):
    from voxeltrace.trial.lesion_review_context import build_review, load_lesion_context

    ctx = load_lesion_context(ai_scan, "S1", "baseline", ([], {"status": "NO_FILE"}))
    (it,) = ctx["items"]
    assert ctx["quant_eligible"] and it["png"][:4] == b"\x89PNG" and it["suvmax_kji"] is not None
    assert it["evidence"].review_status == "UNREVIEWED"
    with pytest.raises(ValueError):
        build_review(
            it["evidence"], reviewer_id=" ", reviewer_role="PET_PHYSICIST", decision="ACCEPT"
        )
    with pytest.raises(ValueError):
        build_review(
            it["evidence"], reviewer_id="r", reviewer_role="PET_PHYSICIST", decision="ADJUST"
        )
    rec = build_review(
        it["evidence"], reviewer_id="r", reviewer_role="PET_PHYSICIST", decision="ACCEPT"
    )
    assert rec.source_type == "AI_GENERATED" and rec.created_via == "HUMAN_UI" and not rec.simulated


def test_cli_lesion_qc_and_review(ai_scan, tmp_path):
    from voxeltrace.cli import main as cli

    out, log = tmp_path / "qc", tmp_path / "lr.jsonl"
    assert (
        cli(
            [
                "lesion-qc",
                str(ai_scan),
                "--subject",
                "S1",
                "--timepoint",
                "baseline",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    data = json.loads((out / "lesion_candidates.json").read_text())
    seg = data["segments"][0]
    assert (
        seg["review_status"] == "UNREVIEWED"
        and (out / seg["qc_image"]).exists()
        and not log.exists()
    )
    base = ["lesion-review", str(ai_scan), "--subject", "S1", "--timepoint", "baseline", "--log", str(log),
            "--reviewer", "me", "--role", "PET_PHYSICIST", "--segment", "1", "--decision", "ACCEPT"]  # fmt: skip
    assert cli(base) == 2 and not log.exists()  # no --confirm
    assert cli([*base, "--expect-mask-sha256", "0" * 64, "--confirm"]) == 2  # stale view refused
    assert cli([*base, "--expect-mask-sha256", seg["mask_sha256"], "--confirm"]) == 0
    reviews = load_reviews(log)
    assert reviews[1]["status"] == "OK" and reviews[0][0].created_via == "HUMAN_CLI"
    tp = tp_of(ai_scan, reviews=reviews)
    assert tp.lesion_target_status == "REVIEWED_TARGET"


def test_lesion_review_page_smoke(tmp_path):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    root = _trial(tmp_path)
    at = AppTest.from_file(
        str(
            __import__("pathlib").Path(__file__).resolve().parents[1]
            / "app"
            / "pages"
            / "6_Lesion_Review.py"
        ),
        default_timeout=120,
    )
    at.run()
    at.sidebar.text_input[0].set_value(str(root)).run()
    assert not at.exception
    at.selectbox[0].set_value("S1 / baseline").run()
    at.selectbox[1].set_value("1").run()
    assert not at.exception
    button = at.button[0]
    assert button.disabled  # nothing chosen, no reviewer: cannot record
    assert not (root / "lesion_review.jsonl").exists()


def test_accepted_organ_segment_is_never_a_target(tmp_path):
    d = make_scan(tmp_path / "o", ai=True)
    seg = next((d / "SEG").glob("*.dcm"))
    ds = pydicom.dcmread(seg)
    ds.SegmentSequence[0].SegmentedPropertyCategoryCodeSequence[
        0
    ].CodeMeaning = "Anatomical Structure"
    ds.save_as(seg)
    cand = tp_of(d).lesion_evidence[0].candidate
    assert cand.target_eligible is False and cand.segment_category == "Anatomical Structure"
    tp = tp_of(d, reviews=load_reviews(log_with(tmp_path, review_for(cand)), allow_simulated=True))
    (ev,) = tp.lesion_evidence
    assert ev.review_status == "ACCEPTED" and not ev.used_as_target and tp.lesion_suvpeak is None
