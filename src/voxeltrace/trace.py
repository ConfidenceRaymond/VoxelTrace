"""Evidence trust trace (VT-EVIDENCE-TRACE-1): answers "why did VoxelTrace say this pair is not
comparable?" without reading source code.

  evidence_trace(bundle) -> rows     one row per (rule set, pair, non-PASS check, reason)
  explain_pair(bundle, subject, ruleset=None) -> text

Read-only join of files already in the evidence bundle; nothing is recomputed:

  verdict + rule + status + observed/expected   rules/<rs>/trial_audit.json
  reason code, field, detail, evidence basis     same (pair check reasons)
  protocol field value, trust level, DICOM source protocol/fingerprints.json (both scans)
  raw-metadata findings for the field            preflight/preflight.json (both scans)
  plain language + remediation                   remediation matrix

Trust levels: LEVEL_A structured standard DICOM attribute; LEVEL_C site attestation; LEVEL_D
vendor free text; LEVEL_U unsupported; NONE missing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TRACE_SCHEMA = "VT-EVIDENCE-TRACE-1"
# names used by the protocol-identity comparison -> protocol fingerprint field names
PROTO_TO_FP = {"manufacturer": "manufacturer", "scanner_model": "scanner_model", "image_units": "units",
               "decay_correction": "decay_correction", "correction_state": "corrections",
               "voxel_size": "voxel_size_mm", "reconstruction_method": "reconstruction_method",
               "iterations": "iterations", "subsets": "subsets", "time_of_flight": "time_of_flight",
               "psf_resolution_modelling": "psf_resolution_modelling", "post_filter": "filter_kernel"}  # fmt: skip


def _rule_fields() -> dict[str, list[str]]:
    from voxeltrace.evidence.fingerprint import FIELD_POLICY

    out: dict[str, list[str]] = {}
    for field, (_, _, rules, _) in FIELD_POLICY.items():
        for r in rules:
            out.setdefault(r, []).append(field)
    return out


def _fp_text(fp: dict[str, Any] | None, field: str) -> str:
    if not fp or field not in fp.get("fields", {}):
        return f"{field}: no fingerprint"
    f = fp["fields"][field]
    v = f.get("value")
    return f"{field}={v if v is not None else '-'} [{f.get('status')}, trust {f.get('trust')}, source {f.get('source') or '-'}]"


def evidence_trace(bundle: str | Path) -> list[dict[str, Any]]:
    from voxeltrace.remediation import customer_wording, remediation_matrix

    b = Path(bundle)
    rem = {r["code"]: r["remediation"] for r in remediation_matrix()}
    fps = (
        json.loads((b / "protocol" / "fingerprints.json").read_text())
        if (b / "protocol" / "fingerprints.json").exists()
        else {}
    )
    pf = (
        json.loads((b / "preflight" / "preflight.json").read_text())
        if (b / "preflight" / "preflight.json").exists()
        else {"scans": []}
    )
    findings: dict[tuple[str, str], list[dict]] = {}
    for sc in pf["scans"]:
        key = (sc.get("subject") or sc.get("scan"), sc.get("scan"))
        findings[key] = sc.get("findings", []) + [
            f for s in sc.get("series", []) for f in s.get("findings", [])
        ]
    rule_fields = _rule_fields()
    rows = []
    for rs_dir in sorted((b / "rules").iterdir()):
        audit = json.loads((rs_dir / "trial_audit.json").read_text())
        for p in audit["pairs"]:
            subj, bl, fu = p["pair"]["subject_id"], p["pair"]["baseline"], p["pair"]["followup"]
            fb, ff = fps.get(f"{subj}/{bl}"), fps.get(f"{subj}/{fu}")
            for c in p["checks"]:
                if c["status"] == "PASS":
                    continue
                observed = c.get("observed")
                if c["rule_id"] in (
                    "VT-PROTOCOL-IDENTITY",
                    "EANM-SAME-SYSTEM-SETTINGS",
                ) and isinstance(observed, dict):
                    fields = [PROTO_TO_FP.get(k, k) for k, v in observed.items() if v != "SAME"]
                else:
                    fields = rule_fields.get(c["rule_id"], [])
                for r in c.get("reasons") or [{"code": f"{c['rule_id']} {c['status']}", "field": "", "detail": "",
                                               "evidence_basis": "decided measurement", "confidence": ""}]:  # fmt: skip
                    raw = [f"{tp}: {f['reason_code']} {f['field']}: {f['evidence']} ({f['source']})"
                           for tp in (bl, fu) for f in findings.get((subj, tp), [])
                           if f["reason_code"] in (r.get("field"), r.get("code"))]  # fmt: skip
                    rows.append({
                        "ruleset": rs_dir.name, "subject": subj, "baseline": bl, "followup": fu,
                        "verdict": p["verdict"], "rule_id": c["rule_id"], "impact": c["impact"], "status": c["status"],
                        "observed": json.dumps(observed, default=str, sort_keys=True), "expected": c.get("expected", ""),
                        "reason_code": r["code"], "reason_field": r.get("field") or "", "reason_detail": r.get("detail") or "",
                        "evidence_basis": r.get("evidence_basis") or "", "confidence": r.get("confidence") or "",
                        "baseline_evidence": " | ".join(_fp_text(fb, f) for f in fields),
                        "followup_evidence": " | ".join(_fp_text(ff, f) for f in fields),
                        "raw_metadata_findings": " | ".join(raw),
                        "plain_language": customer_wording(r["code"]),
                        "remediation": rem.get(r["code"], "see the reason detail"),
                    })  # fmt: skip
    return rows


def explain_pair(bundle: str | Path, subject: str, ruleset: str | None = None) -> str:
    rows = [
        r
        for r in evidence_trace(bundle)
        if r["subject"] == subject and (ruleset is None or r["ruleset"] == ruleset)
    ]
    if not rows:
        audits = sorted((Path(bundle) / "rules").iterdir())
        known = {
            p["pair"]["subject_id"]
            for d in audits
            for p in json.loads((d / "trial_audit.json").read_text())["pairs"]
        }
        if subject not in known:
            return f"{subject}: no pair in this bundle"
        return f"{subject}: every rule PASSED in the selected rule set(s) (no blocking or warning evidence)"
    L = []
    for rs in sorted({r["ruleset"] for r in rows}):
        sub = [r for r in rows if r["ruleset"] == rs]
        L += [f"{subject} {sub[0]['baseline']} -> {sub[0]['followup']} [{rs}]: {sub[0]['verdict']}"]
        for r in sub:
            L += [f"  {r['rule_id']} ({r['impact']}) {r['status']}: expected {r['expected']}",
                  f"    reason {r['reason_code']} {r['reason_field']}: {r['reason_detail']} "
                  f"[basis: {r['evidence_basis'] or '-'}; confidence {r['confidence'] or '-'}]"]  # fmt: skip
            if r["baseline_evidence"]:
                L += [
                    f"    baseline evidence: {r['baseline_evidence']}",
                    f"    follow-up evidence: {r['followup_evidence']}",
                ]
            if r["raw_metadata_findings"]:
                L.append(f"    raw metadata: {r['raw_metadata_findings']}")
            L += [
                f"    in plain language: {r['plain_language']}",
                f"    what can fix it: {r['remediation']}",
            ]
    return "\n".join(L)
