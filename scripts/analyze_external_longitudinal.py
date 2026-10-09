#!/usr/bin/env python3
"""Full validation of bounded EXTERNAL real pairs (non-ACRIN IDC collections). No AI.

  analyze_external_longitudinal.py <collection> <subject>

Inputs: ../data/external_longitudinal/<collection>/<subject>/<baseline|followup>/{PET,CT,SEG}
        configs/external_longitudinal/frozen_plans/<collection>__<subject>.json (predictions,
        frozen and committed before download)
Outputs: ../outputs/external_longitudinal/<collection>__<subject>/
  ingestion.json, suv_sul.json, protocol_fingerprints.json, audit_<ruleset>/, pair_rules.csv,
  census_crosscheck.csv (frozen prediction vs full-series truth), reference_review/ (QC +
  worksheet; no decision is created), summary.json

Reuses the unchanged helpers of analyze_acrin_longitudinal.py (ingestion, strict SUV/SUL,
fingerprint, diff, blocked_by). The trial directory links ONLY the PET and CT series:
supplied SEG files are withheld from rule evaluation because no lesion review gate exists yet
(a SEG in a scan folder would otherwise be measured as a lesion without human review).
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import yaml

from voxeltrace.evidence.comparability import compare_protocols
from voxeltrace.trial.audit import run_trial_audit
from voxeltrace.trial.export import export_audit
from voxeltrace.trial.layers import assessability_layers

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("acrin", HERE / "analyze_acrin_longitudinal.py")
acrin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(acrin)

ROOT = HERE.parents[1]
TPS = ("baseline", "followup")
RULESETS = ("qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0")


def safe(fn, *a):
    try:
        return fn(*a)
    except Exception as exc:  # noqa: BLE001 - record, never guess
        return {"error": f"{type(exc).__name__}: {exc}"}


def main(argv: list[str]) -> int:
    col, subj = argv[1], argv[2]
    acrin.DATA = ROOT / "data" / "external_longitudinal" / col
    out = ROOT / "outputs" / "external_longitudinal" / f"{col}__{subj}"
    out.mkdir(parents=True, exist_ok=True)
    plan = json.loads(
        (
            HERE.parent
            / "configs"
            / "external_longitudinal"
            / "frozen_plans"
            / f"{col}__{subj}.json"
        ).read_text()
    )
    ing = [safe(acrin.ingestion, subj, t) for t in TPS]
    (out / "ingestion.json").write_text(json.dumps(ing, indent=2, default=str) + "\n")
    res, fps, protos = [], {}, {}
    for t in TPS:
        r, f = acrin.suv_sul(subj, t)
        res.append(r)
        fps[t], protos[t] = f["fingerprint"], f["protocol"]
    (out / "suv_sul.json").write_text(json.dumps(res, indent=2, default=str) + "\n")
    cmp = compare_protocols(protos["baseline"], protos["followup"])
    (out / "protocol_fingerprints.json").write_text(
        json.dumps(
            {
                "baseline": fps["baseline"],
                "followup": fps["followup"],
                "diff": acrin.diff(fps["baseline"], fps["followup"]),
                "protocol_comparability": {
                    "category": cmp.category,
                    "blocking_differences": cmp.blocking_differences,
                    "blocking_unknowns": cmp.blocking_unknowns,
                    "warnings": cmp.warnings,
                },
            },
            indent=2,
            default=str,
        )
        + "\n"
    )
    trial = out / "trial"
    for t in TPS:
        # file-level links (discovery does not descend into nested directory symlinks)
        for mod in ("PET", "CT"):  # SEG withheld (no lesion review gate yet)
            src = acrin.DATA / subj / t / mod
            d = trial / subj / t / mod
            d.mkdir(parents=True, exist_ok=True)
            for f in sorted(src.glob("*.dcm")) if src.exists() else []:
                if not (d / f.name).exists():
                    (d / f.name).symlink_to(f)
    rv = out / "reference_review"
    rv.mkdir(exist_ok=True)
    (trial / "trial.yaml").write_text(
        yaml.safe_dump(
            {
                "trial_id": f"EXTERNAL-{col}-{subj}",
                "ruleset": "qiba-fdg-1.14",
                "timepoint_order": list(TPS),
                "reference_proposals": "auto",
                "reference_review_file": "../reference_review/reference_review.yaml",
                "note": f"REAL public data (IDC {col}, {','.join(plan['license'])}). Lesion SEG "
                "withheld from rule evaluation pending a human lesion review gate. Reviews live "
                "only in reference_review/reference_review.yaml, written by a human.",
            },
            sort_keys=False,
        )
    )
    audits = {}
    for rs in RULESETS:
        a = run_trial_audit(trial, ruleset=rs, qc_dir=rv / "qc")
        export_audit(a, out / f"audit_{rs}")
        audits[rs] = a
    rows, verdicts, layers = [], {}, {}
    for rs, a in audits.items():
        p = a.pairs[0]
        verdicts[rs] = p.verdict
        layers[rs] = assessability_layers(p)
        for c in p.checks:
            rows.append(
                {
                    "ruleset": rs,
                    "pair_verdict": p.verdict,
                    "rule_id": c.rule_id,
                    "impact": c.impact,
                    "status": c.status,
                    "observed": json.dumps(c.observed, default=str)[:400],
                    "reason_codes": ";".join(sorted({r.code for r in c.reasons})),
                    "blocked_by": acrin.blocked_by(c),
                }
            )
    with (out / "pair_rules.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    # census crosscheck: frozen plan prediction vs full-series truth
    pred = plan["census_prediction"]
    b, f = res
    tps = {t.timepoint: t for t in audits["qiba-fdg-1.14"].timepoints}

    def pair(fn):
        return f"{fn(b)} / {fn(f)}"

    actual = {
        "suv": pair(lambda r: r["suv_status"] if r["suv_status"] != "PASS" else "PASS"),
        "decay_crosscheck": pair(lambda r: r["decay_factor_crosscheck"]),
        "height": pair(lambda r: r["anthropometrics"]["PatientSize"] not in ("None", "", "0")),
        "uptake_min": pair(lambda r: r["uptake_interval_min"]),
        "ct_for": pair(
            lambda r: next(
                (
                    i.get("pet_ct_same_frame_of_reference")
                    for i in ing
                    if i.get("timepoint") == r["timepoint"]
                ),
                None,
            )
        ),  # fmt: skip
        "recon_reconstruction_method": pair(
            lambda r: fps[r["timepoint"]]["reconstruction_description"]["value"]
        ),
        "qiba": verdicts["qiba-fdg-1.14"],
        "eanm": verdicts["eanm-fdg-2.0"],
        "percist": verdicts["percist-1.0"],
    }
    sul_ok = pair(lambda r: r["sul"].get("LBMJAMES128", {}).get("status"))
    actual["sul_eligible"] = sul_ok
    pred["sul_eligible"] = "PASS / PASS" if pred.get("height") == "True / True" else "no height"

    def same(k, pv, v) -> bool:
        if k == "decay_crosscheck":  # census checks the sampled slices only
            return (
                pv == "CHECKED_ON_SAMPLES"
                and v == "VERIFIED / VERIFIED"
                or (pv.startswith("UNVERIFIED") and "NOT_AVAILABLE" in v)
            )
        if k == "uptake_min":
            try:
                p2 = [float(x) for x in pv.split(" / ")]
                a2 = [float(x) for x in v.split(" / ")]
                return all(abs(x - y) <= 0.1 for x, y in zip(p2, a2, strict=True))
            except ValueError:
                return False
        if k == "sul_eligible" and pv == "no height":
            return v == "REFUSED / REFUSED"
        return str(pv) == str(v)

    cross = []
    for k, v in actual.items():
        p_key = {"qiba": "qiba_if_voxel_confirmed", "eanm": "eanm_if_voxel_confirmed",
                 "percist": "percist_if_voxel_confirmed"}.get(k, k)  # fmt: skip
        pv = pred.get(p_key)
        cross.append({"field": k, "predicted": pv, "actual": v, "match": same(k, str(pv), str(v))})
    with (out / "census_crosscheck.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["field", "predicted", "actual", "match"])
        w.writeheader()
        w.writerows(cross)
    summary = {
        "collection": col,
        "subject": subj,
        "ingestion_ok": [i.get("ingestion_ok") for i in ing],
        "suv": [r["suv_status"] for r in res],
        "decay_factor_crosscheck": [r["decay_factor_crosscheck"] for r in res],
        "sul": [{k: v["status"] for k, v in r["sul"].items()} for r in res],
        "protocol_comparability": cmp.category,
        "verdicts": verdicts,
        "layers": layers,
        "reference_proposals": {
            t: {
                "liver": getattr(tps[t].liver, "status", None),
                "blood_pool": getattr(tps[t].blood_pool, "status", None),
            }
            for t in TPS
        },
        "census_misses": [c for c in cross if not c["match"]],
        "seg_withheld": any((acrin.DATA / subj / t / "SEG").exists() for t in TPS),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
