#!/usr/bin/env python3
"""External cross-check with third-party open-source implementations (no VoxelTrace code).

- SUVbw: Z-Rad (MIT, https://github.com/medical-physics-usz/z-rad) ``read_dicom_image``
  (its own vendor-aware DICOM SUV conversion);
- SEG decoding: highdicom (MIT) ``segread(...).get_pixels_by_source_instance``;
- SUVpeak: Z-Rad IBSI local-intensity features (``loc_peak_loc`` = sphere centred on the max
  voxel, ``loc_peak_glob`` = max over ROI centres). NOTE Z-Rad hard-codes r = 6.2 mm while
  VoxelTrace uses r = (3/4π)^(1/3) cm = 6.2035 mm; the kernel voxel sets are compared.

Run with the isolated cross-check venv (../tmp/crosscheck-venv), e.g.:
  ../tmp/crosscheck-venv/bin/python scripts/crosscheck_external.py <pet_dir> <seg.dcm> <out_dir>
"""

from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

import highdicom as hd
import numpy as np
import pydicom
import SimpleITK as sitk
from zrad.io.dicom import read_dicom_image
from zrad.radiomics.intensity import LocalIntensityFeatures


def _independent_suv(pet_dir: str) -> tuple[sitk.Image, np.ndarray]:
    from datetime import datetime

    reader = sitk.ImageSeriesReader()
    reader.SetFileNames(reader.GetGDCMSeriesFileNames(pet_dir))
    img = reader.Execute()
    files = sorted(Path(pet_dir).glob("*.dcm"))
    h = pydicom.dcmread(files[0], stop_before_pixels=True)
    rp = h.RadiopharmaceuticalInformationSequence[0]
    if "RadiopharmaceuticalStartDateTime" in rp:
        t_inj = datetime.strptime(str(rp.RadiopharmaceuticalStartDateTime)[:14], "%Y%m%d%H%M%S")
    else:  # TM only: same documented rule (SeriesDate); must precede the series time
        t_inj = datetime.strptime(
            f"{h.SeriesDate}{str(rp.RadiopharmaceuticalStartTime)[:6]}", "%Y%m%d%H%M%S"
        )
    t_ref = datetime.strptime(f"{h.SeriesDate}{str(h.SeriesTime)[:6]}", "%Y%m%d%H%M%S")
    dt = (t_ref - t_inj).total_seconds()
    if dt < 0:
        raise SystemExit("injection after series time: not handled by this cross-check")
    factor = (
        float(h.PatientWeight)
        * 1000.0
        / (float(rp.RadionuclideTotalDose) * 2.0 ** (-dt / float(rp.RadionuclideHalfLife)))
    )
    return img, sitk.GetArrayFromImage(img).astype(np.float64) * factor


def main(pet_dir: str, seg_file: str, out_dir: str) -> int:
    zr_warn: list[str] = []
    zrad_suv_status = "OK"
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            img = read_dicom_image(pet_dir, "PET")
        zr_warn = sorted({str(x.message)[:120] for x in w})
        sitk_img = img if isinstance(img, sitk.Image) else img.image
        suv = sitk.GetArrayFromImage(sitk_img).astype(np.float64)  # [k, j, i]
        suv_source = "z-rad read_dicom_image (independent vendor-aware SUVbw)"
    except Exception as exc:  # noqa: BLE001 - record the external tool's refusal verbatim
        zrad_suv_status = f"REFUSED: {type(exc).__name__}: {exc}"
        sitk_img, suv = _independent_suv(pet_dir)
        suv_source = (
            "SimpleITK/GDCM pixels x SUVbw factor from standard tags (script-local, "
            "SeriesDate/Time reference) because z-rad refused"
        )
    sx, sy, sz = sitk_img.GetSpacing()

    # highdicom spatial decode: SEG voxels -> patient LPS (volume affine) -> PET index
    # (SimpleITK physical transform). Independent of VoxelTrace's slice matching.
    seg = hd.seg.segread(seg_file)
    vol = seg.get_volume(segment_numbers=[1], combine_segments=True)
    arr = np.asarray(vol.array)
    idx = np.argwhere(arr > 0)
    lps = (np.asarray(vol.affine) @ np.c_[idx, np.ones(len(idx))].T).T[:, :3]
    mask = np.zeros(suv.shape, bool)
    off_grid = 0
    for x, y, z in lps:
        cont = sitk_img.TransformPhysicalPointToContinuousIndex((float(x), float(y), float(z)))
        ijk = np.round(cont).astype(int)
        if np.abs(np.asarray(cont) - ijk).max() > 1e-3:
            off_grid += 1
        mask[ijk[2], ijk[1], ijk[0]] = True
    if off_grid:
        raise SystemExit(f"{off_grid} SEG voxels do not fall on PET voxel centres")
    vals = suv[mask]
    masked = np.where(mask, suv, np.nan)
    li = LocalIntensityFeatures((sz, sy, sx)).calculate_features(suv, masked)
    ext = {
        "lesion_voxels": int(mask.sum()),
        "suv_max": float(vals.max()),
        "suv_mean": float(vals.mean()),
        "mtv_ml": float(mask.sum() * sx * sy * sz / 1000.0),
        "suv_volume_max": float(suv.max()),
        "zrad_loc_peak_glob": float(li["loc_peak_glob"]),
        "zrad_loc_peak_loc": float(li["loc_peak_loc"]),
    }
    ext["tlg"] = ext["mtv_ml"] * ext["suv_mean"]
    les = json.loads((Path(out_dir) / "lesion_metrics.json").read_text())["lesions"][0]
    res = json.loads((Path(out_dir) / "suv_result.json").read_text())
    vt = {
        "lesion_voxels": les["voxel_count"],
        "suv_max": les["suv_max"],
        "suv_mean": les["suv_mean"],
        "mtv_ml": les["mtv_ml"],
        "suv_volume_max": res["suv_stats"]["finite_max"],
        "tlg": les["tlg"],
        "zrad_loc_peak_glob": les["suv_peak"]["value"],
        "zrad_loc_peak_loc": les["suv_peak"]["value"],
    }
    rows = []
    worst = 0.0
    for k, v in ext.items():
        rel = abs(v - vt[k]) / max(abs(v), 1e-300)
        rows.append({"quantity": k, "external": v, "voxeltrace": vt[k], "rel_diff": rel})
        if not k.startswith("zrad_loc_peak_loc"):
            worst = max(worst, rel)
    print(f"{'quantity':20} {'external':>20} {'voxeltrace':>20} {'rel diff':>10}")
    for r in rows:
        print(
            f"{r['quantity']:20} {r['external']:20.12g} {r['voxeltrace']:20.12g} "
            f"{r['rel_diff']:10.2e}"
        )
    print(
        "notes: loc_peak_loc (sphere at the max voxel) is a different IBSI feature from "
        "VoxelTrace SUVpeak (global peak); shown for information only."
    )
    print(f"SUV source: {suv_source}")
    print(f"z-rad SUV conversion: {zrad_suv_status}")
    if zr_warn:
        print("z-rad warnings:", zr_warn)
    print(f"max relative difference (excluding loc_peak_loc): {worst:.2e}")
    (Path(out_dir) / "external_crosscheck.json").write_text(
        json.dumps(
            {
                "tools": {"z-rad": "26.9.0", "highdicom": hd.__version__},
                "rows": rows,
                "suv_source": suv_source,
                "zrad_suv_conversion": zrad_suv_status,
                "max_rel_diff_excluding_loc_peak_loc": worst,
                "zrad_warnings": zr_warn,
            },
            indent=2,
        )
    )
    return 0 if worst < 1e-6 else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
