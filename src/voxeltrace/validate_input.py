"""Intake decision for a submitted folder, before any audit (read-only, headers only).

  ACCEPT_FOR_AUDIT       no finding above INFO
  ACCEPT_WITH_WARNINGS   WARNING findings only: the audit runs; the warnings are reported
  NEEDS_REEXPORT         a BLOCKING or NEEDS_REVIEW finding the site can address by
                         re-exporting or supplying records (missing dose, time, weight,
                         ambiguous series, secondary capture, unrecognised tracer name, ...)
  UNSUPPORTED            outside what VoxelTrace audits: a known non-FDG tracer
                         (PSMA / amyloid / tau), or units or decay correction without a
                         documented strict-SUV path (UNSUPPORTED_UNITS, UNSUPPORTED_DECAY_CORRECTION)

Built only on preflight (VT-PREFLIGHT-1) findings plus the tracer name; it never computes
SUV and never changes a preflight finding. The folder decision is the worst scan decision.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

DECISIONS = ("ACCEPT_FOR_AUDIT", "ACCEPT_WITH_WARNINGS", "NEEDS_REEXPORT", "UNSUPPORTED")
UNSUPPORTED_CODES = {"UNSUPPORTED_UNITS", "UNSUPPORTED_DECAY_CORRECTION"}
EXIT_CODES = {
    "ACCEPT_FOR_AUDIT": 0,
    "ACCEPT_WITH_WARNINGS": 0,
    "NEEDS_REEXPORT": 2,
    "UNSUPPORTED": 3,
}


def tracer_class(name: str | None) -> str:
    """Same patterns as the census (scripts/census_v3_public_pet.py)."""
    if not name:
        return "UNKNOWN"
    s = name.casefold()
    for cls, pat in (
        ("FDG", r"fdg|fluorodeoxyglucose|fludeoxyglucose"),
        ("PSMA", r"psma|dcfpyl|pylarify|gozetotide|piflufolastat|1007"),
        ("AMYLOID", r"florbetapir|florbetaben|flutemetamol|pittsburgh|\bpib\b|nav4694|amyvid"),
        ("TAU", r"flortaucipir|av.?1451|mk.?6240|pi.?2620|tauvid"),
    ):
        if re.search(pat, s):
            return cls
    return "OTHER"


def classify_scan(scan: Any) -> dict[str, Any]:
    findings = list(scan.findings) + [f for s in scan.series for f in s.findings]
    reasons = [
        {
            "code": f.reason_code,
            "severity": f.severity,
            "field": f.field,
            "remediation": f.remediation,
        }
        for f in findings
        if f.severity != "INFO"
    ]
    tracers = {s.facts.get("tracer") for s in scan.series if s.facts.get("tracer")}
    for t in sorted(tracers):
        cls = tracer_class(t)
        if cls in ("PSMA", "AMYLOID", "TAU"):
            reasons.append({"code": "NON_FDG_TRACER", "severity": "UNSUPPORTED", "field": "Radiopharmaceutical",
                            "remediation": f"{t} ({cls}): the FDG rule sets do not apply; no tracer-specific rule set exists"})  # fmt: skip
        elif cls == "OTHER":
            reasons.append({"code": "TRACER_NOT_RECOGNISED", "severity": "BLOCKING", "field": "Radiopharmaceutical",
                            "remediation": f"'{t}' is not recognised as FDG; confirm the tracer or re-export with "
                            "RadiopharmaceuticalCodeSequence populated"})  # fmt: skip
    sev = {r["severity"] for r in reasons}
    codes = {r["code"] for r in reasons}
    if "UNSUPPORTED" in sev or codes & UNSUPPORTED_CODES:
        decision = "UNSUPPORTED"
    elif sev & {"BLOCKING", "NEEDS_REVIEW"}:
        decision = "NEEDS_REEXPORT"
    elif "WARNING" in sev:
        decision = "ACCEPT_WITH_WARNINGS"
    else:
        decision = "ACCEPT_FOR_AUDIT"
    return {"subject": scan.subject, "scan": scan.scan, "preflight_state": scan.state, "decision": decision,
            "reasons": sorted(reasons, key=lambda r: (r["severity"], r["code"]))}  # fmt: skip


def validate_input(path: str | Path) -> dict[str, Any]:
    from voxeltrace.preflight.batch import preflight_batch

    path = Path(path)
    out: dict[str, Any] = {"schema": "VT-VALIDATE-INPUT-1", "input": path.name, "layout": []}
    if (path / "trial.yaml").exists():
        from voxeltrace.trial.discovery import discover_trial

        try:
            layout = discover_trial(path)
            single = sorted(s for s, tps in layout.scans.items() if len(tps) < 2)
            if single:
                out["layout"].append({"code": "SINGLE_TIMEPOINT_SUBJECTS", "severity": "WARNING",
                                      "detail": f"{len(single)} subject(s) have no follow-up to pair: {single[:10]}"})  # fmt: skip
        except Exception as exc:  # noqa: BLE001 - report any config error as an intake finding
            out["layout"].append(
                {"code": "TRIAL_CONFIG_INVALID", "severity": "BLOCKING", "detail": str(exc)}
            )
    scans = [classify_scan(sc) for sc in preflight_batch(path).scans]
    out["scans"] = scans
    decisions = [s["decision"] for s in scans]
    if any(x["severity"] == "BLOCKING" for x in out["layout"]):
        decisions.append("NEEDS_REEXPORT")
    elif out["layout"]:
        decisions.append("ACCEPT_WITH_WARNINGS")
    if not scans:
        decisions.append("NEEDS_REEXPORT")
        out["layout"].append(
            {"code": "NO_SCANS_FOUND", "severity": "BLOCKING", "detail": "no DICOM files found"}
        )
    out["decision"] = max(decisions, key=DECISIONS.index)
    out["counts"] = {d: Counter(decisions)[d] for d in DECISIONS}
    out["note"] = (
        "Intake check only: no SUV is computed and no verdict is produced. RESEARCH PROTOTYPE."
    )
    return out


def format_text(r: dict[str, Any]) -> str:
    L = [
        f"{r['input']}: {r['decision']}",
        f"  scans: {', '.join(f'{k} {v}' for k, v in r['counts'].items() if v)}",
    ]
    L += [f"  layout {x['severity']} {x['code']}: {x['detail']}" for x in r["layout"]]
    for s in r["scans"]:
        L.append(f"  {s['subject'] or '-'} / {s['scan']}: {s['decision']}")
        L += [f"      {x['severity']:12} {x['code']}: {x['remediation']}" for x in s["reasons"]
              if x["severity"] in ("UNSUPPORTED", "BLOCKING", "NEEDS_REVIEW")]  # fmt: skip
        warn = sorted({x["code"] for x in s["reasons"] if x["severity"] == "WARNING"})
        if warn:
            L.append(f"      warnings: {', '.join(warn)}")
    return "\n".join(L)
