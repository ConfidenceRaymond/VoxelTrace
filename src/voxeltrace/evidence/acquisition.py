"""Acquisition protocol evidence. Missing values are reported as MISSING, never inferred.

Timing values (injection, reference time, uptake interval) are taken ONLY from the strict
Milestone 3 validator (``validated_suv_input``); if that validator refused timing, they are
MISSING with the refusal codes in ``note``.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel
from pydicom.dataset import Dataset

from voxeltrace.evidence._dicom import derived, first_item, missing, tag_field
from voxeltrace.ingest.dicom import _get
from voxeltrace.quant.dicom_time import DicomTimeError, combine_da_tm, parse_dt
from voxeltrace.schemas import EvidenceField, ImageGeometry, SUVInputs, SUVValidation


class AcquisitionProtocol(BaseModel):
    series_uid: str
    tracer: EvidenceField
    radiopharmaceutical_code: EvidenceField
    radionuclide: EvidenceField
    injected_activity_bq: EvidenceField
    injection_datetime: EvidenceField
    uptake_interval_s: EvidenceField
    acquisition_reference_datetime: EvidenceField
    acquisition_start_datetime: EvidenceField
    acquisition_duration_s: EvidenceField
    acquisition_time_span_s: EvidenceField
    frame_duration_ms: EvidenceField
    bed_duration_s: EvidenceField
    number_of_bed_positions: EvidenceField
    series_type: EvidenceField
    temporal_type: EvidenceField
    is_dynamic: EvidenceField
    number_of_time_slices: EvidenceField
    number_of_slices: EvidenceField
    matrix_rows: EvidenceField
    matrix_columns: EvidenceField
    pixel_spacing_mm: EvidenceField
    slice_spacing_mm: EvidenceField
    axial_coverage_mm: EvidenceField
    patient_position: EvidenceField
    patient_orientation: EvidenceField
    patient_gantry_relationship: EvidenceField
    body_part_examined: EvidenceField
    image_units: EvidenceField
    decay_correction: EvidenceField


def _acq_datetimes(headers: Sequence[Dataset]):
    out = []
    for h in headers:
        if _get(h, "AcquisitionDateTime") is not None:
            out.append(parse_dt(_get(h, "AcquisitionDateTime")))
        else:
            out.append(combine_da_tm(_get(h, "AcquisitionDate"), _get(h, "AcquisitionTime")))
    return out


def extract_acquisition(
    series_uid: str,
    headers: Sequence[Dataset],
    geometry: ImageGeometry | None,
    suv_inputs: SUVInputs | None,
    suv_validation: SUVValidation | None,
) -> AcquisitionProtocol:
    rp = first_item("RadiopharmaceuticalInformationSequence")

    def rp_code(seq: str):
        def pick(h: Dataset):
            item = rp(h)
            s = _get(item, seq) if item is not None else None
            return s[0] if s else None

        return pick

    timing_codes = [
        r.code
        for r in (suv_validation.reasons if suv_validation else [])
        if any(
            k in r.code
            for k in ("TIME", "DATETIME", "INTERVAL", "TIMEZONE", "SCAN_REF", "SERIES", "INJECTION")
        )
    ]
    tnote = (
        ("strict timing validation refused: " + ", ".join(timing_codes)) if timing_codes else None
    )
    si = suv_inputs or SUVInputs()

    def timing(name: str, value, source: str | None, unit: str | None = None) -> EvidenceField:
        return derived(
            name,
            value,
            source=source or "strict SUV timing validator",
            derivation="validated_suv_input",
            unit=unit,
            note=None if value is not None else tnote or "not established",
        )

    # Acquisition time span: earliest acquisition start to latest start + frame duration.
    frame = tag_field(headers, "ActualFrameDuration", kind="float", unit="ms")
    try:
        acq = _acq_datetimes(headers)
        span = (max(acq) - min(acq)).total_seconds() + (
            float(frame.value) / 1000.0 if frame.known else 0.0
        )
        span_field = derived(
            "acquisition_time_span_s",
            span if frame.known else None,
            source="AcquisitionDate/Time (all slices) + ActualFrameDuration",
            derivation="derived_from_timing",
            unit="s",
            ambiguous=True,
            note="latest − earliest slice acquisition start + one frame duration; approximate "
            "(bed overlap/gaps not resolved)"
            if frame.known
            else "frame duration missing",
        )
    except (DicomTimeError, ValueError):
        span_field = missing(
            "acquisition_time_span_s",
            "AcquisitionDate/Time",
            note="acquisition times missing or invalid",
        )

    st = tag_field(headers, "SeriesType", kind="list")
    temporal = st.value[0] if isinstance(st.value, list) and st.value else None
    dyn = (
        {"DYNAMIC": True, "STATIC": False, "WHOLE BODY": False}.get(temporal) if temporal else None
    )
    bed = derived(
        "bed_duration_s",
        float(frame.value) / 1000.0
        if frame.known and temporal in ("WHOLE BODY", "STATIC")
        else None,
        source="(0018,1242) ActualFrameDuration",
        derivation="derived_from_timing",
        unit="s",
        ambiguous=True,
        note="assumes one frame per bed position for a static/whole-body series",
    )

    if geometry is not None and geometry.spacing_ijk[2] is not None:
        slice_sp = derived(
            "slice_spacing_mm",
            geometry.spacing_ijk[2],
            source="ImagePositionPatient (geometry)",
            derivation="derived_from_geometry",
            unit="mm",
        )
        cover = derived(
            "axial_coverage_mm",
            geometry.extent_mm[2],
            source="number of slices × slice spacing (geometry)",
            derivation="derived_from_geometry",
            unit="mm",
        )
    else:
        slice_sp = missing("slice_spacing_mm", "geometry", "geometry unavailable or non-uniform")
        cover = missing("axial_coverage_mm", "geometry", "geometry unavailable or non-uniform")

    return AcquisitionProtocol(
        series_uid=series_uid,
        tracer=tag_field(headers, "Radiopharmaceutical", name="tracer", item=rp),
        radiopharmaceutical_code=tag_field(
            headers,
            "CodeMeaning",
            name="radiopharmaceutical_code",
            item=rp_code("RadiopharmaceuticalCodeSequence"),
        ),
        radionuclide=tag_field(
            headers, "CodeMeaning", name="radionuclide", item=rp_code("RadionuclideCodeSequence")
        ),
        injected_activity_bq=tag_field(
            headers,
            "RadionuclideTotalDose",
            name="injected_activity_bq",
            kind="float",
            unit="Bq",
            item=rp,
        ),
        injection_datetime=timing(
            "injection_datetime", si.injection_datetime, si.injection_datetime_source
        ),
        uptake_interval_s=timing(
            "uptake_interval_s",
            si.decay_interval_s,
            "scan reference − injection (strict SUV timing)",
            "s",
        ),
        acquisition_reference_datetime=timing(
            "acquisition_reference_datetime",
            si.scan_reference_datetime,
            si.scan_reference_datetime_source,
        ),
        acquisition_start_datetime=timing(
            "acquisition_start_datetime",
            si.earliest_acquisition_datetime,
            "earliest AcquisitionDate/Time over all slices",
        ),
        acquisition_duration_s=tag_field(headers, "AcquisitionDuration", kind="float", unit="s"),
        acquisition_time_span_s=span_field,
        frame_duration_ms=frame,
        bed_duration_s=bed,
        number_of_bed_positions=missing(
            "number_of_bed_positions",
            "not encoded in standard attributes",
            note="not determinable without vendor-private data (not parsed)",
        ),
        series_type=st,
        temporal_type=derived(
            "temporal_type",
            temporal,
            source="(0054,1000) SeriesType[0]",
            derivation="standard_enumeration",
        ),
        is_dynamic=derived(
            "is_dynamic",
            dyn,
            source="(0054,1000) SeriesType[0]",
            derivation="standard_enumeration",
            note=None if dyn is not None else "GATED or unknown SeriesType",
        ),
        number_of_time_slices=tag_field(headers, "NumberOfTimeSlices", kind="int"),
        number_of_slices=tag_field(headers, "NumberOfSlices", kind="int"),
        matrix_rows=tag_field(headers, "Rows", kind="int"),
        matrix_columns=tag_field(headers, "Columns", kind="int"),
        pixel_spacing_mm=tag_field(headers, "PixelSpacing", kind="floatlist", unit="mm"),
        slice_spacing_mm=slice_sp,
        axial_coverage_mm=cover,
        patient_position=tag_field(headers, "PatientPosition"),
        patient_orientation=tag_field(
            headers,
            "CodeMeaning",
            name="patient_orientation",
            item=first_item("PatientOrientationCodeSequence"),
        ),
        patient_gantry_relationship=tag_field(
            headers,
            "CodeMeaning",
            name="patient_gantry_relationship",
            item=first_item("PatientGantryRelationshipCodeSequence"),
        ),
        body_part_examined=tag_field(headers, "BodyPartExamined"),
        image_units=tag_field(headers, "Units"),
        decay_correction=tag_field(headers, "DecayCorrection"),
    )
