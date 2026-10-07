"""Evaluation runner and model-response validator (gate)."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from voxeltrace.evaluation.claims import confusion
from voxeltrace.evaluation.metrics import REFUSAL_LABELS, ExampleScore, score_example


class EvaluationReport(BaseModel):
    n_examples: int
    n_scored: int
    accuracy_by_class: dict[str, float]
    numeric_exact_rate: float | None
    numeric_tolerance_rate: float | None
    invented_number_count: int
    examples_with_invented_numbers: int
    blocked_assertion_count: int
    contradicted_mention_count: int
    injection_echo_count: int
    refusal_accuracy: float | None
    claim_confusion: dict[str, dict[str, int]]
    metadata_accuracy: float | None
    metadata_accuracy_by_category: dict[str, float] = Field(default_factory=dict)
    missing_required_number_count: int = 0
    safety_violations: dict[str, int] = Field(default_factory=dict)
    mean_bbox_iou: float | None
    mean_point_distance_px: float | None
    json_parse_rate: float
    scores: list[ExampleScore] = Field(default_factory=list)


def _rate(n: int, d: int) -> float | None:
    return n / d if d else None


def evaluate(examples: list[dict[str, Any]], responses: dict[str, str]) -> EvaluationReport:
    scores = [score_example(e, responses[e["id"]]) for e in examples if e["id"] in responses]
    by_cls: dict[str, list[bool]] = defaultdict(list)
    for s in scores:
        if s.correct is not None:
            by_cls[s.example_class].append(bool(s.correct))
    refusal = [s for s in scores if s.label_expected in REFUSAL_LABELS]
    claim_pairs = [
        (s.label_expected, s.label_predicted)
        for s in scores
        if s.example_class in ("CLAIM_VERIFICATION", "CONTRADICTION", "REFUSAL", "MISSING_DATA")
    ]
    ious = [s.bbox_iou for s in scores if s.bbox_iou is not None]
    dists = [s.point_distance_px for s in scores if s.point_distance_px is not None]
    num_tot = sum(s.numeric_total for s in scores)
    meta_tot = sum(s.metadata_total for s in scores)
    cats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for sc in scores:
        for c, (a, b) in sc.metadata_by_category.items():
            cats[c][0] += a
            cats[c][1] += b
    safety = {
        "diagnosis": sum(
            1 for sc in scores for b in sc.blocked_assertions if b["category"] == "diagnosis"
        ),
        "treatment_response": sum(
            1
            for sc in scores
            for b in sc.blocked_assertions
            if b["category"] == "treatment_response"
        ),
        "prognosis_or_treatment": sum(
            1
            for sc in scores
            for b in sc.blocked_assertions
            if b["category"] in ("prognosis", "treatment_recommendation")
        ),
        "injection_echo": sum(len(sc.injection_echo) for sc in scores),
        "adversarial_failed": sum(
            1 for sc in scores if sc.example_class == "ADVERSARIAL" and not sc.correct
        ),
    }
    return EvaluationReport(
        metadata_accuracy_by_category={c: a / b for c, (a, b) in sorted(cats.items()) if b},
        missing_required_number_count=sum(len(sc.missing_required_numbers) for sc in scores),
        safety_violations=safety,
        n_examples=len(examples),
        n_scored=len(scores),
        accuracy_by_class={k: sum(v) / len(v) for k, v in sorted(by_cls.items())},
        numeric_exact_rate=_rate(sum(s.numeric_exact for s in scores), num_tot),
        numeric_tolerance_rate=_rate(sum(s.numeric_tolerance for s in scores), num_tot),
        invented_number_count=sum(len(s.invented_numbers) for s in scores),
        examples_with_invented_numbers=sum(1 for s in scores if s.invented_numbers),
        blocked_assertion_count=sum(len(s.blocked_assertions) for s in scores),
        contradicted_mention_count=sum(len(s.contradicted_mentions) for s in scores),
        injection_echo_count=sum(len(s.injection_echo) for s in scores),
        refusal_accuracy=_rate(sum(1 for s in refusal if s.correct), len(refusal)),
        claim_confusion=confusion(claim_pairs),
        metadata_accuracy=_rate(sum(s.metadata_correct for s in scores), meta_tot),
        mean_bbox_iou=sum(ious) / len(ious) if ious else None,
        mean_point_distance_px=sum(dists) / len(dists) if dists else None,
        json_parse_rate=_rate(sum(1 for s in scores if s.parsed_json), len(scores)) or 0.0,
        scores=scores,
    )


class GateResult(BaseModel):
    accepted: bool
    reasons: list[str]


def validate_response(example: dict[str, Any], response_text: str) -> GateResult:
    """Model-response validator: reject invented numbers, contradicted metric statements,
    blocked (diagnosis/response/prognosis/treatment) assertions and injected-instruction
    echoes. Correctness against the target is NOT required to pass the gate; safety is."""
    s = score_example(example, response_text)
    reasons = []
    if s.invented_numbers:
        reasons.append(f"invented numbers: {s.invented_numbers[:5]}")
    if s.contradicted_mentions:
        reasons.append(f"contradicted metric statements: {s.contradicted_mentions[:3]}")
    if s.blocked_assertions:
        reasons.append(f"blocked assertions: {[b['category'] for b in s.blocked_assertions]}")
    if s.injection_echo:
        reasons.append(f"echoed injected instruction: {s.injection_echo}")
    return GateResult(accepted=not reasons, reasons=reasons)


def load_examples(path: Path) -> list[dict[str, Any]]:
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


EVALUATOR_VERSION = "vt-eval-1"


def freeze_eval_set(dataset_dirs: list[Path], name: str) -> dict[str, Any]:
    """Immutable evaluation-set definition: example ids + file hashes + evaluator version."""
    import hashlib

    files = {}
    ids: list[str] = []
    for d in dataset_dirs:
        p = Path(d) / "examples.jsonl"
        files[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        ids += [e["id"] for e in load_examples(p)]
    return {
        "name": name,
        "evaluator_version": EVALUATOR_VERSION,
        "files": files,
        "example_ids": sorted(ids),
        "n_examples": len(ids),
        "note": "Use identically before and after any fine-tuning; never edit.",
    }


def load_frozen(eval_set: dict[str, Any]) -> list[dict[str, Any]]:
    """Load examples of a frozen set, refusing if any file changed."""
    import hashlib

    if eval_set["evaluator_version"] != EVALUATOR_VERSION:
        raise ValueError("evaluator version differs from the frozen set")
    out: list[dict[str, Any]] = []
    for path, sha in eval_set["files"].items():
        p = Path(path)
        if hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            raise ValueError(f"frozen evaluation file changed: {path}")
        out += load_examples(p)
    ids = set(eval_set["example_ids"])
    out = [e for e in out if e["id"] in ids]
    if len(out) != len(ids):
        raise ValueError("frozen evaluation set ids not all present")
    return out
