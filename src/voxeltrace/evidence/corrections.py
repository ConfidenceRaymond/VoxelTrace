"""Correction evidence: exact CorrectedImage flags, structured Enhanced-PET booleans, methods.

DICOM PS3.3: CorrectedImage (0028,0051) lists corrections that HAVE been applied. If the
attribute is present, an unlisted flag is recorded as ``False`` ("not declared applied"). If
the attribute is absent, every flag is MISSING (unknown), never ``False``.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field
from pydicom.dataset import Dataset

from voxeltrace.evidence._dicom import derived, first_item, tag_field
from voxeltrace.schemas import EvidenceField

# DICOM defined terms for CorrectedImage (PET Series module).
FLAG_MEANINGS = {
    "UNIF": "flood corrected",
    "COR": "center of rotation corrected",
    "NCO": "non-circular orbit corrected",
    "DECY": "decay corrected",
    "ATTN": "attenuation corrected",
    "SCAT": "scatter corrected",
    "DTIM": "dead time corrected",
    "NRGY": "energy corrected",
    "LIN": "linearity corrected",
    "MOTN": "motion corrected",
    "CLN": "count loss normalization",
    "NORM": "normalization (detector efficiency)",
    "RAN": "randoms corrected",
    "RADL": "non-uniform radial sampling corrected",
    "DCAL": "dose calibrated",
}

# correction name -> (CorrectedImage flag, Enhanced PET structured attribute)
CORRECTIONS = {
    "attenuation": ("ATTN", "AttenuationCorrected"),
    "scatter": ("SCAT", "ScatterCorrected"),
    "randoms": ("RAN", "RandomsCorrected"),
    "decay": ("DECY", "DecayCorrected"),
    "normalization": ("NORM", "DetectorNormalizationCorrection"),
    "dead_time": ("DTIM", "DeadTimeCorrected"),
    "sensitivity": (None, "SensitivityCalibrated"),
}


class CorrectionEvidence(BaseModel):
    series_uid: str
    corrected_image: EvidenceField
    applied: dict[str, EvidenceField] = Field(
        description="attenuation, scatter, randoms, decay, normalization, dead_time, sensitivity"
    )
    other_flags: list[str] = Field(default_factory=list)
    unknown_flags: list[str] = Field(default_factory=list)
    decay_correction: EvidenceField
    attenuation_correction_method: EvidenceField
    scatter_correction_method: EvidenceField
    randoms_correction_method: EvidenceField
    dose_calibration_factor: EvidenceField
    scatter_fraction_factor: EvidenceField
    dead_time_factor: EvidenceField
    slice_sensitivity_factor: EvidenceField

    def applied_set(self) -> set[str] | None:
        """Names of corrections known to be applied; None if CorrectedImage is unknown."""
        if not self.corrected_image.known:
            return None
        return {k for k, f in self.applied.items() if f.value is True}


def _structured(headers: Sequence[Dataset], keyword: str) -> EvidenceField:
    """Enhanced-PET YES/NO attribute, top level or in PETReconstructionSequence."""
    top = tag_field(headers, keyword)
    if top.status == "MISSING":
        top = tag_field(headers, keyword, item=first_item("PETReconstructionSequence"))
    return top


def extract_corrections(series_uid: str, headers: Sequence[Dataset]) -> CorrectionEvidence:
    ci = tag_field(headers, "CorrectedImage", kind="list")
    flags: list[str] = list(ci.value) if isinstance(ci.value, list) else []
    applied: dict[str, EvidenceField] = {}
    for name, (flag, structured_kw) in CORRECTIONS.items():
        s = _structured(headers, structured_kw)
        if s.known and s.value in ("YES", "NO"):
            applied[name] = derived(
                name, s.value == "YES", source=s.source or structured_kw, derivation="standard_tag"
            )
        elif flag is None:
            applied[name] = derived(
                name,
                None,
                source=f"{structured_kw} (Enhanced PET)",
                derivation="standard_tag",
                note="no CorrectedImage flag defines this correction",
            )
        elif ci.known:
            applied[name] = derived(
                name,
                flag in flags,
                source=f"(0028,0051) CorrectedImage flag {flag}",
                derivation="standard_enumeration",
                note=None
                if flag in flags
                else "not listed in CorrectedImage (not declared applied)",
                ambiguous=ci.status == "PRESENT_BUT_AMBIGUOUS",
            )
        else:
            applied[name] = derived(
                name,
                None,
                source=f"(0028,0051) CorrectedImage flag {flag}",
                derivation="standard_enumeration",
                note="CorrectedImage absent: correction state unknown",
            )
    mapped = {f for f, _ in CORRECTIONS.values() if f}
    return CorrectionEvidence(
        series_uid=series_uid,
        corrected_image=ci,
        applied=applied,
        other_flags=[
            f"{f} ({FLAG_MEANINGS[f]})" for f in flags if f in FLAG_MEANINGS and f not in mapped
        ],
        unknown_flags=[f for f in flags if f not in FLAG_MEANINGS],
        decay_correction=tag_field(headers, "DecayCorrection"),
        attenuation_correction_method=tag_field(headers, "AttenuationCorrectionMethod"),
        scatter_correction_method=tag_field(headers, "ScatterCorrectionMethod"),
        randoms_correction_method=tag_field(headers, "RandomsCorrectionMethod"),
        dose_calibration_factor=tag_field(headers, "DoseCalibrationFactor", kind="float"),
        scatter_fraction_factor=tag_field(
            headers, "ScatterFractionFactor", kind="float", varies_ok=True
        ),
        dead_time_factor=tag_field(headers, "DeadTimeFactor", kind="float", varies_ok=True),
        slice_sensitivity_factor=tag_field(
            headers, "SliceSensitivityFactor", kind="float", varies_ok=True
        ),
    )
