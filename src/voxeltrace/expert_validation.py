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


def _inter_reviewer(recs: list[dict], rs: str) -> dict[str, Any]:
    """Reviewer vs reviewer on cases answered by two or more reviewers (analysis plan, C)."""
    by_case: dict[str, list[str]] = {}
    for r in recs:
        v = r["independent_verdicts"].get(rs)
        if v in VERDICTS:
            by_case.setdefault(r["case_id"], []).append(v)
    multi = {c: v for c, v in by_case.items() if len(v) > 1}
    return {"cases_with_multiple_reviewers": len(multi),
            "unanimous": sum(len(set(v)) == 1 for v in multi.values())}  # fmt: skip


def _ii_agreement(pairs: list[tuple[str, str]]) -> dict[str, Any]:
    """Agreement on INSUFFICIENT_INFORMATION specifically (2x2: VoxelTrace II vs expert II)."""
    both = sum(a == b == "INSUFFICIENT_INFORMATION" for a, b in pairs)
    vt_only = sum(a == "INSUFFICIENT_INFORMATION" != b for a, b in pairs)
    ex_only = sum(b == "INSUFFICIENT_INFORMATION" != a for a, b in pairs)
    either = both + vt_only + ex_only
    return {"both": both, "voxeltrace_only": vt_only, "expert_only": ex_only,
            "positive_agreement": round(2 * both / (2 * both + vt_only + ex_only), 4) if either else None}  # fmt: skip


ABSTAIN = {"ABSTAIN", "UNABLE_TO_DECIDE", "UNDECIDABLE", "UNKNOWN", "CANNOT_DETERMINE"}
CONFIDENCE = {"low", "medium", "high"}
SYNTHETIC_MARK = "SYNTHETIC_TEST_ONLY"


def is_synthetic(form: dict) -> bool:
    """A reviewer form produced for software tests, never a real review."""
    return bool(form.get("simulated") or form.get("synthetic_test_only")
                or str(form.get("reviewer_id", "")).startswith(SYNTHETIC_MARK))  # fmt: skip


def load_forms(package: Path, rdir: Path, key: dict, rulesets: list[str]) -> dict[str, Any]:
    """Read and validate every response form. Returns accepted real/synthetic forms plus the
    rejected, duplicate, conflicting and empty ones with reasons; nothing is silently dropped."""
    out: dict[str, Any] = {
        "real": [],
        "synthetic": [],
        "rejected": [],
        "empty": 0,
        "duplicates": [],
        "conflicts": [],
    }
    seen: dict[tuple[str, str], dict] = {}
    for p in sorted(rdir.glob("*.response.yaml")):
        try:
            r = yaml.safe_load(p.read_text())
        except yaml.YAMLError as exc:
            out["rejected"].append(
                {"file": p.name, "reason": f"MALFORMED_YAML: {str(exc).splitlines()[0]}"}
            )
            continue
        if not isinstance(r, dict):
            out["rejected"].append({"file": p.name, "reason": "MALFORMED_FORM: not a mapping"})
            continue
        verdicts = r.get("independent_verdicts")
        if not r.get("reviewer_id") or not isinstance(verdicts, dict) or not any(verdicts.values()):
            out["empty"] += 1  # unfilled form
            continue
        problems = []
        if r.get("schema", SCHEMA) != SCHEMA:
            problems.append(f"WRONG_SCHEMA {r.get('schema')}")
        if r.get("case_id") not in key:
            problems.append(f"UNKNOWN_CASE {r.get('case_id')}")
        bad = {
            rs: v
            for rs, v in verdicts.items()
            if v and str(v).upper() not in set(VERDICTS) | ABSTAIN
        }
        if bad:
            problems.append(f"INVALID_VERDICT {bad}")
        unknown_rs = sorted(set(verdicts) - set(rulesets))
        if unknown_rs:
            problems.append(f"UNKNOWN_RULESET {unknown_rs}")
        conf = r.get("confidence")
        if conf not in (None, "") and str(conf).lower() not in CONFIDENCE:
            problems.append(f"INVALID_CONFIDENCE {conf}")
        t = r.get("review_time_min")
        if t is not None:
            try:
                if float(t) < 0:
                    problems.append("NEGATIVE_REVIEW_TIME")
            except (TypeError, ValueError):
                problems.append(f"INVALID_REVIEW_TIME {t}")
        if problems:
            out["rejected"].append({"file": p.name, "reason": "; ".join(problems)})
            continue
        r = {
            **r,
            "independent_verdicts": {rs: str(v).upper() for rs, v in verdicts.items() if v},
            "_file": p.name,
        }
        k = (str(r["reviewer_id"]), r["case_id"])
        if k in seen:
            if seen[k]["independent_verdicts"] == r["independent_verdicts"]:
                out["duplicates"].append({"file": p.name, "duplicate_of": seen[k]["_file"]})
            else:  # same reviewer, same case, different answers: neither is used
                out["conflicts"].append(
                    {"files": [seen[k]["_file"], p.name], "reviewer_id": k[0], "case_id": k[1]}
                )
                seen[k]["_conflict"] = True
            continue
        seen[k] = r
    for r in seen.values():
        if not r.get("_conflict"):
            out["synthetic" if is_synthetic(r) else "real"].append(r)
    return out


def score_responses(
    package: str | Path, responses: str | Path | None = None, *, allow_simulated: bool = False
) -> dict[str, Any]:
    """Score reviewer forms against the answer key. Real and SYNTHETIC_TEST_ONLY forms are never
    mixed: by default synthetic forms are excluded; with ``allow_simulated`` (software tests only)
    real forms must be absent and the whole result is labelled SYNTHETIC_TEST_ONLY."""
    package = Path(package)
    key = json.loads((package / "COORDINATOR_ONLY_answer_key.json").read_text())
    rdir = Path(responses) if responses else package / "responses"
    rulesets = sorted({rs for v in key.values() for rs in v["verdicts"]})
    forms = load_forms(package, rdir, key, rulesets)
    if allow_simulated and forms["real"]:
        raise ValueError("refusing to score SYNTHETIC_TEST_ONLY and real reviewer forms together")
    recs = forms["synthetic"] if allow_simulated else forms["real"]
    out: dict[str, Any] = {
        "schema": SCHEMA,
        "evidence_class": (SYNTHETIC_MARK if allow_simulated else "REAL_REVIEWER_FORMS") if recs else "NONE",
        "responses_used": len(recs), "rulesets": {},
        "forms": {"empty": forms["empty"], "rejected": forms["rejected"], "duplicates": forms["duplicates"],
                  "conflicts": forms["conflicts"],
                  "synthetic_excluded": 0 if allow_simulated else len(forms["synthetic"])},
        "missing_cases": sorted(set(key) - {r["case_id"] for r in recs}),
    }  # fmt: skip
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
            "abstentions": sum(r["independent_verdicts"].get(rs) in ABSTAIN for r in recs if r["case_id"] in key),
            "agreement_by_confidence": {
                c: (lambda ps: {"n": len(ps), "raw_agreement": round(sum(a == b for a, b in ps) / len(ps), 4) if ps else None})(
                    [(key[r["case_id"]]["verdicts"][rs], r["independent_verdicts"][rs]) for r in recs
                     if r["case_id"] in key and str(r.get("confidence", "")).lower() == c
                     and r["independent_verdicts"].get(rs) in VERDICTS])
                for c in sorted(CONFIDENCE)},
            "inter_reviewer": _inter_reviewer(recs, rs),
        }  # fmt: skip
    out["rule_level_disagreement"] = dict(
        Counter(rule for r in recs for rule in r.get("rules_disagreed") or [])
    )
    times = [float(r["review_time_min"]) for r in recs if r.get("review_time_min") is not None]
    out["review_time_min"] = (
        {"median": statistics.median(times), "min": min(times), "max": max(times), "n": len(times),
         "total": round(sum(times), 2)}
        if times
        else None
    )  # fmt: skip
    out["confidence_counts"] = dict(
        Counter(str(r.get("confidence") or "missing").lower() for r in recs)
    )
    return out
