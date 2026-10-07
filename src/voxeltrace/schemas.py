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


# --------------------------------------------------------------------------------------
# Quantification models (milestone 3). Every number carries its source.
# --------------------------------------------------------------------------------------

SUV_PATH = "SUVbw: Units=BQML, DecayCorrection=START, CorrectedImage⊇{ATTN,DECY}"


class QuantField(BaseModel):
    """One DICOM value used (or inspected) for quantification, with its consistency audit."""

    name: str
    tag: str
    value: str | None = Field(description="Raw value from the first slice (as recorded).")
    unit: str | None = None
    slices_present: int
    slices_total: int
    distinct_values: list[str] = Field(default_factory=list, description="Up to 5 shown.")
    n_distinct: int = 0


class CheckResult(BaseModel):
    name: str
    passed: bool
    detail: str


class SUVRefusalReason(BaseModel):
    code: str
    message: str
    field: str | None = None


class SUVValidation(BaseModel):
    eligible: bool
    supported_path: str = SUV_PATH
    checks: list[CheckResult] = Field(default_factory=list)
    reasons: list[SUVRefusalReason] = Field(default_factory=list)
    warnings: list[QCWarning] = Field(default_factory=list)


class SUVInputs(BaseModel):
    """Validated inputs. ``None`` means not established (and SUV is then refused)."""

    units: str | None = None
    decay_correction: str | None = None
    corrected_image: list[str] | None = None
    patient_weight_kg: float | None = None
    radionuclide_total_dose_bq: float | None = None
    radionuclide_half_life_s: float | None = None
    radionuclide: str | None = None
    injection_datetime: str | None = None
    injection_datetime_source: str | None = None
    scan_reference_datetime: str | None = None
    scan_reference_datetime_source: str | None = None
    earliest_acquisition_datetime: str | None = None
    series_datetime: str | None = None
    decay_interval_s: float | None = None
    fields: list[QuantField] = Field(default_factory=list)


class SUVScaleFactors(BaseModel):
    """SUVbw = C[Bq/mL] × suv_per_bqml, suv_per_bqml = W[g] / (D[Bq] · 2^(−Δt/T½))."""

    patient_weight_g: float
    injected_dose_bq: float
    half_life_s: float
    decay_interval_s: float
    dose_decay_factor: float = Field(description="2^(−Δt/T½), dimensionless.")
    decayed_dose_bq: float
    suv_per_bqml: float = Field(description="g/Bq; multiply Bq/mL to obtain SUVbw in g/mL.")
    formula: str = "SUVbw = C_PET[Bq/mL] * W[g] / (D_inj[Bq] * 2^(-Δt[s]/T½[s]))"


class RescaleAudit(BaseModel):
    """Per-slice modality LUT factors (stored → Bq/mL), in volume slice order k."""

    n_slices: int
    n_distinct_slopes: int
    slope_min: float | None
    slope_max: float | None
    n_distinct_intercepts: int
    intercepts: list[float] = Field(default_factory=list, description="Distinct, up to 5.")
    per_slice: list[tuple[int, str | None, float | None, float | None]] = Field(
        default_factory=list, description="(k, SOPInstanceUID, RescaleSlope, RescaleIntercept)"
    )


class QuantitativeProvenance(BaseModel):
    calculation: str
    calculation_version: str
    voxeltrace_version: str
    git_commit: str | None = None
    git_dirty: bool | None = None
    computed_at: str
    dataset: str | None = None
    subject_pseudonym: str | None = None
    pet_series_uid: str | None = None
    seg_series_uid: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class SUVResult(BaseModel):
    status: Literal["PASS"] = "PASS"
    units: str = "g/mL"
    inputs: SUVInputs
    scale: SUVScaleFactors
    validation: SUVValidation
    rescale: RescaleAudit
    activity_units: str = "Bq/mL"
    volume_shape_kji: tuple[int, int, int]
    suv_stats: ImageStats
    provenance: QuantitativeProvenance


class SUVRefusal(BaseModel):
    status: Literal["REFUSED"] = "REFUSED"
    reasons: list[SUVRefusalReason]
    validation: SUVValidation
    inputs: SUVInputs
    provenance: QuantitativeProvenance


class SUVPeak(BaseModel):
    status: Literal["COMPUTED", "NOT_AVAILABLE"]
    value: float | None = None
    definition: str = (
        "max over candidate centres (voxel centres inside the segment) of the mean SUV of all "
        "image voxels whose centres lie within r=(3/(4π))^(1/3) cm of the centre (1.0 cm³ sphere)"
    )
    sphere_volume_ml: float = 1.0
    radius_mm: float
    kernel_voxel_count: int
    kernel_effective_volume_ml: float
    center_kji: tuple[int, int, int] | None = None
    center_patient_mm: tuple[float, float, float] | None = None
    fraction_of_sphere_voxels_in_segment: float | None = None
    candidates_evaluated: int = 0
    candidates_excluded_at_image_edge: int = 0
    note: str | None = None


class LesionComponent(BaseModel):
    index: int
    voxel_count: int
    volume_ml: float
    suv_max: float
    suv_mean: float


class LesionMetrics(BaseModel):
    """Metrics for one supplied segment. MTV is the volume of the supplied mask."""

    segment_number: int
    segment_label: str | None = None
    voxel_count: int
    voxel_volume_ml: float
    mtv_ml: float
    suv_min: float | None = None
    suv_max: float | None = None
    suv_mean: float | None = None
    suv_median: float | None = None
    suv_std: float | None = Field(default=None, description="Population SD (ddof=0).")
    suv_p10: float | None = None
    suv_p25: float | None = None
    suv_p75: float | None = None
    suv_p90: float | None = None
    tlg: float | None = Field(default=None, description="MTV[mL] × SUVmean (g).")
    n_components: int = 0
    connectivity: str = "26-connected (face, edge and corner neighbours)"
    components: list[LesionComponent] = Field(default_factory=list)
    suv_peak: SUVPeak | None = None
    warnings: list[QCWarning] = Field(default_factory=list)


class LesionSummary(BaseModel):
    n_segments: int
    n_nonempty_segments: int
    total_mtv_ml: float
    total_tlg: float
    max_suv_max: float | None = None
    max_suv_max_segment: int | None = None


class EvidenceMeasured(BaseModel):
    suv_status: Literal["PASS", "REFUSED"]
    suv_volume_stats: ImageStats | None = None
    lesions: list[LesionMetrics] = Field(default_factory=list)
    lesion_summary: LesionSummary | None = None


class QuantEvidence(BaseModel):
    """Structured evidence for later (local) AI interpretation. JSON-serialisable."""

    schema_version: str = "voxeltrace.quant-evidence/1"
    disclaimer: str
    measured: EvidenceMeasured
    provenance: QuantitativeProvenance
    quantitative_inputs: SUVInputs
    scale_factors: SUVScaleFactors | None = None
    refusal_reasons: list[SUVRefusalReason] = Field(default_factory=list)
    warnings: list[QCWarning] = Field(default_factory=list)
    not_established: list[str] = Field(
        default_factory=lambda: [
            "diagnosis",
            "histology",
            "treatment response",
            "prognosis",
            "lesion malignancy",
            "clinical significance of any measurement",
        ]
    )
