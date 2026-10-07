"""Deterministic evaluation of model responses against VoxelTrace ground truth."""

from voxeltrace.evaluation.metrics import ExampleScore, parse_response, score_example
from voxeltrace.evaluation.runner import (
    EvaluationReport,
    GateResult,
    evaluate,
    load_examples,
    validate_response,
)

__all__ = [
    "EvaluationReport",
    "ExampleScore",
    "GateResult",
    "evaluate",
    "load_examples",
    "parse_response",
    "score_example",
    "validate_response",
]
