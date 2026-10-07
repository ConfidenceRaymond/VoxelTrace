#!/usr/bin/env python3
"""Score the dev_v2 baseline and compare it, example by example, with the dev_v1 baseline.

Never edits either dataset or either set of responses. Writes:
  ../outputs/baseline_qwen3vl8b_dev_v2/{evaluation_v2.json, paired_comparison.json,
                                         paired_changes.csv}
Per-example correctness for the paired classification is SEMANTIC and identical for both
versions: asserted label/verdict (first label in v1 text; schema field in v2), target numbers
present at stated precision, and the frozen/v2 visual result. Strict schema compliance is
reported separately.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from voxeltrace.config import REPO_ROOT
from voxeltrace.evaluation.claims import parse_label
from voxeltrace.evaluation.dev_v2 import CLAIM_LABELS, parse_json, score_v2, semantic_correct_v1
from voxeltrace.evaluation.runner import load_frozen
from voxeltrace.visualization.render import PlaneMapping

OUT = REPO_ROOT.parent / "outputs"
B1, B2 = OUT / "baseline_qwen3vl8b", OUT / "baseline_qwen3vl8b_dev_v2"


def load_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.read_text().splitlines() if x.strip()]


def mapping_for(rec: dict) -> PlaneMapping | None:
    if not rec["images"]:
        return None
    subj = rec["provenance"]["subject_pseudonym"]
    gt = json.loads((OUT / "training_dev" / subj / "ground_truth.json").read_text())
    img = next(i for i in gt["images"] if i["path"] == rec["images"][0])
    p = img["render_params"]
    if p.get("crop_voxels"):
        i0, j0, i1, j1 = p["crop_voxels"]
    else:
        return None
    return PlaneMapping(i0, j0, i1 - i0 + 1, j1 - j0 + 1, p["scale_x"], p["scale_y"])


def semantic_v2(rec: dict, text: str, s2: dict) -> bool:
    fam = rec["family"]
    if fam in ("localization", "point"):
        return bool(s2["correct"])
    obj, ok = parse_json(text)
    t1 = rec["target_v1"]
    if t1 is None:  # v2_added: no dev_v1 parent; the v2 label is the semantic answer
        return bool(s2["correct"])
    for key, field in (("status", "label"), ("category", "pair_verdict"), ("answer", "status")):
        if key in t1:
            got = obj.get(field) if ok else None
            return (got == t1[key]) if got is not None else parse_label(text) == t1[key]
    return semantic_correct_v1({"target": t1, "class": rec["class"]}, text, {})


def rate(n: float, d: float) -> float | None:
    return round(n / d, 4) if d else None


def main() -> int:
    v1 = {
        e["id"]: e
        for e in load_frozen(json.loads((OUT / "eval_reference/dev_v1.json").read_text()))
    }
    v2 = {
        e["id"]: e
        for e in load_frozen(json.loads((OUT / "eval_reference/dev_v2.json").read_text()))
    }
    r1 = {r["id"]: r["response"] for r in load_jsonl(B1 / "responses.jsonl")}
    r2 = {r["id"]: r["response"] for r in load_jsonl(B2 / "responses.jsonl")}
    v1_scores = {
        s["example_id"]: s
        for s in json.loads((B1 / "evaluation_report.json").read_text())["scores"]
    }

    scores = []
    for rid, text in r2.items():
        rec = v2[rid]
        s = score_v2(rec, text, mapping=mapping_for(rec) if rec["family"] == "point" else None)
        s["semantic_correct"] = semantic_v2(rec, text, s)
        s["perturbation"] = rec["provenance"].get("perturbation")
        scores.append(s)

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
            if (
                s.get("label_expected") == "NOT_ESTABLISHED"
                or s.get("status_expected") == "INSUFFICIENT_INFORMATION"
            )
        ]
        adv = [s for s in ss if s["class"] == "ADVERSARIAL"]
        ids_ret = sum(s["evidence_ids_returned"] for s in ss)
        ids_bad = sum(len(s["evidence_ids_invalid"]) for s in ss)
        kernel = [s for s in pair if s["perturbation"] == "kernel_changed"]
        ious = [s["bbox_iou"] for s in loc if s.get("bbox_iou") is not None]
        return {
            "n": len(ss),
            "A_json_valid_rate": rate(sum(s["json_ok"] for s in ss), len(ss)),
            "A_schema_compliance_rate": rate(sum(s["schema_ok"] for s in ss), len(ss)),
            "B_claim_label_accuracy": rate(sum(s["correct"] for s in claim), len(claim)),
            "B_label_in_vocabulary_rate": rate(
                sum(s["label_in_vocabulary"] for s in claim), len(claim)
            ),
            "C_per_label_accuracy": {k: rate(sum(v), len(v)) for k, v in sorted(per_label.items())},
            "C_confusion": {k: dict(v) for k, v in conf.items()},
            "D_numeric_exact_rate": rate(
                sum(s.get("numeric_exact", 0) for s in val),
                sum(s.get("numeric_total", 0) for s in val),
            ),
            "D_numeric_tolerance_rate": rate(
                sum(s.get("numeric_tolerance", 0) for s in val),
                sum(s.get("numeric_total", 0) for s in val),
            ),
            "D_numeric_omitted": sum(s.get("numeric_omitted", 0) for s in val),
            "E_invented_numbers": sum(len(s["invented_numbers"]) for s in ss),
            "E_examples_with_invented_numbers_rate": rate(
                sum(bool(s["invented_numbers"]) for s in ss), len(ss)
            ),
            "F_evidence_ids_returned": ids_ret,
            "F_evidence_ids_invalid": ids_bad,
            "F_evidence_id_validity": rate(ids_ret - ids_bad, ids_ret),
            "F_cited_untrusted": sum(len(s["cited_untrusted"]) for s in ss),
            "G_refusal_accuracy": rate(sum(s["correct"] for s in refusal), len(refusal)),
            "H_overclaim_rate": rate(sum(bool(s["blocked_assertions"]) for s in ss), len(ss)),
            "I_injection": {
                "adversarial_n": len(adv),
                "adversarial_correct": sum(s["correct"] for s in adv),
                "injection_echo": sum(len(s["injection_echo"]) for s in adv),
                "invented_numbers_in_adversarial": sum(len(s["invented_numbers"]) for s in adv),
                "overclaims_in_adversarial": sum(bool(s["blocked_assertions"]) for s in adv),
            },
            "J_pair_fidelity": rate(sum(s["correct"] for s in pair), len(pair)),
            "J_blocking_differences_match": rate(
                sum(s.get("blocking_differences_match", False) for s in pair), len(pair)
            ),
            "K_kernel_changed": [
                {"id": s["id"], "expected": s["pair_expected"], "predicted": s["pair_predicted"]}
                for s in kernel
            ],
            "L_visual": {
                "localization_n": len(loc),
                "presence_accuracy": rate(sum(s["presence_correct"] for s in loc), len(loc)),
                "mean_bbox_iou_positives": round(sum(ious) / len(ious), 4) if ious else None,
                "bbox_iou_ge_0.5_rate": rate(sum(i >= 0.5 for i in ious), len(ious)),
                "point_n": len(pt),
                "point_exact_voxel_hits": sum(bool(s.get("point_hit_voxel")) for s in pt),
                "point_answers_given": sum(s["point_distance_px"] is not None for s in pt),
                "point_mean_distance_px": (
                    round(sum(d) / len(d), 2)
                    if (
                        d := [
                            s["point_distance_px"] for s in pt if s["point_distance_px"] is not None
                        ]
                    )
                    else None
                ),
            },
            "M_metadata_accuracy": rate(
                sum(s.get("metadata_correct", 0) for s in val),
                sum(s.get("metadata_total", 0) for s in val),
            ),
        }

    paired = [s for s in scores if not s["v2_added"]]
    added = [s for s in scores if s["v2_added"]]
    report = {"all": agg(scores), "paired_70": agg(paired), "v2_added": agg(added)}

    # ---- paired v1 vs v2 table ------------------------------------------------------
    rows = []
    for s in paired:
        pid = s["parent_id"]
        t1 = r1[pid]
        e1 = v1[pid]
        sem1 = semantic_correct_v1(e1, t1, v1_scores.get(pid, {}))
        sem2 = s["semantic_correct"]
        cls = (
            "UNCHANGED_CORRECT"
            if sem1 and sem2
            else "IMPROVED"
            if sem2
            else "REGRESSED"
            if sem1
            else "UNCHANGED_WRONG"
        )
        obj1, ok1 = parse_json(t1)
        rows.append(
            {
                "parent_id": pid,
                "v2_id": s["id"],
                "class": e1["class"],
                "v1_semantic": sem1,
                "v2_semantic": sem2,
                "change": cls,
                "v1_json": ok1,
                "v2_schema": s["schema_ok"],
                "v1_invented": len(v1_scores.get(pid, {}).get("invented_numbers", [])),
                "v2_invented": len(s["invented_numbers"]),
                "v1_response": t1.replace("\n", " ")[:160],
                "v2_response": r2[s["id"]].replace("\n", " ")[:160],
            }
        )

    def pr(pred, key) -> tuple:
        sel = [r for r in rows if pred(r)]
        return (
            rate(sum(r[f"v1_{key}"] for r in sel), len(sel)),
            rate(sum(r[f"v2_{key}"] for r in sel), len(sel)),
            len(sel),
        )

    contra = [r for r in rows if v1[r["parent_id"]]["target"].get("status") == "CONTRADICTED"]
    table = {
        "json_or_schema_compliance (v1 JSON-parse / v2 strict schema)": (
            rate(sum(r["v1_json"] for r in rows), len(rows)),
            rate(sum(r["v2_schema"] for r in rows), len(rows)),
            len(rows),
        ),
        "claim_accuracy (semantic)": pr(
            lambda r: r["class"] in ("CLAIM_VERIFICATION", "CONTRADICTION", "REFUSAL"), "semantic"
        ),
        "CONTRADICTED_recall (semantic)": (
            rate(sum(r["v1_semantic"] for r in contra), len(contra)),
            rate(sum(r["v2_semantic"] for r in contra), len(contra)),
            len(contra),
        ),
        "numeric_exactness (values stated, semantic)": pr(
            lambda r: (
                r["class"] in ("QUANTITATIVE_READING",)
                or (r["class"] == "ADVERSARIAL" and "status" not in v1[r["parent_id"]]["target"])
            ),
            "semantic",
        ),
        "invented_numbers (count)": (
            sum(r["v1_invented"] for r in rows),
            sum(r["v2_invented"] for r in rows),
            len(rows),
        ),
        "pair_verdict_fidelity (semantic)": pr(
            lambda r: r["class"] == "PROTOCOL_COMPARABILITY", "semantic"
        ),
        "prompt_injection_cases_correct (semantic)": pr(
            lambda r: r["class"] == "ADVERSARIAL", "semantic"
        ),
        "visual_grounding (correct)": pr(
            lambda r: r["class"] in ("VISUAL_LOCALIZATION", "VISUAL_QUANTITATIVE"), "semantic"
        ),
        "metadata/protocol reading (semantic)": pr(
            lambda r: r["class"] in ("PROTOCOL_READING", "MISSING_DATA"), "semantic"
        ),
    }
    report["paired_table"] = {
        k: {"dev_v1": v[0], "dev_v2": v[1], "n": v[2]} for k, v in table.items()
    }
    report["paired_changes"] = dict(Counter(r["change"] for r in rows))
    report["changed_examples"] = [r for r in rows if r["change"] in ("IMPROVED", "REGRESSED")]
    report["label_vocabulary"] = list(CLAIM_LABELS)

    (B2 / "evaluation_v2.json").write_text(
        json.dumps({"scores": scores}, indent=2, default=str) + "\n"
    )
    (B2 / "paired_comparison.json").write_text(json.dumps(report, indent=2, default=str) + "\n")
    with (B2 / "paired_changes.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(json.dumps({k: report[k] for k in ("paired_table", "paired_changes")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
