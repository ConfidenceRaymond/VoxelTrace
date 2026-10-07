"""DICOM discovery, PET metadata extraction and geometry-aware volume loading.

Rules:
- Modality comes from the Modality / SOPClassUID header only, never from paths.
- Discovery reads headers only (``stop_before_pixels=True``).
- Malformed files produce QC warnings, not exceptions.
- Missing or invalid metadata is reported, never defaulted.
- Slices are ordered by ImagePositionPatient projected on the slice normal.
"""

from __future__ import annotations

import math
import os
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pydicom
from pydicom.dataset import Dataset
from pydicom.errors import InvalidDicomError

from voxeltrace.schemas import (
    DicomInstance,
    ImageGeometry,
    ImagingSeries,
    MissingMetadata,
    PETMetadata,
    QCWarning,
    SeriesCategory,
)

SEG_SOP_CLASS_UID = "1.2.840.10008.5.1.4.1.1.66.4"
PET_SOP_CLASS_UIDS = frozenset(
    {"1.2.840.10008.5.1.4.1.1.128", "1.2.840.10008.5.1.4.1.1.130"}  # PET, Enhanced PET
)
CT_SOP_CLASS_UIDS = frozenset(
    {"1.2.840.10008.5.1.4.1.1.2", "1.2.840.10008.5.1.4.1.1.2.1"}  # CT, Enhanced CT
)

# Geometry tolerances.
ORIENTATION_TOL = 1e-4
POSITION_TOL_MM = 1e-3
SPACING_REL_TOL = 0.01

# PET fields required later for SUVbw (see docs/suv_requirements.md).
PET_REQUIRED_FIELDS = (
    "Units",
    "DecayCorrection",
    "CorrectedImage",
    "PatientWeight",
    "SeriesDate",
    "SeriesTime",
    "RadionuclideTotalDose",
    "RadionuclideHalfLife",
    "RadiopharmaceuticalStartTime",
)


class IngestError(RuntimeError):
    """Raised when data are too ambiguous or inconsistent to load safely."""


# --------------------------------------------------------------------------------------
# Value helpers: never raise, never default.
# --------------------------------------------------------------------------------------


def _get(ds: Dataset, keyword: str) -> Any:
    """Return an element value, ``None`` if absent; raw string if pydicom cannot convert it."""
    if keyword not in ds:
        return None
    try:
        return ds[keyword].value
    except Exception:  # noqa: BLE001 - malformed value; return what bytes we have
        raw = ds.get_item(keyword)
        val = getattr(raw, "value", None)
        return val.decode(errors="replace") if isinstance(val, bytes) else val


def _str(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _floats(value: Any, n: int) -> tuple[float, ...] | None:
    if value is None:
        return None
    try:
        vals = tuple(
            float(v)
            for v in (
                value
                if isinstance(value, Iterable) and not isinstance(value, str | bytes)
                else [value]
            )
        )
    except (TypeError, ValueError):
        return None
    if len(vals) != n or not all(math.isfinite(v) for v in vals):
        return None
    return vals


@dataclass
class _Checked:
    value: float | None
    problem: MissingMetadata | None


def _positive_number(value: Any, fieldname: str, scope: str, required: bool) -> _Checked:
    """Parse a numeric header value that must be finite and > 0 (weight, dose, half-life)."""
    if value is None:
        return _Checked(
            None, MissingMetadata(field=fieldname, scope=scope, status="absent", required=required)
        )
    raw = str(value).strip()
    if raw == "":
        return _Checked(
            None, MissingMetadata(field=fieldname, scope=scope, status="empty", required=required)
        )
    try:
        num = float(value)
    except (TypeError, ValueError):
        num = math.nan
    if not math.isfinite(num) or num <= 0:
        return _Checked(
            None,
            MissingMetadata(
                field=fieldname,
                scope=scope,
                status="invalid",
                required=required,
                raw_value=raw,
                note="must be a finite number > 0",
            ),
        )
    return _Checked(num, None)


def _presence(value: Any, fieldname: str, scope: str, required: bool) -> MissingMetadata | None:
    if value is None:
        return MissingMetadata(field=fieldname, scope=scope, status="absent", required=required)
    if (isinstance(value, str) and not value.strip()) or (
        isinstance(value, list | tuple | pydicom.multival.MultiValue) and len(value) == 0
    ):
        return MissingMetadata(field=fieldname, scope=scope, status="empty", required=required)
    return None


# --------------------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------------------


@dataclass
class DicomDiscovery:
    root: str
    series: list[ImagingSeries] = field(default_factory=list)
    warnings: list[QCWarning] = field(default_factory=list)
    files_scanned: int = 0
    dicom_files: int = 0
    non_dicom_ignored: int = 0
    unreadable: int = 0


def has_dicom_preamble(path: Path) -> bool:
    """True if the file has the 128-byte preamble + ``DICM`` marker (DICOM Part 10)."""
    try:
        with path.open("rb") as fh:
            head = fh.read(132)
    except OSError:
        return False
    return len(head) == 132 and head[128:132] == b"DICM"


def classify_series(modality: str | None, sop_class_uids: Iterable[str]) -> SeriesCategory:
    sops = set(sop_class_uids)
    if modality == "SEG" or SEG_SOP_CLASS_UID in sops:
        return "SEG"
    if modality == "PT" or sops & PET_SOP_CLASS_UIDS:
        return "PET"
    if modality == "CT" or sops & CT_SOP_CLASS_UIDS:
        return "CT"
    return "OTHER"


def _instance_from_header(ds: Dataset, path: Path) -> DicomInstance:
    pos = _floats(_get(ds, "ImagePositionPatient"), 3)
    ori = _floats(_get(ds, "ImageOrientationPatient"), 6)
    spacing = _floats(_get(ds, "PixelSpacing"), 2)
    thick = _floats(_get(ds, "SliceThickness"), 1)
    return DicomInstance(
        path=str(path),
        sop_instance_uid=_str(_get(ds, "SOPInstanceUID")),
        sop_class_uid=_str(_get(ds, "SOPClassUID")),
        instance_number=_int(_get(ds, "InstanceNumber")),
        image_position=pos,  # type: ignore[arg-type]
        image_orientation=ori,  # type: ignore[arg-type]
        pixel_spacing=spacing,  # type: ignore[arg-type]
        slice_thickness=thick[0] if thick else None,
        rows=_int(_get(ds, "Rows")),
        columns=_int(_get(ds, "Columns")),
        number_of_frames=_int(_get(ds, "NumberOfFrames")),
        frame_of_reference_uid=_str(_get(ds, "FrameOfReferenceUID")),
    )


def discover_dicom(root: str | os.PathLike[str]) -> DicomDiscovery:
    """Recursively discover DICOM Part-10 files under ``root`` and group them by UID."""
    root_path = Path(root)
    result = DicomDiscovery(root=str(root_path))
    if not root_path.is_dir():
        result.warnings.append(
            QCWarning(
                code="ROOT_NOT_A_DIRECTORY",
                severity="error",
                message=f"{root_path} is not a directory",
            )
        )
        return result

    groups: dict[tuple[str, str], list[tuple[Dataset, DicomInstance]]] = defaultdict(list)
    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(dirpath) / name
            if not path.is_file():
                continue
            result.files_scanned += 1
            if not has_dicom_preamble(path):
                result.non_dicom_ignored += 1
                continue
            try:
                ds = pydicom.dcmread(path, stop_before_pixels=True)
                study_uid = _str(_get(ds, "StudyInstanceUID"))
                series_uid = _str(_get(ds, "SeriesInstanceUID"))
            except (
                InvalidDicomError,
                OSError,
                ValueError,
                EOFError,
                KeyError,
                TypeError,
                AttributeError,
                NotImplementedError,
            ) as exc:
                result.unreadable += 1
                result.warnings.append(
                    QCWarning(
                        code="DICOM_UNREADABLE",
                        path=str(path),
                        message=f"cannot parse DICOM header: {type(exc).__name__}: {exc}",
                    )
                )
                continue
            if not study_uid or not series_uid:
                result.unreadable += 1
                result.warnings.append(
                    QCWarning(
                        code="DICOM_MISSING_UID",
                        path=str(path),
                        message="StudyInstanceUID or SeriesInstanceUID missing; file not grouped",
                    )
                )
                continue
            result.dicom_files += 1
            groups[(study_uid, series_uid)].append((ds, _instance_from_header(ds, path)))

    for (study_uid, series_uid), members in sorted(groups.items()):
        result.series.append(_build_series(study_uid, series_uid, members, result.warnings))
    return result


def _distinct(values: Iterable[Any]) -> list[Any]:
    out: list[Any] = []
    for v in values:
        if v is not None and v not in out:
            out.append(v)
    return out


def _build_series(
    study_uid: str,
    series_uid: str,
    members: list[tuple[Dataset, DicomInstance]],
    warnings: list[QCWarning],
) -> ImagingSeries:
    first = members[0][0]
    modalities = _distinct(_str(_get(ds, "Modality")) for ds, _ in members)
    sops = _distinct(inst.sop_class_uid for _, inst in members)
    fors = _distinct(inst.frame_of_reference_uid for _, inst in members)
    if len(modalities) > 1:
        warnings.append(
            QCWarning(
                code="MIXED_SERIES_MODALITY",
                severity="error",
                series_uid=series_uid,
                message=f"series contains several modalities: {modalities}",
            )
        )
    if len(fors) > 1:
        warnings.append(
            QCWarning(
                code="MIXED_FRAME_OF_REFERENCE",
                severity="error",
                series_uid=series_uid,
                message=f"series spans {len(fors)} FrameOfReferenceUIDs",
            )
        )
    if not modalities:
        warnings.append(
            QCWarning(
                code="MODALITY_MISSING",
                series_uid=series_uid,
                message="no Modality attribute in series",
            )
        )
    modality = modalities[0] if len(modalities) == 1 else None
    uids = [inst.sop_instance_uid for _, inst in members if inst.sop_instance_uid]
    if len(uids) != len(set(uids)):
        warnings.append(
            QCWarning(
                code="DUPLICATE_SOP_INSTANCE",
                severity="error",
                series_uid=series_uid,
                message="duplicate SOPInstanceUIDs in series",
            )
        )
    instances = sorted(
        (inst for _, inst in members),
        key=lambda i: (i.instance_number is None, i.instance_number or 0, i.path),
    )
    return ImagingSeries(
        study_uid=study_uid,
        series_uid=series_uid,
        modality=modality,
        category=classify_series(modality, sops) if len(modalities) <= 1 else "OTHER",
        series_description=_str(_get(first, "SeriesDescription")),
        study_description=_str(_get(first, "StudyDescription")),
        sop_class_uids=sops,
        frame_of_reference_uids=fors,
        series_number=_int(_get(first, "SeriesNumber")),
        manufacturer=_str(_get(first, "Manufacturer")),
        manufacturer_model_name=_str(_get(first, "ManufacturerModelName")),
        software_versions=_str(_get(first, "SoftwareVersions")),
        rows=_int(_get(first, "Rows")),
        columns=_int(_get(first, "Columns")),
        number_of_frames=_int(_get(first, "NumberOfFrames")),
        instances=instances,
    )


# --------------------------------------------------------------------------------------
# PET metadata
# --------------------------------------------------------------------------------------


def extract_pet_metadata(series: ImagingSeries) -> tuple[PETMetadata, list[QCWarning]]:
    """Read PET headers of every instance; report absent/invalid/inconsistent fields."""
    uid = series.series_uid
    warnings: list[QCWarning] = []
    headers = [pydicom.dcmread(i.path, stop_before_pixels=True) for i in series.instances]
    ds = headers[0]
    missing: list[MissingMetadata] = []

    def text(keyword: str, src: Dataset = ds) -> str | None:
        return _str(_get(src, keyword))

    for kw in ("Units", "DecayCorrection", "CorrectedImage", "SeriesDate", "SeriesTime"):
        if (m := _presence(_get(ds, kw), kw, uid, required=True)) is not None:
            missing.append(m)
    for kw in ("AcquisitionDate", "AcquisitionTime"):
        if (m := _presence(_get(ds, kw), kw, uid, required=False)) is not None:
            missing.append(m)

    weight = _positive_number(_get(ds, "PatientWeight"), "PatientWeight", uid, required=True)
    if weight.problem:
        missing.append(weight.problem)

    rp_seq = _get(ds, "RadiopharmaceuticalInformationSequence")
    rp: Dataset | None = None
    if not rp_seq:
        missing.append(
            MissingMetadata(
                field="RadiopharmaceuticalInformationSequence",
                scope=uid,
                status="absent" if rp_seq is None else "empty",
                required=True,
            )
        )
    else:
        rp = rp_seq[0]
        if len(rp_seq) > 1:
            warnings.append(
                QCWarning(
                    code="MULTIPLE_RADIOPHARMACEUTICAL_ITEMS",
                    series_uid=uid,
                    message=f"{len(rp_seq)} radiopharmaceutical items; only item 1 recorded",
                )
            )

    def rp_val(keyword: str) -> Any:
        return _get(rp, keyword) if rp is not None else None

    dose = _positive_number(rp_val("RadionuclideTotalDose"), "RadionuclideTotalDose", uid, True)
    half = _positive_number(rp_val("RadionuclideHalfLife"), "RadionuclideHalfLife", uid, True)
    start_time = _str(rp_val("RadiopharmaceuticalStartTime"))
    start_dt = _str(rp_val("RadiopharmaceuticalStartDateTime"))
    if rp is not None:
        for chk in (dose, half):
            if chk.problem:
                missing.append(chk.problem)
        if start_time is None and start_dt is None:
            missing.append(
                MissingMetadata(
                    field="RadiopharmaceuticalStartTime",
                    scope=uid,
                    status="absent",
                    required=True,
                    note="neither RadiopharmaceuticalStartTime nor ...StartDateTime present",
                )
            )
        if _str(rp_val("Radiopharmaceutical")) is None:
            missing.append(
                MissingMetadata(
                    field="Radiopharmaceutical", scope=uid, status="absent", required=False
                )
            )

    # Cross-instance consistency for fields that must be constant within a series.
    for kw in ("Units", "DecayCorrection", "PatientWeight", "SeriesDate", "SeriesTime"):
        vals = _distinct(_str(_get(h, kw)) for h in headers)
        if len(vals) > 1:
            missing.append(
                MissingMetadata(
                    field=kw,
                    scope=uid,
                    status="inconsistent",
                    required=kw in PET_REQUIRED_FIELDS,
                    raw_value=" | ".join(vals[:5]),
                )
            )
            warnings.append(
                QCWarning(
                    code="PET_FIELD_INCONSISTENT",
                    severity="error",
                    series_uid=uid,
                    message=f"{kw} differs between instances",
                )
            )

    slopes, intercepts = _rescale_values(headers, uid, missing, warnings)
    corrected = _get(ds, "CorrectedImage")
    recon_diam = _floats(_get(ds, "ReconstructionDiameter"), 1)

    meta = PETMetadata(
        series_uid=uid,
        units=text("Units"),
        decay_correction=text("DecayCorrection"),
        corrected_image=[str(v) for v in corrected] if corrected else None,
        patient_weight=weight.value,
        series_date=text("SeriesDate"),
        series_time=text("SeriesTime"),
        acquisition_date=text("AcquisitionDate"),
        acquisition_time=text("AcquisitionTime"),
        radiopharmaceutical=_str(rp_val("Radiopharmaceutical")),
        radionuclide_total_dose=dose.value,
        radionuclide_half_life=half.value,
        radiopharmaceutical_start_time=start_time,
        radiopharmaceutical_start_datetime=start_dt,
        rescale_slopes=slopes,
        rescale_intercepts=intercepts,
        manufacturer=text("Manufacturer"),
        manufacturer_model_name=text("ManufacturerModelName"),
        software_versions=text("SoftwareVersions"),
        reconstruction_method=text("ReconstructionMethod"),
        reconstruction_diameter=recon_diam[0] if recon_diam else None,
        rows=_int(_get(ds, "Rows")),
        columns=_int(_get(ds, "Columns")),
        number_of_frames=_int(_get(ds, "NumberOfFrames")),
        missing=missing,
    )
    return meta, warnings


def _rescale_values(
    headers: list[Dataset], uid: str, missing: list[MissingMetadata], warnings: list[QCWarning]
) -> tuple[list[float], list[float]]:
    slopes: list[float] = []
    intercepts: list[float] = []
    n_missing = 0
    for h in headers:
        s = _floats(_get(h, "RescaleSlope"), 1)
        b = _floats(_get(h, "RescaleIntercept"), 1)
        if s is None or b is None:
            n_missing += 1
            continue
        if s[0] not in slopes:
            slopes.append(s[0])
        if b[0] not in intercepts:
            intercepts.append(b[0])
    if n_missing:
        missing.append(
            MissingMetadata(
                field="RescaleSlope/RescaleIntercept",
                scope=uid,
                status="absent",
                required=True,
                note=f"absent or non-numeric in {n_missing}/{len(headers)} instances",
            )
        )
    if len(slopes) > 1:
        warnings.append(
            QCWarning(
                code="RESCALE_SLOPE_VARIES",
                severity="info",
                series_uid=uid,
                message=f"{len(slopes)} distinct RescaleSlope values (per-slice scaling; normal "
                "for many PET scanners, applied per slice on load)",
            )
        )
    return slopes, intercepts


# --------------------------------------------------------------------------------------
# Geometry and volume loading
# --------------------------------------------------------------------------------------


@dataclass
class _SliceGeometry:
    geometry: ImageGeometry
    ordered: list[DicomInstance]


def _series_geometry(series: ImagingSeries) -> tuple[_SliceGeometry | None, list[QCWarning]]:
    uid = series.series_uid
    warns: list[QCWarning] = []
    insts = series.instances

    def fail(code: str, msg: str) -> tuple[None, list[QCWarning]]:
        warns.append(QCWarning(code=code, severity="error", series_uid=uid, message=msg))
        return None, warns

    if any((i.number_of_frames or 1) > 1 for i in insts):
        return fail(
            "MULTIFRAME_NOT_SUPPORTED",
            "multi-frame image geometry is not supported for volume loading yet",
        )
    if any(
        i.image_position is None or i.image_orientation is None or i.pixel_spacing is None
        for i in insts
    ):
        return fail(
            "GEOMETRY_MISSING",
            "ImagePositionPatient/ImageOrientationPatient/PixelSpacing missing or invalid",
        )
    if len({(i.rows, i.columns) for i in insts}) != 1 or insts[0].rows is None:
        return fail("INCONSISTENT_MATRIX", "Rows/Columns differ between instances or missing")

    ori = np.array([i.image_orientation for i in insts], dtype=float)
    if np.abs(ori - ori[0]).max() > ORIENTATION_TOL:
        return fail("INCONSISTENT_ORIENTATION", "ImageOrientationPatient differs between slices")
    sp = np.array([i.pixel_spacing for i in insts], dtype=float)
    if np.abs(sp - sp[0]).max() > SPACING_REL_TOL * sp[0].min():
        return fail("INCONSISTENT_PIXEL_SPACING", "PixelSpacing differs between slices")

    row_dir = ori[0, :3]
    col_dir = ori[0, 3:]
    if (
        abs(np.linalg.norm(row_dir) - 1) > 1e-3
        or abs(np.linalg.norm(col_dir) - 1) > 1e-3
        or abs(float(row_dir @ col_dir)) > 1e-3
    ):
        return fail("INVALID_ORIENTATION", "ImageOrientationPatient is not orthonormal")
    normal = np.cross(row_dir, col_dir)

    pos = np.array([i.image_position for i in insts], dtype=float)
    proj = pos @ normal
    order = np.argsort(proj, kind="stable")
    proj_sorted = proj[order]
    pos_sorted = pos[order]
    ordered = [insts[k] for k in order]

    if len(insts) > 1 and np.diff(proj_sorted).min() < POSITION_TOL_MM:
        return fail(
            "DUPLICATE_SLICE_POSITION",
            "two or more slices share a position; refusing to guess the order",
        )

    slice_spacing: float | None = None
    uniform: bool | None = None
    if len(insts) > 1:
        steps = np.diff(proj_sorted)
        uniform = bool(np.abs(steps - steps.mean()).max() <= SPACING_REL_TOL * steps.mean())
        if uniform:
            slice_spacing = float(steps.mean())
        else:
            warns.append(
                QCWarning(
                    code="NONUNIFORM_SLICE_SPACING",
                    series_uid=uid,
                    message=f"slice spacing varies {steps.min():.4g}-{steps.max():.4g} mm; "
                    "slice_spacing undefined, positions recorded per slice",
                )
            )
        # In-plane offset between slices (e.g. gantry tilt) breaks the simple affine.
        lateral = pos_sorted[1:] - pos_sorted[:-1] - np.outer(steps, normal)
        if np.abs(lateral).max() > max(POSITION_TOL_MM, 0.01 * float(steps.mean())):
            warns.append(
                QCWarning(
                    code="SLICES_NOT_ALONG_NORMAL",
                    severity="error",
                    series_uid=uid,
                    message="slice positions are not aligned with the slice normal (tilt/shear)",
                )
            )
            uniform = False
            slice_spacing = None
    else:
        warns.append(
            QCWarning(
                code="SINGLE_SLICE",
                severity="info",
                series_uid=uid,
                message="series has one slice; slice spacing undeterminable",
            )
        )

    dr, dc = float(sp[0, 0]), float(sp[0, 1])
    origin = pos_sorted[0]
    k_step = slice_spacing if slice_spacing is not None else 0.0
    affine = np.eye(4)
    affine[:3, 0] = row_dir * dc
    affine[:3, 1] = col_dir * dr
    affine[:3, 2] = normal * k_step
    affine[:3, 3] = origin
    rows, cols = insts[0].rows, insts[0].columns
    assert rows is not None and cols is not None
    nz = len(insts)
    geom = ImageGeometry(
        coordinate_system="LPS",
        shape_ijk=(cols, rows, nz),
        spacing_ijk=(dc, dr, slice_spacing),
        origin=tuple(float(v) for v in origin),  # type: ignore[arg-type]
        direction=tuple(float(v) for v in np.column_stack([row_dir, col_dir, normal]).ravel()),
        affine=affine.tolist(),
        extent_mm=(cols * dc, rows * dr, nz * slice_spacing if slice_spacing is not None else None),
        uniform_slice_spacing=uniform,
        slice_positions_mm=[float(v) for v in proj_sorted],
    )
    return _SliceGeometry(geom, ordered), warns


def series_geometry(series: ImagingSeries) -> tuple[ImageGeometry | None, list[QCWarning]]:
    """Geometry from headers only (no pixel data). ``None`` with error warnings if unsafe."""
    sg, warns = _series_geometry(series)
    return (sg.geometry if sg else None), warns


@dataclass
class LoadedVolume:
    """Pixel data after the DICOM modality LUT (stored * RescaleSlope + RescaleIntercept).

    Units are those of the source header (e.g. PET ``Units``, CT Hounsfield units); no
    further conversion is applied. Array indexing is ``[slice, row, column]``.
    """

    series_uid: str
    array: np.ndarray
    geometry: ImageGeometry
    warnings: list[QCWarning]
    rescaled: bool


def load_series_volume(series: ImagingSeries) -> LoadedVolume:
    """Load a single-frame PET/CT series into a geometry-sorted float64 volume.

    Raises IngestError when geometry is missing/ambiguous or pixel decoding fails.
    """
    if series.category not in ("PET", "CT"):
        raise IngestError(f"volume loading supports PET/CT only, got {series.category}")
    sg, warns = _series_geometry(series)
    if sg is None or any(w.severity == "error" for w in warns):
        raise IngestError(
            "; ".join(w.message for w in warns if w.severity == "error") or "geometry unavailable"
        )
    slices: list[np.ndarray] = []
    rescaled_all = True
    for inst in sg.ordered:
        try:
            ds = pydicom.dcmread(inst.path)
            pix = ds.pixel_array
        except Exception as exc:  # noqa: BLE001 - decoder errors vary by transfer syntax
            raise IngestError(f"cannot decode pixels of {inst.path}: {exc}") from exc
        slope = _floats(_get(ds, "RescaleSlope"), 1)
        intercept = _floats(_get(ds, "RescaleIntercept"), 1)
        arr = pix.astype(np.float64)
        if slope is not None and intercept is not None:
            arr = arr * slope[0] + intercept[0]
        elif slope is None and intercept is None:
            rescaled_all = False
        else:
            raise IngestError(f"only one of RescaleSlope/RescaleIntercept present in {inst.path}")
        slices.append(arr)
    if not rescaled_all:
        warns.append(
            QCWarning(
                code="NO_RESCALE",
                series_uid=series.series_uid,
                message="some slices have no RescaleSlope/Intercept; stored values used unchanged",
            )
        )
    return LoadedVolume(series.series_uid, np.stack(slices), sg.geometry, warns, rescaled_all)
