"""NIfTI loading with nibabel. Orientation is preserved exactly as stored."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import nibabel as nib
import numpy as np

from voxeltrace.quant import compute_image_stats
from voxeltrace.schemas import ImageGeometry, ImageStats, QCWarning

NIFTI_SUFFIXES = (".nii", ".nii.gz")
AFFINE_TOL_MM = 1e-3


def is_nifti_path(path: str | os.PathLike[str]) -> bool:
    return str(path).lower().endswith(NIFTI_SUFFIXES)


@dataclass
class NiftiVolume:
    """``array`` is in nibabel (i, j, k) order; ``geometry.affine`` is the file's RAS affine."""

    path: str
    array: np.ndarray
    geometry: ImageGeometry
    on_disk_dtype: str
    stats: ImageStats
    warnings: list[QCWarning]


def nifti_geometry(img: nib.Nifti1Image | nib.Nifti2Image) -> ImageGeometry:
    shape = tuple(int(n) for n in img.shape[:3])
    if len(shape) != 3:
        raise ValueError(f"expected a 3-D image, got shape {img.shape}")
    zooms = tuple(float(z) for z in img.header.get_zooms()[:3])
    aff = np.asarray(img.affine, dtype=float)
    direction = aff[:3, :3] / np.where(np.array(zooms) == 0, 1, np.array(zooms))
    return ImageGeometry(
        coordinate_system="RAS",
        shape_ijk=shape,  # type: ignore[arg-type]
        spacing_ijk=zooms,  # type: ignore[arg-type]
        origin=tuple(float(v) for v in aff[:3, 3]),  # type: ignore[arg-type]
        direction=tuple(float(v) for v in direction.ravel()),
        affine=aff.tolist(),
        extent_mm=tuple(n * z for n, z in zip(shape, zooms, strict=True)),  # type: ignore[arg-type]
        uniform_slice_spacing=True,
    )


def load_nifti(path: str | os.PathLike[str]) -> NiftiVolume:
    """Load a 3-D NIfTI image. Header scaling (scl_slope/inter) is applied by nibabel."""
    p = Path(path)
    img = nib.load(str(p))
    if not isinstance(img, nib.Nifti1Image | nib.Nifti2Image):
        raise ValueError(f"{p} is not a NIfTI image")
    warnings: list[QCWarning] = []
    if len(img.shape) == 4 and img.shape[3] == 1:
        warnings.append(
            QCWarning(
                code="NIFTI_SINGLETON_4D",
                severity="info",
                path=str(p),
                message="4-D image with one volume; using volume 0",
            )
        )
    elif len(img.shape) != 3:
        raise ValueError(f"{p}: expected 3-D image, got shape {img.shape}")
    data = np.asanyarray(img.dataobj)
    if data.ndim == 4:
        data = data[..., 0]
    geom = nifti_geometry(img)
    stats = compute_image_stats(np.asarray(data))
    if stats.finite_count < stats.voxel_count:
        warnings.append(
            QCWarning(
                code="NONFINITE_VOXELS",
                path=str(p),
                message=f"{stats.voxel_count - stats.finite_count} non-finite voxels",
            )
        )
    qform, sform = int(img.header["qform_code"]), int(img.header["sform_code"])
    if qform == 0 and sform == 0:
        warnings.append(
            QCWarning(
                code="NIFTI_NO_SPATIAL_CODE",
                path=str(p),
                message="qform_code and sform_code are 0; affine unreliable",
            )
        )
    return NiftiVolume(str(p), np.asarray(data), geom, str(img.get_data_dtype()), stats, warnings)


def compare_geometry(
    a: ImageGeometry, b: ImageGeometry, tol_mm: float = AFFINE_TOL_MM
) -> tuple[bool, str]:
    """Same voxel grid? Compares shape and the RAS affine. No resampling, no reorientation."""
    if a.shape_ijk != b.shape_ijk:
        return False, f"shape differs: {a.shape_ijk} vs {b.shape_ijk}"
    if None in a.spacing_ijk or None in b.spacing_ijk:
        return False, "slice spacing undefined for at least one image"
    diff = np.abs(np.asarray(a.affine_ras()) - np.asarray(b.affine_ras())).max()
    if diff > tol_mm:
        return False, f"affine differs (max abs difference {diff:.4g})"
    return True, "same grid"
