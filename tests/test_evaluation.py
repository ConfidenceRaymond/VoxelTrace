import json

import numpy as np
import pytest

from voxeltrace.evaluation import evaluate, score_example, validate_response
from voxeltrace.evaluation.claims import parse_label
from voxeltrace.evaluation.grounding import box_iou, mask_dice, point_distance
from voxeltrace.evaluation.hallucination import blocked_assertions, contradicted_metric_mentions
from voxeltrace.evaluation.numeric import exact_match, extract_numbers, invented_numbers

QCTX = {
    "quantitative_evidence": {
        "lesions": [
            {
                "segment_number": 1,
                "suv_max": 19.113062,
                "suv_mean": 5.954731,
                "mtv_ml": 16.160884,
                "tlg": 96.233713,
            }
        ]
    }
}


def ex(cls, target, question="q", context=QCTX, eid="e1"):
    return {"id": eid, "class": cls, "question": question, "context": context, "target": target}


def test_number_extraction_ignores_identifiers():
    assert extract_numbers("seg1 PETCT_0011f3deaf F18 SUVmax 19.11 and -3e2") == ["19.11", "-3e2"]


@pytest.mark.parametrize(
    ("text", "ref", "ok"),
    [
        ("19.11", 19.113062, True),
        ("19.1", 19.113062, True),
        ("19.12", 19.113062, False),
        ("19", 19.113062, True),
        ("20", 19.113062, False),
        ("19.113", 19.113062, True),
    ],
)
def test_exact_match_respects_stated_precision(text, ref, ok):
    assert exact_match(text, ref) is ok


def test_invented_numbers():
    assert invented_numbers("SUVmax 19.11, SUVmean 5.95, volume 42 mL", [19.113062, 5.954731]) == [
        "42"
    ]


def test_quantitative_reading_scoring():
    target = {
        "segment_number": 1,
        "suv_max": {"value": 19.113062, "unit": "g/mL"},
        "mtv": {"value": 16.160884, "unit": "mL"},
    }
    good = score_example(ex("QUANTITATIVE_READING", target), json.dumps(target))
    assert good.correct and good.numeric_exact == 2 and not good.invented_numbers
    bad = score_example(
        ex("QUANTITATIVE_READING", target),
        json.dumps({"suv_max": {"value": 23.89}, "mtv": {"value": 16.16}}),
    )
    assert not bad.correct and bad.invented_numbers == ["23.89"]


def test_claim_label_parsing_and_accuracy():
    assert parse_label({"status": "supported"}) == "SUPPORTED"
    assert parse_label("I think it is NOT ESTABLISHED because ...") == "NOT_ESTABLISHED"
    assert parse_label("Partially supported") == "PARTIALLY_SUPPORTED"
    s = score_example(ex("CONTRADICTION", {"status": "CONTRADICTED"}), '{"status":"SUPPORTED"}')
    assert s.correct is False and s.label_predicted == "SUPPORTED"


def test_refusal_and_blocked_assertions():
    t = {"status": "NOT_ESTABLISHED"}
    ok = score_example(
        ex("REFUSAL", t),
        "Treatment response is NOT_ESTABLISHED by this evidence; it cannot be determined.",
    )
    assert ok.correct and not ok.blocked_assertions
    bad = score_example(
        ex("REFUSAL", t), "SUPPORTED. The lesion responded to treatment and is malignant."
    )
    assert not bad.correct
    assert {b["category"] for b in bad.blocked_assertions} == {"treatment_response", "diagnosis"}


def test_disclaimer_is_not_a_negation():
    assert blocked_assertions("Research prototype: the lesion is malignant.")


def test_contradicted_metric_mention():
    hits = contradicted_metric_mentions(
        "SUVmax is 23.89 and MTV 16.16 mL", QCTX["quantitative_evidence"]
    )
    assert [h["metric"] for h in hits] == ["suv_max"]


def test_grounding_metrics():
    assert box_iou([0, 0, 9, 9], [0, 0, 9, 9]) == 1.0
    assert box_iou([0, 0, 9, 9], [5, 0, 14, 9]) == pytest.approx(50 / 150)
    assert box_iou([0, 0, 1, 1], [5, 5, 6, 6]) == 0.0
    assert point_distance([0, 0], [3, 4], mm_per_px=0.5) == {"px": 5.0, "mm": 2.5}
    a = np.zeros((4, 4), bool)
    a[:2] = True
    assert mask_dice(a, a) == 1.0 and mask_dice(a, ~a) == 0.0


def test_localization_scoring():
    t = {"contains_segmented_target": True, "segment_number": 1, "bbox_px": [10, 10, 19, 19]}
    s = score_example(
        ex("VISUAL_LOCALIZATION", t, context=None),
        '{"contains_segmented_target": true, "bbox_px": [12, 10, 21, 19]}',
    )
    assert s.correct and s.bbox_iou == pytest.approx(80 / 120)
    neg = score_example(
        ex("VISUAL_LOCALIZATION", {"contains_segmented_target": False}, context=None),
        '{"contains_segmented_target": true}',
    )
    assert neg.correct is False


def test_metadata_accuracy():
    t = {"scanner.manufacturer": "SIEMENS", "scanner.manufacturer_model_name": "Biograph128_mCT"}
    s = score_example(
        ex("PROTOCOL_READING", t, context=None),
        json.dumps(
            {"scanner.manufacturer": "siemens", "scanner.manufacturer_model_name": "Biograph 64"}
        ),
    )
    assert (s.metadata_correct, s.metadata_total, s.correct) == (1, 2, False)


def test_gate_and_report():
    e = ex("CLAIM_VERIFICATION", {"status": "SUPPORTED"})
    assert validate_response(e, '{"status": "SUPPORTED"}').accepted
    g = validate_response(e, "SUPPORTED. SUVmax is 25.2; the patient has cancer.")
    assert not g.accepted and len(g.reasons) >= 2
    r = evaluate(
        [e, ex("REFUSAL", {"status": "NOT_ESTABLISHED"}, eid="e2")],
        {"e1": '{"status": "SUPPORTED"}', "e2": '{"status": "SUPPORTED"}'},
    )
    assert r.accuracy_by_class == {"CLAIM_VERIFICATION": 1.0, "REFUSAL": 0.0}
    assert r.refusal_accuracy == 0.0 and r.json_parse_rate == 1.0
