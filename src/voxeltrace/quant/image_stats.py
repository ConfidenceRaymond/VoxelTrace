"""Deterministic whole-array image statistics.

Inputs are validated rather than coerced: non-numeric, boolean, complex and
empty arrays are rejected. NaN and +/-inf are counted and excluded from the
intensity statistics; they are never replaced. Finite values are promoted to
float64 for the arithmetic only, so integer arrays do not overflow.
"""

from __future__ import annotations

import numpy as np

from voxeltrace.schemas import ImageStats


def compute_image_stats(array: np.ndarray) -> ImageStats:
    """Compute deterministic summary statistics for a real-valued numeric array.

    Raises:
        TypeError: if ``array`` is not an ndarray or has a non-real-numeric dtype.
        ValueError: if ``array`` is empty.
    """
    if not isinstance(array, np.ndarray):
        raise TypeError(f"expected numpy.ndarray, got {type(array).__name__}")
    if array.dtype == np.bool_ or not (
        np.issubdtype(array.dtype, np.integer) or np.issubdtype(array.dtype, np.floating)
    ):
        raise TypeError(f"unsupported dtype {array.dtype}; expected real integer or float")
    if array.size == 0:
        raise ValueError("cannot compute statistics of an empty array")

    voxel_count = int(array.size)
    finite_mask = np.isfinite(array)
    finite_count = int(finite_mask.sum())

    if np.issubdtype(array.dtype, np.floating):
        nan_count = int(np.isnan(array).sum())
        posinf_count = int(np.isposinf(array).sum())
        neginf_count = int(np.isneginf(array).sum())
    else:
        nan_count = posinf_count = neginf_count = 0

    zero_count = int((array == 0).sum())

    finite = array[finite_mask].astype(np.float64, copy=False)
    if finite_count:
        p01, median, p99 = np.percentile(finite, [1.0, 50.0, 99.0])
        intensity = {
            "finite_min": float(finite.min()),
            "finite_max": float(finite.max()),
            "finite_mean": float(finite.mean()),
            "finite_std": float(finite.std(ddof=0)),
            "median": float(median),
            "p01": float(p01),
            "p99": float(p99),
        }
    else:
        intensity = dict.fromkeys(
            ("finite_min", "finite_max", "finite_mean", "finite_std", "median", "p01", "p99")
        )

    return ImageStats(
        shape=tuple(int(n) for n in array.shape),
        dtype=str(array.dtype),
        voxel_count=voxel_count,
        finite_count=finite_count,
        nan_count=nan_count,
        nan_fraction=nan_count / voxel_count,
        posinf_count=posinf_count,
        neginf_count=neginf_count,
        zero_count=zero_count,
        zero_fraction=zero_count / voxel_count,
        **intensity,
    )
