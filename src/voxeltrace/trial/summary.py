"""Subject x timepoint matrix and site-level comparability summary."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from voxeltrace.trial.audit import TrialAudit

VERDICTS = ("ASSESSABLE", "ASSESSABLE_WITH_WARNINGS", "NOT_ASSESSABLE", "INSUFFICIENT_INFORMATION")


def matrix(audit: TrialAudit) -> list[dict[str, Any]]:
    rows = []
    by_pair = {(p.pair.subject_id, p.pair.followup): p for p in audit.pairs}
    for tp in audit.timepoints:
        p = by_pair.get((tp.subject_id, tp.timepoint))
        rows.append(
            {
                "subject": tp.subject_id,
                "timepoint": tp.timepoint,
                "site": tp.site_id,
                "synthetic_perturbation": tp.synthetic_perturbation or "",
                "scanner": tp.scanner,
                "software": tp.software,
                "reconstruction": tp.reconstruction,
                "suv_status": tp.suv_status,
                "uptake_min": round(tp.uptake_s / 60, 2) if tp.uptake_s else None,
                "pair_verdict": p.verdict
                if p
                else (
                    "BASELINE"
                    if any(
                        q.pair.subject_id == tp.subject_id and q.pair.baseline == tp.timepoint
                        for q in audit.pairs
                    )
                    else "NO_PAIR"
                ),
                "reason_codes": ";".join(sorted({r.code for r in p.reasons})) if p else "",
                "failed_rules": ";".join(c.rule_id for c in p.checks if c.status == "FAIL")
                if p
                else "",
            }
        )
    return rows


def site_summary(audit: TrialAudit) -> dict[str, Any]:
    tps = {(t.subject_id, t.timepoint): t for t in audit.timepoints}
    out: dict[str, Any] = {
        "scans_analyzed": len(audit.timepoints),
        "pairs_analyzed": len(audit.pairs),
        "verdicts": dict(Counter(p.verdict for p in audit.pairs)),
        "synthetic_pairs": sum(1 for p in audit.pairs if p.synthetic_perturbation),
    }
    for dim in ("site", "scanner", "software", "reconstruction"):
        table: dict[str, Counter] = defaultdict(Counter)
        for p in audit.pairs:
            f = tps[(p.pair.subject_id, p.pair.followup)]
            key = {
                "site": f.site_id,
                "scanner": f.scanner,
                "software": f.software,
                "reconstruction": f.reconstruction,
            }[dim] or "UNKNOWN"
            table[str(key)][p.verdict] += 1
        out[f"by_{dim}"] = {k: dict(v) for k, v in sorted(table.items())}
    reasons: Counter = Counter()
    failures: Counter = Counter()
    for p in audit.pairs:
        for code in {r.code for r in p.reasons}:
            reasons[code] += 1
        for c in p.checks:
            if c.status == "FAIL":
                failures[c.rule_id] += 1
    out["insufficient_information_by_reason"] = dict(reasons.most_common())
    out["failures_by_rule"] = dict(failures.most_common())
    return out
