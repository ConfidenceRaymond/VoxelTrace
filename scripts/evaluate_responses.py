#!/usr/bin/env python3
"""Score model responses against VoxelTrace examples (deterministic; no model involved).

Usage:
    python scripts/evaluate_responses.py examples.jsonl responses.jsonl --out report.json
responses.jsonl lines: {"id": "<example id>", "response": "<raw model text>"}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from voxeltrace.evaluation import evaluate, load_examples
from voxeltrace.evaluation.runner import freeze_eval_set, load_frozen


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("examples", type=Path, help="examples.jsonl, or a frozen eval-set .json")
    ap.add_argument("responses", type=Path, nargs="?")
    ap.add_argument("--out", type=Path)
    ap.add_argument(
        "--freeze",
        nargs="+",
        type=Path,
        metavar="DATASET_DIR",
        help="write a frozen eval-set definition to EXAMPLES path and exit",
    )
    args = ap.parse_args(argv)
    if args.freeze:
        args.examples.write_text(
            json.dumps(freeze_eval_set(args.freeze, args.examples.stem), indent=2) + "\n"
        )
        print(f"frozen eval set written: {args.examples}")
        return 0
    if args.examples.suffix == ".json":
        ex = load_frozen(json.loads(args.examples.read_text()))
    else:
        ex = load_examples(args.examples)
    resp = {r["id"]: r["response"] for r in load_examples(args.responses)}
    rep = evaluate(ex, resp)
    summary = rep.model_dump(exclude={"scores"})
    print(json.dumps(summary, indent=2))
    if args.out:
        args.out.write_text(rep.model_dump_json(indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
