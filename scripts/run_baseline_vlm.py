#!/usr/bin/env python3
"""Baseline (no fine-tuning) inference of a local Qwen3-VL model on DEVELOPMENT_ONLY examples.

Runs in the isolated model venv (../tmp/vlm-venv) with all caches redirected
(source ../tmp/vlm_env.sh). The assistant/target turn is NEVER sent to the model.
Outputs are MODEL_GENERATED responses (never ground truth) written to
../outputs/baseline_qwen3vl8b/responses.jsonl for scoring with scripts/evaluate_responses.py.

Usage:
    python scripts/run_baseline_vlm.py --model ../models/Qwen3-VL-8B-Instruct \
        --datasets ../outputs/training_dev/PETCT_0011f3deaf ... --out ../outputs/baseline_qwen3vl8b
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

PER_CLASS = 2


def select(records: list[dict]) -> list[dict]:
    """Deterministic small subset: <= PER_CLASS per class per subject + all ADVERSARIAL."""
    out, seen = [], defaultdict(int)
    for r in sorted(records, key=lambda r: r["id"]):
        key = (r["id"].rsplit("-", 2)[0], r["metadata"]["class"])
        if r["metadata"]["class"] == "ADVERSARIAL" or seen[key] < PER_CLASS:
            seen[key] += 1
            out.append(r)
    return out


def to_messages(rec: dict, root: Path) -> tuple[list[dict], list[Image.Image]]:
    msgs, images = [], []
    for m in rec["messages"]:
        if m["role"] == "assistant":
            continue  # never leak the target
        content = []
        for c in m["content"]:
            if c["type"] == "image":
                img = Image.open(root / c["image"]).convert("RGB")
                images.append(img)
                content.append({"type": "image", "image": img})
            else:
                content.append(c)
        msgs.append({"role": m["role"], "content": content})
    return msgs, images


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--datasets", type=Path, nargs="+", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--max-new-tokens", type=int, default=384)
    ap.add_argument("--ids", type=Path, help="JSON list of example ids to run (exact set)")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa"
    )
    model.eval()
    load_s = time.time() - t0

    todo = []
    for d in args.datasets:
        recs = [json.loads(x) for x in (d / "examples_qwen3vl.jsonl").read_text().splitlines()]
        if args.ids is not None:
            wanted = set(json.loads(args.ids.read_text()))
            todo += [(d, r) for r in sorted(recs, key=lambda r: r["id"]) if r["id"] in wanted]
        else:
            todo += [(d, r) for r in select(recs)]
    rows = []
    for d, rec in todo:
        msgs, _ = to_messages(rec, d)
        inputs = processor.apply_chat_template(
            msgs, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
        )
        inputs = inputs.to(model.device)
        t = time.time()
        with torch.inference_mode():
            gen = model.generate(**inputs, max_new_tokens=args.max_new_tokens, do_sample=False)
        text = processor.batch_decode(
            gen[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True
        )[0]
        rows.append(
            {
                "id": rec["id"],
                "response": text,
                "class": rec["metadata"]["class"],
                "input_tokens": int(inputs["input_ids"].shape[1]),
                "latency_s": round(time.time() - t, 2),
                "source": "MODEL_GENERATED",
            }
        )
        print(f"{rec['id']}: {len(text)} chars in {rows[-1]['latency_s']} s", flush=True)
    (args.out / "responses.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    meta = {
        "model_dir": str(args.model),
        "n_examples": len(rows),
        "load_seconds": round(load_s, 1),
        "max_new_tokens": args.max_new_tokens,
        "decoding": "greedy (do_sample=False)",
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "device": torch.cuda.get_device_name(0),
        "peak_gpu_mem_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
        "selection": (f"explicit id list {args.ids}" if args.ids is not None else
                      f"<= {PER_CLASS} per class per subject + all ADVERSARIAL, sorted by id"),
        "datasets": [str(d) for d in args.datasets],
        "examples_sha256": {
            str(d): hashlib.sha256((d / "examples_qwen3vl.jsonl").read_bytes()).hexdigest()
            for d in args.datasets
        },
        "note": "MODEL_GENERATED baseline responses; never ground truth; no fine-tuning",
    }
    (args.out / "run_metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
