import pytest
from pydantic import ValidationError

from voxeltrace.training.schema import SOURCE_LEVEL, GTValue, TrainingExample, gt


def test_hierarchy_levels():
    assert [
        SOURCE_LEVEL[k]
        for k in (
            "PRIMARY_IMAGE",
            "PRIMARY_DICOM_METADATA",
            "REFERENCE_SEGMENTATION",
            "DETERMINISTIC_DERIVATION",
            "RULE_DERIVATION",
            "EXPERT_ANNOTATION",
            "MODEL_GENERATED",
        )
    ] == [1, 2, 3, 4, 5, 6, 7]


def test_model_generated_never_ground_truth():
    with pytest.raises(ValidationError, match="MODEL_GENERATED"):
        GTValue(
            value=1,
            source_type="MODEL_GENERATED",
            source_ref="llm",
            derivation="none",
            validation_status="VALIDATED",
        )


def test_expert_annotation_requires_review():
    with pytest.raises(ValidationError):
        gt("text", "EXPERT_ANNOTATION", "r1", "human_review", "VALIDATED")
    ok = gt("text", "EXPERT_ANNOTATION", "r1", "human_review", "REVIEWED")
    assert ok.usable_as_target and ok.level == 6
    with pytest.raises(ValidationError):
        gt(1, "DETERMINISTIC_DERIVATION", "x", "lesion_metric", "REVIEWED")


@pytest.mark.parametrize(
    ("status", "usable"),
    [("VALIDATED", True), ("VALIDATED_ABSENT", True), ("UNVALIDATED", False), ("REJECTED", False)],
)
def test_usable_as_target(status, usable):
    assert (
        gt(1.0, "DETERMINISTIC_DERIVATION", "x", "lesion_metric", status).usable_as_target is usable
    )


def _example(sources, level):
    return TrainingExample(
        example_id="e",
        example_class="QUANTITATIVE_READING",
        split="DEVELOPMENT_ONLY",
        subject_pseudonym="S",
        study_pseudonym="T",
        question="q",
        target={"a": 1},
        target_sources=sources,
        ground_truth_level=level,
    )


def test_example_rejects_unvalidated_or_missing_sources():
    with pytest.raises(ValidationError, match="not usable"):
        _example(
            [gt(1, "PRIMARY_DICOM_METADATA", "x", "dicom_free_text_pattern", "UNVALIDATED")], 2
        )
    with pytest.raises(ValidationError, match="at least one"):
        _example([], 4)


def test_example_level_is_max_source_level():
    src = [
        gt(1, "PRIMARY_DICOM_METADATA", "a", "dicom_attribute"),
        gt(2, "RULE_DERIVATION", "b", "rule_engine"),
    ]
    assert _example(src, 5).ground_truth_level == 5
    with pytest.raises(ValidationError, match="highest source level"):
        _example(src, 2)
