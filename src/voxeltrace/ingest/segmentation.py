"""Segmentation ingestion: NIfTI label masks and DICOM SEG.

DICOM SEG pixel decoding is deliberately strict. It supports only:
- SegmentationType BINARY (FRACTIONAL and LABELMAP are refused),
- frames whose PlanePositionSequence positions coincide with slices of a single-frame
  reference series in the same FrameOfReference and orientation,
- matching Rows/Columns and pixel spacing.
Anything else is refused with a QC error rather than partially reconstructed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pydicom
from pydicom.dataset import Dataset

from voxeltrace.ingest.dicom import (
    ORIENTATION_TOL,
    POSITION_TOL_MM,
    IngestError,
    _floats,
    _get,
    _int,
    _str,
    series_geometry,
)
from voxeltrace.ingest.nifti import compare_geometry, load_nifti
from voxeltrace.schemas import (
    ImageGeometry,
    ImagingSeries,
    QCWarning,
    SegmentationMetadata,
    SegmentInfo,
)

# --------------------------------------------------------------------------------------
# NIfTI masks
# --------------------------------------------------------------------------------------


@dataclass
class LabelMask:
    array: np.ndarray
    metadata: SegmentationMetadata
    warnings: list[QCWarning]


def load_nifti_mask(
    path: str | os.PathLike[str], reference: ImageGeometry | None = None
) -> LabelMask:
    """Load a NIfTI label mask, validate label content and compare to a reference grid.

    Raises ValueError if the content is not a label map (non-integral or non-finite values).
    Label values are preserved exactly; nothing is binarised or relabelled.
    """
    vol = load_nifti(path)
    arr = vol.array
    warnings = list(vol.warnings)
    if np.issubdtype(arr.dtype, np.floating):
        if not np.isfinite(arr).all():
            raise ValueError(f"{path}: mask contains NaN/inf; not a valid label map")
        if not np.array_equal(arr, np.round(arr)):
            raise ValueError(f"{path}: mask has non-integer values; not a label map")
        warnings.append(
            QCWarning(
                code="MASK_FLOAT_STORAGE",
                severity="info",
                path=str(path),
                message="mask stored as float; values are integral",
            )
        )
    elif not np.issubdtype(arr.dtype, np.integer) and arr.dtype != np.bool_:
        raise ValueError(f"{path}: unsupported mask dtype {arr.dtype}")
    if (arr < 0).any():
        warnings.append(
            QCWarning(
                code="MASK_NEGATIVE_LABELS",
                path=str(path),
                message="mask contains negative label values",
            )
        )
    values, counts = np.unique(arr, return_counts=True)
    labels = [int(v) for v in values]
    meta = SegmentationMetadata(
        source="NIFTI",
        path=str(path),
        label_values=labels,
        label_voxel_counts={int(v): int(c) for v, c in zip(values, counts, strict=True)},
        segments=[SegmentInfo(number=v) for v in labels if v != 0],
        pixel_decoding="DECODED",
    )
    if set(labels) <= {0, 1}:
        meta.segmentation_type = "BINARY"
    else:
        meta.segmentation_type = "LABELMAP"
    if reference is not None:
        ok, why = compare_geometry(vol.geometry, reference)
        meta.geometry_matches_reference = ok
        if not ok:
            warnings.append(
                QCWarning(
                    code="MASK_GEOMETRY_MISMATCH",
                    severity="error",
                    path=str(path),
                    message=f"mask vs reference: {why}",
                )
            )
    return LabelMask(arr, meta, warnings)


# --------------------------------------------------------------------------------------
# DICOM SEG metadata
# --------------------------------------------------------------------------------------


def _code_meaning(item: Dataset, keyword: str) -> str | None:
    seq = _get(item, keyword)
    return _str(_get(seq[0], "CodeMeaning")) if seq else None


def parse_dicom_seg(path: str | os.PathLike[str]) -> tuple[SegmentationMetadata, list[QCWarning]]:
    """Read DICOM SEG header metadata (no pixel data)."""
    ds = pydicom.dcmread(path, stop_before_pixels=True)
    warnings: list[QCWarning] = []
    series_uid = _str(_get(ds, "SeriesInstanceUID"))
    segments: list[SegmentInfo] = []
    for item in _get(ds, "SegmentSequence") or []:
        num = _int(_get(item, "SegmentNumber"))
        if num is None:
            warnings.append(
                QCWarning(
                    code="SEG_SEGMENT_NUMBER_MISSING",
                    series_uid=series_uid,
                    path=str(path),
                    message="segment item without number",
                )
            )
            continue
        segments.append(
            SegmentInfo(
                number=num,
                label=_str(_get(item, "SegmentLabel")),
                description=_str(_get(item, "SegmentDescription")),
                algorithm_type=_str(_get(item, "SegmentAlgorithmType")),
                category=_code_meaning(item, "SegmentedPropertyCategoryCodeSequence"),
                type=_code_meaning(item, "SegmentedPropertyTypeCodeSequence"),
            )
        )
    if not segments:
        warnings.append(
            QCWarning(
                code="SEG_NO_SEGMENTS",
                severity="error",
                path=str(path),
                series_uid=series_uid,
                message="SegmentSequence empty/absent",
            )
        )

    ref_series: list[str] = []
    for item in _get(ds, "ReferencedSeriesSequence") or []:
        if (uid := _str(_get(item, "SeriesInstanceUID"))) and uid not in ref_series:
            ref_series.append(uid)
    if not ref_series:
        warnings.append(
            QCWarning(
                code="SEG_NO_REFERENCED_SERIES",
                path=str(path),
                series_uid=series_uid,
                message="ReferencedSeriesSequence absent; source series unknown",
            )
        )
    meta = SegmentationMetadata(
        source="DICOM_SEG",
        path=str(path),
        series_uid=series_uid,
        segmentation_type=_str(_get(ds, "SegmentationType")),
        segments=segments,
        referenced_series_uids=ref_series,
        referenced_study_uid=_str(_get(ds, "StudyInstanceUID")),
        frame_of_reference_uid=_str(_get(ds, "FrameOfReferenceUID")),
        number_of_frames=_int(_get(ds, "NumberOfFrames")),
    )
    return meta, warnings


# --------------------------------------------------------------------------------------
# DICOM SEG strict pixel decoding
# --------------------------------------------------------------------------------------


@dataclass
class DecodedSeg:
    """Per-segment boolean masks on the reference grid, array order ``[slice, row, column]``."""

    masks: dict[int, np.ndarray]
    geometry: ImageGeometry
    metadata: SegmentationMetadata
    warnings: list[QCWarning]


def _frame_info(
    ds: Dataset, idx: int
) -> tuple[int | None, tuple[float, ...] | None, tuple[float, ...] | None]:
    pffg = _get(ds, "PerFrameFunctionalGroupsSequence")
    sfg = _get(ds, "SharedFunctionalGroupsSequence")
    shared = sfg[0] if sfg else None
    frame = pffg[idx] if pffg and idx < len(pffg) else None

    def lookup(seq_kw: str, attr: str, n: int) -> tuple[float, ...] | None:
        for grp in (frame, shared):
            if grp is None:
                continue
            seq = _get(grp, seq_kw)
            if seq:
                return _floats(_get(seq[0], attr), n)
        return None

    seg_num: int | None = None
    if frame is not None and (sis := _get(frame, "SegmentIdentificationSequence")):
        seg_num = _int(_get(sis[0], "ReferencedSegmentNumber"))
    pos = lookup("PlanePositionSequence", "ImagePositionPatient", 3)
    ori = lookup("PlaneOrientationSequence", "ImageOrientationPatient", 6)
    return seg_num, pos, ori


def _seg_pixel_spacing(ds: Dataset) -> tuple[float, ...] | None:
    sfg = _get(ds, "SharedFunctionalGroupsSequence")
    if sfg and (pms := _get(sfg[0], "PixelMeasuresSequence")):
        return _floats(_get(pms[0], "PixelSpacing"), 2)
    return None


def decode_dicom_seg(path: str | os.PathLike[str], reference: ImagingSeries) -> DecodedSeg:
    """Reconstruct BINARY DICOM SEG segments onto the grid of ``reference``.

    Raises IngestError (and never returns partial masks) if any check fails.
    """
    meta, warnings = parse_dicom_seg(path)

    def refuse(msg: str) -> IngestError:
        meta.pixel_decoding = "REFUSED"
        return IngestError(f"DICOM SEG decoding refused: {msg}")

    if meta.segmentation_type != "BINARY":
        raise refuse(f"SegmentationType {meta.segmentation_type!r} not supported (BINARY only)")
    if meta.referenced_series_uids and reference.series_uid not in meta.referenced_series_uids:
        raise refuse("reference series is not referenced by the SEG")
    if meta.frame_of_reference_uid is None or reference.frame_of_reference_uids != [
        meta.frame_of_reference_uid
    ]:
        raise refuse("FrameOfReferenceUID missing or differs from reference series")
    ref_geom, geom_warns = series_geometry(reference)
    if ref_geom is None or ref_geom.slice_positions_mm is None:
        raise refuse(
            "reference series geometry unavailable: " + "; ".join(w.message for w in geom_warns)
        )

    ds = pydicom.dcmread(path)
    rows, cols = _int(_get(ds, "Rows")), _int(_get(ds, "Columns"))
    if (cols, rows) != ref_geom.shape_ijk[:2]:
        raise refuse(f"SEG matrix {rows}x{cols} differs from reference")
    spacing = _seg_pixel_spacing(ds)
    if (
        spacing is None
        or abs(spacing[1] - ref_geom.spacing_ijk[0]) > 1e-3
        or abs(spacing[0] - ref_geom.spacing_ijk[1]) > 1e-3
    ):
        raise refuse("SEG PixelSpacing missing or differs from reference")
    try:
        frames = ds.pixel_array
    except Exception as exc:  # noqa: BLE001
        raise refuse(f"pixel data cannot be decoded: {exc}") from exc
    n_frames = _int(_get(ds, "NumberOfFrames")) or 1
    if frames.ndim == 2:
        frames = frames[np.newaxis]
    if frames.shape[0] != n_frames:
        raise refuse("frame count does not match NumberOfFrames")
    if not set(np.unique(frames).tolist()) <= {0, 1}:
        raise refuse("BINARY SEG contains values other than 0/1")

    ref_dir = np.asarray(ref_geom.direction).reshape(3, 3)
    row_dir, col_dir, normal = ref_dir[:, 0], ref_dir[:, 1], ref_dir[:, 2]
    origin = np.asarray(ref_geom.origin)
    positions = np.asarray(ref_geom.slice_positions_mm)
    dx, dy = float(ref_geom.spacing_ijk[0]), float(ref_geom.spacing_ijk[1])
    known = {s.number for s in meta.segments}
    nz, ny, nx = len(positions), ref_geom.shape_ijk[1], ref_geom.shape_ijk[0]
    masks: dict[int, np.ndarray] = {n: np.zeros((nz, ny, nx), dtype=bool) for n in known}
    seen: set[tuple[int, int]] = set()
    mirrored = False
    grid_tol = 0.01  # voxel units: frame pixels must land on reference voxel centres
    for f in range(n_frames):
        seg_num, pos, ori = _frame_info(ds, f)
        if seg_num is None or seg_num not in known:
            raise refuse(f"frame {f}: missing/unknown ReferencedSegmentNumber")
        if pos is None or ori is None:
            raise refuse(f"frame {f}: missing plane position/orientation")
        fx, fy = np.asarray(ori[:3]), np.asarray(ori[3:])
        # Only axis-aligned mirroring is supported (no rotation/transposition/obliquity).
        sx = (
            1
            if np.abs(fx - row_dir).max() <= ORIENTATION_TOL
            else (-1 if np.abs(fx + row_dir).max() <= ORIENTATION_TOL else 0)
        )
        sy = (
            1
            if np.abs(fy - col_dir).max() <= ORIENTATION_TOL
            else (-1 if np.abs(fy + col_dir).max() <= ORIENTATION_TOL else 0)
        )
        if sx == 0 or sy == 0:
            raise refuse(f"frame {f}: orientation differs from reference (not a pure mirror)")
        mirrored |= sx < 0 or sy < 0
        p = np.asarray(pos)
        i0 = float((p - origin) @ row_dir) / dx
        j0 = float((p - origin) @ col_dir) / dy
        if abs(i0 - round(i0)) > grid_tol or abs(j0 - round(j0)) > grid_tol:
            raise refuse(f"frame {f}: pixel grid offset from reference voxel centres")
        i_idx = round(i0) + sx * np.arange(cols)  # type: ignore[operator]
        j_idx = round(j0) + sy * np.arange(rows)  # type: ignore[operator]
        if i_idx.min() < 0 or i_idx.max() >= nx or j_idx.min() < 0 or j_idx.max() >= ny:
            raise refuse(f"frame {f}: frame extends outside the reference grid")
        k = int(np.argmin(np.abs(positions - p @ normal)))
        if abs(positions[k] - p @ normal) > POSITION_TOL_MM * 10:
            raise refuse(f"frame {f}: position does not match any reference slice")
        if (seg_num, k) in seen:
            raise refuse(f"frame {f}: duplicate frame for segment {seg_num} slice {k}")
        seen.add((seg_num, k))
        masks[seg_num][k][np.ix_(j_idx, i_idx)] = frames[f].astype(bool)
    if mirrored:
        warnings.append(
            QCWarning(
                code="SEG_FRAMES_MIRRORED",
                severity="info",
                path=str(path),
                series_uid=meta.series_uid,
                message="SEG frames are stored with mirrored row/column direction relative to the "
                "reference; mapped voxel-exactly via frame geometry (no interpolation)",
            )
        )
    meta.pixel_decoding = "DECODED"
    meta.geometry_matches_reference = True
    return DecodedSeg(masks, ref_geom, meta, warnings)
