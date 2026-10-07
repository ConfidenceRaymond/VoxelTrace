#!/usr/bin/env python3
"""Strict SUVbw + lesion quantification for a local PET case. Deterministic; no AI.

Usage:
    python scripts/quantify_case.py /path/to/case [--subject ID] [--dataset NAME] [--out DIR]

Exit status: 0 = SUV computed, 2 = SUV refused (reasons written), 1 = usage/input error.
Outputs default to /home/dell/voxeltrace_hackathon/outputs/<subject or directory name>/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from voxeltrace.config import REPO_ROOT
from voxeltrace.ingest import build_case
from voxeltrace.quant.evidence import quantify_case, summary_text, write_outputs

DEFAULT_OUTPUTS = REPO_ROOT.parent / "outputs"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path")
    ap.add_argument("--subject", help="public subject pseudonym (not read from headers)")
    ap.add_argument("--dataset")
    ap.add_argument("--pet-series", help="PET SeriesInstanceUID if more than one")
    ap.add_argument("--seg-series", help="SEG SeriesInstanceUID if more than one")
    ap.add_argument("--out", type=Path, help="output directory")
    ap.add_argument("--no-peak", action="store_true", help="skip SUVpeak search")
    args = ap.parse_args(argv)

    root = Path(args.path).expanduser().resolve()
    if not root.is_dir():
        print(f"not a directory: {root}", file=sys.stderr)
        return 1
    case = build_case(root, dataset=args.dataset, subject_id=args.subject)
    try:
        run = quantify_case(
            case,
            pet_uid=args.pet_series,
            seg_uid=args.seg_series,
            dataset=args.dataset,
            subject=args.subject,
            compute_peak=not args.no_peak,
        )
    except ValueError as exc:
        print(f"cannot quantify: {exc}", file=sys.stderr)
        return 1
    out = args.out or DEFAULT_OUTPUTS / (args.subject or root.name)
    written = write_outputs(run, out)
    print(summary_text(run))
    print("written:")
    for p in written:
        print(f"  {p}")
    return 0 if run.passed else 2


if __name__ == "__main__":
    sys.exit(main())
