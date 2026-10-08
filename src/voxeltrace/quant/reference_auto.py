"""Deterministic, CT-guided PROPOSALS for PERCIST reference regions (``vt-refauto-1``).

No AI, no learned model. Every output is a PROPOSAL that a human must review
(``trial/reference.py``); an unreviewed proposal never feeds an assessability rule.

Regions (PERCIST 1.0, Wahl 2009):
  LIVER       3 cm diameter sphere in the right hepatic lobe;
  BLOOD_POOL  1 cm diameter x 2 cm long cylinder in the descending thoracic aorta.

Method (all on a 3 mm isotropic working grid resampled from the CT; Gaussian sigma 2 mm
before linear resampling; PET resampled the same way for QC only):
  1. Body = largest connected component of HU > -300. Each axial slice is hole-filled.
     Lungs = connected components of HU < -400 inside the filled body, each >= 300 mL.
     The patient midline is the body centroid x (LPS: -x = patient right).
  2. LIVER: soft tissue (10 < HU < 150) inside the body, right of the midline by >= 10 mm,
     within [-150, +40] mm (z) of the right-lung base and outside the supplied lesions.
     The centre is the voxel deepest inside that mask (largest 3-D distance to its boundary);
     the depth must be >= 15 mm (sphere radius) + 3 mm.
  3. BLOOD_POOL: on each slice in the middle 30-75 % of the lung z-range, the vertebral body
     is located (HU > 250 near the midline, posterior half). Candidates are local maxima of
     the 2-D distance map of soft tissue (0 < HU < 400, not bone), restricted to a window
     left-anterior of the vertebral body (x: +3..+45 mm, y: -35..+20 mm from its anterior
     edge), with an inscribed radius of 6-18 mm and the lung within (radius + 10) mm.
     Candidates are chained slice to slice (<= 4.5 mm in-plane step). The proposal is the 2 cm
     run whose centres deviate <= 4.5 mm from their median, closest to 55 % of the lung
     z-range; centre = median x, y and mean z of that run.

QC recorded for the reviewer: CT HU mean/SD in the region, depth/radius, chain deviation.
Everything else (QC refusals, SUV statistics on the PET grid) is done by
``measure_reference_region`` when the region is measured.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Literal

import numpy as np
import SimpleITK as sitk
from pydantic import BaseModel, Field

from voxeltrace.quant.reference_region import ReferenceRegionSpec, Region
from voxeltrace.schemas import ImageGeometry

ALGORITHM_VERSION = "vt-refauto-1"
WORK_MM = 3.0
SMOOTH_SIGMA_MM = 2.0
LIVER_DIAMETER_MM = 30.0
BLOOD_DIAMETER_MM = 10.0
BLOOD_LENGTH_MM = 20.0
MIN_LUNG_ML = 300.0
LIVER_DEPTH_MARGIN_MM = 3.0
CHAIN_STEP_MM = 4.5
CHAIN_DEV_MM = 4.5
STANDARD_AXIAL = np.array([1.0, 0.0, 0.0, 0.0, 1.0, 0.0])


class ReferenceProposal(BaseModel):
    region: Region
    status: Literal["PROPOSED", "NOT_FOUND"]
    algorithm_version: str = ALGORITHM_VERSION
    method: Literal["SPHERE_AT_SUPPLIED_CENTRE", "CYLINDER_AT_SUPPLIED_CENTRE"] | None = None
    centre_patient_mm: tuple[float, float, float] | None = None
    diameter_mm: float | None = None
    length_mm: float | None = None
    pet_series_pseudonym: str | None = None
    ct_series_pseudonym: str | None = None
    failure_reason: str | None = None
    qc: dict[str, float] = Field(default_factory=dict)

    @property
    def sha256(self) -> str:
        """Binds a review to this exact proposal (region, geometry, algorithm, series)."""
        key = {
            "region": self.region,
            "status": self.status,
            "algorithm_version": self.algorithm_version,
            "method": self.method,
            "centre_patient_mm": self.centre_patient_mm,
            "diameter_mm": self.diameter_mm,
            "length_mm": self.length_mm,
            "pet_series_pseudonym": self.pet_series_pseudonym,
            "ct_series_pseudonym": self.ct_series_pseudonym,
        }
        return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()

    def to_spec(
        self, provenance: str, centre: tuple[float, float, float] | None = None
    ) -> ReferenceRegionSpec:
        if self.status != "PROPOSED":
            raise ValueError("no proposal to convert")
        return ReferenceRegionSpec(
            region=self.region,
            method=self.method,  # type: ignore[arg-type]
            centre_patient_mm=centre or self.centre_patient_mm,
            diameter_mm=self.diameter_mm,
            length_mm=self.length_mm,
            provenance=provenance,
        )


@dataclass
class WorkGrid:
    """CT (HU) and PET (SUV) on the working grid; kept for QC rendering."""

    hu: np.ndarray
    suv: np.ndarray | None
    origin: np.ndarray
    spacing: float
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray

    def index_of(self, xyz: tuple[float, float, float]) -> tuple[int, int, int]:
        i, j, k = ((np.asarray(xyz) - self.origin) / self.spacing).round().astype(int)
        return int(k), int(j), int(i)


def _to_sitk(arr: np.ndarray, g: ImageGeometry) -> sitk.Image:
    im = sitk.GetImageFromArray(arr)
    im.SetOrigin([float(v) for v in g.origin])
    im.SetSpacing([float(v) for v in g.spacing_ijk])  # type: ignore[arg-type]
    im.SetDirection([float(v) for v in g.direction])
    return im


def _axial(g: ImageGeometry) -> str | None:
    d = np.asarray(g.direction, dtype=float).reshape(3, 3)
    if np.abs(np.concatenate([d[:, 0], d[:, 1]]) - STANDARD_AXIAL).max() > 1e-4:
        return "non-axial orientation"
    if g.spacing_ijk[2] is None:
        return "non-uniform slice spacing"
    if g.coordinate_system != "LPS":
        return "not a DICOM LPS grid"
    return None


def _dist(mask: np.ndarray, spacing: float, inside: bool = True) -> np.ndarray:
    """Euclidean distance (mm) to the mask boundary: positive inside (``inside``) or to the
    mask from outside (``inside=False``)."""
    if not mask.any():
        return np.full(mask.shape, -np.inf if inside else np.inf)
    im = sitk.GetImageFromArray(mask.astype(np.uint8))
    d = sitk.GetArrayFromImage(
        sitk.SignedMaurerDistanceMap(
            im, insideIsPositive=inside, squaredDistance=False, useImageSpacing=False
        )
    )
    return d * spacing


def _ranked_components(mask: np.ndarray) -> np.ndarray:
    cc = sitk.ConnectedComponent(sitk.GetImageFromArray(mask.astype(np.uint8)))
    return sitk.GetArrayFromImage(sitk.RelabelComponent(cc))


def work_grid(
    ct: np.ndarray,
    ct_geom: ImageGeometry,
    suv: np.ndarray | None = None,
    pet_geom: ImageGeometry | None = None,
) -> WorkGrid:
    img = sitk.SmoothingRecursiveGaussian(_to_sitk(ct.astype(np.float32), ct_geom), SMOOTH_SIGMA_MM)
    size = [int(np.floor(img.GetSize()[a] * img.GetSpacing()[a] / WORK_MM)) for a in range(3)]
    ref = sitk.Image(size, sitk.sitkFloat32)
    ref.SetOrigin(img.GetOrigin())
    ref.SetSpacing([WORK_MM] * 3)
    ref.SetDirection(img.GetDirection())
    hu = sitk.GetArrayFromImage(sitk.Resample(img, ref, sitk.Transform(), sitk.sitkLinear, -1024.0))
    pet = None
    if suv is not None and pet_geom is not None:
        pet = sitk.GetArrayFromImage(
            sitk.Resample(
                _to_sitk(suv.astype(np.float32), pet_geom),
                ref,
                sitk.Transform(),
                sitk.sitkLinear,
                0.0,
            )
        )
    o = np.asarray(ref.GetOrigin(), dtype=float)
    nk, nj, ni = hu.shape
    return WorkGrid(
        hu=hu,
        suv=pet,
        origin=o,
        spacing=WORK_MM,
        x=o[0] + WORK_MM * np.arange(ni),
        y=o[1] + WORK_MM * np.arange(nj),
        z=o[2] + WORK_MM * np.arange(nk),
    )


def _lesion_mask_on_work(
    lesion_masks: list[np.ndarray] | None, pet_geom: ImageGeometry | None, w: WorkGrid
) -> np.ndarray | None:
    if not lesion_masks or pet_geom is None:
        return None
    union = np.zeros_like(lesion_masks[0], dtype=np.uint8)
    for m in lesion_masks:
        union |= m.astype(np.uint8)
    ref = sitk.Image([len(w.x), len(w.y), len(w.z)], sitk.sitkUInt8)
    ref.SetOrigin(w.origin.tolist())
    ref.SetSpacing([w.spacing] * 3)
    out = sitk.Resample(
        _to_sitk(union, pet_geom), ref, sitk.Transform(), sitk.sitkNearestNeighbor, 0
    )
    return sitk.GetArrayFromImage(out) > 0


def _not_found(region: Region, why: str, **kw) -> ReferenceProposal:
    return ReferenceProposal(region=region, status="NOT_FOUND", failure_reason=why, **kw)


def propose_reference_regions(
    ct: np.ndarray,
    ct_geom: ImageGeometry,
    *,
    suv: np.ndarray | None = None,
    pet_geom: ImageGeometry | None = None,
    lesion_masks: list[np.ndarray] | None = None,
    pet_series_pseudonym: str | None = None,
    ct_series_pseudonym: str | None = None,
) -> tuple[dict[str, ReferenceProposal], WorkGrid | None]:
    ids = {"pet_series_pseudonym": pet_series_pseudonym, "ct_series_pseudonym": ct_series_pseudonym}
    bad = _axial(ct_geom)
    if bad:
        return {
            r: _not_found(r, f"CT {bad} not supported", **ids) for r in ("LIVER", "BLOOD_POOL")
        }, None
    w = work_grid(ct, ct_geom, suv, pet_geom)
    hu = w.hu
    nk = hu.shape[0]
    body = _ranked_components(hu > -300) == 1
    if not body.any():
        return {r: _not_found(r, "no body found on CT", **ids) for r in ("LIVER", "BLOOD_POOL")}, w
    filled = np.zeros_like(body)
    for k in range(nk):
        filled[k] = (
            sitk.GetArrayFromImage(
                sitk.BinaryFillhole(sitk.GetImageFromArray(body[k].astype(np.uint8)))
            )
            > 0
        )
    lab = _ranked_components((hu < -400) & filled)
    vox_ml = w.spacing**3 / 1000.0
    vols = np.bincount(lab.ravel())[1:] * vox_ml
    lungs = np.isin(lab, [i + 1 for i, v in enumerate(vols) if v >= MIN_LUNG_ML])
    if not lungs.any():
        return {
            r: _not_found(r, "lungs not found on CT", **ids) for r in ("LIVER", "BLOOD_POOL")
        }, w
    x_mid = float(w.x[np.nonzero(body)[2]].mean())
    lk = np.nonzero(lungs)[0]
    z_lmin, z_lmax = float(w.z[lk].min()), float(w.z[lk].max())
    lesions = _lesion_mask_on_work(lesion_masks, pet_geom, w)
    out = {
        "LIVER": _liver(w, body, lungs, x_mid, lesions, ids),
        "BLOOD_POOL": _blood_pool(w, body, lungs, x_mid, z_lmin, z_lmax, ids),
    }
    return out, w


def _region_hu(w: WorkGrid, m: np.ndarray) -> dict[str, float]:
    q = {"ct_hu_mean": float(w.hu[m].mean()), "ct_hu_sd": float(w.hu[m].std())}
    if w.suv is not None:
        q["work_grid_suv_mean"] = float(w.suv[m].mean())
    return q


def _liver(w, body, lungs, x_mid, lesions, ids) -> ReferenceProposal:
    xg, zg = w.x[None, None, :], w.z[:, None, None]
    right_lung = lungs & (xg < x_mid)
    area = right_lung.sum(axis=(1, 2)) * w.spacing**2
    ks = np.nonzero(area > 500.0)[0]
    if ks.size == 0:
        return _not_found("LIVER", "right lung base not found", **ids)
    z_base = float(w.z[ks.min()])
    soft = (
        (w.hu > 10)
        & (w.hu < 150)
        & body
        & (xg < x_mid - 10)
        & (zg < z_base + 40)
        & (zg > z_base - 150)
    )
    if lesions is not None:
        soft &= ~lesions
    dist = _dist(soft, w.spacing)
    flat = int(np.argmax(dist))
    depth = float(dist.ravel()[flat])
    need = LIVER_DIAMETER_MM / 2 + LIVER_DEPTH_MARGIN_MM
    if not np.isfinite(depth) or depth < need:
        return _not_found(
            "LIVER", f"no homogeneous right upper-abdominal soft tissue >= {need} mm deep", **ids
        )
    k, j, i = np.unravel_index(flat, dist.shape)
    c = (round(float(w.x[i]), 1), round(float(w.y[j]), 1), round(float(w.z[k]), 1))
    yg = w.y[None, :, None]
    sph = (xg - c[0]) ** 2 + (yg - c[1]) ** 2 + (zg - c[2]) ** 2 <= (LIVER_DIAMETER_MM / 2) ** 2
    return ReferenceProposal(
        region="LIVER",
        status="PROPOSED",
        method="SPHERE_AT_SUPPLIED_CENTRE",
        centre_patient_mm=c,
        diameter_mm=LIVER_DIAMETER_MM,
        qc={"depth_mm": depth, "right_lung_base_z_mm": z_base, **_region_hu(w, sph)},
        **ids,
    )


def _blood_pool(w, body, lungs, x_mid, z_lmin, z_lmax, ids) -> ReferenceProposal:
    xs2, ys2 = np.meshgrid(w.x, w.y)  # [j, i]
    span = z_lmax - z_lmin
    band = [k for k, z in enumerate(w.z) if z_lmin + 0.30 * span < z < z_lmin + 0.75 * span]
    cands: dict[int, list[tuple[float, float, float]]] = {}
    for k in band:
        hu, bk = w.hu[k], body[k]
        if not bk.any():
            continue
        bone = (hu > 250) & bk
        spine = bone & (np.abs(xs2 - x_mid) < 25) & (ys2 > ys2[bk].mean())
        if spine.sum() < 20:
            continue
        cx = float(xs2[spine].mean())
        front = spine & (np.abs(xs2 - cx) < 12)
        if not front.any():
            continue
        y_ant = float(ys2[front].min())
        win = (xs2 > cx + 3) & (xs2 < cx + 45) & (ys2 > y_ant - 35) & (ys2 < y_ant + 20)
        soft = (hu > 0) & (hu < 400) & ~bone & bk
        dm = _dist(soft, w.spacing)
        ld = _dist(lungs[k], w.spacing, inside=False)
        ok = soft & win & (dm >= 6) & (dm <= 18) & (ld <= dm + 10)
        if not ok.any():
            continue
        pad = np.pad(dm, 1, constant_values=-np.inf)
        nb = np.max(
            [
                pad[1 + a : 1 + a + dm.shape[0], 1 + b : 1 + b + dm.shape[1]]
                for a in (-1, 0, 1)
                for b in (-1, 0, 1)
                if (a, b) != (0, 0)
            ],
            axis=0,
        )
        js, is_ = np.nonzero(ok & (dm >= nb))
        cands[k] = [
            (float(xs2[j, i]), float(ys2[j, i]), float(dm[j, i]))
            for j, i in zip(js, is_, strict=True)
        ]
    need = int(np.ceil(BLOOD_LENGTH_MM / w.spacing)) + 1
    z_target = z_lmin + 0.55 * span
    best: tuple[tuple[float, float], list[tuple[int, float, float, float]]] | None = None
    for k0 in sorted(cands):
        for c0 in cands[k0]:
            chain = [(k0, *c0)]
            k = k0
            while k + 1 in cands:
                px, py = chain[-1][1], chain[-1][2]
                nxt = [c for c in cands[k + 1] if np.hypot(c[0] - px, c[1] - py) <= CHAIN_STEP_MM]
                if not nxt:
                    break
                chain.append((k + 1, *min(nxt, key=lambda c: (np.hypot(c[0] - px, c[1] - py), c))))
                k += 1
            for s0 in range(len(chain) - need + 1):
                seg = chain[s0 : s0 + need]
                sx = np.array([c[1] for c in seg])
                sy = np.array([c[2] for c in seg])
                dev = float(np.hypot(sx - np.median(sx), sy - np.median(sy)).max())
                if dev > CHAIN_DEV_MM:
                    continue
                zmid = float(np.mean([w.z[c[0]] for c in seg]))
                key = (abs(zmid - z_target), dev)
                if best is None or key < best[0]:
                    best = (key, seg)
    if best is None:
        return _not_found(
            "BLOOD_POOL", "no consistent 2 cm descending-aorta segment found on CT", **ids
        )
    seg = best[1]
    sx = np.array([c[1] for c in seg])
    sy = np.array([c[2] for c in seg])
    c = (
        round(float(np.median(sx)), 1),
        round(float(np.median(sy)), 1),
        round(float(np.mean([w.z[s[0]] for s in seg])), 1),
    )
    xg, yg, zg = w.x[None, None, :], w.y[None, :, None], w.z[:, None, None]
    cyl = ((xg - c[0]) ** 2 + (yg - c[1]) ** 2 <= (BLOOD_DIAMETER_MM / 2) ** 2) & (
        np.abs(zg - c[2]) <= BLOOD_LENGTH_MM / 2
    )
    return ReferenceProposal(
        region="BLOOD_POOL",
        status="PROPOSED",
        method="CYLINDER_AT_SUPPLIED_CENTRE",
        centre_patient_mm=c,
        diameter_mm=BLOOD_DIAMETER_MM,
        length_mm=BLOOD_LENGTH_MM,
        qc={
            "chain_deviation_mm": best[0][1],
            "mean_inscribed_radius_mm": float(np.mean([s[3] for s in seg])),
            "lung_fraction_of_z_range": (c[2] - z_lmin) / span,
            **_region_hu(w, cyl),
        },
        **ids,
    )
