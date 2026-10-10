#!/usr/bin/env python3
"""Per-model GE / Philips blocker table from the census v3 header samples (read-only, no
download). Output: JSON with, per vendor/model, series counts, FDG subset, strict-SUV
eligibility, refusal-code counts, units / decay-correction distributions and the presence of
the fields a strict SUV and the pair rules need.

  non_siemens_gap.py <census_v3 pet_series_v3.jsonl> <out.json>
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict


def vendor(m: str) -> str | None:
    s = (m or "").upper()
    return "GE" if s.startswith(("GE", "GEMS")) else "Philips" if "PHILIPS" in s else None


def main(argv: list[str]) -> int:
    with open(argv[1]) as fh:
        rows = [json.loads(line) for line in fh]
    agg: dict = defaultdict(lambda: defaultdict(Counter))
    for r in rows:
        v = vendor(r.get("manufacturer"))
        if not v or r.get("status") != "OK":
            continue
        key = f"{v} | {r.get('model')}"
        a = agg[key]
        fdg = bool(
            re.search(
                r"fdg|fluorodeoxyglucose|fludeoxyglucose",
                f"{r.get('tracer_name')} {r.get('tracer_code')}",
                re.I,
            )
        )
        a["n"]["series"] += 1
        a["n"]["fdg"] += fdg
        a["n"]["suv_eligible"] += bool(r.get("suv_eligible"))
        a["n"]["fdg_suv_eligible"] += bool(r.get("suv_eligible")) and fdg
        a["collections"][r["collection_id"]] += 1
        for c in r.get("refusal_codes") or []:
            a["refusals_all"][c] += 1
            if fdg:
                a["refusals_fdg"][c] += 1
        a["units"][str(r.get("units"))] += 1
        a["decay_correction"][str(r.get("decay_correction"))] += 1
        a["fields"]["software_missing"] += (r.get("software") or {}).get("status") != "PRESENT"
        a["fields"]["height_present"] += bool(r.get("height_present"))
        a["fields"]["weight_present"] += bool(r.get("weight_present"))
        a["fields"]["injection_time_present"] += bool(r.get("injection_time_present"))
        a["fields"]["decay_factor_present"] += bool(r.get("decay_factor_present"))
        a["fields"]["frt_zero_with_decay_factor"] += bool(r.get("frt_zero_with_decay_factor"))
        a["fields"]["attn_in_corrected_image"] += "ATTN" in (r.get("corrected_image") or [])
        a["fields"]["derived"] += bool(r.get("derived"))
        for k, f in (r.get("recon") or {}).items():
            a["recon_present"][k] += f.get("status") == "PRESENT"
    out = {k: {kk: dict(vv) for kk, vv in v.items()} for k, v in sorted(agg.items())}
    doc = {
        "source": "census v3 header samples (IDC v25); acrin_nsclc_fdg_pet excluded (census v2)",
        "models": out,
    }
    with open(argv[2], "w") as fh:
        json.dump(doc, fh, indent=2)
    for k, v in out.items():
        print(k, v["n"], dict(Counter(v.get("refusals_fdg", {})).most_common(5)), v["units"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
