"""External PET-physicist validation package (VT-EXPERT-VALIDATION-1).

  export_package(bundle, out, mode="BLINDED"|"UNBLINDED")  -> case packets + response forms
  score_responses(package, responses_dir)                    -> agreement metrics

BLINDED packets contain the evidence a physicist needs (preflight findings, quantitative
status, timing, scanner/software, reconstruction fields with trust, CT frame of reference,
reference-region status, attestation/adjudication status) but NOT VoxelTrace's verdicts,
rule statuses or reason codes that encode them. UNBLINDED packets add the verdicts.

Response forms are EMPTY. VoxelTrace never generates expert labels; scoring refuses records
marked simulated unless explicitly allowed (tests only).

Metrics per rule set (categories = the four pair verdicts):
  raw agreement, Cohen's kappa (when >= 2 categories occur), confusion matrix,
  false-safe rate   = VoxelTrace ASSESSABLE / ASSESSABLE_WITH_WARNINGS while the expert says
                      NOT_ASSESSABLE or INSUFFICIENT_INFORMATION (VoxelTrace too permissive),
  false-unsafe rate = VoxelTrace NOT_ASSESSABLE / INSUFFICIENT_INFORMATION while the expert
                      says ASSESSABLE / ASSESSABLE_WITH_WARNINGS (VoxelTrace too strict),
  VoxelTrace and expert INSUFFICIENT_INFORMATION rates, rule-level disagreement counts (rules
  the expert flags), review time (median / range).
"""

from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

SCHEMA = "VT-EXPERT-VALIDATION-1"
VERDICTS = ("ASSESSABLE", "ASSESSABLE_WITH_WARNINGS", "NOT_ASSESSABLE", "INSUFFICIENT_INFORMATION")
SAFE = {"ASSESSABLE", "ASSESSABLE_WITH_WARNINGS"}


def _read_csv(p: Path) -> list[dict]:
    return list(csv.DictReader(p.open())) if p.exists() else []


BLINDED_QUANT_FIELDS = ("subject", "timepoint", "data_origin", "uptake_min")


class BlindingLeakError(RuntimeError):
    """A BLINDED packet would contain a VoxelTrace verdict, rule ID, reason code or state."""


def forbidden_tokens(bundle: Path, preflight: dict, rulesets: list[str]) -> set[str]:
    """Every label VoxelTrace itself produced for this bundle: verdicts, rule IDs, reason
    codes, preflight states and finding codes. None may appear in a BLINDED packet."""
    from voxeltrace.trial.reasons import CATALOG

    tokens = set(VERDICTS) | set(CATALOG) | {"NOT_COMPARABLE", "COMPARABLE_WITH_WARNINGS"}
    for rs in rulesets:
        for row in _read_csv(bundle / "rules" / rs / "pair_checks.csv"):
            tokens.add(row["rule_id"])
            tokens.update(c for c in (row.get("reason_codes") or "").split(";") if c)
        for row in _read_csv(bundle / "pair_verdicts" / f"{rs}.csv"):
            tokens.update(c for c in (row.get("reason_codes") or "").split(";") if c)
            tokens.add(row.get("protocol_comparability") or "")
    for sc in preflight["scans"]:
        for s in sc["series"]:
            tokens.add(s["state"])
            tokens.update(f["reason_code"] for f in s["findings"])
    return {t for t in tokens if t and len(t) > 3}


def find_leaks(text: str, forbidden: set[str]) -> set[str]:
    import re

    return {
        t
        for t in forbidden
        if re.search(rf"(?<![A-Za-z0-9_-]){re.escape(t)}(?![A-Za-z0-9_-])", text)
    }


def redact(text: str, forbidden: set[str]) -> str:
    """Replace VoxelTrace labels inside free-text evidence (facts are kept)."""
    import re

    for t in sorted(forbidden, key=len, reverse=True):
        text = re.sub(
            rf"(?<![A-Za-z0-9_-]){re.escape(t)}(?![A-Za-z0-9_-])", "[label withheld]", text
        )
    return text


def _case_order(pairs: dict) -> list[tuple[str, str, str]]:
    """Deterministic order that does not group cases by collection or subject name."""
    import hashlib

    return sorted(pairs, key=lambda k: hashlib.sha256("|".join(k).encode()).hexdigest())


def export_package(bundle: str | Path, out: str | Path, *, mode: str = "BLINDED") -> list[Path]:
    if mode not in ("BLINDED", "UNBLINDED"):
        raise ValueError("mode must be BLINDED or UNBLINDED")
    b, out = Path(bundle), Path(out)
    if out.exists():
        raise FileExistsError(f"{out} exists")
    (out / "cases").mkdir(parents=True)
    (out / "responses").mkdir()
    pf = json.loads((b / "preflight" / "preflight.json").read_text())
    quant = _read_csv(b / "quantitative" / "timepoints.csv")
    fps = json.loads((b / "protocol" / "fingerprints.json").read_text())
    reviews = _read_csv(b / "reviews" / "review_status.csv")
    rulesets = sorted(p.name for p in (b / "rules").iterdir() if p.is_dir())
    pairs = {}
    for rs in rulesets:
        for row in _read_csv(b / "pair_verdicts" / f"{rs}.csv"):
            pairs.setdefault((row["subject"], row["baseline"], row["followup"]), {})[rs] = row[
                "verdict"
            ]
    blinded = mode == "BLINDED"
    forbidden = forbidden_tokens(b, pf, rulesets)
    order = _case_order(pairs)
    written = []
    for i, (subj, bl, fu) in enumerate(order, 1):
        verdicts = pairs[(subj, bl, fu)]
        case_id = f"CASE-{i:03d}"
        findings = [
            {"scan": sc["scan"], "state": s["state"],
             "findings": [{k: f[k] for k in ("reason_code", "severity", "field", "evidence")} for f in s["findings"]]}
            for sc in pf["scans"] if (sc.get("subject") or sc["scan"]) in (subj, None) or sc["scan"] in (bl, fu)
            for s in sc["series"]
        ]  # fmt: skip
        q_rows = [q for q in quant if q["subject"] == subj]
        refs = [r for r in reviews if r["subject"] == subj]
        if blinded:  # facts only: no VoxelTrace states, severities, codes or pass/refuse labels
            findings = [{"scan": f["scan"], "observations": [{"field": x["field"], "evidence": redact(x["evidence"], forbidden)}
                                                             for x in f["findings"]]} for f in findings]  # fmt: skip
            q_rows = [{k: q[k] for k in BLINDED_QUANT_FIELDS if k in q} for q in q_rows]
            refs = [{"timepoint": r["timepoint"], "region": r["region"],
                     "human_review_recorded": bool(r.get("review_decision"))} for r in refs]  # fmt: skip
        ev = {
            "case_id": case_id,
            "schema": SCHEMA,
            "mode": mode,
            "subject": subj,
            "timepoints": [bl, fu],
            "preflight_findings": findings,
            "quantitative": q_rows,
            "protocol_fingerprints": {k: {f: {"value": v["value"], "status": v["status"], "trust": v["trust"]}
                                          for f, v in fp["fields"].items()}
                                      for k, fp in fps.items() if k.startswith(f"{subj}/")},
            "reference_regions": refs,
            "question": "Independently of any software, would you consider this baseline/follow-up pair "
                        "quantitatively comparable under each listed standard? Answer per rule set.",
            "rule_sets": rulesets,
        }  # fmt: skip
        if mode == "UNBLINDED":
            ev["voxeltrace_verdicts"] = verdicts
            ev["voxeltrace_evidence_bundle"] = str(b)
        text = json.dumps(ev, indent=2, default=str) + "\n"
        if blinded and (leaks := find_leaks(text, forbidden)):
            raise BlindingLeakError(f"{case_id}: blinded packet would reveal {sorted(leaks)[:5]}")
        p = out / "cases" / f"{case_id}.json"
        p.write_text(text)
        form = {
            "schema": SCHEMA, "case_id": case_id, "mode": mode, "reviewer_id": "", "reviewer_role": "",
            "independent_verdicts": {rs: "" for rs in rulesets}, "confidence": "",
            "reason": "", "missing_evidence": "", "rules_disagreed": [], "disagreement_reason": "",
            "review_time_min": None, "simulated": False,
        }  # fmt: skip
        (out / "responses" / f"{case_id}.response.yaml").write_text(
            "# EMPTY reviewer form. Fill by hand; VoxelTrace never fills this.\n"
            + yaml.safe_dump(form, sort_keys=False)
        )
        written.append(p)
    key = {f"CASE-{i:03d}": {"pair": list(k), "verdicts": pairs[k]} for i, k in enumerate(order, 1)}
    # the answer key stays with the coordinator, outside the reviewer folder
    (out / "COORDINATOR_ONLY_answer_key.json").write_text(json.dumps(key, indent=2) + "\n")
    (out / "README.md").write_text(
        f"# Expert validation package ({mode})\n\nGive reviewers `cases/` and `responses/` only. "
        "`COORDINATOR_ONLY_answer_key.json` holds VoxelTrace's verdicts and must not be shared in "
        "BLINDED mode. Score with `voxeltrace score-validation`.\n"
    )
    return written


def _kappa(pairs: list[tuple[str, str]]) -> float | None:
    n = len(pairs)
    cats = {c for p in pairs for c in p}
    if n == 0 or len(cats) < 2:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[c] * cb[c] for c in cats) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 4)


# ordinal severity used for weighted agreement (0 = least restrictive)
SEVERITY = {
    "ASSESSABLE": 0,
    "ASSESSABLE_WITH_WARNINGS": 1,
    "INSUFFICIENT_INFORMATION": 2,
    "NOT_ASSESSABLE": 3,
}


def _weight(a: str, b: str) -> float:
    return 1 - abs(SEVERITY[a] - SEVERITY[b]) / (len(SEVERITY) - 1)


def _weighted_agreement(pairs: list[tuple[str, str]]) -> float | None:
    """Mean linear agreement weight (1 = identical, 0 = ASSESSABLE vs NOT_ASSESSABLE)."""
    return round(sum(_weight(a, b) for a, b in pairs) / len(pairs), 4) if pairs else None


def _weighted_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Linear-weighted Cohen's kappa over the ordinal verdict scale."""
    n = len(pairs)
    if n == 0 or len({c for p in pairs for c in p}) < 2:
        return None
    po = sum(_weight(a, b) for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[x] * cb[y] * _weight(x, y) for x in SEVERITY for y in SEVERITY) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 4)


def _false_safe(pairs: list[tuple[str, str]]) -> dict[str, int]:
    """VoxelTrace more permissive than the expert, by severity. CRITICAL: VoxelTrace
    ASSESSABLE* while the expert says NOT_ASSESSABLE (highest severity); MAJOR: VoxelTrace
    ASSESSABLE* while the expert says INSUFFICIENT_INFORMATION; MINOR: VoxelTrace
    INSUFFICIENT_INFORMATION while the expert says NOT_ASSESSABLE."""
    c = {"CRITICAL": 0, "MAJOR": 0, "MINOR": 0}
    for a, b in pairs:
        if a in SAFE and b == "NOT_ASSESSABLE":
            c["CRITICAL"] += 1
        elif a in SAFE and b == "INSUFFICIENT_INFORMATION":
            c["MAJOR"] += 1
        elif a == "INSUFFICIENT_INFORMATION" and b == "NOT_ASSESSABLE":
            c["MINOR"] += 1
    c["total"] = c["CRITICAL"] + c["MAJOR"] + c["MINOR"]
    return c


def _ii_agreement(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    """Agreement on INSUFFICIENT_INFORMATION specifically (2x2: VoxelTrace II vs expert II)."""
    both = sum(a == b == "INSUFFICIENT_INFORMATION" for a, b in pairs)
    vt_only = sum(a == "INSUFFICIENT_INFORMATION" != b for a, b in pairs)
    ex_only = sum(b == "INSUFFICIENT_INFORMATION" != a for a, b in pairs)
    either = both + vt_only + ex_only
    return {"both": both, "voxeltrace_only": vt_only, "expert_only": ex_only,
            "positive_agreement": round(2 * both / (2 * both + vt_only + ex_only), 4) if either else None}  # fmt: skip


def score_responses(
    package: str | Path, responses: str | Path | None = None, *, allow_simulated: bool = False
) -> dict[str, Any]:
    package = Path(package)
    key = json.loads((package / "COORDINATOR_ONLY_answer_key.json").read_text())
    rdir = Path(responses) if responses else package / "responses"
    recs = []
    for p in sorted(rdir.glob("*.response.yaml")):
        r = yaml.safe_load(p.read_text())
        if not r.get("reviewer_id") or not any(r.get("independent_verdicts", {}).values()):
            continue  # unfilled form
        if r.get("simulated") and not allow_simulated:
            continue
        recs.append(r)
    out: dict[str, Any] = {"schema": SCHEMA, "responses_used": len(recs), "rulesets": {}}
    rulesets = sorted({rs for v in key.values() for rs in v["verdicts"]})
    for rs in rulesets:
        pairs = [(key[r["case_id"]]["verdicts"][rs], r["independent_verdicts"][rs])
                 for r in recs if r["case_id"] in key and r["independent_verdicts"].get(rs) in VERDICTS]  # fmt: skip
        n = len(pairs)
        safe_vt = [p for p in pairs if p[0] in SAFE]
        unsafe_vt = [p for p in pairs if p[0] not in SAFE]
        out["rulesets"][rs] = {
            "n": n,
            "raw_agreement": round(sum(a == b for a, b in pairs) / n, 4) if n else None,
            "cohens_kappa": _kappa(pairs),
            "confusion": {f"{a} -> {b}": c for (a, b), c in Counter(pairs).items()},
            "false_safe_rate": round(sum(b not in SAFE for _, b in safe_vt) / len(safe_vt), 4) if safe_vt else None,
            "false_unsafe_rate": round(sum(b in SAFE for _, b in unsafe_vt) / len(unsafe_vt), 4) if unsafe_vt else None,
            "voxeltrace_ii_rate": round(sum(a == "INSUFFICIENT_INFORMATION" for a, _ in pairs) / n, 4) if n else None,
            "expert_ii_rate": round(sum(b == "INSUFFICIENT_INFORMATION" for _, b in pairs) / n, 4) if n else None,
            "weighted_agreement": _weighted_agreement(pairs),
            "weighted_kappa_linear": _weighted_kappa(pairs),
            "false_safe": _false_safe(pairs),
            "false_unsafe_count": sum(a not in SAFE and b in SAFE for a, b in pairs),
            "ii_agreement": _ii_agreement(pairs),
        }  # fmt: skip
    out["rule_level_disagreement"] = dict(
        Counter(rule for r in recs for rule in r.get("rules_disagreed") or [])
    )
    times = [float(r["review_time_min"]) for r in recs if r.get("review_time_min") is not None]
    out["review_time_min"] = (
        {"median": statistics.median(times), "min": min(times), "max": max(times)}
        if times
        else None
    )
    return out
