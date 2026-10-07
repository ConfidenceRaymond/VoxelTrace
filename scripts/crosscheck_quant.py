#!/usr/bin/env python3
"""Independent cross-check of SUVbw and lesion metrics for one PET/SEG case.

Deliberately shares NO code with voxeltrace.quant / voxeltrace.ingest:
- PET pixels + rescale via SimpleITK ImageSeriesReader (GDCM);
- SUV constants read directly with pydicom, times parsed with datetime.strptime;
- SEG decoded by simple z-position matching (axial, BINARY only);
- SUVpeak via FFT convolution with an explicit 1 cm³ voxel-centre sphere kernel.

Compares against outputs/<subject>/suv_result.json and lesion_metrics.json.
Usage: python scripts/crosscheck_quant.py <pet_dir> <seg_file> <outputs_dir>
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pydicom
import SimpleITK as sitk


def main(pet_dir: str, seg_file: str, out_dir: str) -> int:
    reader = sitk.ImageSeriesReader()
    files = reader.GetGDCMSeriesFileNames(pet_dir)
    reader.SetFileNames(files)
    img = reader.Execute()
    act = sitk.GetArrayFromImage(img).astype(np.float64)  # [k, j, i], Bq/mL
    h = pydicom.dcmread(files[0], stop_before_pixels=True)
    rp = h.RadiopharmaceuticalInformationSequence[0]
    t_inj = datetime.strptime(
        str(rp.RadiopharmaceuticalStartDateTime).split(".")[0], "%Y%m%d%H%M%S"
    )
    t_ref = datetime.strptime(f"{h.SeriesDate}{str(h.SeriesTime).split('.')[0]}", "%Y%m%d%H%M%S")
    dt = (t_ref - t_inj).total_seconds()
    factor = (
        float(h.PatientWeight)
        * 1000
        / (float(rp.RadionuclideTotalDose) * 0.5 ** (dt / float(rp.RadionuclideHalfLife)))
    )
    suv = act * factor

    seg = pydicom.dcmread(seg_file)
    frames = seg.pixel_array.astype(bool)
    zs = [img.TransformIndexToPhysicalPoint((0, 0, k))[2] for k in range(img.GetSize()[2])]
    mask = np.zeros(suv.shape, bool)
    for f, fg in enumerate(seg.PerFrameFunctionalGroupsSequence):
        z = float(fg.PlanePositionSequence[0].ImagePositionPatient[2])
        k = int(np.argmin([abs(z - zz) for zz in zs]))
        mask[k] |= frames[f]

    sx, sy, sz = img.GetSpacing()
    r = (3 / (4 * math.pi)) ** (1 / 3) * 10
    nk, nj, ni = (int(r // s) for s in (sz, sy, sx))
    kk, jj, ii = np.mgrid[-nk : nk + 1, -nj : nj + 1, -ni : ni + 1]
    kern = ((kk * sz) ** 2 + (jj * sy) ** 2 + (ii * sx) ** 2) <= r * r
    # FFT "same" convolution restricted to a padded bounding box around the mask
    ks, js, is_ = np.nonzero(mask)
    lo = np.maximum([ks.min() - nk, js.min() - nj, is_.min() - ni], 0)
    hi = np.minimum([ks.max() + nk + 1, js.max() + nj + 1, is_.max() + ni + 1], suv.shape)
    sub = suv[lo[0] : hi[0], lo[1] : hi[1], lo[2] : hi[2]]
    shape = [a + b - 1 for a, b in zip(sub.shape, kern.shape, strict=True)]
    ax = (0, 1, 2)
    conv = np.fft.irfftn(
        np.fft.rfftn(sub, shape, axes=ax) * np.fft.rfftn(kern[::-1, ::-1, ::-1], shape, axes=ax),
        shape,
        axes=ax,
    )
    conv = conv[nk : nk + sub.shape[0], nj : nj + sub.shape[1], ni : ni + sub.shape[2]] / kern.sum()
    centres = np.argwhere(mask)
    ok = np.all((centres - [nk, nj, ni] >= 0) & (centres + [nk, nj, ni] < suv.shape), axis=1)
    c = centres[ok] - lo
    peak = float(conv[c[:, 0], c[:, 1], c[:, 2]].max())

    vals = suv[mask]
    mine = {
        "decay_interval_s": dt,
        "suv_per_bqml": factor,
        "suv_max_volume": float(suv.max()),
        "lesion_voxels": int(mask.sum()),
        "suv_max": float(vals.max()),
        "suv_mean": float(vals.mean()),
        "mtv_ml": mask.sum() * sx * sy * sz / 1000,
        "suv_peak": peak,
        "kernel_voxels": int(kern.sum()),
    }
    mine["tlg"] = mine["mtv_ml"] * mine["suv_mean"]
    res = json.loads((Path(out_dir) / "suv_result.json").read_text())
    les = json.loads((Path(out_dir) / "lesion_metrics.json").read_text())["lesions"][0]
    theirs = {
        "decay_interval_s": res["scale"]["decay_interval_s"],
        "suv_per_bqml": res["scale"]["suv_per_bqml"],
        "suv_max_volume": res["suv_stats"]["finite_max"],
        "lesion_voxels": les["voxel_count"],
        "suv_max": les["suv_max"],
        "suv_mean": les["suv_mean"],
        "mtv_ml": les["mtv_ml"],
        "suv_peak": les["suv_peak"]["value"],
        "kernel_voxels": les["suv_peak"]["kernel_voxel_count"],
        "tlg": les["tlg"],
    }
    worst = 0.0
    print(f"{'quantity':18} {'independent':>22} {'voxeltrace':>22} {'rel diff':>10}")
    for k, v in mine.items():
        rel = abs(v - theirs[k]) / max(abs(v), 1e-300)
        worst = max(worst, rel)
        print(f"{k:18} {v:22.12g} {theirs[k]:22.12g} {rel:10.2e}")
    print(f"max relative difference: {worst:.2e}")
    return 0 if worst < 1e-9 else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:4]))
