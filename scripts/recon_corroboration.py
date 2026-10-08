#!/usr/bin/env python3
"""Image-derived CORROBORATING features for reconstruction consistency (trust LEVEL_E).

These features can at most support "no obvious reconstruction inconsistency detected". They
never establish reconstruction identity and are never read by any rule.

  recon_corroboration.py <subject> <outputs namespace>

Uses the strict SUV volumes and the HUMAN-ACCEPTED liver geometry from the namespace's
reference_review.yaml (read-only). Writes <ns>/recon_corroboration.json.

Features (baseline vs follow-up):
  voxel grid                      identical / different (exact)
  liver SUV mean, SD, CoV         from the accepted sphere
  liver high-pass noise ratio     SD of (SUV - 3x3x3 local mean) / liver mean
  liver lag-1 autocorrelation     mean of x/y/z neighbour correlations of mean-removed SUV
                                  (a smoothing / post-filter proxy)
  whole-body gradient sharpness   mean |grad SUV| / mean SUV over voxels with SUV > 0.5
Classification of each feature: CONSISTENT if the relative difference is <= the stated
heuristic tolerance, DIFFERENT if > 2x it, else INCONCLUSIVE. The tolerances are heuristics,
not validated thresholds, and are reported alongside every result.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import yaml

from voxeltrace.ingest import build_case
from voxeltrace.quant.evidence import quantify_case
from voxeltrace.quant.reference_region import sphere_mask

ROOT = Path(__file__).resolve().parents[2]
TOL = {
    "liver_cov": 0.25,
    "liver_highpass_noise_ratio": 0.25,
    "liver_lag1_autocorrelation": 0.10,
    "body_gradient_sharpness": 0.15,
}


def box_mean3(a: np.ndarray) -> np.ndarray:
    p = np.pad(a, 1, mode="edge")
    acc = np.zeros_like(a)
    for dk in range(3):
        for dj in range(3):
            for di in range(3):
                acc += p[dk : dk + a.shape[0], dj : dj + a.shape[1], di : di + a.shape[2]]
    return acc / 27.0


def features(suv: np.ndarray, geom, centre, diameter) -> dict:
    m = sphere_mask(geom, centre, diameter)
    vals = suv[m]
    mean, sd = float(vals.mean()), float(vals.std())
    hp = (suv - box_mean3(suv))[m]
    r = suv - mean
    cors = []
    for axis in range(3):
        a = np.moveaxis(r, axis, 0)
        mm = np.moveaxis(m, axis, 0)
        both = mm[1:] & mm[:-1]
        x, y = a[1:][both], a[:-1][both]
        cors.append(float(np.corrcoef(x, y)[0, 1]))
    body = suv > 0.5
    g = np.sqrt(sum(np.gradient(suv, axis=ax) ** 2 for ax in range(3)))
    return {
        "liver_voxels": int(m.sum()),
        "liver_suv_mean": mean,
        "liver_suv_sd": sd,
        "liver_cov": sd / mean,
        "liver_highpass_noise_ratio": float(hp.std() / mean),
        "liver_lag1_autocorrelation": float(np.mean(cors)),
        "body_gradient_sharpness": float(g[body].mean() / suv[body].mean()),
        "grid": {"shape": list(suv.shape), "spacing": list(geom.spacing_ijk)},
    }


def classify(a: float, b: float, tol: float) -> str:
    rel = abs(a - b) / max(abs(a), abs(b), 1e-12)
    if rel <= tol:
        return "CONSISTENT"
    if rel > 2 * tol:
        return "DIFFERENT"
    return "INCONCLUSIVE"


def main(argv: list[str]) -> int:
    subject, ns = argv[1], ROOT / "outputs" / argv[2]
    reviews = yaml.safe_load((ns / "reference_review" / "reference_review.yaml").read_text())
    feats = {}
    for tp in ("baseline", "followup"):
        rv = reviews["reviews"][f"{subject}/{tp}"]["LIVER"]
        if rv["decision"] not in ("ACCEPT", "ADJUST"):
            print(f"{tp}: liver not accepted; stop")
            return 2
        g = rv["final_geometry"]
        case = build_case(ROOT / "data" / "acrin_longitudinal" / subject / tp, subject_id=subject)
        run = quantify_case(case, subject=subject)
        feats[tp] = features(
            run.outcome.suv,
            run.outcome.activity.geometry,
            tuple(g["centre_patient_mm"]),
            g["diameter_mm"],
        )
    b, f = feats["baseline"], feats["followup"]
    comp = {
        "voxel_grid": "IDENTICAL" if b["grid"] == f["grid"] else "DIFFERENT",
        **{
            k: {
                "baseline": b[k],
                "followup": f[k],
                "relative_difference": abs(b[k] - f[k]) / max(abs(b[k]), abs(f[k])),
                "heuristic_tolerance": t,
                "class": classify(b[k], f[k], t),
            }
            for k, t in TOL.items()
        },
    }
    overall = (
        "NO_OBVIOUS_RECONSTRUCTION_INCONSISTENCY_DETECTED"
        if comp["voxel_grid"] == "IDENTICAL"
        and all(v["class"] == "CONSISTENT" for k, v in comp.items() if k != "voxel_grid")
        else "POSSIBLE_RECONSTRUCTION_DIFFERENCE"
        if any(v["class"] == "DIFFERENT" for k, v in comp.items() if k != "voxel_grid")
        else "INCONCLUSIVE"
    )
    out = {
        "trust_level": "LEVEL_E (image-derived corroboration; cannot establish identity)",
        "features": feats,
        "comparison": comp,
        "overall": overall,
    }
    (ns / "recon_corroboration.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({"comparison": comp, "overall": overall}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
