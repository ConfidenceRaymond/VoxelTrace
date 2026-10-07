#!/usr/bin/env python3
"""Build a DEVELOPMENT_ONLY multimodal example dataset for one case (no model involved).

Usage:
    python scripts/build_dev_dataset.py <case_dir> --subject ID [--dataset NAME]
Outputs: ../outputs/training_dev/<ID>/ and ../outputs/visual_audit/<ID>_contact_sheet.png
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from voxeltrace.config import REPO_ROOT
from voxeltrace.training.pipeline import build_case_dataset

OUT = REPO_ROOT.parent / "outputs"
LICENSE = "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/)"
CITATION = (
    "Gatidis S, Kuestner T. A whole-body FDG-PET/CT dataset with manually annotated "
    "tumor lesions (FDG-PET-CT-Lesions) (Version 2). The Cancer Imaging Archive. "
    "https://doi.org/10.7937/gkr0-xv29"
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("case_dir")
    ap.add_argument("--subject", required=True)
    ap.add_argument("--dataset", default="FDG-PET-CT-Lesions")
    ap.add_argument("--license", default=LICENSE)
    ap.add_argument("--citation", default=CITATION)
    ap.add_argument("--out", type=Path, default=OUT / "training_dev")
    args = ap.parse_args(argv)
    res = build_case_dataset(
        args.case_dir,
        args.out,
        subject=args.subject,
        dataset=args.dataset,
        license=args.license,
        citation=args.citation,
        evidence_dir=OUT / args.subject,
        audit_dir=OUT / "visual_audit",
    )
    m = res["manifest"]
    print(f"dataset: {res['out_dir']}")
    print(f"examples: {sum(m.example_counts.values())} {m.example_counts}")
    print(f"images: {len(m.images)}  splits: {[(s.name, s.n_examples) for s in m.splits]}")
    print(f"positive slices: {res['positives']}  negative slices: {res['negatives']}")
    print(f"QC-excluded slices (segment over zero PET): {res['excluded']}")
    print(f"ground-truth levels: {m.label_provenance}")
    print(f"contact sheet: {res['contact_sheet']}")
    print("validation: OK (no leakage, hashes verified, no identifiers, no raw UIDs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
