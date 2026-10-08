#!/usr/bin/env python3
"""Cross-rule-set report for the trial demo (reads existing audit outputs; computes nothing new).

Reads ../outputs/synthetic_comparability/audit_<ruleset>/trial_audit.json for QIBA, PERCIST
and EANM and writes ../outputs/synthetic_comparability/{TRIAL_AUDIT_REPORT.md,
failures_classified.csv, reference_regions_real.csv}.

REAL and SYNTHETIC_PERTURBATION findings are reported separately and never pooled.
Failure classes:
  EXPECTED_SYNTHETIC_PERTURBATION  rule listed in the PRE-DECLARED expectation for the
                                   perturbation kind (perturb.EXPECTED, declared for QIBA;
                                   VT-* prerequisites are shared by every rule set)
  SYNTHETIC_PERTURBATION_CONSISTENT  failure of a rule that targets what the perturbation
                                   changed, in a rule set without pre-declared expectations
                                   (POST-HOC consistency judgement, labelled as such)
  MISSING_DATA_SYNTHETIC_CONSTRUCTION  information absent because of how the synthetic
                                   follow-up was built (e.g. no CT, so no follow-up
                                   reference region)
  TECHNICAL / MISSING_DATA         anything else (FAIL / UNKNOWN)
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter

from voxeltrace.config import REPO_ROOT
from voxeltrace.trial.perturb import EXPECTED
from voxeltrace.trial.summary import compact_observed

OUT = REPO_ROOT.parent / "outputs" / "synthetic_comparability"
RULESETS = ("qiba-fdg-1.14", "percist-1.0", "eanm-fdg-2.0")
VERDICTS = ("ASSESSABLE", "ASSESSABLE_WITH_WARNINGS", "NOT_ASSESSABLE", "INSUFFICIENT_INFORMATION")
# What each perturbation changes (from trial/perturb.py), used ONLY for the post-hoc label.
TARGETS = {
    "identity": (),
    "recon_blur": ("PROTOCOL-IDENTITY", "SAME-SYSTEM"),
    "recon_metadata": ("PROTOCOL-IDENTITY", "SAME-SYSTEM"),
    "uptake_violation": ("UPTAKE",),
    "missing_dose": ("SUV-BOTH", "UPTAKE", "DOSE"),
    "anonymization_loss": ("PROTOCOL-IDENTITY", "SAME-SYSTEM", "SCANNER-SOFTWARE"),
    "correction_mismatch": ("PROTOCOL-IDENTITY", "SAME-SYSTEM"),
}


def kind_of(subject: str) -> str | None:
    return subject.split("-", 2)[2].lower() if subject.startswith("DEMO-") else None


def classify(rs: str, subject: str, synthetic: bool, check: dict, tps: dict) -> str:
    rid, status = check["rule_id"], check["status"]
    codes = {r["code"] for r in check["reasons"]}
    kind = kind_of(subject)
    if synthetic and kind:
        declared = set(EXPECTED[kind][1])
        if rid in declared and (rs == "qiba-fdg-1.14" or rid.startswith("VT-")):
            return "EXPECTED_SYNTHETIC_PERTURBATION"
        fu = tps.get((subject, "FOLLOWUP"), {})
        if "REFERENCE_AUTO_NOT_FOUND" in codes and fu.get("synthetic_perturbation"):
            return "MISSING_DATA_SYNTHETIC_CONSTRUCTION"
        not_quantified = any(
            "no quantitative SUV" in r["detail"] and "FOLLOWUP" in r["detail"]
            for r in check["reasons"]
        )
        if any(t in rid for t in TARGETS[kind]) or not_quantified:
            return "SYNTHETIC_PERTURBATION_CONSISTENT (post hoc; not pre-declared)"
    return "TECHNICAL" if status == "FAIL" else "MISSING_DATA"


def main() -> int:
    audits = {
        rs: json.loads((OUT / f"audit_{rs}" / "trial_audit.json").read_text()) for rs in RULESETS
    }
    lines = [
        "# Trial audit report: VOXELTRACE-DEMO-001",
        "",
        "RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. Comparability/assessability only; no "
        "biological or treatment response is assessed. BASELINE scans are real public data; "
        "every FOLLOWUP is a SYNTHETIC_PERTURBATION copy, not a real follow-up scan.",
        "",
        "## Verdict distributions (all pairs are synthetic-follow-up pairs)",
        "",
        "| Rule set | " + " | ".join(VERDICTS) + " | reviews applied |",
        "|---|" + "---|" * (len(VERDICTS) + 1),
    ]
    for rs, a in audits.items():
        c = Counter(p["verdict"] for p in a["pairs"])
        lines.append(
            f"| {rs} | "
            + " | ".join(str(c.get(v, 0)) for v in VERDICTS)
            + f" | {a['reference_reviews_applied']} |"
        )

    # ---------------------------------------------------------------- REAL
    a0 = audits["percist-1.0"]
    real_pairs = [
        p for rs in RULESETS for p in audits[rs]["pairs"] if not p["synthetic_perturbation"]
    ]
    lines += [
        "",
        "## REAL DATA FINDINGS",
        "",
        f"Real pairs: {len(real_pairs)} (no real follow-up scans).",
        "",
    ]
    seen: dict[str, list[str]] = {}
    for t in a0["timepoints"]:
        if t["synthetic_perturbation"]:
            continue
        seen.setdefault(t["pet_series_pseudonym"], []).append(f"{t['subject_id']}/{t['timepoint']}")
    lines.append(
        f"Real scan entries: {sum(len(v) for v in seen.values())}, from {len(seen)} distinct "
        "real PET series (the 7 DEMO baselines are links to the same real scan)."
    )
    ref_rows = []
    for pseudo, keys in seen.items():
        t = next(x for x in a0["timepoints"] if x["pet_series_pseudonym"] == pseudo)
        sul = t["sul"].get("LBMJAMES128") or {}
        anon = t.get("anonymization") or {}
        lines += [
            "",
            f"### {t['subject_id']} (PET series {pseudo}; appears as {len(keys)} scan entr"
            f"{'y' if len(keys) == 1 else 'ies'})",
            f"- strict SUVbw: {t['suv_status']}; uptake "
            f"{round(t['uptake_s'] / 60, 2) if t['uptake_s'] else None} min; "
            f"SUL (LBMJAMES128): {sul.get('status')}"
            + (
                f" ({', '.join(r['code'] for r in sul.get('refusals', []))})"
                if sul.get("refusals")
                else ""
            ),
            f"- timepoint reasons: {sorted({r['code'] for r in t['reasons']}) or 'none'}",
        ]
        for r in t["reasons"]:
            lines.append(f"  - {r['code']}: {r['detail'][:200]}")
        if anon:
            lines.append(
                "- anonymization: de-identification declared "
                f"{anon.get('deidentification_declared')}"
                f", method {anon.get('deidentification_method')!r}; summary {anon.get('summary')}"
            )
            for r in anon.get("timing_crosschecks", []):
                lines.append(f"  - timing cross-check {r['code']}: {r['detail'][:200]}")
        for region, key in (("LIVER", "liver"), ("BLOOD_POOL", "blood_pool")):
            r = t.get(key) or {}
            ref_rows.append(
                {
                    "subject": t["subject_id"],
                    "pet_series": pseudo,
                    "region": region,
                    "status": r.get("status"),
                    "review": r.get("review_decision"),
                    "reviewer": r.get("reviewer"),
                    "voxel_count": r.get("voxel_count"),
                    "volume_ml": r.get("volume_ml"),
                    "suv_mean": r.get("suv_mean"),
                    "suv_sd": r.get("suv_sd"),
                    "cov": r.get("cov"),
                    "suv_max": r.get("suv_max"),
                    "sul_mean": r.get("sul_mean"),
                    "sul_sd": r.get("sul_sd"),
                    "proposal_sha256": r.get("proposal_sha256"),
                }
            )

    # ---------------------------------------------------------------- SYNTHETIC
    lines += ["", "## SYNTHETIC_PERTURBATION FINDINGS", ""]
    lines += [
        "### QIBA vs the PRE-DECLARED expectations (perturb.EXPECTED)",
        "",
        "| subject | expected | observed | expected blocking rules present | match |",
        "|---|---|---|---|---|",
    ]
    ok_all = True
    for p in audits["qiba-fdg-1.14"]["pairs"]:
        kind = kind_of(p["pair"]["subject_id"])
        exp_v, exp_rules = EXPECTED[kind]
        blocking = {
            c["rule_id"]
            for c in p["checks"]
            if c["impact"] == "blocking" and c["status"] in ("FAIL", "UNKNOWN")
        }
        ok = p["verdict"] == exp_v and set(exp_rules) <= blocking
        ok_all &= ok
        lines.append(
            f"| {p['pair']['subject_id']} | {exp_v} | {p['verdict']} | "
            f"{', '.join(exp_rules) or '-'} | {'yes' if ok else 'NO'} |"
        )
    lines += [
        "",
        "PERCIST and EANM have no pre-declared expected verdicts; their synthetic outcomes are "
        "reported as observed and classified below (post-hoc labels are marked).",
    ]
    rows = []
    for rs, a in audits.items():
        tps = {(t["subject_id"], t["timepoint"]): t for t in a["timepoints"]}
        for p in a["pairs"]:
            for c in p["checks"]:
                if c["status"] not in ("FAIL", "UNKNOWN"):
                    continue
                rows.append(
                    {
                        "ruleset": rs,
                        "data_origin": "SYNTHETIC_PERTURBATION"
                        if p["synthetic_perturbation"]
                        else "REAL",
                        "subject": p["pair"]["subject_id"],
                        "pair": f"{p['pair']['baseline']}->{p['pair']['followup']}",
                        "verdict": p["verdict"],
                        "rule_id": c["rule_id"],
                        "impact": c["impact"],
                        "status": c["status"],
                        "observed": compact_observed(c["observed"]),
                        "condition": c["expected"],
                        "reason_codes": ";".join(sorted({r["code"] for r in c["reasons"]})),
                        "reason_detail": " | ".join(
                            dict.fromkeys(r["detail"] for r in c["reasons"])
                        )[:400],
                        "classification": classify(
                            rs, p["pair"]["subject_id"], p["synthetic_perturbation"], c, tps
                        ),
                    }
                )
    for rs in RULESETS:
        lines += [
            "",
            f"### {rs}: every FAIL / UNKNOWN check",
            "",
            "| subject | rule | impact | status | observed | condition | reasons | class |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            if r["ruleset"] != rs:
                continue
            lines.append(
                f"| {r['subject']} | {r['rule_id']} | {r['impact']} | {r['status']} | "
                f"{r['observed'][:70]} | {r['condition'][:60]} | {r['reason_codes'] or '-'} | "
                f"{r['classification']} |"
            )
    with (OUT / "failures_classified.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with (OUT / "reference_regions_real.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ref_rows[0]))
        w.writeheader()
        w.writerows(ref_rows)
    lines += [
        "",
        "## Files",
        "",
        "Per rule set (audit_<ruleset>/): trial_audit.json, subject_timepoint_matrix.csv, "
        "pair_verdicts.csv, pair_checks.csv, rule_summary.csv, failure_reasons.csv, "
        "site_summary.json, reference_regions.csv, AUDIT_REPORT.md. Cross-rule-set: "
        "failures_classified.csv, reference_regions_real.csv, this report.",
    ]
    (OUT / "TRIAL_AUDIT_REPORT.md").write_text("\n".join(lines) + "\n")
    print("QIBA synthetic verdicts match pre-declared expectations:", ok_all)
    print(json.dumps(Counter(r["classification"] for r in rows), indent=1))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
