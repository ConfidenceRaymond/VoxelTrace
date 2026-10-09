#!/usr/bin/env python3
"""Write a FROZEN download plan + allow-list for one census v3 candidate (no download).

  plan_external_download.py <collection> <subject> "<why worth downloading>"

From census v3 (../data/census/public_pet_v3/) picks the subject's best-ranked pair, then
exactly: baseline PET, follow-up PET, the smallest CT series in each PET frame of reference,
and (only if a non-AI COLLECTION_ANNOTATION / human-corrected SEG exists in the baseline study)
that SEG. Writes:
  ../outputs/autonomous_download_plan/<collection>__<subject>.json   (plan, predictions)
  configs/external_longitudinal/allowlist_<collection>__<subject>.json (fetch allow-list)
and appends the plan's sha256 to ../outputs/autonomous_download_plan/FROZEN_PLAN_HASHES.txt.
Refuses to overwrite an existing plan (plans are never modified after creation).
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
V3 = ROOT / "data" / "census" / "public_pet_v3"
PLANS = ROOT / "outputs" / "autonomous_download_plan"
ALLOW = Path(__file__).resolve().parents[1] / "configs" / "external_longitudinal"
MAX_MB_PER_CANDIDATE = 1000.0
HUMAN_SEG = ("COLLECTION_ANNOTATION", "HUMAN_CORRECTED_RADIOLOGIST", "HUMAN_CORRECTED_NON_EXPERT")


def main(argv: list[str]) -> int:
    col, subj, why = argv[1], argv[2], argv[3]
    PLANS.mkdir(parents=True, exist_ok=True)
    ALLOW.mkdir(parents=True, exist_ok=True)
    plan_path = PLANS / f"{col}__{subj}.json"
    if plan_path.exists():
        print(f"STOP: {plan_path} exists; plans are frozen", file=sys.stderr)
        return 2
    cand = next(
        r
        for r in csv.DictReader((V3 / "candidates_v3.csv").open())
        if r["collection"] == col and r["subject"] == subj
    )
    idx = {r["SeriesInstanceUID"]: r for r in csv.DictReader((V3 / "series_index.csv").open())}
    pet = {
        json.loads(x)["SeriesInstanceUID"]: json.loads(x)
        for x in (V3 / "pet_series_v3.jsonl").read_text().splitlines()
    }
    cts = [json.loads(x) for x in (V3 / "ct_series_v3.jsonl").read_text().splitlines()]
    series = []
    pairs = (("baseline", cand["pet_series_baseline"]), ("followup", cand["pet_series_followup"]))
    for tp, uid in pairs:
        p, row = pet[uid], idx[uid]
        series.append(entry(row, tp, "PET"))
        match = [
            c
            for c in cts
            if c.get("status") == "OK"
            and c["StudyInstanceUID"] == row["StudyInstanceUID"]
            and c["frame_of_reference"] == p["frame_of_reference"]
        ]
        # a volumetric CT: >= 20 instances (excludes 1-file localizers); smallest of those.
        # (Plans frozen before 2026-10-09 used "smallest", which picked a localizer for
        # cmb_mel MSB-07612; those plans are not modified.)
        match = [c for c in match if int(idx[c["SeriesInstanceUID"]]["instanceCount"]) >= 20]
        if match:
            ct = min(match, key=lambda c: c["series_size_MB"])
            series.append(entry(idx[ct["SeriesInstanceUID"]], tp, "CT"))
        if tp == "baseline":
            from census_v3_public_pet import seg_source  # noqa: PLC0415 - script-local helper

            segs = [
                r
                for r in idx.values()
                if r["StudyInstanceUID"] == row["StudyInstanceUID"]
                and r["Modality"] in ("SEG", "RTSTRUCT")
                and seg_source(r["SeriesDescription"], r["analysis_result_id"]) in HUMAN_SEG
            ]
            series += [entry(s, tp, s["Modality"]) for s in segs[:1]]
    total_mb = round(sum(s["expected_MB"] for s in series), 3)
    if total_mb > MAX_MB_PER_CANDIDATE:
        print(f"STOP: {total_mb} MB > {MAX_MB_PER_CANDIDATE} MB per candidate", file=sys.stderr)
        return 2
    plan = {
        "schema": "voxeltrace.download-plan/1",
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "frozen_before_download": True,
        "collection": col,
        "subject": subj,
        "timepoints": {
            "baseline": cand["pet_series_baseline"],
            "followup": cand["pet_series_followup"],
        },
        "series": series,
        "expected_files": sum(s["expected_instances"] for s in series),
        "expected_MB": total_mb,
        "license": sorted({s["license"] for s in series}),
        "expected_vendor_scanner": cand["scanner"],
        "census_prediction": {
            k: cand.get(k)
            for k in (
                "class",
                "qiba",
                "eanm",
                "percist",
                "qiba_if_voxel_confirmed",
                "eanm_if_voxel_confirmed",
                "percist_if_voxel_confirmed",
                "percist_readiness",
                "suv",
                "decay_crosscheck",
                "height",
                "uptake_min",
                "ct_for",
                "tracer",
                "recon_reconstruction_method",
                "recon_iterations",
                "recon_subsets",
                "recon_convolution_kernel",
                "recon_time_of_flight",
                "recon_psf_resolution_modelling",
                "seg_baseline",
            )
        },  # fmt: skip
        "expected_blockers": cand["main_blockers"],
        "why_worth_downloading": why,
        "guards": "exact series prefixes only; instance count and size checked before download",
    }
    text = json.dumps(plan, indent=2) + "\n"
    plan_path.write_text(text)
    plan_path.chmod(0o444)
    digest = hashlib.sha256(text.encode()).hexdigest()
    with (PLANS / "FROZEN_PLAN_HASHES.txt").open("a") as fh:
        fh.write(f"{digest}  {plan_path.name}  {plan['created']}\n")
    allow = {
        "schema": "voxeltrace.bounded-download/1",
        "approval": "autonomous session budget (<=3 pairs, <=2.5 GB); frozen plan "
        f"{plan_path.name} sha256 {digest}",
        "approved_subjects": [subj],
        "collection": col,
        "expected_MB": total_mb,
        "expected_instances": plan["expected_files"],
        "expected_series": len(series),
        "series": series,
    }
    (ALLOW / f"allowlist_{col}__{subj}.json").write_text(json.dumps(allow, indent=2) + "\n")
    print(
        f"plan {plan_path.name}: {len(series)} series, {plan['expected_files']} files, "
        + f"{total_mb} MB, sha256 {digest}"
    )
    return 0


def entry(row: dict, tp: str, modality: str) -> dict:
    return {
        "PatientID": row["PatientID"],
        "collection": row["collection_id"],
        "timepoint": tp,
        "modality": modality,
        "StudyInstanceUID": row["StudyInstanceUID"],
        "SeriesInstanceUID": row["SeriesInstanceUID"],
        "SeriesDescription": row["SeriesDescription"],
        "aws_bucket": row["aws_bucket"],
        "crdc_series_uuid": row["crdc_series_uuid"],
        "expected_instances": int(row["instanceCount"]),
        "expected_MB": float(row["series_size_MB"]),
        "license": row["license_short_name"],
    }


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent))
    sys.exit(main(sys.argv))
