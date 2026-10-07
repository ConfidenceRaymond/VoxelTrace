"""Scanner / device evidence from standard DICOM attributes.

Site- and device-identifying attributes (DeviceSerialNumber, StationName, InstitutionName,
InstitutionAddress, InstitutionalDepartmentName) are NEVER copied. Only the fact that they
are recorded is noted (``identifying_attributes_recorded``), so outputs stay non-identifying.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, Field
from pydicom.dataset import Dataset

from voxeltrace.evidence._dicom import first_item, tag_field
from voxeltrace.ingest.dicom import _get
from voxeltrace.schemas import EvidenceField

IDENTIFYING_ATTRIBUTES = (
    "DeviceSerialNumber",
    "StationName",
    "InstitutionName",
    "InstitutionAddress",
    "InstitutionalDepartmentName",
)


class ScannerEvidence(BaseModel):
    series_uid: str
    modality: EvidenceField
    sop_class_uid: EvidenceField
    frame_of_reference_uid: EvidenceField
    manufacturer: EvidenceField
    manufacturer_model_name: EvidenceField
    software_versions: EvidenceField
    magnetic_field_strength: EvidenceField = Field(description="PET/MR only (T).")
    collimator_type: EvidenceField
    counts_source: EvidenceField
    axial_acceptance: EvidenceField
    axial_mash: EvidenceField
    energy_window_lower_kev: EvidenceField
    energy_window_upper_kev: EvidenceField
    identifying_attributes_recorded: list[str] = Field(
        default_factory=list,
        description="Names (not values) of site/device identifiers present in headers.",
    )


def extract_scanner(series_uid: str, headers: Sequence[Dataset]) -> ScannerEvidence:
    energy = first_item("EnergyWindowRangeSequence")
    recorded = [
        kw for kw in IDENTIFYING_ATTRIBUTES if any(str(_get(h, kw) or "").strip() for h in headers)
    ]
    return ScannerEvidence(
        series_uid=series_uid,
        modality=tag_field(headers, "Modality"),
        sop_class_uid=tag_field(headers, "SOPClassUID"),
        frame_of_reference_uid=tag_field(headers, "FrameOfReferenceUID"),
        manufacturer=tag_field(headers, "Manufacturer"),
        manufacturer_model_name=tag_field(headers, "ManufacturerModelName"),
        software_versions=tag_field(headers, "SoftwareVersions", kind="list"),
        magnetic_field_strength=tag_field(headers, "MagneticFieldStrength", kind="float", unit="T"),
        collimator_type=tag_field(headers, "CollimatorType"),
        counts_source=tag_field(headers, "CountsSource"),
        axial_acceptance=tag_field(headers, "AxialAcceptance", kind="float"),
        axial_mash=tag_field(headers, "AxialMash", kind="list"),
        energy_window_lower_kev=tag_field(
            headers, "EnergyWindowLowerLimit", kind="float", unit="keV", item=energy
        ),
        energy_window_upper_kev=tag_field(
            headers, "EnergyWindowUpperLimit", kind="float", unit="keV", item=energy
        ),
        identifying_attributes_recorded=recorded,
    )
