#!/usr/bin/env python3
"""Performance benchmark on local data (no image duplication: file-level symlinks).

  benchmark.py

Builds ../tmp/benchmark/trial_{1,8}/ (1 subject; all 8 local real subjects: ACRIN 050, 094,
153, 167, 168 and the 3 external pairs), PET+CT only (SEG excluded), then times in
subprocesses (/usr/bin/time -v for peak RSS):
  preflight, audit (QIBA only, no input hashing), audit (3 rule sets + input hashing + bundle)
Writes ../outputs/benchmark/benchmark.json and prints a table for docs/performance.md.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
BENCH = ROOT / "tmp" / "benchmark"
OUT = ROOT / "outputs" / "benchmark"
SUBJECTS = [
    DATA / "acrin_longitudinal" / s
    for s in ("ACRIN-NSCLC-FDG-PET-168", "ACRIN-NSCLC-FDG-PET-050", "ACRIN-NSCLC-FDG-PET-094",
              "ACRIN-NSCLC-FDG-PET-153", "ACRIN-NSCLC-FDG-PET-167")
] + [
    DATA / "external_longitudinal" / c / s
    for c, s in (("fdg_pet_ct_lesions", "PETCT_c2ffda4725"), ("cc_tumor_heterogeneity", "CCTH-B02"),
                 ("cmb_mel", "MSB-07612"))
]  # fmt: skip
VT = shutil.which("voxeltrace") or str(Path(sys.executable).parent / "voxeltrace")


def build(n: int) -> tuple[Path, int, int]:
    t = BENCH / f"trial_{n}"
    if t.exists():
        shutil.rmtree(t)
    files = bytes_ = 0
    for subj in SUBJECTS[:n]:
        for tp in ("baseline", "followup"):
            for mod in ("PET", "CT"):
                src = subj / tp / mod
                d = t / subj.name / tp / mod
                d.mkdir(parents=True, exist_ok=True)
                for f in src.glob("*.dcm"):
                    (d / f.name).symlink_to(f)
                    files += 1
                    bytes_ += f.stat().st_size
    (t / "trial.yaml").write_text(
        "trial_id: BENCHMARK\nruleset: qiba-fdg-1.14\ntimepoint_order: [baseline, followup]\n"
        "reference_proposals: auto\n"
    )
    return t, files, bytes_


def timed(cmd: list[str]) -> dict:
    t0 = time.perf_counter()
    r = subprocess.run(["/usr/bin/time", "-v", *cmd], capture_output=True, text=True)
    wall = time.perf_counter() - t0
    m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", r.stderr)
    return {"cmd": " ".join(cmd[1:3]), "returncode": r.returncode, "wall_s": round(wall, 2),
            "peak_rss_MB": round(int(m.group(1)) / 1024, 1) if m else None}  # fmt: skip


def du(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file() and not f.is_symlink())


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    results = []
    for n in (1, len(SUBJECTS)):
        trial, files, nbytes = build(n)
        row = {
            "subjects": n,
            "scans": 2 * n,
            "dicom_files": files,
            "input_MB": round(nbytes / 1e6, 1),
        }
        row["preflight"] = timed([VT, "preflight", str(trial), "--out", str(OUT / f"pf_{n}")])
        runs = (
            ("audit_qiba_nohash", ["--ruleset", "qiba-fdg-1.14", "--no-input-hashes"]),
            ("audit_full_bundle", []),
        )
        for name, extra in runs:
            out = BENCH / f"out_{name}_{n}"
            if out.exists():
                shutil.rmtree(out)
            row[name] = timed([VT, "audit", "--input", str(trial), "--output", str(out), *extra])
            row[name]["bundle_MB"] = round(du(out) / 1e6, 2)
        row["dicom_headers_per_s_preflight"] = round(files / row["preflight"]["wall_s"], 1)
        row["subjects_per_min_full"] = round(60 * n / row["audit_full_bundle"]["wall_s"], 2)
        row["series_per_min_full"] = round(60 * 4 * n / row["audit_full_bundle"]["wall_s"], 2)
        results.append(row)
        print(json.dumps(row, indent=1))
    (OUT / "benchmark.json").write_text(json.dumps(results, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
