#!/usr/bin/env python3
"""Cross-collection public PET census v3, step 1: series index from IDC (metadata only).

Run with the isolated census venv (``../tmp/census-venv``: idc-index + pydicom):
  ../tmp/census-venv/bin/python scripts/census_v3_index.py

Selects, from the local IDC index (no image access):
  * every PT series of patients with PET on >= 2 distinct study dates (longitudinal), in every
    IDC collection except ACRIN-NSCLC-FDG-PET (already censused, census v2) and preclinical
    collections;
  * every PT series of the PET phantom collections (reconstruction/harmonisation metadata only;
    never paired);
  * the CT / SEG / RTSTRUCT series of those studies.
PT series whose description marks them as derived renderings or non-attenuation-corrected
(MIP, MOVIE, NAC, uncorrected, fused, screen capture ...) or with < 20 instances are kept in the
index but not header-sampled (role PET_EXCLUDED_DERIVED_OR_SMALL).

Writes ../data/census/public_pet_v3/{series_index.csv, collections.csv}.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from idc_index import index

OUT = Path(__file__).resolve().parents[2] / "data" / "census" / "public_pet_v3"
EXCLUDE = {
    "acrin_nsclc_fdg_pet": "already censused (census v2, docs/census_v2.md)",
    "uw_cirp_mouse_pet_ct_nsclc": "preclinical (mouse)",
}
PHANTOM = {"qin_pet_phantom", "rider_phantom_pet_ct"}
DERIVED = re.compile(
    r"MIP|MOVIE|\bNAC\b|NON.?AC|UNCORR|NO.?AC\b|SCREEN|FUSED|FUSION|KEY ?IMAGE|SAVE|TOPO|SCOUT",
    re.I,
)
COLS = [
    "collection_id", "PatientID", "StudyInstanceUID", "SeriesInstanceUID", "Modality",
    "StudyDate", "SeriesDescription", "Manufacturer", "ManufacturerModelName", "instanceCount",
    "series_size_MB", "license_short_name", "aws_bucket", "crdc_series_uuid",
    "analysis_result_id",
]  # fmt: skip


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    client = index.IDCClient()
    df = client.index
    pt = df[df.Modality == "PT"]
    ndates = pt.groupby(["collection_id", "PatientID"]).StudyDate.nunique()
    longi = set(ndates[ndates >= 2].index)
    is_longi = pd.Series(
        [(c, p) in longi for c, p in zip(pt.collection_id, pt.PatientID, strict=True)],
        index=pt.index,
    )
    keep = pt[(is_longi | pt.collection_id.isin(PHANTOM)) & ~pt.collection_id.isin(EXCLUDE)]
    derived = keep.SeriesDescription.astype(str).str.contains(DERIVED)
    small = keep.instanceCount < 20
    cand, excl = keep[~derived & ~small], keep[derived | small]
    studies = set(keep.StudyInstanceUID)
    aux = df[df.StudyInstanceUID.isin(studies) & df.Modality.isin(["CT", "SEG", "RTSTRUCT"])]
    out = pd.concat(
        [
            cand[COLS].assign(role="PET_CANDIDATE"),
            excl[COLS].assign(role="PET_EXCLUDED_DERIVED_OR_SMALL"),
            aux[COLS].assign(role="AUX"),
        ]
    )
    out.to_csv(OUT / "series_index.csv", index=False)

    rows = []
    for col, g in pt.groupby("collection_id"):
        nd = g.groupby("PatientID").StudyDate.nunique()
        allc = df[df.collection_id == col]
        rows.append(
            {
                "collection": col,
                "idc_version": client.get_idc_version(),
                "pt_series": len(g),
                "patients": g.PatientID.nunique(),
                "longitudinal_patients": int((nd >= 2).sum()),
                "manufacturers": ";".join(sorted({str(x) for x in g.Manufacturer})),
                "models": ";".join(sorted({str(x) for x in g.ManufacturerModelName})),
                "pt_MB": round(g.series_size_MB.sum(), 1),
                "license": ";".join(sorted({str(x) for x in allc.license_short_name})),
                "status": "EXCLUDED: " + EXCLUDE[col]
                if col in EXCLUDE
                else "PHANTOM (metadata only)"
                if col in PHANTOM
                else "LONGITUDINAL_CANDIDATES"
                if (nd >= 2).any()
                else "SINGLE_TIMEPOINT_ONLY",
            }
        )
    pd.DataFrame(rows).sort_values("longitudinal_patients", ascending=False).to_csv(
        OUT / "collections.csv", index=False
    )
    print(f"IDC {client.get_idc_version()}: PET candidates {len(cand)}, excluded {len(excl)}, "
          f"aux {len(aux)}")  # fmt: skip
    per = cand.groupby("collection_id").agg(
        series=("SeriesInstanceUID", "size"),
        patients=("PatientID", "nunique"),
        instances=("instanceCount", "sum"),
    )
    print(per.to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
