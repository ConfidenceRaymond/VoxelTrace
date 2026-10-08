"""JSON + CSV export of a trial audit (no PDF; no patient identifiers)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import yaml

from voxeltrace.trial.audit import TrialAudit
from voxeltrace.trial.summary import (
    REFERENCE_COLUMNS,
    audit_report_md,
    failure_rows,
    matrix,
    pair_rows,
    reference_rows,
    review_worksheet,
    rule_rows,
    site_summary,
)

WORKSHEET_HEADER = """\
# VoxelTrace reference-region review worksheet (generated; RESEARCH PROTOTYPE).
# Preferred: record decisions on the Reference Review page of the VoxelTrace app.
# By hand: open qc_image, then set decision to ACCEPT (keep final_geometry), ADJUST (move
# only final_geometry.centre_patient_mm, LPS mm) or REJECT (set final_geometry: null), fill
# reviewer and reviewed_at (ISO-8601 timestamp), save as <trial>/reference_review.yaml and
# re-run the audit. PENDING proposals are never used by any assessability rule.
# A review applies only to the proposal_sha256 it names; if the proposal changes, the
# review becomes OUTDATED and is not reused.
"""


def export_audit(audit: TrialAudit, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    full = out / "trial_audit.json"
    full.write_text(
        audit.model_dump_json(indent=2, exclude={"timepoints": {"__all__": {"protocol"}}}) + "\n"
    )
    paths.append(full)
    rows = matrix(audit)
    mpath = out / "subject_timepoint_matrix.csv"
    with mpath.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["subject"])
        w.writeheader()
        w.writerows(rows)
    paths.append(mpath)
    ppath = out / "pair_checks.csv"
    with ppath.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "subject",
                "baseline",
                "followup",
                "verdict",
                "rule_id",
                "standard",
                "impact",
                "status",
                "observed",
                "expected",
                "source",
                "reason_codes",
            ]
        )
        for p in audit.pairs:
            for c in p.checks:
                w.writerow(
                    [
                        p.pair.subject_id,
                        p.pair.baseline,
                        p.pair.followup,
                        p.verdict,
                        c.rule_id,
                        c.standard,
                        c.impact,
                        c.status,
                        json.dumps(c.observed, default=str),
                        c.expected,
                        c.source,
                        ";".join(r.code for r in c.reasons),
                    ]
                )
    paths.append(ppath)
    rpath = out / "reference_regions.csv"
    with rpath.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REFERENCE_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(reference_rows(audit))
    paths.append(rpath)
    wpath = out / "reference_review_worksheet.yaml"
    wpath.write_text(
        WORKSHEET_HEADER + yaml.safe_dump(review_worksheet(audit), sort_keys=True, width=100)
    )
    paths.append(wpath)
    for name, rows in (
        ("pair_verdicts.csv", pair_rows(audit)),
        ("rule_summary.csv", rule_rows(audit)),
        ("failure_reasons.csv", failure_rows(audit)),
    ):
        path = out / name
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["empty"])
            w.writeheader()
            w.writerows(rows)
        paths.append(path)
    mdpath = out / "AUDIT_REPORT.md"
    mdpath.write_text(audit_report_md(audit))
    paths.append(mdpath)
    spath = out / "site_summary.json"
    spath.write_text(json.dumps(site_summary(audit), indent=2) + "\n")
    paths.append(spath)
    return paths
