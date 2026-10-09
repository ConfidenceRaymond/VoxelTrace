#!/usr/bin/env python3
"""Read-only disclosure scan of VoxelTrace outputs (reports what is there; changes nothing).

  privacy_scan.py <dir> [<dir> ...]

Per text file (json/csv/md/yaml/txt/log), counts:
  identifying DICOM keywords followed by a value (PatientName, PatientBirthDate, PatientID,
  InstitutionName, ReferringPhysicianName, AccessionNumber, OperatorsName, StationName,
  DeviceSerialNumber), raw DICOM UIDs (dotted numeric >= 20 chars), DICOM DA dates
  (YYYYMMDD 19xx/20xx), and absolute paths (/home/...).
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

KEYWORDS = ("PatientName", "PatientBirthDate", "PatientID", "InstitutionName", "ReferringPhysicianName",
            "AccessionNumber", "OperatorsName", "StationName", "DeviceSerialNumber", "InstitutionAddress")  # fmt: skip
PAT = {
    "identifying_keyword_with_value": re.compile(r"\b(" + "|".join(KEYWORDS) + r")\b\W{1,4}[\"']?[A-Za-z0-9^]"),
    "dicom_uid": re.compile(r"\b[12](?:\.\d+){5,}\b"),
    "dicom_da_date": re.compile(r"\b(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\b"),
    "absolute_home_path": re.compile(r"/home/[A-Za-z0-9_.-]+/"),
}  # fmt: skip
EXT = {".json", ".csv", ".md", ".yaml", ".yml", ".txt", ".log", ".jsonl"}


def scan(root: Path) -> dict:
    totals: Counter = Counter()
    files: dict[str, dict] = {}
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in EXT or p.stat().st_size > 50_000_000:
            continue
        text = p.read_text(errors="ignore")
        hits = {k: len(r.findall(text)) for k, r in PAT.items()}
        hits = {k: v for k, v in hits.items() if v}
        if hits:
            files[str(p.relative_to(root))] = hits
            totals.update(hits)
    return {"root": str(root), "files_with_hits": len(files), "totals": dict(totals),
            "examples": dict(list(files.items())[:15])}  # fmt: skip


def main(argv: list[str]) -> int:
    out = [scan(Path(a)) for a in argv[1:]]
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
