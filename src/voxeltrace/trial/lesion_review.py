"""Human review gate for lesion / target segmentations (schema voxeltrace.lesion-review/1).

No supplied mask (DICOM SEG, NIfTI, RTSTRUCT-derived, AI-generated or external) is treated as
quantitative ground truth by default. Under the default policy REVIEW_REQUIRED a segment can
serve as a PERCIST baseline target only after a named human ACCEPTED that exact mask
(mask_sha256). Review status and source type are separate facts: an AI_GENERATED mask that a
human accepted stays AI_GENERATED with review status ACCEPTED.

States:   UNREVIEWED, ACCEPTED, ADJUSTED (reserved: no safe voxel-editing workflow exists yet,
          so it is never produced), REJECTED, OUTDATED (mask changed since review),
          INVALID (wrong series, simulated in production, tampered log, malformed record)
Decisions: ACCEPT, REJECT, REJECT_AND_REPLACE_REQUIRED (instead of a fake ADJUST)
Sources:   HUMAN_MANUAL, HUMAN_CORRECTED, AI_GENERATED, ALGORITHM_GENERATED, UNKNOWN

Storage: JSON lines, each record chained to the previous record's hash; any edit, deletion or
reordering makes the whole log TAMPERED and every review INVALID. Source files are never
modified. Policy LEGACY_UNREVIEWED_ALLOWED reproduces the historical behaviour (first non-empty
segment, unreviewed) for SYNTHETIC test trials only and is labelled in every output.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, Field

from voxeltrace.ids import pseudonym

SCHEMA = "voxeltrace.lesion-review/1"
GENESIS = "0" * 64
Policy = Literal["REVIEW_REQUIRED", "LEGACY_UNREVIEWED_ALLOWED"]
SourceType = Literal[
    "HUMAN_MANUAL", "HUMAN_CORRECTED", "AI_GENERATED", "ALGORITHM_GENERATED", "UNKNOWN"
]
Status = Literal["UNREVIEWED", "ACCEPTED", "ADJUSTED", "REJECTED", "OUTDATED", "INVALID"]
Decision = Literal["ACCEPT", "REJECT", "REJECT_AND_REPLACE_REQUIRED"]
ReviewerRole = Literal[
    "PET_PHYSICIST",
    "NUCLEAR_MEDICINE_PHYSICIAN",
    "RADIOLOGIST",
    "IMAGING_CORE_LEAD",
    "TRIAL_QC_REVIEWER",
]
AI_TEXT = re.compile(
    r"\b(ai|deep|nnu-?net|neural|cnn|aimi|totalsegmentator|monai|unet|model)\b", re.I
)
HUMAN_CORR_TEXT = re.compile(r"corrected|edited|revised|refined", re.I)


def mask_sha256(mask: np.ndarray) -> str:
    m = np.asarray(mask).astype(bool)
    h = hashlib.sha256(str(m.shape).encode())
    h.update(np.packbits(m.ravel()).tobytes())
    return h.hexdigest()


def classify_source(series_description: str | None, algorithm_type: str | None,
                    algorithm_name: str | None) -> tuple[SourceType, str]:  # fmt: skip
    """Conservative source classification from SEG header facts (never upgraded by review)."""
    desc, alg, name = series_description or "", (algorithm_type or "").upper(), algorithm_name or ""
    if HUMAN_CORR_TEXT.search(desc) and re.search(
        r"radiologist|expert|reader|human|physician", desc, re.I
    ):
        return "HUMAN_CORRECTED", f"SeriesDescription {desc!r}"
    if alg == "MANUAL":
        return "HUMAN_MANUAL", "SegmentAlgorithmType MANUAL"
    if alg == "SEMIAUTOMATIC":
        return (
            "ALGORITHM_GENERATED",
            "SegmentAlgorithmType SEMIAUTOMATIC (human-initiated algorithm)",
        )
    if alg == "AUTOMATIC":
        if AI_TEXT.search(desc) or AI_TEXT.search(name):
            return "AI_GENERATED", f"SegmentAlgorithmType AUTOMATIC; {desc or name!r}"
        return "ALGORITHM_GENERATED", f"SegmentAlgorithmType AUTOMATIC; algorithm {name!r}"
    if AI_TEXT.search(desc):
        return "AI_GENERATED", f"SeriesDescription {desc!r}"
    return "UNKNOWN", "no algorithm type or descriptive provenance"


class LesionCandidate(BaseModel):
    """One supplied segment on one scan, as VoxelTrace measured it (mask on the PET grid)."""

    subject: str
    timepoint: str
    study_hash: str
    pet_series_hash: str
    seg_series_hash: str
    seg_file_sha256: str
    segment_number: int
    segment_label: str | None = None
    mask_sha256: str
    source_type: SourceType
    source_provenance: dict[str, Any] = Field(default_factory=dict)
    segment_category: str | None = None
    segment_type: str | None = None
    target_eligible: bool = Field(
        default=True, description="False for anatomical-structure segments (e.g. an organ mask)"
    )
    voxel_count: int = 0
    volume_ml: float | None = None
    suv_max: float | None = None
    suv_mean: float | None = None
    suv_peak: float | None = None
    mtv_ml: float | None = None
    tlg: float | None = None
    bbox_kji: list[list[int]] | None = None
    centroid_kji: list[float] | None = None


class LesionReview(BaseModel):
    schema_version: Literal["voxeltrace.lesion-review/1"] = SCHEMA
    subject: str = Field(min_length=1)
    timepoint: str = Field(min_length=1)
    study_hash: str
    pet_series_hash: str
    seg_series_hash: str
    seg_file_sha256: str
    segment_number: int
    segment_label: str | None = None
    mask_sha256: str = Field(min_length=64, max_length=64)
    source_type: SourceType
    source_provenance: dict[str, Any] = Field(default_factory=dict)
    reviewer_id: str = Field(min_length=1)
    reviewer_role: ReviewerRole
    decision: Decision
    timestamp: datetime
    software_version: str
    git_commit: str | None = None
    note: str = ""
    created_via: Literal["HUMAN_UI", "HUMAN_CLI"]
    simulated: bool = False


class LesionEvidence(BaseModel):
    """Report row: a candidate with its review status (and the record that decided it)."""

    candidate: LesionCandidate
    review_status: Status
    reviewer: str | None = None
    decision: str | None = None
    reasons: list[str] = Field(default_factory=list)
    used_as_target: bool = False
    evidence_label: str = ""


def _line_hash(prev: str, rec_json: str) -> str:
    return hashlib.sha256((prev + rec_json).encode()).hexdigest()


def verify_log(path: str | Path | None) -> dict[str, Any]:
    if path is None or not Path(path).exists():
        return {"status": "NO_FILE", "head": GENESIS, "records": 0}
    prev, n = GENESIS, 0
    for i, line in enumerate(Path(path).read_text().splitlines()):
        try:
            obj = json.loads(line)
            rec = LesionReview.model_validate(obj["record"]).model_dump_json()
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "INVALID",
                "head": prev,
                "records": n,
                "line": i + 1,
                "error": str(exc)[:200],
            }
        if obj.get("prev") != prev or obj.get("hash") != _line_hash(prev, rec):
            return {"status": "TAMPERED", "head": prev, "records": n, "line": i + 1}
        prev, n = obj["hash"], n + 1
    return {"status": "OK", "head": prev, "records": n}


def append_review(path: str | Path, review: LesionReview, *, confirmed: bool) -> str:
    """Append ONE human lesion review (explicit confirmation required). Never rewrites lines."""
    if not confirmed:
        raise PermissionError("lesion review requires explicit human confirmation")
    chain = verify_log(path)
    if chain["status"] not in ("OK", "NO_FILE"):
        raise ValueError(f"lesion review log is {chain['status']}; refusing to append")
    rec = review.model_dump_json()
    h = _line_hash(chain["head"], rec)
    with Path(path).open("a") as fh:
        fh.write(json.dumps({"record": json.loads(rec), "prev": chain["head"], "hash": h}) + "\n")
    return h


def load_reviews(
    path: str | Path | None, *, allow_simulated: bool = False
) -> tuple[list[LesionReview], dict]:
    chain = verify_log(path)
    if chain["status"] != "OK":
        return [], chain
    recs = [
        LesionReview.model_validate(json.loads(x)["record"])
        for x in Path(path).read_text().splitlines()
    ]  # type: ignore[arg-type]
    chain["simulated_rejected"] = sum(r.simulated for r in recs) if not allow_simulated else 0
    return [r for r in recs if allow_simulated or not r.simulated], chain


def resolve(candidate: LesionCandidate, reviews: list[LesionReview], chain: dict) -> LesionEvidence:
    """Status of one candidate given the (already chain-verified) review records."""
    if chain.get("status") in ("TAMPERED", "INVALID"):
        return LesionEvidence(
            candidate=candidate, review_status="INVALID", reasons=[f"REVIEW_LOG_{chain['status']}"]
        )
    mine = [r for r in reviews if (r.subject, r.timepoint, r.segment_number, r.seg_series_hash)
            == (candidate.subject, candidate.timepoint, candidate.segment_number, candidate.seg_series_hash)]  # fmt: skip
    if not mine:
        reasons = ["SIMULATED_REVIEW_REJECTED"] if chain.get("simulated_rejected") else []
        return LesionEvidence(candidate=candidate, review_status="UNREVIEWED", reasons=reasons)
    r = mine[-1]  # latest record wins
    if r.pet_series_hash != candidate.pet_series_hash or r.study_hash != candidate.study_hash:
        return LesionEvidence(candidate=candidate, review_status="INVALID", reviewer=r.reviewer_id,
                              decision=r.decision, reasons=["REVIEW_FOR_DIFFERENT_SERIES"])  # fmt: skip
    if r.source_type != candidate.source_type:
        return LesionEvidence(candidate=candidate, review_status="INVALID", reviewer=r.reviewer_id,
                              decision=r.decision, reasons=["SOURCE_TYPE_MISMATCH"])  # fmt: skip
    if r.mask_sha256 != candidate.mask_sha256 or r.seg_file_sha256 != candidate.seg_file_sha256:
        return LesionEvidence(candidate=candidate, review_status="OUTDATED", reviewer=r.reviewer_id,
                              decision=r.decision, reasons=["MASK_CHANGED_SINCE_REVIEW"])  # fmt: skip
    status: Status = "ACCEPTED" if r.decision == "ACCEPT" else "REJECTED"
    reasons = ["REPLACEMENT_MASK_REQUIRED"] if r.decision == "REJECT_AND_REPLACE_REQUIRED" else []
    return LesionEvidence(candidate=candidate, review_status=status, reviewer=f"{r.reviewer_id} ({r.reviewer_role})",
                          decision=r.decision, reasons=reasons)  # fmt: skip


def choose_target(
    evidence: list[LesionEvidence], policy: Policy
) -> tuple[LesionEvidence | None, str]:
    """PERCIST baseline target. REVIEW_REQUIRED: the ACCEPTED segment with the highest SUVpeak.
    LEGACY_UNREVIEWED_ALLOWED: historical behaviour (first non-empty segment), labelled."""
    if not evidence:
        return None, "NO_LESION_SUPPLIED"
    if policy == "LEGACY_UNREVIEWED_ALLOWED":
        nonempty = [e for e in evidence if e.candidate.voxel_count > 0]
        if nonempty:
            t = nonempty[0]
            t.used_as_target = True
            t.evidence_label = f"UNREVIEWED_LEGACY_POLICY ({t.review_status})"
            return t, "LEGACY_UNREVIEWED_TARGET"
        return None, "NO_NONEMPTY_LESION"
    ok = [e for e in evidence if e.review_status == "ACCEPTED" and e.candidate.suv_peak is not None
          and e.candidate.target_eligible]  # fmt: skip
    if not ok:
        statuses = sorted({e.review_status for e in evidence})
        return None, "LESION_REVIEW_REQUIRED:" + ",".join(statuses)
    t = max(ok, key=lambda e: e.candidate.suv_peak or 0.0)
    t.used_as_target = True
    t.evidence_label = f"HUMAN_REVIEWED ({t.candidate.source_type} accepted)"
    return t, "REVIEWED_TARGET"


NON_TARGET_CATEGORIES = re.compile(r"anatomical structure|body substance|tissue", re.I)


def target_eligible(category: str | None) -> bool:
    """Organ / tissue segments (DICOM SegmentedPropertyCategory) are never lesion targets."""
    return not (category and NON_TARGET_CATEGORIES.search(category))


def hashes(study_uid: str | None, pet_uid: str | None, seg_uid: str | None) -> dict[str, str]:
    return {"study_hash": pseudonym(study_uid, "study"), "pet_series_hash": pseudonym(pet_uid, "pet"),
            "seg_series_hash": pseudonym(seg_uid, "seg")}  # fmt: skip
