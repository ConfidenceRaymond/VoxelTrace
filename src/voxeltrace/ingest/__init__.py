"""PET/CT/segmentation ingestion. Header-first, typed, no SUV computation."""

from voxeltrace.ingest.case import build_case
from voxeltrace.ingest.dicom import (
    IngestError,
    LoadedVolume,
    discover_dicom,
    extract_pet_metadata,
    load_series_volume,
    series_geometry,
)
from voxeltrace.ingest.nifti import compare_geometry, load_nifti
from voxeltrace.ingest.segmentation import decode_dicom_seg, load_nifti_mask, parse_dicom_seg

__all__ = [
    "IngestError",
    "LoadedVolume",
    "build_case",
    "compare_geometry",
    "decode_dicom_seg",
    "discover_dicom",
    "extract_pet_metadata",
    "load_nifti",
    "load_nifti_mask",
    "load_series_volume",
    "parse_dicom_seg",
    "series_geometry",
]
