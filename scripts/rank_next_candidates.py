#!/usr/bin/env python3
"""Rank the next real ACRIN longitudinal pair to download (metadata only; downloads nothing).

Reads census v2 (12 sampled slice headers per AC PET series, already on disk):
  ../data/census/acrin_nsclc_fdg_pet_v2/pet_series_v2.jsonl   (protocol evidence per series)
  ../data/census/acrin_nsclc_fdg_pet_v2/pet_series_v2_enriched.jsonl (CT FoR, dates, sizes)
  ../data/census/acrin_nsclc_fdg_pet/series_index.csv          (SEG series per study)

Unlike census v2 (first two study dates only), EVERY ordered pair of AC PET series with
different study dates is evaluated with the unchanged rule code (assess_pair), for subjects
not yet downloaded. Per pair, for QIBA and EANM:
  DECIDABLE     no blocking check UNKNOWN (verdict is then an evidence-backed decision)
  outcome       DECIDABLE_ASSESSABLE / DECIDABLE_NOT_ASSESSABLE / NOT_DECIDABLE
PERCIST readiness (Part B):
  PERCIST_BLOCKED_BY_SUL        height missing at a timepoint (SUL impossible)
  PERCIST_BLOCKED_BY_REFERENCE  no CT in the PET frame of reference (no liver region)
  PERCIST_BLOCKED_BY_RECON      VT-PROTOCOL-IDENTITY not PASS
  PERCIST_READY                 none of the above, SUV passes, and a HUMAN-CORRECTED SEG exists
                                at baseline (still requires VoxelTrace review before use)
  PERCIST_LIVER_READY_BUT_LESION_MISSING  as READY but no human-corrected baseline SEG
  UNKNOWN                       strict SUV predicted to refuse at a timepoint
Unreviewed AI SEGs are listed but never count as a lesion source.

Writes ../data/census/acrin_nsclc_fdg_pet_v2/next_candidates.{csv,json}.
"""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from voxeltrace.evidence.comparability import compare_protocols
from voxeltrace.rules.registry import assess_pair, get_ruleset
from voxeltrace.trial.schema import PairContext, ScanPair

ROOT = Path(__file__).resolve().parents[2]
V1 = ROOT / "data" / "census" / "acrin_nsclc_fdg_pet"
V2 = ROOT / "data" / "census" / "acrin_nsclc_fdg_pet_v2"
DOWNLOADED = {f"ACRIN-NSCLC-FDG-PET-{n}" for n in ("094", "153", "167", "050", "168")}
RULESETS = ("qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0")

_spec = importlib.util.spec_from_file_location(
    "census_v2", Path(__file__).with_name("census_v2_acrin.py")
)
census_v2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(census_v2)


def ev(rec: dict, part: str, field: str):
    p = json.loads(rec["protocol_json"])[part][field]
    return p.get("value") if p.get("status") == "PRESENT" else None


def status(rec: dict, part: str, field: str) -> str:
    return json.loads(rec["protocol_json"])[part][field].get("status")


def seg_kind(desc: str) -> str:
    d = desc.lower()
    if "radiologist" in d:
        return "RADIOLOGIST_CORRECTED"
    if "non-expert" in d:
        return "NON_EXPERT_CORRECTED"
    return "AI_UNREVIEWED"


def blocking(v, kind: str) -> list[str]:
    return sorted(c.rule_id for c in v.checks if c.impact == "blocking" and c.status == kind)


def outcome(v) -> str:
    if blocking(v, "UNKNOWN"):
        return "NOT_DECIDABLE"
    return "DECIDABLE_NOT_ASSESSABLE" if blocking(v, "FAIL") else "DECIDABLE_ASSESSABLE"


def main() -> int:
    raw = {
        json.loads(x)["SeriesInstanceUID"]: json.loads(x)
        for x in (V2 / "pet_series_v2.jsonl").read_text().splitlines()
    }
    enr = [json.loads(x) for x in (V2 / "pet_series_v2_enriched.jsonl").read_text().splitlines()]
    segs: dict[str, list[str]] = defaultdict(list)
    for r in csv.DictReader((V1 / "series_index.csv").open()):
        if r["Modality"] == "SEG":
            segs[r["StudyInstanceUID"]].append(seg_kind(r["SeriesDescription"]))
    by_patient: dict[str, list[dict]] = defaultdict(list)
    for e in enr:
        if e.get("status") == "OK" and e["PatientID"] not in DOWNLOADED:
            by_patient[e["PatientID"]].append({**raw[e["SeriesInstanceUID"]], **e})
    rulesets = {rs: get_ruleset(rs) for rs in RULESETS}
    rows = []
    for pid, ss in sorted(by_patient.items()):
        for b in ss:
            for f in ss:
                if b["StudyDate"] >= f["StudyDate"]:
                    continue
                rows.append(score(pid, b, f, rulesets, segs))
    rows.sort(key=rank_key)
    best: dict[str, dict] = {}
    for r in rows:
        best.setdefault(r["subject"], r)
    top = sorted(best.values(), key=rank_key)
    for i, r in enumerate(top, 1):
        r["rank"] = i
    with (V2 / "next_candidates.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["rank", *[k for k in top[0] if k != "rank"]])
        w.writeheader()
        w.writerows(top)
    summary = {
        "recon_evidence_completeness_by_vendor": completeness(raw, enr),
        "pairs_evaluated": len(rows),
        "subjects": len(best),
        "excluded_already_downloaded": sorted(DOWNLOADED),
        "qiba_outcomes_all_pairs": _count(r["qiba_outcome"] for r in rows),
        "eanm_outcomes_all_pairs": _count(r["eanm_outcome"] for r in rows),
        "qiba_eanm_both_decidable_pairs": sum(
            r["qiba_outcome"] != "NOT_DECIDABLE" and r["eanm_outcome"] != "NOT_DECIDABLE"
            for r in rows
        ),
        "suv_pass_both_pairs": sum(r["suv_baseline"] == r["suv_followup"] == "PASS" for r in rows),
        "percist_readiness_best_per_subject": _count(r["percist_readiness"] for r in top),
        "top10": top[:10],
    }
    (V2 / "next_candidates.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "top10"}, indent=2))
    for r in top[:10]:
        print(
            r["rank"], r["subject"], r["scanner"], r["suv_baseline"], r["suv_followup"],
            r["uptake_min"], r["recon"], r["qiba_outcome"], r["eanm_outcome"],
            r["percist_readiness"], r["main_blocker"], r["download_MB"],
        )  # fmt: skip
    return 0


def score(pid: str, b: dict, f: dict, rulesets, segs) -> dict:
    tb = census_v2.timepoint(b, pid, "baseline")
    tf = census_v2.timepoint(f, pid, "followup")
    ctx = PairContext(
        pair=ScanPair(subject_id=pid, baseline="baseline", followup="followup"),
        baseline=tb,
        followup=tf,
    )
    cat = compare_protocols(tb.protocol, tf.protocol).category
    v = {rs: assess_pair(r, ctx, cat) for rs, r in rulesets.items()}
    q, e, p = v["qiba-fdg-1.14"], v["eanm-fdg-2.0"], v["percist-1.0"]
    suv_both = bool(b["suv_eligible"] and f["suv_eligible"])
    height = bool(b["height_present"] and f["height_present"])
    ct = bool(b["ct_same_for"] and f["ct_same_for"])
    ident = next((c.status for c in p.checks if c.rule_id == "VT-PROTOCOL-IDENTITY"), None)
    bseg, fseg = segs.get(b["StudyInstanceUID"], []), segs.get(f["StudyInstanceUID"], [])
    human_b = [s for s in bseg if s != "AI_UNREVIEWED"]
    blockers = []
    if not suv_both:
        blockers.append("SUV")
    if not height:
        blockers.append("SUL")
    if not ct:
        blockers.append("REFERENCE")
    if ident != "PASS":
        blockers.append("RECON")
    if not suv_both:
        readiness = "UNKNOWN"
    elif not height:
        readiness = "PERCIST_BLOCKED_BY_SUL"
    elif not ct:
        readiness = "PERCIST_BLOCKED_BY_REFERENCE"
    elif ident != "PASS":
        readiness = "PERCIST_BLOCKED_BY_RECON"
    elif human_b:
        readiness = "PERCIST_READY"
    else:
        readiness = "PERCIST_LIVER_READY_BUT_LESION_MISSING"
    ub = b["uptake_s"] / 60 if b["suv_eligible"] and b["uptake_s"] else None
    uf = f["uptake_s"] / 60 if f["suv_eligible"] and f["uptake_s"] else None
    unk = sorted(set(blocking(q, "UNKNOWN")) | set(blocking(e, "UNKNOWN")))
    fails = sorted(set(blocking(q, "FAIL")) | set(blocking(e, "FAIL")))
    df = [
        "UNVERIFIED" if "DECAY_FACTOR_UNVERIFIED" in s["warning_codes"]
        else "INCONSISTENT" if "DECAY_FACTOR_INCONSISTENT" in s["refusal_codes"]
        else "VERIFIED_SAMPLED"
        for s in (b, f)
    ]  # fmt: skip

    def two(part, field):
        return f"{ev(b, part, field)} / {ev(f, part, field)}"

    return {
        "subject": pid,
        "vendor": census_v2.vendor(b["manufacturer"]),
        "scanner": f"{b['manufacturer']} {b['model']} / {f['manufacturer']} {f['model']}",
        "software": two("scanner", "software_versions"),
        "tracer": f"{ev(b, 'acquisition', 'tracer')} / {ev(f, 'acquisition', 'tracer')}",
        "tracer_code": two("acquisition", "radiopharmaceutical_code"),
        "interval_days": (
            date.fromisoformat(f["StudyDate"]) - date.fromisoformat(b["StudyDate"])
        ).days,
        "uptake_min": f"{ub and round(ub, 1)} / {uf and round(uf, 1)}",
        "uptake_diff_min": round(abs(uf - ub), 1) if ub and uf else None,
        "height": f"{b['height_present']} / {f['height_present']}",
        "suv_baseline": "PASS" if b["suv_eligible"] else ";".join(b["refusal_codes"]),
        "suv_followup": "PASS" if f["suv_eligible"] else ";".join(f["refusal_codes"]),
        "decay_crosscheck": " / ".join(df),
        "ct_for": f"{b['ct_same_for']} / {f['ct_same_for']}",
        "recon": two("reconstruction", "reconstruction_method"),
        "iterations": two("reconstruction", "iterations"),
        "subsets": two("reconstruction", "subsets"),
        "filter_kernel": two("reconstruction", "convolution_kernel"),
        "tof": two("reconstruction", "time_of_flight"),
        "psf": two("reconstruction", "psf_resolution_modelling"),
        "seg_baseline": ";".join(sorted(bseg)) or "none",
        "seg_followup": ";".join(sorted(fseg)) or "none",
        "download_MB": round(
            b["pet_MB"]
            + f["pet_MB"]
            + (b["ct_same_for_min_MB"] or 0)
            + (f["ct_same_for_min_MB"] or 0),
            1,
        ),
        "qiba_verdict": q.verdict,
        "eanm_verdict": e.verdict,
        "percist_verdict": p.verdict,
        "qiba_outcome": outcome(q),
        "eanm_outcome": outcome(e),
        "protocol_identity": ident,
        "percist_readiness": readiness,
        "blocking_unknown": ";".join(unk),
        "blocking_fail": ";".join(fails),
        "percist_blockers": ";".join(blockers),
        "main_blocker": (unk or fails or ["none"])[0] if suv_both else "STRICT_SUV_REFUSED",
        "_score": (
            not suv_both,
            len(unk),
            len(fails),
            "UNVERIFIED" in df,
            status(b, "reconstruction", "reconstruction_method") != "PRESENT",
            not height,
            not ct,
        ),
        "pet_series_baseline": b["SeriesInstanceUID"],
        "pet_series_followup": f["SeriesInstanceUID"],
    }


RECON_FIELDS = (
    "reconstruction_method",
    "iterations",
    "subsets",
    "convolution_kernel",
    "time_of_flight",
    "psf_resolution_modelling",
)


def completeness(raw: dict, enr: list[dict]) -> dict:
    """Fraction of OK AC PET series (all subjects) with each reconstruction field PRESENT."""
    out: dict[str, dict] = {}
    for e in enr:
        if e.get("status") != "OK":
            continue
        v = out.setdefault(census_v2.vendor(e["manufacturer"]), {"series": 0})
        v["series"] += 1
        for fld in RECON_FIELDS:
            v[fld] = v.get(fld, 0) + (
                status(raw[e["SeriesInstanceUID"]], "reconstruction", fld) == "PRESENT"
            )
    return out


def rank_key(r: dict) -> tuple:
    return (*r["_score"], r["download_MB"])


def _count(it) -> dict:
    d: dict[str, int] = defaultdict(int)
    for x in it:
        d[x] += 1
    return dict(sorted(d.items()))


if __name__ == "__main__":
    sys.exit(main())
