#!/usr/bin/env python3
"""Trial-wide batch comparability / assessability audit (deterministic; no AI).

  run_trial_audit.py <trial_dir> --out <dir> [--ruleset percist-1.0] [--reviews FILE]

<trial_dir> holds trial.yaml and <subject>/<timepoint>/<DICOM>. Writes to --out:
  trial_audit.json, subject_timepoint_matrix.csv, pair_checks.csv, site_summary.json,
  reference_regions.csv, reference_review_worksheet.yaml, reference_qc/*.png
The output directory must lie inside the project root (the parent of this repository).
No biological or treatment response is assessed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from voxeltrace.config import REPO_ROOT
from voxeltrace.trial.audit import run_trial_audit
from voxeltrace.trial.export import export_audit
from voxeltrace.trial.summary import site_summary

PROJECT_ROOT = REPO_ROOT.parent.resolve()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("trial_dir", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--ruleset", help="override trial.yaml ruleset (recorded in the output)")
    ap.add_argument("--reviews", type=Path, help="reference review file (default from trial.yaml)")
    a = ap.parse_args(argv)
    out = a.out.resolve()
    if PROJECT_ROOT not in (out, *out.parents):
        print(f"--out must be inside {PROJECT_ROOT}", file=sys.stderr)
        return 2
    audit = run_trial_audit(
        a.trial_dir, ruleset=a.ruleset, qc_dir=out / "reference_qc", reviews_file=a.reviews
    )
    for p in export_audit(audit, out):
        print(p)
    s = site_summary(audit)
    print(
        json.dumps(
            {
                "ruleset": f"{audit.ruleset_id} ({audit.ruleset_version})",
                "verdicts": s["verdicts"],
                "insufficient_information_by_reason": s["insufficient_information_by_reason"],
                "reference_regions": s["reference_regions"],
                "reference_reviews_applied": audit.reference_reviews_applied,
                "reference_reviews_unmatched": audit.reference_reviews_unmatched,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
