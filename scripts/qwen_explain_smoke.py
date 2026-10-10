#!/usr/bin/env python3
"""Tiny product-relevant smoke test of the OPTIONAL local VLM as an EXPLAINER (no evaluation
set, no image, no decision). Runs in the isolated model venv only:

  source ../tmp/vlm_env.sh && ../tmp/vlm-venv/bin/python scripts/qwen_explain_smoke.py \
      --model ../models/Qwen3-VL-8B-Instruct --trace <pair_evidence_trace.csv> --subject S --out <dir>

Checks (all recorded in <out>/qwen_smoke.json):
  - local-only: offline flags set, the model is loaded from a local directory, no network
  - the deterministic verdict and every number come from VoxelTrace (the prompt); the model's
    numbers must be a subset of the numbers it was given (any new number = FAIL)
  - the reply must not claim a different verdict or recommend a clinical action
  - runtime and peak VRAM
The model output is MODEL_GENERATED explanatory prose; it is never written into a bundle.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

VERDICTS = ("ASSESSABLE_WITH_WARNINGS", "ASSESSABLE", "NOT_ASSESSABLE", "INSUFFICIENT_INFORMATION")
NUM = re.compile(r"(?<![\w.])\d+(?:\.\d+)?")


def evidence(trace: Path, subject: str) -> dict:
    rows = [r for r in csv.DictReader(trace.open()) if r["subject"] == subject]
    by_rs: dict[str, dict] = {}
    for r in rows:
        d = by_rs.setdefault(r["ruleset"], {"verdict": r["verdict"], "open_rules": []})
        d["open_rules"].append(
            {
                k: r[k]
                for k in ("rule_id", "status", "reason_code", "reason_detail", "plain_language")
            }
        )
    return {"subject": subject, "rulesets": by_rs}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if not (a.model / "config.json").exists():
        raise SystemExit(f"{a.model} is not a local model directory (no download is attempted)")
    import torch
    from transformers import AutoModelForImageTextToText, AutoProcessor

    ev = evidence(a.trace, a.subject)
    prompt = (
        "You are explaining a deterministic PET comparability audit to a clinical-trial imaging "
        "manager. The verdicts and reasons below were computed by VoxelTrace and are final; do not "
        "change them, do not add numbers, do not diagnose, do not recommend treatment. In at most "
        "120 words, explain what each verdict means for this pair and what would have to be "
        "supplied or reviewed.\n\nEVIDENCE (computed deterministically):\n"
        + json.dumps(ev, indent=1)
    )
    t0 = time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    proc = AutoProcessor.from_pretrained(a.model, local_files_only=True)
    model = AutoModelForImageTextToText.from_pretrained(
        a.model, local_files_only=True, dtype=torch.bfloat16, device_map="cuda"
    )
    t_load = time.perf_counter() - t0
    msgs = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
    inputs = proc.apply_chat_template(
        msgs, add_generation_prompt=True, tokenize=True, return_dict=True, return_tensors="pt"
    ).to(model.device)
    t1 = time.perf_counter()
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=220, do_sample=False)
    t_gen = time.perf_counter() - t1
    text = proc.batch_decode(out[:, inputs["input_ids"].shape[1] :], skip_special_tokens=True)[
        0
    ].strip()
    given = set(NUM.findall(prompt))
    new_numbers = sorted(set(NUM.findall(text)) - given)
    mentioned = [v for v in VERDICTS if re.search(rf"\b{v}\b", text)]
    wrong_verdict = [v for v in mentioned if not any(v == d["verdict"] for d in ev["rulesets"].values())
                     and not any(v in d["verdict"] for d in ev["rulesets"].values())]  # fmt: skip
    clinical = re.findall(
        r"\b(diagnos\w*|treat(?:ment)? (?:plan|change)|respon(?:se|der) to therapy|progressi\w+ disease)\b",
        text,
        re.I,
    )
    result = {
        "schema": "VT-QWEN-SMOKE-1",
        "model_dir": a.model.name,
        "offline_flags": {k: os.environ.get(k) for k in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")},
        "torch": torch.__version__, "cuda": torch.version.cuda, "gpu": torch.cuda.get_device_name(0),
        "load_s": round(t_load, 2), "generate_s": round(t_gen, 2),
        "new_tokens": int(out.shape[1] - inputs["input_ids"].shape[1]),
        "peak_vram_GiB": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "evidence_given": ev, "model_output_MODEL_GENERATED": text,
        "checks": {"new_numbers_not_in_evidence": new_numbers, "verdicts_mentioned": mentioned,
                   "verdicts_not_in_evidence": wrong_verdict, "clinical_language": clinical},
    }  # fmt: skip
    result["status"] = (
        "PASS" if not new_numbers and not wrong_verdict and not clinical else "FLAGGED"
    )
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "qwen_smoke.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("evidence_given",)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
