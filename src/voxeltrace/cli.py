"""VoxelTrace command line (deterministic; no AI involved in any subcommand).

voxeltrace preflight <path> [--out DIR] [--format text|json|csv]
voxeltrace inspect <path>
voxeltrace audit --input DIR [--config trial.yaml] --output DIR [--ruleset ID ...]
voxeltrace verify-bundle <bundle>
voxeltrace summarize <bundle>
voxeltrace list-reviews <bundle>
voxeltrace adjudicate ... --confirm    (explicit human action only)
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


def _inspect(a: argparse.Namespace) -> int:
    from voxeltrace.ingest import discover_dicom

    disc = discover_dicom(Path(a.path))
    print(DISCLAIMER)
    for s in disc.series:
        print(f"{s.category:5} {len(s.instances):5} instances  frames-of-reference "
              f"{len(s.frame_of_reference_uids)}  {s.series_description or ''}")  # fmt: skip
    for w in disc.warnings:
        print(f"warning {w.code}: {w.message}")
    return 0


def _audit(a: argparse.Namespace) -> int:
    from voxeltrace.pilot import RULESETS, run_audit

    res = run_audit(
        a.input, a.output, config=a.config, rulesets=tuple(a.ruleset or RULESETS),
        attestations=a.attestations, adjudications=a.adjudications,
        hash_inputs=not a.no_input_hashes, qc_images=a.qc_images,
    )  # fmt: skip
    print(DISCLAIMER)
    print(f"bundle: {res['bundle']}")
    print(json.dumps({k: v for k, v in res["summary"].items() if k != "rulesets"}, indent=2))
    for rs, r in res["summary"]["rulesets"].items():
        print(f"{rs}: real {r['verdicts_real']} synthetic {r['verdicts_synthetic']}")
    return 0


def _verify(a: argparse.Namespace) -> int:
    from voxeltrace.bundle import verify_bundle

    r = verify_bundle(a.bundle)
    print(json.dumps(r, indent=2))
    return 0 if r["status"] == "OK" else 1


def _summarize(a: argparse.Namespace) -> int:
    p = Path(a.bundle) / "reports" / "summary.json"
    if not p.exists():
        print(f"error: {p} not found", file=sys.stderr)
        return 2
    s = json.loads(p.read_text())
    print(DISCLAIMER)
    print(json.dumps({k: v for k, v in s.items() if k != "rulesets"}, indent=2))
    for rs, r in s["rulesets"].items():
        print(f"{rs}: real {r['verdicts_real']}; unresolved {r['unresolved_rules']}")
    return 0


def _list_reviews(a: argparse.Namespace) -> int:
    p = Path(a.bundle) / "reviews" / "review_status.csv"
    if not p.exists():
        print(f"error: {p} not found", file=sys.stderr)
        return 2
    import csv

    rows = list(csv.DictReader(p.open()))
    pending = [r for r in rows if r.get("task") == "HUMAN_REVIEW_REQUIRED"]
    print(f"{len(pending)} pending human reference-region review(s); {len(rows)} regions total")
    for r in rows:
        print(
            f"  {r['subject']}/{r['timepoint']} {r['region']}: {r['status']} {r['review_decision']}"
        )
    return 0


def _adjudicate(a: argparse.Namespace) -> int:
    """Append ONE human adjudication. Requires --confirm; never run by automation."""
    from datetime import UTC, datetime

    import voxeltrace
    from voxeltrace.quant.suv import git_state
    from voxeltrace.trial.adjudication import Adjudication, EvidenceItem, append_adjudication

    if not a.confirm:
        print("refused: adjudication requires --confirm (explicit human action)", file=sys.stderr)
        return 2
    ev = [
        EvidenceItem(description=d, attachment_sha256=h)
        for d, h in (x.split("=", 1) for x in a.evidence or [])
    ]
    rec = Adjudication(
        adjudication_id=a.id, subject=a.subject, baseline=a.baseline, followup=a.followup,
        ruleset_id=a.ruleset, automated_verdict=a.automated_verdict,
        automated_result_sha256=a.result_sha256, affected_rules=a.rules or [], action=a.action,
        adjudicated_verdict=a.new_verdict, reason=a.reason, supplied_evidence=ev,
        reviewer_id=a.reviewer, reviewer_role=a.role, timestamp=datetime.now(UTC),
        software_version=voxeltrace.__version__, git_commit=git_state()[0], created_via="HUMAN_CLI",
    )  # fmt: skip
    h = append_adjudication(a.log, rec, confirmed=True)
    print(f"appended {a.id} (chain {h})")
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

    p = sub.add_parser("inspect", help="list the DICOM series found under a path (read-only)")
    p.add_argument("path")
    p.set_defaults(func=_inspect)

    p = sub.add_parser("audit", help="whole-trial comparability audit -> immutable evidence bundle")
    p.add_argument("--input", required=True, help="trial folder: <subject>/<timepoint>/<DICOM>")
    p.add_argument("--config", help="trial.yaml (default: <input>/trial.yaml)")
    p.add_argument("--output", required=True, help="new output directory (never overwritten)")
    p.add_argument(
        "--ruleset", action="append", choices=["qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0"]
    )
    p.add_argument(
        "--attestations", help="site-supplied reconstruction attestation file (QIBA only)"
    )
    p.add_argument("--adjudications", help="human adjudication log (JSON lines)")
    p.add_argument("--no-input-hashes", action="store_true", help="skip hashing every input file")
    p.add_argument("--qc-images", action="store_true", help="render reference-proposal QC images")
    p.set_defaults(func=_audit)

    p = sub.add_parser("verify-bundle", help="verify an evidence bundle's checksums (tamper check)")
    p.add_argument("bundle")
    p.set_defaults(func=_verify)

    p = sub.add_parser("summarize", help="print the summary of an evidence bundle")
    p.add_argument("bundle")
    p.set_defaults(func=_summarize)

    p = sub.add_parser("list-reviews", help="list human review tasks recorded in a bundle")
    p.add_argument("bundle")
    p.set_defaults(func=_list_reviews)

    p = sub.add_parser("adjudicate", help="append ONE human pair adjudication (requires --confirm)")
    for name in ("log", "id", "subject", "baseline", "followup", "ruleset", "automated-verdict",
                 "result-sha256", "action", "reason", "reviewer", "role"):  # fmt: skip
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--new-verdict")
    p.add_argument("--rules", nargs="*")
    p.add_argument("--evidence", nargs="*", help="description=sha256 (repeatable)")
    p.add_argument("--confirm", action="store_true", help="I am the named human reviewer")
    p.set_defaults(func=_adjudicate)
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
