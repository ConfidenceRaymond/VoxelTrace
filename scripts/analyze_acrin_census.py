#!/usr/bin/env python3
"""Analyse the ACRIN-NSCLC-FDG-PET metadata census (no images; predictions only).

Reads ../data/census/acrin_nsclc_fdg_pet/{series_index.csv, pet_headers.jsonl}. Writes
pet_series_risk.csv, candidate_pairs.csv and census_summary.json next to them.

The II-risk categories PREDICT, from one header per series, how VoxelTrace's deterministic
gates are likely to behave. Metadata-only inspection does NOT prove final assessability:
slice-level consistency, timing cross-checks and the image data are not examined.

  LIKELY_INSUFFICIENT_INFORMATION   a strict-SUVbw input is missing/unsupported (Units not
                                    BQML, DecayCorrection not START, ATTN/DECY absent, dose,
                                    injection time, half-life, weight or series time
                                    missing), or the series is DERIVED/secondary, or no
                                    reconstruction description exists (protocol identity
                                    would be UNKNOWN)
  LIKELY_ANALYZABLE_WITH_WARNINGS   SUV inputs complete and reconstruction described, but
                                    patient height missing (SUL refused -> PERCIST liver
                                    rules UNKNOWN) or software version missing
  LIKELY_ANALYZABLE                 all of the above present
  UNKNOWN                           header not retrieved
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

D = Path(__file__).resolve().parents[2] / "data" / "census" / "acrin_nsclc_fdg_pet"


def clean(d: dict) -> dict:
    """pandas turns missing JSON values into NaN, which is truthy; map it back to None."""
    return {k: (None if isinstance(v, float) and math.isnan(v) else v) for k, v in d.items()}


def risk(h: dict) -> tuple[str, list[str], list[str]]:
    if h.get("status") != "OK":
        return "UNKNOWN", ["header not retrieved"], []
    ii, warn = [], []
    ci = h.get("CorrectedImage") or []
    ci = [ci] if isinstance(ci, str) else ci
    it = h.get("ImageType") or []
    it = [it] if isinstance(it, str) else it
    if h.get("Units") != "BQML":
        ii.append(f"Units={h.get('Units')} (strict SUV supports BQML only)")
    if h.get("DecayCorrection") != "START":
        ii.append(f"DecayCorrection={h.get('DecayCorrection')} (START only)")
    for need in ("ATTN", "DECY"):
        if need not in ci:
            ii.append(f"CorrectedImage lacks {need}")
    for f in ("RadionuclideTotalDose", "RadionuclideHalfLife", "PatientWeight", "SeriesTime"):
        if not h.get(f):
            ii.append(f"{f} missing")
    if not (h.get("RadiopharmaceuticalStartTime") or h.get("RadiopharmaceuticalStartDateTime")):
        ii.append("injection time missing")
    if "DERIVED" in it or "SECONDARY" in it:
        ii.append(f"ImageType {it} (derived/secondary: provenance)")
    if not (h.get("ReconstructionMethod") or h.get("ConvolutionKernel")):
        ii.append("no ReconstructionMethod/ConvolutionKernel (protocol identity UNKNOWN)")
    if not h.get("PatientSize"):
        warn.append("PatientSize missing (SUL refused; PERCIST liver rules UNKNOWN)")
    if not h.get("SoftwareVersions"):
        warn.append("SoftwareVersions missing (same-system rules UNKNOWN)")
    if ii:
        return "LIKELY_INSUFFICIENT_INFORMATION", ii, warn
    return ("LIKELY_ANALYZABLE_WITH_WARNINGS" if warn else "LIKELY_ANALYZABLE"), ii, warn


def vendor(manufacturer: str) -> str:
    m = manufacturer.upper()
    if "PHILIPS" in m:
        return "Philips"
    if "GE" in m.split() or m.startswith("GE") or "GEMS" in m:
        return "GE"
    if "SIEMENS" in m or m.startswith("CPS"):
        return "Siemens/CTI"
    return "other"


def is_ac_primary(h: dict) -> bool:
    ci = h.get("CorrectedImage") or []
    ci = [ci] if isinstance(ci, str) else ci
    desc = str(h.get("SeriesDescription") or "").upper()
    return "ATTN" in ci and "MIP" not in desc and "NAC" not in desc and "UNCORR" not in desc


def main() -> int:
    idx = pd.read_csv(D / "series_index.csv")
    hdr = pd.DataFrame([json.loads(x) for x in (D / "pet_headers.jsonl").read_text().splitlines()])
    pet = idx[idx.Modality == "PT"].merge(
        hdr, on=["SeriesInstanceUID", "PatientID"], how="left", suffixes=("", "_hdr")
    )
    rows = []
    for _, r in pet.iterrows():
        h = clean(r.to_dict())
        cat, ii, warn = risk(h)
        rows.append(
            {
                "PatientID": r.PatientID,
                "StudyInstanceUID": r.StudyInstanceUID,
                "SeriesInstanceUID": r.SeriesInstanceUID,
                "StudyDate": r.StudyDate,
                "Manufacturer": r.Manufacturer,
                "Model": r.ManufacturerModelName,
                "SoftwareVersions": h.get("SoftwareVersions"),
                "SeriesDescription": r.SeriesDescription,
                "Units": h.get("Units"),
                "DecayCorrection": h.get("DecayCorrection"),
                "CorrectedImage": json.dumps(h.get("CorrectedImage")),
                "ReconstructionMethod": h.get("ReconstructionMethod"),
                "ConvolutionKernel": h.get("ConvolutionKernel"),
                "Rows": h.get("Rows"),
                "PixelSpacing": json.dumps(h.get("PixelSpacing")),
                "SliceThickness": h.get("SliceThickness"),
                "Radiopharmaceutical": h.get("Radiopharmaceutical"),
                "has_height": bool(h.get("PatientSize")),
                "has_weight": bool(h.get("PatientWeight")),
                "private_creators": json.dumps(h.get("private_creators")),
                "ac_primary": is_ac_primary(h) if h.get("status") == "OK" else None,
                "vendor": vendor(str(r.Manufacturer)),
                "series_size_MB": r.series_size_MB,
                "risk": cat,
                "ii_reasons": "; ".join(ii),
                "warnings": "; ".join(warn),
            }
        )
    risk_df = pd.DataFrame(rows)
    risk_df.to_csv(D / "pet_series_risk.csv", index=False)

    # studies: AC primary PET + CT in the same study
    ct = idx[idx.Modality == "CT"].groupby("StudyInstanceUID").series_size_MB.agg(["count", "min"])
    seg = idx[idx.Modality == "SEG"].groupby("StudyInstanceUID").size()
    rank = {"LIKELY_ANALYZABLE": 0, "LIKELY_ANALYZABLE_WITH_WARNINGS": 1}
    ac = risk_df[risk_df.ac_primary == True].copy()  # noqa: E712
    ac["rank"] = ac.risk.map(rank).fillna(9)
    best = ac.sort_values(["rank", "series_size_MB"]).groupby("StudyInstanceUID").head(1)
    best = best[best.StudyInstanceUID.isin(ct.index)]
    best["ct_series"] = best.StudyInstanceUID.map(ct["count"])
    best["ct_min_MB"] = best.StudyInstanceUID.map(ct["min"])
    best["seg_series"] = best.StudyInstanceUID.map(seg).fillna(0).astype(int)
    pairs = []
    for pid, g in best.sort_values("StudyDate").groupby("PatientID"):
        g = g.reset_index(drop=True)
        if len(g) < 2 or g.StudyDate.iloc[0] == g.StudyDate.iloc[1]:
            continue
        b, f = g.iloc[0], g.iloc[1]
        rb = str(b.ReconstructionMethod or b.ConvolutionKernel)
        rf = str(f.ReconstructionMethod or f.ConvolutionKernel)
        days = (pd.to_datetime(f.StudyDate) - pd.to_datetime(b.StudyDate)).days
        pair_risk = max(
            b.risk, f.risk, key=lambda c: {**rank, "LIKELY_INSUFFICIENT_INFORMATION": 2}.get(c, 3)
        )
        pairs.append(
            {
                "PatientID": pid,
                "baseline_date": b.StudyDate,
                "followup_date": f.StudyDate,
                "interval_days": days,
                "baseline_scanner": f"{b.Manufacturer} {b.Model}",
                "followup_scanner": f"{f.Manufacturer} {f.Model}",
                "same_model": f"{b.Manufacturer} {b.Model}" == f"{f.Manufacturer} {f.Model}",
                "same_recon_description": rb == rf,
                "vendor": b.vendor,
                "baseline_risk": b.risk,
                "followup_risk": f.risk,
                "pair_risk": pair_risk,
                "baseline_recon": b.ReconstructionMethod or b.ConvolutionKernel,
                "followup_recon": f.ReconstructionMethod or f.ConvolutionKernel,
                "height_both": bool(b.has_height and f.has_height),
                "seg_series": int(b.seg_series + f.seg_series),
                "pet_series_baseline": b.SeriesInstanceUID,
                "pet_series_followup": f.SeriesInstanceUID,
                "study_baseline": b.StudyInstanceUID,
                "study_followup": f.StudyInstanceUID,
                "download_MB_pet_ct": round(
                    b.series_size_MB + f.series_size_MB + b.ct_min_MB + f.ct_min_MB, 1
                ),
                "warnings": "; ".join(sorted({w for w in (b.warnings, f.warnings) if w})),
                "ii_reasons": "; ".join(sorted({w for w in (b.ii_reasons, f.ii_reasons) if w})),
            }
        )
    cand = pd.DataFrame(pairs)
    order = {"LIKELY_ANALYZABLE": 0, "LIKELY_ANALYZABLE_WITH_WARNINGS": 1}
    cand["score"] = (
        cand.pair_risk.map(order).fillna(5) * 100
        + (~cand.same_model) * 10
        + (~cand.same_recon_description) * 5
        + cand.download_MB_pet_ct / 100
    )
    cand = cand.sort_values("score").reset_index(drop=True)
    # vendor-diverse shortlist: best pair per vendor first, then the rest by score
    first = cand.groupby("vendor", sort=False).head(1)
    cand["shortlist_rank"] = None
    for i, idx_ in enumerate(list(first.sort_values("score").index)):
        cand.loc[idx_, "shortlist_rank"] = i + 1
    cand.to_csv(D / "candidate_pairs.csv", index=False)

    summary = {
        "collection": "ACRIN-NSCLC-FDG-PET (IDC/TCIA, CC BY 3.0)",
        "method": "IDC index + one header per PT series via HTTP byte range (<= 64 KB); "
        "no image volumes downloaded",
        "series_total": int(len(idx)),
        "series_by_modality": idx.Modality.value_counts().to_dict(),
        "patients": int(idx.PatientID.nunique()),
        "pet_series": int(len(risk_df)),
        "pet_headers_ok": int((pet.status == "OK").sum()),
        "pet_ac_primary": int(ac.shape[0]),
        "pet_risk_all_series": risk_df.risk.value_counts().to_dict(),
        "pet_risk_ac_primary": ac.risk.value_counts().to_dict(),
        "ii_reason_counts_ac_primary": pd.Series(
            [x for s in ac.ii_reasons if s for x in s.split("; ")]
        )
        .str.replace(r"=.*|\[.*", "", regex=True)
        .value_counts()
        .to_dict(),
        "ac_primary_by_scanner_and_risk": ac.groupby(["Manufacturer", "Model"])
        .risk.value_counts()
        .unstack(fill_value=0)
        .reset_index()
        .to_dict(orient="records"),
        "studies_with_ac_pet_and_ct": int(best.shape[0]),
        "patients_with_candidate_pair": int(cand.shape[0]),
        "candidate_pair_risk": cand.pair_risk.value_counts().to_dict(),
        "candidate_pairs_same_model": int(cand.same_model.sum()),
        "candidate_pairs_same_model_and_recon": int(
            (cand.same_model & cand.same_recon_description).sum()
        ),
        "candidate_pairs_by_vendor_and_risk": cand.groupby("vendor")
        .pair_risk.value_counts()
        .unstack(fill_value=0)
        .reset_index()
        .to_dict(orient="records"),
        "ac_primary_height_present": int(ac.has_height.sum()),
        "ac_primary_weight_present": int(ac.has_weight.sum()),
        "pet_total_size_GB": round(float(risk_df.series_size_MB.sum()) / 1000, 2),
        "caveat": "Predictions from one header per series; not proof of assessability.",
    }
    (D / "census_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps(summary, indent=2, default=str))
    print(cand.head(12).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
