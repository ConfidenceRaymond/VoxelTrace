"""Deterministic PET/CT visualization for human review and multimodal model input.

Display only: windowing and colour maps never alter quantitative arrays. Outlines come only
from supplied segmentations. See docs/visualization.md.
"""

from voxeltrace.visualization.annotations import (
    RenderVerificationError,
    mask_annotations,
    peak_circle,
    point_annotation,
    verify_axial_render,
)
from voxeltrace.visualization.crops import crop_box
from voxeltrace.visualization.ct import ct_axial, resample_ct_to_pet
from voxeltrace.visualization.fusion import fused_axial
from voxeltrace.visualization.mip import pet_coronal_mip
from voxeltrace.visualization.pet import pet_axial
from voxeltrace.visualization.render import (
    RENDERER_VERSION,
    PlaneMapping,
    RenderError,
    RenderParams,
    add_footer,
    patient_to_voxel,
    png_bytes,
    voxel_to_patient,
)

__all__ = [
    "RENDERER_VERSION",
    "PlaneMapping",
    "RenderError",
    "RenderParams",
    "RenderVerificationError",
    "add_footer",
    "crop_box",
    "ct_axial",
    "fused_axial",
    "mask_annotations",
    "patient_to_voxel",
    "peak_circle",
    "pet_axial",
    "pet_coronal_mip",
    "png_bytes",
    "point_annotation",
    "resample_ct_to_pet",
    "verify_axial_render",
    "voxel_to_patient",
]
