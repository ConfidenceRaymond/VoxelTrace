import json

import pytest

from voxeltrace.evaluation.dev_v2 import (
    CLAIM_LABELS,
    LABEL_DEFS,
    reframe,
    score_v2,
    semantic_correct_v1,
)
from voxeltrace.visualization.render import PlaneMapping

Q = {
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
P = {
    "scanner": {"manufacturer": {"value": "SIEMENS", "status": "PRESENT"}},
    "reconstruction": {"convolution_kernel": {"value": ["XYZ Gauss2.00"], "status": "PRESENT"}},
}
PROV = {
    "target_sources": [{"source_ref": "claims-1:value-suv_max-seg1"}],
    "subject_pseudonym": "S",
    "image_sha256": {},
}


def rec(cls, target, context=None, images=(), q="Q?"):
    return {
        "id": f"S-{cls.lower()}-001",
        "class": cls,
        "question": q,
        "context": context,
        "images": list(images),
        "target": target,
        "provenance": PROV,
        "split": "DEVELOPMENT_ONLY",
        "ground_truth_level": 5,
    }


CASES = [
    rec(
        "CLAIM_VERIFICATION",
        {"status": "SUPPORTED", "claim_type": "QUANTITATIVE_VALUE"},
        {"quantitative_evidence": Q},
    ),
    rec(
        "CONTRADICTION",
        {"status": "CONTRADICTED", "claim_type": "QUANTITATIVE_VALUE"},
        {"quantitative_evidence": Q},
    ),
    rec(
        "QUANTITATIVE_READING",
        {"segment_number": 1, "suv_max": {"value": 19.113062, "unit": "g/mL"}},
        {"quantitative_evidence": Q},
        ["images/a.png"],
    ),
    rec(
        "MISSING_DATA",
        {
            "answer": "INSUFFICIENT_INFORMATION",
            "field": "reconstruction.reconstruction_diameter_mm",
        },
        {"protocol_evidence": P},
    ),
    rec(
        "PROTOCOL_COMPARABILITY",
        {
            "category": "NOT_COMPARABLE",
            "blocking_differences": ["post_filter"],
            "blocking_unknowns": [],
            "warnings": [],
        },
        {"scan_a": P, "scan_b": P},
    ),
    rec(
        "VISUAL_LOCALIZATION",
        {
            "contains_segmented_target": True,
            "segment_number": 1,
            "slice_k": 3,
            "bbox_px": [10, 10, 19, 19],
        },
        None,
        ["images/b.png"],
    ),
    rec(
        "VISUAL_QUANTITATIVE",
        {
            "suvmax_px": [7, 7],
            "suvmax_voxel_kji": [3, 1, 1],
            "suv_max": {"value": 19.113062, "unit": "g/mL"},
        },
        {"quantitative_evidence": Q},
        ["images/c.png"],
    ),
]


@pytest.mark.parametrize("r", CASES, ids=lambda r: r["class"])
def test_reframe_preserves_everything_but_framing(r):
    v2 = reframe(r)
    assert v2["parent_id"] == r["id"] and v2["images"] == r["images"]
    assert v2["target_v1"] == r["target"] and v2["provenance"] == r["provenance"]
    if r["class"] != "PROTOCOL_COMPARABILITY":
        assert v2["context"] == r["context"]
    else:  # documented exception: deterministic verdict supplied as evidence
        assert v2["context"]["deterministic_comparability"]["category"] == "NOT_COMPARABLE"
        assert "authoritative" in v2["question"]
    assert "untrusted data" in v2["question"] and "Required response schema" in v2["question"]


def test_v2_targets_lossless():
    by = {r["class"]: reframe(r)["target"] for r in CASES}
    assert by["CLAIM_VERIFICATION"] == {"label": "SUPPORTED"}
    assert by["QUANTITATIVE_READING"] == {"status": "REPORTED", "values": {"suv_max": 19.113062}}
    assert by["MISSING_DATA"]["status"] == "INSUFFICIENT_INFORMATION"
    assert by["PROTOCOL_COMPARABILITY"]["pair_verdict"] == "NOT_COMPARABLE"
    assert by["VISUAL_LOCALIZATION"]["bbox_px"] == [10, 10, 19, 19]


def test_no_answer_leak_in_question_outside_documented_exception():
    for r in CASES:
        v2 = reframe(r)
        q = v2["question"]
        if v2["family"] == "claim":  # labels appear only in the fixed definitions/schema
            for lab in CLAIM_LABELS:
                assert q.count(lab) == (
                    LABEL_DEFS.count(lab) + q.split("Required response schema")[1].count(lab)
                )
        if v2["family"] in ("value", "point"):
            assert "19.113062" not in q
        if v2["family"] == "localization":
            assert "10, 10, 19, 19" not in q


def test_evidence_catalog():
    v2 = reframe(CASES[0])
    ids = v2["evidence_ids_valid"]
    assert "quant.seg1.suv_max" in ids and "claim.value-suv_max-seg1" in ids


def test_score_v2_claim_and_ids_and_vocabulary():
    v2 = reframe(CASES[1])
    good = score_v2(
        v2,
        json.dumps(
            {
                "label": "CONTRADICTED",
                "answer": "measured 19.113",
                "evidence_ids": ["quant.seg1.suv_max"],
                "limitations": [],
            }
        ),
    )
    assert good["correct"] and good["schema_ok"] and not good["evidence_ids_invalid"]
    bad = score_v2(
        v2,
        json.dumps(
            {"label": "FALSE", "answer": "", "evidence_ids": ["made.up"], "limitations": []}
        ),
    )
    assert not bad["correct"] and bad["evidence_ids_invalid"] == ["made.up"]
    assert not bad["label_in_vocabulary"]


def test_score_v2_value_point_localization_pair():
    q = reframe(CASES[2])
    s = score_v2(
        q, json.dumps({"status": "REPORTED", "values": {"suv_max": 19.113062}, "evidence_ids": []})
    )
    assert s["correct"] and s["numeric_exact"] == 1
    s2 = score_v2(
        q, json.dumps({"status": "REPORTED", "values": {"suv_max": 500}, "evidence_ids": []})
    )
    assert not s2["correct"] and "500" in s2["invented_numbers"]
    m = score_v2(
        reframe(CASES[3]),
        json.dumps(
            {
                "status": "INSUFFICIENT_INFORMATION",
                "values": {"reconstruction.reconstruction_diameter_mm": None},
                "evidence_ids": [],
            }
        ),
    )
    assert m["correct"]
    pair = reframe(CASES[4])
    assert score_v2(
        pair,
        json.dumps(
            {
                "pair_verdict": "NOT_COMPARABLE",
                "blocking_differences": ["post_filter"],
                "evidence_ids": [],
            }
        ),
    )["correct"]
    assert not score_v2(
        pair,
        json.dumps({"pair_verdict": "COMPARABLE", "blocking_differences": [], "evidence_ids": []}),
    )["correct"]
    loc = reframe(CASES[5])
    assert score_v2(
        loc, json.dumps({"contains_segmented_target": True, "bbox_px": [10, 10, 19, 19]})
    )["correct"]
    pt = reframe(CASES[6])
    mp = PlaneMapping(0, 0, 5, 5, 6, 6)
    hit = score_v2(pt, json.dumps({"suvmax_px": [8, 9], "suv_max": 19.113062}), mapping=mp)
    assert hit["point_hit_voxel"] and hit["correct"]
    miss = score_v2(pt, json.dumps({"suvmax_px": [13, 7], "suv_max": 19.113062}), mapping=mp)
    assert miss["point_hit_voxel"] is False and not miss["correct"]


def test_semantic_v1_definition():
    r = CASES[1]
    assert semantic_correct_v1(r, "This is CONTRADICTED.", {})
    assert not semantic_correct_v1(r, '{"supported": false}', {})
