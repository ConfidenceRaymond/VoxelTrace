"""Conservative pattern scan of a delivery package (VT-PRIVACY-SCAN-1).

This is a last-line safety net, NOT a de-identification method and not a HIPAA / GDPR
compliance tool. It flags text that should never appear in a package VoxelTrace delivers:

  DICOM_IDENTIFIER_ATTRIBUTE  PatientName / PatientID / AccessionNumber / PatientBirthDate /
                              OtherPatientIDs / IssuerOfPatientID or their (gggg,eeee) tags
  DICOM_UID                   a raw dotted DICOM UID (VoxelTrace writes pseudonyms instead)
  LOCAL_PATH                  an absolute local path (/home/..., /Users/..., C:\\Users\\..., ...)
  WORKSPACE_NAME              the development workspace name
  LOCAL_ACCOUNT               the current user name or host name as a whole word
  EMAIL                       an e-mail address
  SECRET                      API keys, tokens, private keys, password assignments
  HIDDEN_FILE                 a file or directory whose name starts with '.'
  DICOM_FILE                  a DICOM file (preamble 'DICM' at byte 128, or a .dcm name)

Text files are scanned line by line; other files (PDF) are scanned as latin-1 text, which
covers the uncompressed text streams VoxelTrace writes. Matches are reported with the secret
part masked. False positives are possible by design; the package must be fixed, not the scan.
"""

from __future__ import annotations

import contextlib
import getpass
import re
import socket
from pathlib import Path
from typing import Any

PRIVACY_SCAN_SCHEMA = "VT-PRIVACY-SCAN-1"
_ATTRS = ("PatientName", "PatientID", "AccessionNumber", "PatientBirthDate", "OtherPatientIDs",
          "IssuerOfPatientID", "PatientAddress", "PatientTelephoneNumbers", "ReferringPhysicianName",
          "OperatorsName", "PerformingPhysicianName", "InstitutionAddress")  # fmt: skip
_TAGS = ("0010,0010", "0010,0020", "0008,0050", "0010,0030", "0010,1000", "0010,0021",
         "0010,1040", "0010,2154", "0008,0090", "0008,1070", "0008,1050", "0008,0081")  # fmt: skip
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("DICOM_IDENTIFIER_ATTRIBUTE", re.compile(r"\b(?:" + "|".join(_ATTRS) + r")\b")),
    ("DICOM_IDENTIFIER_ATTRIBUTE", re.compile(r"\(?\b(?:" + "|".join(re.escape(t) for t in _TAGS) + r")\b\)?", re.I)),
    ("DICOM_IDENTIFIER_ATTRIBUTE", re.compile(r"\b(?:InstitutionName|StationName|DeviceSerialNumber)\b[\"']?\s*[:=]\s*[\"']?[A-Za-z0-9]")),
    ("DICOM_UID", re.compile(r"(?<![\w.])[12](?:\.\d{1,40}){5,}(?![\w])")),
    ("LOCAL_PATH", re.compile(r"(?<![\w.:/])/(?:home|Users|root|mnt|media|tmp|var/folders|private/var|scratch|data)/[^\s\"'`,;)\]}]+")),
    ("LOCAL_PATH", re.compile(r"\b[A-Za-z]:\\(?:Users|Documents and Settings)\\[^\s\"']+")),
    ("LOCAL_PATH", re.compile(r"(?<![\w])~/[^\s\"'`,;)]+")),
    ("WORKSPACE_NAME", re.compile(r"voxeltrace_hackathon")),
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("SECRET", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|hf_[A-Za-z0-9]{30,}|AKIA[0-9A-Z]{16}|xox[abprs]-[A-Za-z0-9-]{10,}|glpat-[A-Za-z0-9_-]{20,})\b")),
    ("SECRET", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("SECRET", re.compile(r"(?i)\b(?:api[_-]?key|secret|access[_-]?token|auth[_-]?token|password|passwd)\b\s*[:=]\s*[\"']?[^\s\"']{8,}")),
]  # fmt: skip
_TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".csv",
    ".yaml",
    ".yml",
    ".sha256",
    ".jsonl",
    ".html",
    ".tsv",
}


def _local_words() -> list[str]:
    words = set()
    with contextlib.suppress(Exception):  # no user name available
        words.add(getpass.getuser())
    with contextlib.suppress(Exception):
        words.add(socket.gethostname().split(".")[0])
    words |= {"mindlab", "dell"}  # development account names of this project
    return sorted(w for w in words if w and len(w) >= 4)


def _mask(s: str) -> str:
    return s if len(s) <= 12 else s[:6] + "…" + s[-3:]


def scan_text(text: str, *, extra_words: list[str] | None = None) -> list[dict[str, Any]]:
    pats = list(PATTERNS)
    words = _local_words() if extra_words is None else extra_words
    if words:
        pats.append(("LOCAL_ACCOUNT", re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(w) for w in words) + r")(?![\w-])", re.I)))  # fmt: skip
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        for cat, pat in pats:
            for m in pat.finditer(line):
                out.append({"line": i, "category": cat, "match": _mask(m.group(0))})
    return out


_DATE = re.compile(r"\b(?:19|20)\d{2}-?(?:0[1-9]|1[0-2])-?(?:0[1-9]|[12]\d|3[01])\b")


def _texts(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES:
            yield p.read_text(errors="replace")


def scan_directory(root: str | Path, *, extra_words: list[str] | None = None) -> dict[str, Any]:
    root = Path(root)
    findings: list[dict[str, Any]] = []
    files = 0
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if any(part.startswith(".") for part in p.relative_to(root).parts):
            findings.append({"file": rel, "line": 0, "category": "HIDDEN_FILE", "match": p.name})
            if p.is_dir():
                continue
        for f in scan_text(rel, extra_words=extra_words):  # file names can leak too
            findings.append({**f, "file": rel, "line": 0})
        if not p.is_file():
            continue
        files += 1
        data = p.read_bytes()
        if p.suffix.lower() == ".dcm" or data[128:132] == b"DICM":
            findings.append({"file": rel, "line": 0, "category": "DICOM_FILE", "match": p.name})
            continue
        text = data.decode("utf-8", errors="replace") if p.suffix.lower() in _TEXT_SUFFIXES else data.decode("latin-1")  # fmt: skip
        findings += [{**f, "file": rel} for f in scan_text(text, extra_words=extra_words)]
    dates = sum(len(_DATE.findall(t)) for t in _texts(root))
    cats: dict[str, int] = {}
    for f in findings:
        cats[f["category"]] = cats.get(f["category"], 0) + 1
    return {
        "schema": PRIVACY_SCAN_SCHEMA,
        "status": "CLEAN" if not findings else "FINDINGS",
        "files_scanned": files,
        "findings": findings,
        "categories": dict(sorted(cats.items())),
        "date_values_present": dates,
        "date_note": "Dates are kept as supplied by the sender (de-identification may have shifted "
        "them). They do not fail the scan; remove them before sharing beyond the data-use agreement "
        "if it requires.",
        "note": "Conservative pattern scan; not a de-identification method and not a HIPAA/GDPR "
        "compliance determination.",
    }
