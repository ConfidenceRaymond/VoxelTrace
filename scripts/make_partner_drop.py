#!/usr/bin/env python3
"""Build a SIMULATED core-lab "partner drop" from the real public cohort (intake robustness
test only; not scientific validation).

  make_partner_drop.py <cohort_trial_dir> <new_out_dir>

The cohort trial is <subject>/<timepoint>/{PET,CT,SEG}/ of public TCIA/IDC data. The drop
re-arranges it as a site might send it:

  SiteA/Subject001..004/{Baseline,Follow-Up}/{PT_AC,CT_WB}/   ACRIN subjects (one has no CT)
  SiteB/Subject005..006/{pre,post}/{PET,CT,Segmentations}/     FDG-PET-CT-Lesions (SEG at pre)
  SiteC/Subject007..008/{BL,FU1}/{series_1,series_2}/          CC-Tumor-Heterogeneity / CMB-MEL

plus ambiguity a real drop has: a protocol PDF placeholder, a JSON metadata sidecar, notes,
.DS_Store, __MACOSX/, and two MODIFIED COPIES of the smallest real PET series, written with new
Series/SOP Instance UIDs and SeriesDescription 'SIMULATED ... (VoxelTrace partner-drop
simulator)':
  - Subject003/Follow-Up/PT_NAC  CorrectedImage without ATTN  -> excluded by rule R1
  - Subject004/Follow-Up/PT_AC_RECON2  identical but a second AC series -> MULTIPLE_PET_CANDIDATES
Real series are symlinked (no copy); only the two simulated series are written (~13 MB).
The source/destination subject mapping is written to <out>/../<name>.SIMULATOR_KEY.json
(outside the drop, as a coordinator would keep it).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pydicom
from pydicom.uid import generate_uid

PLAN = [  # (source subject, site, drop subject, timepoint names, series folder names)
    ("ACRIN-NSCLC-FDG-PET-094", "SiteA", "Subject001", ("Baseline", "Follow-Up"), {"PET": "PT_AC", "CT": "CT_WB"}),
    ("ACRIN-NSCLC-FDG-PET-153", "SiteA", "Subject002", ("Baseline", "Follow-Up"), {"PET": "PT_AC", "CT": "CT_WB"}),
    ("ACRIN-NSCLC-FDG-PET-167", "SiteA", "Subject003", ("Baseline", "Follow-Up"), {"PET": "PT_AC", "CT": "CT_WB"}),
    ("ACRIN-NSCLC-FDG-PET-168", "SiteA", "Subject004", ("Baseline", "Follow-Up"), {"PET": "PT_AC", "CT": "CT_WB"}),
    ("PETCT_97320b0b58", "SiteB", "Subject005", ("pre", "post"), {"PET": "PET", "CT": "CT", "SEG": "Segmentations"}),
    ("PETCT_c2ffda4725", "SiteB", "Subject006", ("pre", "post"), {"PET": "PET", "CT": "CT", "SEG": "Segmentations"}),
    ("CCTH-B02", "SiteC", "Subject007", ("BL", "FU1"), {"PET": "series_1", "CT": "series_2"}),
    ("MSB-07612", "SiteC", "Subject008", ("BL", "FU1"), {"PET": "series_1", "CT": "series_2"}),
]  # fmt: skip
SRC_TP = ("baseline", "followup")


def link_tree(src: Path, dst: Path) -> int:
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(src.iterdir()):
        if p.is_file():
            (dst / p.name).symlink_to(p.resolve())
            n += 1
    return n


def simulated_copy(src: Path, dst: Path, label: str, *, nac: bool) -> int:
    dst.mkdir(parents=True)
    series_uid = generate_uid()
    n = 0
    for p in sorted(src.iterdir()):
        ds = pydicom.dcmread(p)
        ds.SeriesInstanceUID = series_uid
        ds.SOPInstanceUID = generate_uid()
        ds.file_meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
        ds.SeriesDescription = f"SIMULATED {label} (VoxelTrace partner-drop simulator)"
        if nac:
            ds.CorrectedImage = [c for c in (ds.get("CorrectedImage") or []) if c != "ATTN"] or [
                "DECY"
            ]
        ds.save_as(dst / f"sim_{n:05d}.dcm", enforce_file_format=True)
        n += 1
    return n


def main(argv: list[str]) -> int:
    src, out = Path(argv[1]), Path(argv[2])
    if out.exists():
        print(f"error: {out} exists", file=sys.stderr)
        return 2
    key, linked = [], 0
    for subj, site, dsubj, tps, names in PLAN:
        for stp, dtp in zip(SRC_TP, tps, strict=True):
            for role, folder in names.items():
                s = src / subj / stp / role
                if s.is_dir():
                    linked += link_tree(s, out / site / dsubj / dtp / folder)
        key.append(
            {
                "source_subject": subj,
                "site": site,
                "drop_subject": dsubj,
                "timepoints": dict(zip(SRC_TP, tps, strict=True)),
            }
        )
    sim = simulated_copy(
        src / "ACRIN-NSCLC-FDG-PET-167" / "followup" / "PET",
        out / "SiteA" / "Subject003" / "Follow-Up" / "PT_NAC",
        "NAC",
        nac=True,
    )
    sim += simulated_copy(
        src / "ACRIN-NSCLC-FDG-PET-168" / "followup" / "PET",
        out / "SiteA" / "Subject004" / "Follow-Up" / "PT_AC_RECON2",
        "SECOND AC RECON",
        nac=False,
    )
    (out / "SiteA" / "Subject001" / "Baseline" / "protocol_scan_parameters.pdf").write_bytes(
        b"%PDF-1.4\n% placeholder: site protocol export would go here (simulated)\n%%EOF\n"
    )
    (out / "SiteA" / "Subject001" / "Baseline" / "metadata_sidecar.json").write_text(
        json.dumps({"simulated": True, "note": "site metadata sidecar"}) + "\n"
    )
    (out / "SiteB" / "transfer_notes.txt").write_text("simulated transfer notes\n")
    (out / "SiteC" / ".DS_Store").write_bytes(b"\0\0\0\1Bud1")
    (out / "__MACOSX" / "SiteC").mkdir(parents=True)
    (out / "__MACOSX" / "SiteC" / "._series_1").write_bytes(b"\0")
    keyfile = out.parent / f"{out.name}.SIMULATOR_KEY.json"
    keyfile.write_text(json.dumps({"simulated_drop": out.name, "source": "public cohort (TCIA/IDC)", "subjects": key,
                                   "simulated_series": ["SiteA/Subject003/Follow-Up/PT_NAC", "SiteA/Subject004/Follow-Up/PT_AC_RECON2"]}, indent=2) + "\n")  # fmt: skip
    print(f"linked {linked} real files; wrote {sim} simulated files; key {keyfile.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
