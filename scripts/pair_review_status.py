#!/usr/bin/env python3
"""Re-run the trial audit for a real-validation namespace and report what the human
reference review has (or has not yet) unlocked. No AI; no review is created here.

  pair_review_status.py <outputs namespace>   e.g. acrin_longitudinal_168

Reads <ns>/trial (trial.yaml points to <ns>/reference_review/reference_review.yaml),
rewrites <ns>/audit_<ruleset>/ and writes <ns>/review_status.json with, per pair:
  liver SUL baseline / follow-up, absolute difference, difference as % of the larger value,
  PERCIST liver-stability status, verdicts per rule set, and the REFERENCE / PROTOCOL /
  OVERALL assessability layers.
"""

from __future__ import annotations

import json
import sys

from voxeltrace.config import REPO_ROOT
from voxeltrace.trial.audit import run_trial_audit
from voxeltrace.trial.export import export_audit
from voxeltrace.trial.layers import assessability_layers

RULESETS = ("percist-1.0", "qiba-fdg-1.14", "eanm-fdg-2.0")


def main(argv: list[str]) -> int:
    ns = REPO_ROOT.parent / "outputs" / argv[1]
    trial = ns / "trial"
    review_file = ns / "reference_review" / "reference_review.yaml"
    audits = {}
    for rs in RULESETS:
        a = run_trial_audit(trial, ruleset=rs, qc_dir=ns / "reference_review" / "qc")
        export_audit(a, ns / f"audit_{rs}")
        audits[rs] = a
    out = {
        "review_file": str(review_file),
        "review_file_present": review_file.exists(),
        "reviews_applied": audits["percist-1.0"].reference_reviews_applied,
        "pairs": {},
    }
    tps = {(t.subject_id, t.timepoint): t for t in audits["percist-1.0"].timepoints}
    for p in audits["percist-1.0"].pairs:
        b, f = tps[(p.pair.subject_id, p.pair.baseline)], tps[(p.pair.subject_id, p.pair.followup)]
        lb = b.liver.sul_mean if b.liver and b.liver.status == "COMPUTED" else None
        lf = f.liver.sul_mean if f.liver and f.liver.status == "COMPUTED" else None
        liver_check = next(c for c in p.checks if c.rule_id == "PERCIST-LIVER-SUL-STABILITY")
        entry = {
            "liver_status": [
                b.liver.status if b.liver else None,
                f.liver.status if f.liver else None,
            ],
            "liver_review": [
                b.liver.review_decision if b.liver else None,
                f.liver.review_decision if f.liver else None,
            ],
            "liver_sul_baseline": lb,
            "liver_sul_followup": lf,
            "liver_abs_difference": abs(lf - lb) if lb is not None and lf is not None else None,
            "liver_pct_of_larger": 100 * abs(lf - lb) / max(lb, lf)
            if lb is not None and lf is not None
            else None,
            "percist_liver_stability": liver_check.status,
            "percist_liver_reasons": sorted({r.code for r in liver_check.reasons}),
            "verdicts": {},
            "layers": {},
        }
        for rs, a in audits.items():
            pr = next(x for x in a.pairs if x.pair.subject_id == p.pair.subject_id)
            entry["verdicts"][rs] = pr.verdict
            entry["layers"][rs] = assessability_layers(pr)
        out["pairs"][p.pair.subject_id] = entry
    (ns / "review_status.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
