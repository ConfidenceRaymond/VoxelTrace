"""JSON + CSV export of a trial audit (no PDF; no patient identifiers)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from voxeltrace.trial.audit import TrialAudit
from voxeltrace.trial.summary import matrix, site_summary


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
    spath = out / "site_summary.json"
    spath.write_text(json.dumps(site_summary(audit), indent=2) + "\n")
    paths.append(spath)
    return paths
