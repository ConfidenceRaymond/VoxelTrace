#!/usr/bin/env python3
"""Score the frozen dev_v3 baseline with evaluator vt-eval-2 and compare dev_v1/dev_v2/dev_v3.

Never edits any dataset or earlier responses. Writes to ../outputs/baseline_qwen3vl8b_dev_v3/:
  evaluation_v3.json        per-example scores (score_v2 correctness + vt-eval-2 safety)
  comparison.json           overall metrics, v2->v3 (104 paired) and v1->v2->v3 (70 paired)
  changes_v2_v3.csv         per-example change classes, dev_v2 -> dev_v3
  changes_v1_v2_v3.csv      per-example change classes, dev_v1 -> dev_v2 -> dev_v3

Correctness definitions:
  * strict (dev_v2 and dev_v3): ``dev_v2.score_v2`` on the version's own record. For value
    tasks this is values-only, i.e. definition-independent.
  * semantic (all three versions; identical to the dev_v1/dev_v2 paired analysis): the
    asserted label/verdict, target numbers at stated precision AND, for the two SUVpeak
    items, the definition text. dev_v3 no longer asks for that text, so those two items are
    listed separately.
Safety: vt-eval-2 for dev_v3. The dev_v2 column, re-scored with vt-eval-2, is for comparison
only; the official dev_v2 numbers stay vt-eval-1.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from voxeltrace.config import REPO_ROOT
from voxeltrace.evaluation.dev_v2 import CLAIM_LABELS, score_v2, semantic_correct_v1
from voxeltrace.evaluation.evaluator_v2 import (
    EVALUATOR_V2_VERSION,
    any_violation,
    load_frozen_v2,
    safety_v2,
)
from voxeltrace.evaluation.runner import load_frozen

OUT = REPO_ROOT.parent / "outputs"
B1, B2, B3 = (
    OUT / "baseline_qwen3vl8b",
    OUT / "baseline_qwen3vl8b_dev_v2",
    OUT / "baseline_qwen3vl8b_dev_v3",
)

_spec = importlib.util.spec_from_file_location(
    "compare_dev_v1_v2", REPO_ROOT / "scripts" / "compare_dev_v1_v2.py"
)
_cmp = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(_cmp)  # type: ignore[union-attr]
mapping_for, semantic_v2 = _cmp.mapping_for, _cmp.semantic_v2


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def rate(n: float, d: float) -> float | None:
    return round(n / d, 4) if d else None


def change(a: bool, b: bool) -> str:
    if a and b:
        return "UNCHANGED_CORRECT"
    if b:
        return "IMPROVED"
    if a:
        return "REGRESSED"
    return "UNCHANGED_WRONG"


def score(rec: dict, text: str) -> dict:
    s = score_v2(rec, text, mapping=mapping_for(rec) if rec["family"] == "point" else None)
    s["semantic_correct"] = semantic_v2(rec, text, s)
    s["safety"] = safety_v2(rec, text)
    s["violation"] = any_violation(s["safety"])
    s["perturbation"] = rec["provenance"].get("perturbation")
    s["v3_added"] = rec.get("v3_added", False)
    s["v3_variant"] = rec.get("v3_variant")
    s["v3_changes"] = rec.get("v3_changes", [])
    return s


def agg(ss: list[dict]) -> dict:
    claim = [s for s in ss if s["family"] == "claim"]
    val = [s for s in ss if s["family"] == "value"]
    pair = [s for s in ss if s["family"] == "pair"]
    loc = [s for s in ss if s["family"] == "localization"]
    pt = [s for s in ss if s["family"] == "point"]
    per_label: dict[str, list[bool]] = defaultdict(list)
    conf: dict[str, Counter] = defaultdict(Counter)
    for s in claim:
        per_label[s["label_expected"]].append(s["correct"])
        conf[s["label_expected"]][str(s["label_predicted"])] += 1
    refusal = [
        s
        for s in ss
        if s.get("label_expected") == "NOT_ESTABLISHED"
        or s.get("status_expected") == "INSUFFICIENT_INFORMATION"
    ]
    adv = [s for s in ss if s["class"] == "ADVERSARIAL"]
    ids_ret = sum(s["evidence_ids_returned"] for s in ss)
    ids_bad = sum(len(s["evidence_ids_invalid"]) for s in ss)
    ious = [s["bbox_iou"] for s in loc if s.get("bbox_iou") is not None]
    contra = per_label.get("CONTRADICTED", [])
    return {
        "n": len(ss),
        "structured_compliance (strict schema)": rate(sum(s["schema_ok"] for s in ss), len(ss)),
        "json_valid": rate(sum(s["json_ok"] for s in ss), len(ss)),
        "claim_label_accuracy": rate(sum(s["correct"] for s in claim), len(claim)),
        "claim_n": len(claim),
        "label_in_vocabulary": rate(sum(s["label_in_vocabulary"] for s in claim), len(claim)),
        "per_label_accuracy": {
            k: {"accuracy": rate(sum(v), len(v)), "n": len(v)} for k, v in sorted(per_label.items())
        },
        "CONTRADICTED_recall": {"recall": rate(sum(contra), len(contra)), "n": len(contra)},
        "confusion": {k: dict(v) for k, v in conf.items()},
        "pair_verdict_fidelity": {
            "accuracy": rate(sum(s["correct"] for s in pair), len(pair)),
            "blocking_differences_match": rate(
                sum(s.get("blocking_differences_match", False) for s in pair), len(pair)
            ),
            "n": len(pair),
            "kernel_changed": [
                (s["id"], s["pair_predicted"])
                for s in pair
                if s["perturbation"] == "kernel_changed"
            ],
        },
        "numeric_exactness": {
            "exact": rate(
                sum(s.get("numeric_exact", 0) for s in val),
                sum(s.get("numeric_total", 0) for s in val),
            ),
            "tolerance": rate(
                sum(s.get("numeric_tolerance", 0) for s in val),
                sum(s.get("numeric_total", 0) for s in val),
            ),
            "omitted": sum(s.get("numeric_omitted", 0) for s in val),
            "values": sum(s.get("numeric_total", 0) for s in val),
        },
        "invented_numbers (vt-eval-2)": {
            "count": sum(len(s["safety"]["invented_numbers"]) for s in ss),
            "examples_rate": rate(sum(bool(s["safety"]["invented_numbers"]) for s in ss), len(ss)),
            "quoted_untrusted_numbers": sum(
                len(s["safety"]["quoted_untrusted_numbers"]) for s in ss
            ),
            "geometry_numbers_excluded": sum(s["safety"]["geometry_numbers"] for s in ss),
        },
        "metadata_accuracy": rate(
            sum(s.get("metadata_correct", 0) for s in val),
            sum(s.get("metadata_total", 0) for s in val),
        ),
        "refusal_accuracy": rate(sum(s["correct"] for s in refusal), len(refusal)),
        "evidence_id_validity": rate(ids_ret - ids_bad, ids_ret),
        "prompt_injection": {
            "adversarial_n": len(adv),
            "adversarial_correct": sum(s["correct"] for s in adv),
            "injection_obeyed (vt-eval-2)": sum(bool(s["safety"]["injection_obeyed"]) for s in adv),
        },
        "safety_violations (vt-eval-2)": {
            "examples_with_any_violation": sum(s["violation"] for s in ss),
            "blocked_assertions": sum(len(s["safety"]["blocked_assertions"]) for s in ss),
            "injection_obeyed": sum(len(s["safety"]["injection_obeyed"]) for s in ss),
            "fallback_v1_unparsed": sum(s["safety"]["fallback_v1"] for s in ss),
        },
        "visual_grounding": {
            "localization_n": len(loc),
            "presence_accuracy": rate(sum(s["presence_correct"] for s in loc), len(loc)),
            "mean_bbox_iou_positives": round(sum(ious) / len(ious), 4) if ious else None,
            "bbox_iou_ge_0.5": rate(sum(i >= 0.5 for i in ious), len(ious)),
            "point_n": len(pt),
            "point_exact_voxel_hits": sum(bool(s.get("point_hit_voxel")) for s in pt),
            "point_answers_given": sum(s["point_distance_px"] is not None for s in pt),
        },
    }


def main() -> int:
    v1 = {
        e["id"]: e
        for e in load_frozen(json.loads((OUT / "eval_reference/dev_v1.json").read_text()))
    }
    v2 = {
        e["id"]: e
        for e in load_frozen(json.loads((OUT / "eval_reference/dev_v2.json").read_text()))
    }
    v3 = {
        e["id"]: e
        for e in load_frozen_v2(json.loads((OUT / "eval_reference/dev_v3.json").read_text()))
    }
    r1 = {r["id"]: r["response"] for r in load_jsonl(B1 / "responses.jsonl")}
    r2 = {r["id"]: r["response"] for r in load_jsonl(B2 / "responses.jsonl")}
    r3 = {r["id"]: r["response"] for r in load_jsonl(B3 / "responses.jsonl")}
    if set(r3) != set(v3):
        raise SystemExit(f"dev_v3 responses incomplete: {len(r3)} of {len(v3)}")
    v1_scores = {
        s["example_id"]: s
        for s in json.loads((B1 / "evaluation_report.json").read_text())["scores"]
    }

    s3 = {rid: score(v3[rid], text) for rid, text in sorted(r3.items())}
    s2 = {rid: score(v2[rid], text) for rid, text in sorted(r2.items())}

    report: dict = {
        "evaluator_version": EVALUATOR_V2_VERSION,
        "label_vocabulary": list(CLAIM_LABELS),
        "dev_v3_all": agg(list(s3.values())),
        "dev_v3_carried_over": agg([s for s in s3.values() if not s["v3_added"]]),
        "dev_v3_added": agg([s for s in s3.values() if s["v3_added"]]),
    }
    by_variant: dict[str, list[bool]] = defaultdict(list)
    for s in s3.values():
        if s["v3_added"]:
            by_variant[f"{s['v3_variant']} ({s['label_expected']})"].append(s["correct"])
    report["dev_v3_added_by_variant"] = {
        k: {"accuracy": rate(sum(v), len(v)), "n": len(v)} for k, v in sorted(by_variant.items())
    }

    # ---- dev_v2 -> dev_v3 on the 104 examples run in dev_v2 (strict, identical scorer)
    rows23 = []
    for id3, s in s3.items():
        pid = v3[id3]["parent_id"]
        if pid not in s2:
            continue
        a, b = s2[pid], s
        rows23.append(
            {
                "v2_id": pid,
                "v3_id": id3,
                "class": a["class"],
                "family": a["family"],
                "v3_changes": ";".join(b["v3_changes"]),
                "v2_strict": a["correct"],
                "v3_strict": b["correct"],
                "change": change(a["correct"], b["correct"]),
                "v2_violation_vt_eval_2": a["violation"],
                "v3_violation_vt_eval_2": b["violation"],
                "v2_response": r2[pid].replace("\n", " ")[:200],
                "v3_response": r3[id3].replace("\n", " ")[:200],
            }
        )
    report["v2_v3_paired"] = {
        "n": len(rows23),
        "changes": dict(Counter(r["change"] for r in rows23)),
        "dev_v2 (re-scored vt-eval-2 for comparison)": agg([s2[r["v2_id"]] for r in rows23]),
        "dev_v3": agg([s3[r["v3_id"]] for r in rows23]),
        "natural_negation_items": {
            "n": sum("NOT_PREFIX" in r["v3_changes"] for r in rows23),
            "v2_correct": sum(r["v2_strict"] for r in rows23 if "NOT_PREFIX" in r["v3_changes"]),
            "v3_correct": sum(r["v3_strict"] for r in rows23 if "NOT_PREFIX" in r["v3_changes"]),
        },
        "examples_changed": [r for r in rows23 if r["change"] in ("IMPROVED", "REGRESSED")],
        "unchanged_wrong": [r for r in rows23 if r["change"] == "UNCHANGED_WRONG"],
    }

    # ---- dev_v1 -> dev_v2 -> dev_v3 on the 70 examples run in all three (semantic)
    rows123 = []
    for id3, s in s3.items():
        id2 = v3[id3]["parent_id"]
        id1 = v2.get(id2, {}).get("parent_id")
        if id2 not in r2 or id1 not in r1:
            continue
        e1 = v1[id1]
        sem1 = semantic_correct_v1(e1, r1[id1], v1_scores.get(id1, {}))
        sem2, sem3 = s2[id2]["semantic_correct"], s["semantic_correct"]
        rows123.append(
            {
                "v1_id": id1,
                "v3_id": id3,
                "class": e1["class"],
                "v3_changes": ";".join(s["v3_changes"]),
                "v1_semantic": sem1,
                "v2_semantic": sem2,
                "v3_semantic": sem3,
                "v3_strict": s["correct"],
                "v1_to_v2": change(sem1, sem2),
                "v2_to_v3": change(sem2, sem3),
                "v1_to_v3": change(sem1, sem3),
            }
        )

    def three(pred) -> dict:
        sel = [r for r in rows123 if pred(r)]
        return {
            "n": len(sel),
            **{
                f"dev_v{i}": rate(sum(r[f"v{i}_semantic"] for r in sel), len(sel))
                for i in (1, 2, 3)
            },
        }

    contra = {
        r["v1_id"] for r in rows123 if v1[r["v1_id"]]["target"].get("status") == "CONTRADICTED"
    }
    report["v1_v2_v3_paired"] = {
        "n": len(rows123),
        "table (semantic)": {
            "claim accuracy": three(
                lambda r: r["class"] in ("CLAIM_VERIFICATION", "CONTRADICTION", "REFUSAL")
            ),
            "CONTRADICTED recall": three(lambda r: r["v1_id"] in contra),
            "numeric exactness (values + SUVpeak definition text)": three(
                lambda r: (
                    r["class"] == "QUANTITATIVE_READING"
                    or (r["class"] == "ADVERSARIAL" and "status" not in v1[r["v1_id"]]["target"])
                )
            ),
            "pair-verdict fidelity": three(lambda r: r["class"] == "PROTOCOL_COMPARABILITY"),
            "prompt-injection cases": three(lambda r: r["class"] == "ADVERSARIAL"),
            "visual grounding": three(
                lambda r: r["class"] in ("VISUAL_LOCALIZATION", "VISUAL_QUANTITATIVE")
            ),
            "metadata / protocol reading": three(
                lambda r: r["class"] in ("PROTOCOL_READING", "MISSING_DATA")
            ),
            "all": three(lambda r: True),
        },
        "v1_to_v2": dict(Counter(r["v1_to_v2"] for r in rows123)),
        "v2_to_v3": dict(Counter(r["v2_to_v3"] for r in rows123)),
        "v1_to_v3": dict(Counter(r["v1_to_v3"] for r in rows123)),
        "suvpeak_definition_items": [
            r for r in rows123 if "SUVPEAK_DEFINITION_INDEPENDENT" in r["v3_changes"]
        ],
    }

    (B3 / "evaluation_v3.json").write_text(
        json.dumps({"scores": list(s3.values())}, indent=2, default=str) + "\n"
    )
    (B3 / "comparison.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    for name, rows in (("changes_v2_v3.csv", rows23), ("changes_v1_v2_v3.csv", rows123)):
        with (B3 / name).open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(
        json.dumps(
            {
                "dev_v3_all": {
                    k: report["dev_v3_all"][k]
                    for k in report["dev_v3_all"]
                    if k not in ("confusion",)
                },
                "dev_v3_added_by_variant": report["dev_v3_added_by_variant"],
                "v2_v3_changes": report["v2_v3_paired"]["changes"],
                "natural_negation_items": report["v2_v3_paired"]["natural_negation_items"],
                "v1_v2_v3": {
                    k: v
                    for k, v in report["v1_v2_v3_paired"].items()
                    if k != "suvpeak_definition_items"
                },
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
