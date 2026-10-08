#!/usr/bin/env python3
"""v2 synthetic demo report: observed vs the FROZEN expectation manifest.

Reads ../outputs/synthetic_comparability/v2/audit_<ruleset>/trial_audit.json and the frozen
manifest (configs/expectations/synthetic_demo_v2.json; its sha256 is checked against the copy
in outputs). Writes to ../outputs/synthetic_comparability/:
  pair_verdicts.csv, rule_results.csv, liver_reference_results.csv,
  failure_reason_summary.csv, TRIAL_AUDIT_REPORT.md
The v1 report is kept as TRIAL_AUDIT_REPORT_v1.md. Computes nothing new; never edits the
manifest. REAL BASELINE SOURCE and SYNTHETIC FOLLOW-UP FINDINGS are separate sections.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from collections import Counter

from voxeltrace.config import REPO_ROOT
from voxeltrace.trial.summary import compact_observed

OUT = REPO_ROOT.parent / "outputs" / "synthetic_comparability"
MANIFEST = REPO_ROOT / "configs" / "expectations" / "synthetic_demo_v2.json"
RULESETS = ("percist-1.0", "qiba-fdg-1.14", "eanm-fdg-2.0")


def sha(p) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write_csv(name: str, rows: list[dict]) -> None:
    with (OUT / name).open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def r4(v):
    return None if v is None else round(v, 4)


def main() -> int:
    msha = sha(MANIFEST)
    if msha != sha(OUT / "expectation_manifest.json"):
        raise SystemExit("expectation manifest copy differs from the committed manifest")
    exp = json.loads(MANIFEST.read_text())["pairs"]
    audits = {
        rs: json.loads((OUT / "v2" / f"audit_{rs}" / "trial_audit.json").read_text())
        for rs in RULESETS
    }
    a = audits["percist-1.0"]
    tps = {(t["subject_id"], t["timepoint"]): t for t in a["timepoints"]}

    pair_rows, rule_rows, liver_rows, fail_rows = [], [], [], []
    mismatches = []
    for subj, e in exp.items():
        b, f = tps[(subj, "BASELINE")], tps[(subj, "FOLLOWUP")]
        lb, lf = b.get("liver") or {}, f.get("liver") or {}
        row = {
            "data_origin": "SYNTHETIC_PERTURBATION (real baseline + synthetic follow-up)",
            "subject": subj,
            "perturbation": e["perturbation"],
            "site": e["site"],
        }
        for rs in RULESETS:
            p = next(p for p in audits[rs]["pairs"] if p["pair"]["subject_id"] == subj)
            ev = e["rulesets"][rs]
            row[f"{rs}_expected"] = ev["expected_verdict"]
            row[f"{rs}_observed"] = p["verdict"]
            if p["verdict"] != ev["expected_verdict"]:
                mismatches.append((subj, rs, "verdict", ev["expected_verdict"], p["verdict"]))
            for c in p["checks"]:
                want = ev["rule_status"].get(c["rule_id"])
                ok = want == c["status"]
                if not ok:
                    mismatches.append((subj, rs, c["rule_id"], want, c["status"]))
                rule_rows.append(
                    {
                        "subject": subj,
                        "perturbation": e["perturbation"],
                        "ruleset": rs,
                        "rule_id": c["rule_id"],
                        "impact": c["impact"],
                        "expected_status": want,
                        "observed_status": c["status"],
                        "match": ok,
                        "observed": compact_observed(c["observed"]),
                        "condition": c["expected"],
                        "reason_codes": ";".join(sorted({r["code"] for r in c["reasons"]})),
                    }
                )
                if c["status"] != "PASS":
                    fail_rows.append(
                        {
                            "subject": subj,
                            "ruleset": rs,
                            "rule_id": c["rule_id"],
                            "status": c["status"],
                            "class": (
                                "EXPECTED_SYNTHETIC_PERTURBATION (pre-declared)"
                                if ok
                                else "UNEXPECTED (not pre-declared)"
                            ),
                            "reason_codes": ";".join(sorted({r["code"] for r in c["reasons"]})),
                            "reason_detail": " | ".join(
                                dict.fromkeys(r["detail"] for r in c["reasons"])
                            )[:300],
                        }
                    )
        proto = next(
            c
            for p in audits["percist-1.0"]["pairs"]
            if p["pair"]["subject_id"] == subj
            for c in p["checks"]
            if c["rule_id"] == "VT-PROTOCOL-IDENTITY"
        )
        diffs = {}
        if isinstance(proto["observed"], dict):
            diffs = {k: v for k, v in proto["observed"].items() if v != "SAME"}
        lsb, lsf = lb.get("sul_mean"), lf.get("sul_mean")
        row.update(
            liver_sul_baseline=r4(lsb),
            liver_sul_followup=r4(lsf),
            liver_sul_delta=r4(lsf - lsb) if lsb is not None and lsf is not None else None,
            uptake_min_baseline=r4(b["uptake_s"] / 60) if b.get("uptake_s") else None,
            uptake_min_followup=r4(f["uptake_s"] / 60) if f.get("uptake_s") else None,
            uptake_delta_min=r4((f["uptake_s"] - b["uptake_s"]) / 60)
            if b.get("uptake_s") and f.get("uptake_s")
            else None,
            protocol_differences=json.dumps(diffs) if diffs else "",
        )
        pair_rows.append(row)
        for region, key in (("LIVER", "liver"), ("BLOOD_POOL", "blood_pool")):
            rb, rf = b.get(key) or {}, f.get(key) or {}
            inh = rf.get("inherited_from") or {}
            liver_rows.append(
                {
                    "subject": subj,
                    "perturbation": e["perturbation"],
                    "region": region,
                    "baseline_status": rb.get("status"),
                    "baseline_review": rb.get("review_decision"),
                    "baseline_reviewer": rb.get("reviewer"),
                    "followup_status": rf.get("status") or "NOT_EVALUATED",
                    "followup_refusal": rf.get("refusal"),
                    "same_geometry": (
                        rf.get("centre_patient_mm") == rb.get("centre_patient_mm")
                        and rf.get("diameter_mm") == rb.get("diameter_mm")
                        and rf.get("length_mm") == rb.get("length_mm")
                    )
                    if rf
                    else None,
                    "centre_patient_mm": rb.get("centre_patient_mm"),
                    "voxels_baseline": rb.get("voxel_count"),
                    "voxels_followup": rf.get("voxel_count"),
                    "suv_mean_baseline": r4(rb.get("suv_mean")),
                    "suv_mean_followup": r4(rf.get("suv_mean")),
                    "suv_sd_baseline": r4(rb.get("suv_sd")),
                    "suv_sd_followup": r4(rf.get("suv_sd")),
                    "cov_baseline": r4(rb.get("cov")),
                    "cov_followup": r4(rf.get("cov")),
                    "sul_mean_baseline": r4(rb.get("sul_mean")),
                    "sul_mean_followup": r4(rf.get("sul_mean")),
                    "source_review_sha256": inh.get("source_review_sha256"),
                }
            )

    # numeric liver expectations
    numeric = []
    for subj, e in exp.items():
        le = e["liver_reference"]
        row = next(r for r in pair_rows if r["subject"] == subj)
        b, f = tps[(subj, "BASELINE")], tps[(subj, "FOLLOWUP")]
        lb, lf = (b.get("liver") or {}), (f.get("liver") or {})
        res = "n/a"
        if "delta_sul_abs" in le and lb.get("sul_mean") is not None and lf.get("sul_mean"):
            d = abs(lf["sul_mean"] - lb["sul_mean"])
            res = "OK" if d <= le["tolerance"] else f"MISMATCH |delta|={d}"
        if "followup_over_baseline_ratio" in le and lf.get("sul_mean"):
            ratio = lf["sul_mean"] / lb["sul_mean"]
            ok = abs(ratio - le["followup_over_baseline_ratio"]) <= le["ratio_tolerance"]
            res = f"{'OK' if ok else 'MISMATCH'} ratio={ratio:.6f}"
        if "delta_sul_abs_max" in le and lf.get("sul_mean"):
            d = abs(lf["sul_mean"] - lb["sul_mean"])
            sd = "DECREASE" if lf["suv_sd"] < lb["suv_sd"] else "NOT_DECREASE"
            mx = "DECREASE" if f["lesion_suvmax"] < b["lesion_suvmax"] else "NOT_DECREASE"
            pk = "DECREASE" if f["lesion_suvpeak"] < b["lesion_suvpeak"] else "NOT_DECREASE"
            ok = (
                d <= le["delta_sul_abs_max"]
                and sd == le["liver_sd"]
                and mx == le["lesion_suvmax"]
                and pk == le["lesion_suvpeak"]
            )
            res = f"{'OK' if ok else 'MISMATCH'} |delta|={d:.4f} sd {sd} suvmax {mx} suvpeak {pk}"
        if le["expect"] == "UNKNOWN":
            res = "OK (not evaluated)" if not lf else "MISMATCH (evaluated)"
        numeric.append((subj, e["perturbation"], res))
        row["liver_numeric_expectation"] = res
        if "MISMATCH" in res:
            mismatches.append((subj, "liver-numeric", "LIVER", json.dumps(le), res))

    write_csv("pair_verdicts.csv", pair_rows)
    write_csv("rule_results.csv", rule_rows)
    write_csv("liver_reference_results.csv", liver_rows)
    write_csv("failure_reason_summary.csv", fail_rows)

    # RECON_BLUR detail
    bb, bf = tps[("DEMO-02-RECON_BLUR", "BASELINE")], tps[("DEMO-02-RECON_BLUR", "FOLLOWUP")]

    def pct(x, y):
        return f"{x:.4f} -> {y:.4f} ({100 * (y - x) / x:+.2f} %)"

    blur = [
        f"- liver SUVmean {pct(bb['liver']['suv_mean'], bf['liver']['suv_mean'])}",
        f"- liver SULmean {pct(bb['liver']['sul_mean'], bf['liver']['sul_mean'])}",
        f"- liver SD (SUV) {pct(bb['liver']['suv_sd'], bf['liver']['suv_sd'])}",
        f"- liver CoV {pct(bb['liver']['cov'], bf['liver']['cov'])}",
        f"- lesion SUVmax {pct(bb['lesion_suvmax'], bf['lesion_suvmax'])}",
        f"- lesion SUVpeak {pct(bb['lesion_suvpeak'], bf['lesion_suvpeak'])}",
    ]

    v1 = OUT / "TRIAL_AUDIT_REPORT.md"
    if v1.exists() and not (OUT / "TRIAL_AUDIT_REPORT_v1.md").exists():
        shutil.copy(v1, OUT / "TRIAL_AUDIT_REPORT_v1.md")
    L = [
        "# Trial audit report v2: VOXELTRACE-DEMO-002 (synthetic longitudinal fixtures)",
        "",
        "RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. Comparability/assessability only; no "
        "biological or treatment response is assessed.",
        "",
        f"Expectation manifest: configs/expectations/synthetic_demo_v2.json sha256 `{msha}`, "
        "committed (b0baa07) before the first v2 audit run.",
        "",
        f"**Observed vs expected: {len(mismatches)} mismatches.**",
        "",
        "## REAL BASELINE SOURCE",
        "",
        "Every synthetic pair uses the same REAL baseline PET/CT (public PETCT_0011f3deaf, "
        "Siemens Biograph mCT). Its liver and blood-pool regions were human-reviewed "
        "(ACCEPT) in trial_demo/reference_review.yaml, read here without modification.",
        "",
    ]
    b0 = tps[("DEMO-01-IDENTITY", "BASELINE")]
    L += [
        f"- strict SUVbw {b0['suv_status']}; uptake {b0['uptake_s'] / 60:.2f} min; lesion "
        f"SUVmax {b0['lesion_suvmax']:.3f}, SUVpeak {b0['lesion_suvpeak']:.3f}",
        f"- liver: {b0['liver']['status']} ({b0['liver']['review_decision']} by "
        f"{b0['liver']['reviewer']!r}); SUVmean {b0['liver']['suv_mean']:.4f}, SULmean "
        f"{b0['liver']['sul_mean']:.4f}, SD {b0['liver']['suv_sd']:.4f}, CoV "
        f"{b0['liver']['cov']:.4f}, {b0['liver']['voxel_count']} voxels",
        "- No real follow-up exists; nothing in the next section is a real longitudinal result.",
        "",
        "## SYNTHETIC FOLLOW-UP FINDINGS",
        "",
        "Each follow-up is a SYNTHETIC_PERTURBATION of the baseline PET with the baseline CT "
        "copied unchanged (CT_COPIED_UNCHANGED_FROM_BASELINE). Follow-up reference regions are "
        "SYNTHETIC_INHERITED_REFERENCE (baseline geometry, inherited for a test fixture only).",
        "",
        "| subject | perturbation | PERCIST (exp/obs) | QIBA (exp/obs) | EANM (exp/obs) | "
        "liver SUL B -> F (delta) | uptake delta min | protocol differences |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in pair_rows:
        L.append(
            f"| {r['subject']} | {r['perturbation']} | {r['percist-1.0_expected']} / "
            f"{r['percist-1.0_observed']} | {r['qiba-fdg-1.14_expected']} / "
            f"{r['qiba-fdg-1.14_observed']} | {r['eanm-fdg-2.0_expected']} / "
            f"{r['eanm-fdg-2.0_observed']} | {r['liver_sul_baseline']} -> "
            f"{r['liver_sul_followup']} ({r['liver_sul_delta']}) | {r['uptake_delta_min']} | "
            f"{r['protocol_differences'] or '-'} |"
        )
    L += ["", "### Liver numeric expectations", ""]
    L += [f"- {s} ({k}): {res}" for s, k, res in numeric]
    L += ["", "### RECON_BLUR: liver (inherited region) vs lesion", ""] + blur
    L += [
        "",
        "Interpretation is limited to this fixture: a 6 mm FWHM blur leaves the mean of a "
        "large homogeneous region nearly unchanged while reducing its SD and the lesion "
        "maxima. It is not a general biological result.",
        "",
        "### Rule results (non-PASS)",
        "",
        "| subject | rule set | rule | status | class | reasons |",
        "|---|---|---|---|---|---|",
    ]
    L += [
        f"| {r['subject']} | {r['ruleset']} | {r['rule_id']} | {r['status']} | {r['class']} | "
        f"{r['reason_codes'] or '-'} |"
        for r in fail_rows
    ]
    if mismatches:
        L += ["", "### MISMATCHES vs the frozen manifest", ""]
        L += [f"- {m}" for m in mismatches]
    L += [
        "",
        "Verdict counts (synthetic pairs only): "
        + "; ".join(
            f"{rs}: {dict(Counter(p['verdict'] for p in audits[rs]['pairs']))}" for rs in RULESETS
        ),
        "",
        "Files: expectation_manifest.json, pair_verdicts.csv, rule_results.csv, "
        "liver_reference_results.csv, failure_reason_summary.csv; per rule set "
        "v2/audit_<ruleset>/ (full audit export).",
    ]
    (OUT / "TRIAL_AUDIT_REPORT.md").write_text("\n".join(L) + "\n")
    print(f"mismatches: {len(mismatches)}")
    for m in mismatches:
        print(" ", m)
    for s, _k, res in numeric:
        print(f"  {s}: {res}")
    print("\n".join(blur))
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
