"""Preflight export: JSON (full) and CSV (one row per finding, plus one per clean series)."""

from __future__ import annotations

import csv
from pathlib import Path

from voxeltrace.preflight.schema import BatchPreflight

CSV_FIELDS = [
    "subject", "scan", "series_pseudonym", "modality", "series_state", "scan_state",
    "reason_code", "severity", "field", "evidence", "remediation", "recoverable", "source",
]  # fmt: skip


def rows(batch: BatchPreflight) -> list[dict]:
    out = []
    for sc in batch.scans:
        for f in sc.findings:
            out.append(
                {
                    "subject": sc.subject,
                    "scan": sc.scan,
                    "series_pseudonym": "",
                    "modality": "",
                    "series_state": "",
                    "scan_state": sc.state,
                    **f.model_dump(),
                }
            )
        for s in sc.series:
            base = {
                "subject": s.subject,
                "scan": s.scan,
                "series_pseudonym": s.series_pseudonym,
                "modality": s.modality,
                "series_state": s.state,
                "scan_state": sc.state,
            }
            if not s.findings:
                out.append(
                    {
                        **base,
                        "reason_code": "",
                        "severity": "",
                        "field": "",
                        "evidence": "",
                        "remediation": "",
                        "recoverable": "",
                        "source": "",
                    }
                )
            out += [{**base, **f.model_dump()} for f in s.findings]
    return out


def export_preflight(batch: BatchPreflight, out_dir: str | Path) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    j = out / "preflight.json"
    j.write_text(batch.model_dump_json(indent=2) + "\n")
    c = out / "preflight.csv"
    with c.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows(batch))
    return [j, c]
