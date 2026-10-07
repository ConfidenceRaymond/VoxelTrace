"""Typed ground-truth and training-example models.

Ground-truth hierarchy (docs/ground_truth.md):
  L1 PRIMARY_IMAGE            original image pixels
  L2 PRIMARY_DICOM_METADATA   scanner / acquisition / reconstruction / correction metadata
  L3 REFERENCE_SEGMENTATION   supplied reference segmentation
  L4 DETERMINISTIC_DERIVATION SUV, SUVmax/mean/median/peak, MTV, TLG, volume, geometry
  L5 RULE_DERIVATION          comparability, claim statuses, contradictions
  L6 EXPERT_ANNOTATION        human-reviewed natural language (only after review)
  L7 MODEL_GENERATED          NEVER ground truth (rejected at construction)

Levels 1-5 may be used automatically as supervised targets when VALIDATED.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

SourceType = Literal[
    "PRIMARY_IMAGE",
    "PRIMARY_DICOM_METADATA",
    "REFERENCE_SEGMENTATION",
    "DETERMINISTIC_DERIVATION",
    "RULE_DERIVATION",
    "EXPERT_ANNOTATION",
    "MODEL_GENERATED",
]
SOURCE_LEVEL: dict[str, int] = {
    "PRIMARY_IMAGE": 1,
    "PRIMARY_DICOM_METADATA": 2,
    "REFERENCE_SEGMENTATION": 3,
    "DETERMINISTIC_DERIVATION": 4,
    "RULE_DERIVATION": 5,
    "EXPERT_ANNOTATION": 6,
    "MODEL_GENERATED": 7,
}
DerivationType = Literal[
    "none",
    "dicom_attribute",
    "dicom_free_text_pattern",
    "segmentation_decode",
    "suv_strict",
    "lesion_metric",
    "geometry_transform",
    "connected_components",
    "rule_engine",
    "synthetic_perturbation",
    "rendering",
    "human_review",
]
ValidationStatus = Literal[
    "VALIDATED",  # produced by a validated deterministic path (tests + cross-checks)
    "VALIDATED_ABSENT",  # the value is verifiably absent (missingness is the fact)
    "UNVALIDATED",  # deterministic but not validated (e.g. vendor free text, ambiguous)
    "REVIEWED",  # human-reviewed (L6 only)
    "REJECTED",
]
SplitName = Literal["TRAIN", "VALIDATION", "LOCKED_TEST", "DEVELOPMENT_ONLY"]
ExampleClass = Literal[
    "VISUAL_LOCALIZATION",
    "QUANTITATIVE_READING",
    "PROTOCOL_READING",
    "CLAIM_VERIFICATION",
    "CONTRADICTION",
    "REFUSAL",
    "MISSING_DATA",
    "VISUAL_QUANTITATIVE",
    "PROTOCOL_COMPARABILITY",
    "ADVERSARIAL",
]


class GTValue(BaseModel):
    """One ground-truth value with full provenance."""

    value: Any = None
    unit: str | None = None
    source_type: SourceType
    source_ref: str = Field(description="Evidence path, DICOM tag or rule identifier.")
    derivation: DerivationType
    validation_status: ValidationStatus

    @model_validator(mode="after")
    def _hierarchy(self) -> GTValue:
        if self.source_type == "MODEL_GENERATED":
            raise ValueError("MODEL_GENERATED content can never be ground truth")
        if self.source_type == "EXPERT_ANNOTATION" and self.validation_status != "REVIEWED":
            raise ValueError("EXPERT_ANNOTATION requires validation_status=REVIEWED")
        if self.validation_status == "REVIEWED" and self.source_type != "EXPERT_ANNOTATION":
            raise ValueError("REVIEWED status is reserved for EXPERT_ANNOTATION")
        return self

    @property
    def level(self) -> int:
        return SOURCE_LEVEL[self.source_type]

    @property
    def usable_as_target(self) -> bool:
        if self.level <= 5:
            return self.validation_status in ("VALIDATED", "VALIDATED_ABSENT")
        return self.level == 6 and self.validation_status == "REVIEWED"


def gt(
    value: Any,
    source_type: SourceType,
    source_ref: str,
    derivation: DerivationType,
    status: ValidationStatus = "VALIDATED",
    unit: str | None = None,
) -> GTValue:
    return GTValue(
        value=value,
        unit=unit,
        source_type=source_type,
        source_ref=source_ref,
        derivation=derivation,
        validation_status=status,
    )


class GroundTruthComponent(BaseModel):
    """A 26-connected component of a supplied segment (deterministic derivation)."""

    component_index: int
    voxel_count: GTValue
    volume_ml: GTValue
    suv_max: GTValue
    centroid_kji: GTValue
    bbox_kji: GTValue = Field(description="[[k0,j0,i0],[k1,j1,i1]] inclusive")
    slices_k: GTValue
    zero_suv_voxels: GTValue | None = None


class GroundTruthLesion(BaseModel):
    """One supplied segment ('lesion' = reference segment; components listed separately)."""

    lesion_id: str
    segment_number: GTValue
    segment_label: GTValue
    voxel_count: GTValue
    mtv_ml: GTValue
    suv_max: GTValue
    suv_mean: GTValue
    suv_median: GTValue
    suv_peak: GTValue
    tlg: GTValue
    centroid_kji: GTValue
    centroid_patient_mm: GTValue
    bbox_kji: GTValue
    suvmax_voxel_kji: GTValue
    suvmax_patient_mm: GTValue
    suvpeak_center_kji: GTValue
    suvpeak_center_patient_mm: GTValue
    slices_k: GTValue
    voxels_per_slice: GTValue = Field(description="{k: voxel count} for slices with voxels")
    zero_suv_voxels_per_slice: GTValue | None = Field(
        default=None, description="{k: count of segment voxels with SUV exactly 0}"
    )
    components: list[GroundTruthComponent] = Field(default_factory=list)


class QuantitativeGroundTruth(BaseModel):
    suv_status: GTValue
    suv_per_bqml: GTValue
    decay_interval_s: GTValue
    suv_volume_max: GTValue
    lesions: list[GroundTruthLesion] = Field(default_factory=list)


class ProtocolGroundTruth(BaseModel):
    fields: dict[str, GTValue] = Field(description="category.field -> value")


class ClaimGroundTruth(BaseModel):
    claim_id: str
    claim_type: str
    statement: str
    status: GTValue
    rule: str


class Annotation2D(BaseModel):
    """An exact annotation in rendered-image pixel coordinates (x right, y down)."""

    kind: Literal["bbox", "point", "circle", "mask_pixel_count"]
    target: str = Field(description="lesion_id / component / marker name")
    value: GTValue = Field(
        description="bbox [x0,y0,x1,y1] inclusive px, point [x,y], circle [x,y,r_px] or pixel count"
    )


class VisualGroundTruth(BaseModel):
    image_id: str
    path: str = Field(description="Relative to the dataset root.")
    sha256: str
    view: str
    slice_k: int | None = None
    width: int
    height: int
    render_params: dict[str, Any]
    annotations: list[Annotation2D] = Field(default_factory=list)
    displayed_values: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Numbers drawn on the image, each with its "
        "evidence path; verified against evidence JSON before saving.",
    )
    contains_segmented_target: bool


class GroundTruthCase(BaseModel):
    schema_version: str = "voxeltrace.ground-truth/1"
    case_id: str
    dataset: str
    license: str
    citation: str | None = None
    subject_pseudonym: str
    study_pseudonym: str
    pet_series_pseudonym: str
    seg_series_pseudonym: str | None = None
    geometry: GTValue
    quantitative: QuantitativeGroundTruth
    protocol: ProtocolGroundTruth
    claims: list[ClaimGroundTruth]
    images: list[VisualGroundTruth] = Field(default_factory=list)
    evidence_sha256: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ImageRef(BaseModel):
    image_id: str
    path: str
    sha256: str
    view: str


class TrainingExample(BaseModel):
    example_id: str
    example_class: ExampleClass
    split: SplitName
    subject_pseudonym: str
    study_pseudonym: str
    images: list[ImageRef] = Field(default_factory=list)
    question: str
    context: dict[str, Any] | None = Field(
        default=None, description="Structured evidence supplied as input (untrusted data)."
    )
    target: dict[str, Any]
    target_sources: list[GTValue]
    ground_truth_level: int
    synthetic_perturbation: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _targets_are_ground_truth(self) -> TrainingExample:
        if not self.target_sources:
            raise ValueError("every target needs at least one ground-truth source")
        bad = [s.source_ref for s in self.target_sources if not s.usable_as_target]
        if bad:
            raise ValueError(f"target sources not usable as ground truth: {bad}")
        if self.ground_truth_level != max(s.level for s in self.target_sources):
            raise ValueError("ground_truth_level must equal the highest source level")
        return self


class DatasetSplit(BaseModel):
    name: SplitName
    subjects: list[str]
    n_examples: int = 0


class DatasetManifest(BaseModel):
    schema_version: str = "voxeltrace.dataset-manifest/1"
    dataset_name: str
    purpose: str
    fine_tuning_suitable: bool
    created_at: str
    voxeltrace_version: str
    git_commit: str | None
    git_dirty: bool | None
    renderer_version: str
    renderer_defaults: dict[str, Any]
    sources: list[dict[str, Any]]
    images: list[dict[str, Any]]
    evidence_sha256: dict[str, str]
    splits: list[DatasetSplit]
    example_counts: dict[str, int]
    label_provenance: dict[str, int] = Field(description="ground-truth level -> example count")
    selection_rules: list[str]
    notes: list[str] = Field(default_factory=list)
