"""Typed structured-evidence objects shared by the quant engine and the AI layer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ImageStats(BaseModel):
    """Deterministic summary statistics of a numeric array.

    Counts and fractions describe the whole array. All intensity statistics
    (min/max/mean/std/median/percentiles) are computed over finite voxels only
    and are ``None`` when the array contains no finite voxels.
    """

    model_config = ConfigDict(frozen=True)

    shape: tuple[int, ...]
    dtype: str
    voxel_count: int = Field(ge=1)
    finite_count: int = Field(ge=0)
    nan_count: int = Field(ge=0)
    nan_fraction: float = Field(ge=0.0, le=1.0)
    posinf_count: int = Field(ge=0)
    neginf_count: int = Field(ge=0)
    zero_count: int = Field(ge=0)
    zero_fraction: float = Field(ge=0.0, le=1.0)
    finite_min: float | None
    finite_max: float | None
    finite_mean: float | None
    finite_std: float | None = Field(
        default=None, description="Population standard deviation (ddof=0)."
    )
    median: float | None
    p01: float | None = Field(description="1st percentile (linear interpolation).")
    p99: float | None = Field(description="99th percentile (linear interpolation).")

    @property
    def has_finite_voxels(self) -> bool:
        return self.finite_count > 0


class AIServerStatus(BaseModel):
    """Result of probing the local OpenAI-compatible endpoint."""

    base_url: str
    reachable: bool
    models: list[str] = Field(default_factory=list)
    error: str | None = None


# --------------------------------------------------------------------------------------
# Ingestion models (milestone 2). Values are recorded as found; nothing is defaulted.
# --------------------------------------------------------------------------------------

Severity = Literal["info", "warning", "error"]
SeriesCategory = Literal["PET", "CT", "SEG", "OTHER"]


class QCWarning(BaseModel):
    """A data-quality finding. ``error`` means the affected object must not be used as-is."""

    code: str
    message: str
    severity: Severity = "warning"
    series_uid: str | None = None
    path: str | None = None


class MissingMetadata(BaseModel):
    """A metadata field that is absent, empty, or present but unusable."""

    field: str
    scope: str = Field(description="Series UID or object the field belongs to.")
    status: Literal["absent", "empty", "invalid", "inconsistent"]
    required: bool = Field(description="Required for planned quantitative use (e.g. SUV).")
    raw_value: str | None = None
    note: str | None = None


class CaseProvenance(BaseModel):
    source_path: str
    dataset: str | None = Field(default=None, description="Caller-supplied dataset label.")
    collection: str | None = None
    subject_id: str | None = Field(
        default=None, description="Caller-supplied public subject id; never read from headers."
    )
    inspected_at: str
    voxeltrace_version: str
    files_scanned: int = 0
    dicom_files: int = 0
    non_dicom_files_ignored: int = 0
    unreadable_files: int = 0


class DicomInstance(BaseModel):
    """Per-file header fields needed for grouping and geometry. No pixel data."""

    path: str
    sop_instance_uid: str | None = None
    sop_class_uid: str | None = None
    instance_number: int | None = None
    image_position: tuple[float, float, float] | None = None
    image_orientation: tuple[float, float, float, float, float, float] | None = None
    pixel_spacing: tuple[float, float] | None = Field(
        default=None, description="DICOM order: (row spacing, column spacing) in mm."
    )
    slice_thickness: float | None = None
    rows: int | None = None
    columns: int | None = None
    number_of_frames: int | None = None
    frame_of_reference_uid: str | None = None


class ImagingSeries(BaseModel):
    study_uid: str
    series_uid: str
    modality: str | None
    category: SeriesCategory
    series_description: str | None = None
    study_description: str | None = None
    sop_class_uids: list[str] = Field(default_factory=list)
    frame_of_reference_uids: list[str] = Field(default_factory=list)
    series_number: int | None = None
    manufacturer: str | None = None
    manufacturer_model_name: str | None = None
    software_versions: str | None = None
    rows: int | None = None
    columns: int | None = None
    number_of_frames: int | None = None
    instances: list[DicomInstance] = Field(default_factory=list)

    @property
    def instance_count(self) -> int:
        return len(self.instances)


class StudySummary(BaseModel):
    study_uid: str
    study_description: str | None = None
    series_uids: list[str] = Field(default_factory=list)


class ImageGeometry(BaseModel):
    """Voxel grid geometry.

    Index convention: the NumPy array is ``[k, j, i]`` = (slice, row, column). ``shape_ijk``,
    ``spacing_ijk`` and ``affine`` use (i=column, j=row, k=slice). For DICOM the affine maps
    (i, j, k, 1) to patient LPS millimetres; for NIfTI it is the file's RAS affine.
    """

    coordinate_system: Literal["LPS", "RAS"]
    shape_ijk: tuple[int, int, int]
    spacing_ijk: tuple[float, float, float | None]
    origin: tuple[float, float, float]
    direction: tuple[float, ...] = Field(description="3x3 column direction cosines, row-major.")
    affine: list[list[float]]
    extent_mm: tuple[float, float, float | None]
    uniform_slice_spacing: bool | None = None
    slice_positions_mm: list[float] | None = Field(
        default=None, description="Slice positions along the normal, in sorted order."
    )

    def affine_ras(self) -> list[list[float]]:
        if self.coordinate_system == "RAS":
            return self.affine
        flip = [-1.0, -1.0, 1.0]
        return [
            [v * flip[r] for v in row] if r < 3 else list(row) for r, row in enumerate(self.affine)
        ]


class PETMetadata(BaseModel):
    """PET header fields as recorded. No unit conversion, no defaults, no SUV."""

    series_uid: str
    units: str | None = None
    decay_correction: str | None = None
    corrected_image: list[str] | None = None
    patient_weight: float | None = Field(default=None, description="As recorded (DICOM: kg).")
    series_date: str | None = None
    series_time: str | None = None
    acquisition_date: str | None = None
    acquisition_time: str | None = None
    radiopharmaceutical: str | None = None
    radionuclide_total_dose: float | None = Field(
        default=None, description="As recorded (DICOM: Bq)."
    )
    radionuclide_half_life: float | None = Field(
        default=None, description="As recorded (DICOM: s)."
    )
    radiopharmaceutical_start_time: str | None = None
    radiopharmaceutical_start_datetime: str | None = None
    rescale_slopes: list[float] = Field(
        default_factory=list, description="Distinct RescaleSlope values across instances."
    )
    rescale_intercepts: list[float] = Field(default_factory=list)
    manufacturer: str | None = None
    manufacturer_model_name: str | None = None
    software_versions: str | None = None
    reconstruction_method: str | None = None
    reconstruction_diameter: float | None = None
    rows: int | None = None
    columns: int | None = None
    number_of_frames: int | None = None
    missing: list[MissingMetadata] = Field(default_factory=list)


class SegmentInfo(BaseModel):
    number: int
    label: str | None = None
    description: str | None = None
    algorithm_type: str | None = None
    category: str | None = None
    type: str | None = None


class SegmentationMetadata(BaseModel):
    source: Literal["DICOM_SEG", "NIFTI"]
    path: str
    series_uid: str | None = None
    segmentation_type: str | None = None
    segments: list[SegmentInfo] = Field(default_factory=list)
    referenced_series_uids: list[str] = Field(default_factory=list)
    referenced_study_uid: str | None = None
    frame_of_reference_uid: str | None = None
    number_of_frames: int | None = None
    label_values: list[int] | None = Field(default=None, description="NIfTI label values.")
    label_voxel_counts: dict[int, int] | None = None
    pixel_decoding: Literal[
        "NOT_ATTEMPTED", "DECODED", "REFUSED", "DICOM_SEG_PIXEL_DECODING_NOT_IMPLEMENTED"
    ] = "NOT_ATTEMPTED"
    geometry_matches_reference: bool | None = None


class VoxelTraceCase(BaseModel):
    provenance: CaseProvenance
    studies: list[StudySummary] = Field(default_factory=list)
    series: list[ImagingSeries] = Field(default_factory=list)
    geometries: dict[str, ImageGeometry] = Field(default_factory=dict)
    pet_metadata: dict[str, PETMetadata] = Field(default_factory=dict)
    segmentations: list[SegmentationMetadata] = Field(default_factory=list)
    missing: list[MissingMetadata] = Field(default_factory=list)
    warnings: list[QCWarning] = Field(default_factory=list)

    def get_series(self, series_uid: str) -> ImagingSeries:
        for s in self.series:
            if s.series_uid == series_uid:
                return s
        raise KeyError(series_uid)

    def series_by_category(self, category: SeriesCategory) -> list[ImagingSeries]:
        return [s for s in self.series if s.category == category]
