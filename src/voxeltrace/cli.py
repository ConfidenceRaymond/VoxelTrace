"""VoxelTrace command line (deterministic; no AI involved in any subcommand).

voxeltrace preflight <path> [--out DIR] [--format json|csv|both]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DISCLAIMER = "RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS."


def _preflight(a: argparse.Namespace) -> int:
    from voxeltrace.preflight import preflight_batch
    from voxeltrace.preflight.export import export_preflight, rows

    path = Path(a.path)
    if not path.exists():
        print(f"error: {path} does not exist", file=sys.stderr)
        return 2
    batch = preflight_batch(path)
    if a.out:
        for p in export_preflight(batch, a.out):
            print(f"wrote {p}")
    elif a.format == "csv":
        import csv

        from voxeltrace.preflight.export import CSV_FIELDS

        w = csv.DictWriter(sys.stdout, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows(batch))
        return 0
    elif a.format == "json":
        print(batch.model_dump_json(indent=2))
        return 0
    print(DISCLAIMER)
    print(json.dumps(batch.summary, indent=2))
    for sc in batch.scans:
        print(f"{sc.subject or '-'}/{sc.scan}: {sc.state}")
        for f in sc.findings:
            print(f"    [{f.severity}] {f.reason_code}: {f.evidence}")
        for s in sc.series:
            print(f"  PET {s.series_pseudonym} ({s.n_instances} instances): {s.state}")
            for f in s.findings:
                print(f"    [{f.severity}] {f.reason_code}: {f.evidence}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="voxeltrace",
        description="VoxelTrace: vendor-neutral quantitative PET comparability, provenance and "
        f"trial audit. {DISCLAIMER}",
    )
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser(
        "preflight",
        help="read-only quantitative preflight of a series, scan, subject or trial folder",
        description="Inspect DICOM headers before quantification. Never computes SUV/SUL. "
        "States: READY_TO_QUANTIFY, READY_WITH_WARNINGS, DO_NOT_QUANTIFY, NEEDS_REVIEW.",
    )
    p.add_argument("path", help="series, scan, subject or trial directory")
    p.add_argument("--out", help="write preflight.json and preflight.csv to this directory")
    p.add_argument("--format", choices=["text", "json", "csv"], default="text")
    p.set_defaults(func=_preflight)
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
