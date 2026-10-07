"""Assemble a VoxelTraceCase from a directory of DICOM (and optional NIfTI) files.

Header-only by default: no pixel data are read unless explicitly requested later via
``load_series_volume`` / ``decode_dicom_seg``. Nothing here computes SUV.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import voxeltrace
from voxeltrace.ingest.dicom import discover_dicom, extract_pet_metadata, series_geometry
from voxeltrace.ingest.nifti import is_nifti_path
from voxeltrace.ingest.segmentation import load_nifti_mask, parse_dicom_seg
from voxeltrace.schemas import (
    CaseProvenance,
    QCWarning,
    StudySummary,
    VoxelTraceCase,
)


def build_case(
    root: str | os.PathLike[str],
    *,
    dataset: str | None = None,
    collection: str | None = None,
    subject_id: str | None = None,
    nifti_masks: list[str | os.PathLike[str]] | None = None,
) -> VoxelTraceCase:
    """Inspect ``root`` and return a typed case description (no pixels loaded)."""
    root_path = Path(root).expanduser().resolve()
    disc = discover_dicom(root_path)
    case = VoxelTraceCase(
        provenance=CaseProvenance(
            source_path=str(root_path),
            dataset=dataset,
            collection=collection,
            subject_id=subject_id,
            inspected_at=datetime.now(UTC).isoformat(timespec="seconds"),
            voxeltrace_version=voxeltrace.__version__,
            files_scanned=disc.files_scanned,
            dicom_files=disc.dicom_files,
            non_dicom_files_ignored=disc.non_dicom_ignored,
            unreadable_files=disc.unreadable,
        ),
        series=disc.series,
        warnings=list(disc.warnings),
    )

    studies: dict[str, StudySummary] = {}
    for s in disc.series:
        st = studies.setdefault(
            s.study_uid, StudySummary(study_uid=s.study_uid, study_description=s.study_description)
        )
        st.series_uids.append(s.series_uid)
    case.studies = list(studies.values())

    for s in disc.series:
        if s.category in ("PET", "CT"):
            geom, warns = series_geometry(s)
            case.warnings.extend(warns)
            if geom is not None:
                case.geometries[s.series_uid] = geom
        if s.category == "PET":
            try:
                meta, warns = extract_pet_metadata(s)
            except Exception as exc:  # noqa: BLE001 - report, do not crash inspection
                case.warnings.append(
                    QCWarning(
                        code="PET_METADATA_UNREADABLE",
                        severity="error",
                        series_uid=s.series_uid,
                        message=f"{type(exc).__name__}: {exc}",
                    )
                )
                continue
            case.pet_metadata[s.series_uid] = meta
            case.missing.extend(meta.missing)
            case.warnings.extend(warns)
        if s.category == "SEG":
            for inst in s.instances:
                try:
                    meta, warns = parse_dicom_seg(inst.path)
                except Exception as exc:  # noqa: BLE001
                    case.warnings.append(
                        QCWarning(
                            code="SEG_UNREADABLE",
                            severity="error",
                            series_uid=s.series_uid,
                            path=inst.path,
                            message=f"{type(exc).__name__}: {exc}",
                        )
                    )
                    continue
                case.segmentations.append(meta)
                case.warnings.extend(warns)
                known = {x.series_uid for x in disc.series}
                for ref in meta.referenced_series_uids:
                    if ref not in known:
                        case.warnings.append(
                            QCWarning(
                                code="SEG_REFERENCE_NOT_FOUND",
                                series_uid=s.series_uid,
                                message=f"referenced series {ref} not present in this directory",
                            )
                        )

    if len(case.studies) > 1:
        case.warnings.append(
            QCWarning(
                code="MULTIPLE_STUDIES",
                severity="info",
                message=f"{len(case.studies)} studies found; analyse one study at a time",
            )
        )

    for m in nifti_masks or []:
        if not is_nifti_path(m):
            case.warnings.append(
                QCWarning(code="NOT_NIFTI", path=str(m), message="mask path is not .nii/.nii.gz")
            )
            continue
        try:
            mask = load_nifti_mask(m)
        except (ValueError, OSError) as exc:
            case.warnings.append(
                QCWarning(
                    code="NIFTI_MASK_INVALID", severity="error", path=str(m), message=str(exc)
                )
            )
            continue
        case.segmentations.append(mask.metadata)
        case.warnings.extend(mask.warnings)
    return case
