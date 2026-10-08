#!/usr/bin/env python3
"""Read-only characterization of PET decay-factor timing (no SUV computed, validator unchanged).

For each downloaded ACRIN PET series, every slice header is read and grouped by bed
(AcquisitionTime). For every candidate decay reference the predicted DecayFactor
2^(t/T½) is compared with the stored DecayFactor. A candidate that fits numerically is NOT
thereby supported: support requires documentation (see docs/vendor_decay_timing.md).

Output: ../outputs/acrin_longitudinal/decay_timing.json (+ printed summary).
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pydicom

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "acrin_longitudinal"
OUT = ROOT / "outputs" / "acrin_longitudinal" / "decay_timing.json"
FIELDS = [
    "SeriesDate",
    "SeriesTime",
    "AcquisitionDate",
    "AcquisitionTime",
    "AcquisitionDateTime",
    "ContentTime",
    "FrameReferenceTime",
    "ActualFrameDuration",
    "DecayFactor",
    "DecayCorrection",
    "Units",
    "RescaleSlope",
    "RescaleIntercept",
    "ImageIndex",
    "InstanceNumber",
    "SliceLocation",
    "NumberOfSlices",
    "NumberOfTimeSlices",
    "SeriesType",
    "CountsSource",
    "DoseCalibrationFactor",
]


def tod(date: str | None, time: str | None) -> datetime | None:
    if not time:
        return None
    t = str(time).split(".")[0].ljust(6, "0")
    d = str(date or "19000101")
    return datetime.strptime(d[:8] + t[:6], "%Y%m%d%H%M%S")


def series(subject: str, tp: str) -> dict:
    files = sorted((DATA / subject / tp / "PET").glob("*.dcm"))
    hs = [pydicom.dcmread(f, stop_before_pixels=True) for f in files]
    hs.sort(key=lambda h: float(h.ImagePositionPatient[2]))
    rp = hs[0].RadiopharmaceuticalInformationSequence[0]
    t_half = float(rp.RadionuclideHalfLife)
    inj = tod(hs[0].get("SeriesDate"), rp.get("RadiopharmaceuticalStartTime"))
    ser = tod(hs[0].get("SeriesDate"), hs[0].get("SeriesTime"))
    beds: dict[str, list] = defaultdict(list)
    for h in hs:
        beds[str(h.get("AcquisitionTime"))].append(h)
    out_beds = []
    for acq_time, bh in sorted(beds.items()):
        h0 = bh[0]
        acq = tod(h0.get("AcquisitionDate") or h0.get("SeriesDate"), acq_time)
        dfs = sorted({float(h.DecayFactor) for h in bh})
        frts = sorted({float(h.FrameReferenceTime) for h in bh})
        dur = float(h0.ActualFrameDuration) / 1000.0
        frt = frts[0] / 1000.0
        df = dfs[0]
        acq_off = (acq - ser).total_seconds() if acq and ser else None
        cands = {
            "FrameReferenceTime (validator)": frt,
            "FRT + duration/2": frt + dur / 2,
            "FRT + duration": frt + dur,
            "acquisition start - series start": acq_off,
            "acquisition start - series start + duration/2": None
            if acq_off is None
            else acq_off + dur / 2,
            "acquisition end - series start": None if acq_off is None else acq_off + dur,
            "acquisition start - injection": (acq - inj).total_seconds() if acq and inj else None,
            "series start - injection": (ser - inj).total_seconds() if ser and inj else None,
        }
        tests = {
            k: None
            if v is None
            else {
                "t_s": v,
                "predicted_df": 2 ** (v / t_half),
                "rel_diff": 2 ** (v / t_half) / df - 1,
            }
            for k, v in cands.items()
        }
        import math

        out_beds.append(
            {
                "acquisition_time": acq_time,
                "n_slices": len(bh),
                "z_range_mm": [
                    float(bh[0].ImagePositionPatient[2]),
                    float(bh[-1].ImagePositionPatient[2]),
                ],
                "distinct_decay_factor": dfs,
                "distinct_frame_reference_time_ms": frts,
                "actual_frame_duration_s": dur,
                "df_implied_decay_s": t_half * math.log2(df),
                "candidates": tests,
            }
        )
    first = hs[0]
    private = sorted(
        {
            f"({e.tag.group:04X},{e.tag.element:04X}) {e.value}"
            for e in first
            if e.tag.is_private and e.tag.element < 0x100
        }
    )
    return {
        "subject": subject,
        "timepoint": tp,
        "n_slices": len(hs),
        "constant_fields": {f: str(first.get(f)) for f in FIELDS},
        "manufacturer": str(first.get("Manufacturer")),
        "model": str(first.get("ManufacturerModelName")),
        "software": str(first.get("SoftwareVersions")),
        "half_life_s": t_half,
        "injection_time": str(rp.get("RadiopharmaceuticalStartTime")),
        "injection_datetime": str(rp.get("RadiopharmaceuticalStartDateTime")),
        "private_creators": private,
        "n_beds": len(out_beds),
        "beds": out_beds,
    }


def main() -> int:
    res = [
        series(s, t)
        for s in ("ACRIN-NSCLC-FDG-PET-094", "ACRIN-NSCLC-FDG-PET-153")
        for t in ("baseline", "followup")
    ]
    OUT.write_text(json.dumps(res, indent=2, default=str) + "\n")
    for r in res:
        print(
            f"== {r['subject'][-3:]} {r['timepoint']} {r['manufacturer']} {r['model']} sw "
            f"{r['software']} slices {r['n_slices']} beds {r['n_beds']} T½ {r['half_life_s']} "
            f"inj {r['injection_time']}"
        )
        print(f"   private creators: {r['private_creators']}")
        for b in r["beds"]:
            best = sorted(
                (abs(v["rel_diff"]), k) for k, v in b["candidates"].items() if v is not None
            )
            print(
                f"   bed {b['acquisition_time']} n={b['n_slices']} DF {b['distinct_decay_factor']} "
                f"FRT {b['distinct_frame_reference_time_ms']} dur {b['actual_frame_duration_s']} "
                f"DF-implied {b['df_implied_decay_s']:.1f}s"
            )
            for d, k in best:
                print(f"       {d:.2e}  {k}  (t={b['candidates'][k]['t_s']:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
