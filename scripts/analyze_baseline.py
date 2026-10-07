#!/usr/bin/env python3
"""Secondary, schema-independent analysis of baseline responses (post hoc, clearly labelled).

The primary score is scripts/evaluate_responses.py on the frozen eval set (unchanged). This
script additionally asks, per example: are the target's numbers present anywhere in the
response text at their stated precision (ignoring JSON key names)? and for label-type targets:
is the expected label the first label mentioned? It never edits ground truth or the evaluator.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from voxeltrace.evaluation.claims import parse_label
from voxeltrace.evaluation.numeric import exact_match, extract_numbers, numeric_leaves
from voxeltrace.evaluation.runner import load_frozen


def main(eval_set: str, responses: str, out: str) -> int:
    ex = {e["id"]: e for e in load_frozen(json.loads(Path(eval_set).read_text()))}
    resp = {
        json.loads(x)["id"]: json.loads(x)["response"]
        for x in Path(responses).read_text().splitlines()
        if x.strip()
    }
    per_class: dict[str, list[float]] = defaultdict(list)
    rows = []
    for rid, text in resp.items():
        e = ex[rid]
        nums = [v for p, v in numeric_leaves(e["target"]) if not p.endswith("segment_number")]
        stated = extract_numbers(text)
        if nums:
            hit = sum(any(exact_match(s, v) for s in stated) for v in nums) / len(nums)
            per_class[e["class"] + ":values_present"].append(hit)
            rows.append({"id": rid, "values_present_fraction": hit})
        for key in ("status", "category", "answer"):
            if key in e["target"]:
                ok = parse_label(text) == e["target"][key]
                per_class[e["class"] + ":label_first_mentioned"].append(float(ok))
                rows.append({"id": rid, "label_ok": ok})
                break
    summary = {k: round(sum(v) / len(v), 3) for k, v in sorted(per_class.items())}
    Path(out).write_text(
        json.dumps(
            {
                "note": "SECONDARY post-hoc analysis; primary score is the frozen evaluator report",
                "summary": summary,
                "rows": rows,
            },
            indent=2,
        )
        + "\n"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
