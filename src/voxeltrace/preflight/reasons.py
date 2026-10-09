"""Preflight reason-code catalog: severity, affected field, remediation, recoverability.

Codes of the strict SUV input validator (quant/suv.py) are reused verbatim: a validator
REFUSAL is BLOCKING (the validator would refuse to quantify), a validator WARNING is WARNING.
Preflight-specific codes cover what the validator does not decide (secondary capture, SUL
anthropometrics, tracer, reconstruction completeness, PET/CT frame of reference, vendor
coverage, de-identification loss).
"""

from __future__ import annotations

from pydantic import BaseModel

from voxeltrace.preflight.schema import Severity


class ReasonSpec(BaseModel):
    severity: Severity
    field: str
    remediation: str
    recoverable: str  # YES / NO / MAYBE (can the site fix it by re-export or records?)


_S = ReasonSpec
CATALOG: dict[str, ReasonSpec] = {
    # ---- validator refusals (BLOCKING) -------------------------------------------------
    "MISSING_UNITS": _S(severity="BLOCKING", field="Units (0054,1001)", remediation="re-export the PET with Units populated (BQML expected)", recoverable="YES"),
    "UNSUPPORTED_UNITS": _S(severity="BLOCKING", field="Units (0054,1001)", remediation="supply the original activity-concentration (BQML) series, not a processed/normalized one", recoverable="MAYBE"),
    "MISSING_DECAYCORRECTION": _S(severity="BLOCKING", field="DecayCorrection (0054,1102)", remediation="re-export with DecayCorrection populated", recoverable="YES"),
    "UNSUPPORTED_DECAY_CORRECTION": _S(severity="BLOCKING", field="DecayCorrection (0054,1102)", remediation="supply images decay-corrected to scan START (or a documented vendor path)", recoverable="MAYBE"),
    "MISSING_CORRECTION": _S(severity="BLOCKING", field="CorrectedImage (0028,0051)", remediation="supply attenuation- and decay-corrected images", recoverable="MAYBE"),
    "IMPLAUSIBLE_PATIENTWEIGHT": _S(severity="BLOCKING", field="PatientWeight (0010,1030)", remediation="confirm patient weight from the site record and re-export", recoverable="YES"),
    "MISSING_PATIENTWEIGHT": _S(severity="BLOCKING", field="PatientWeight (0010,1030)", remediation="provide patient weight (de-identification must retain patient characteristics, PS3.15 E.3.7)", recoverable="YES"),
    "NONPOSITIVE_PATIENTWEIGHT": _S(severity="BLOCKING", field="PatientWeight (0010,1030)", remediation="provide a positive patient weight", recoverable="YES"),
    "MISSING_RADIONUCLIDETOTALDOSE": _S(severity="BLOCKING", field="RadionuclideTotalDose (0018,1074)", remediation="provide injected activity from the site record", recoverable="YES"),
    "IMPLAUSIBLE_RADIONUCLIDETOTALDOSE": _S(severity="BLOCKING", field="RadionuclideTotalDose (0018,1074)", remediation="confirm injected activity (units Bq) with the site", recoverable="YES"),
    "MISSING_RADIONUCLIDEHALFLIFE": _S(severity="BLOCKING", field="RadionuclideHalfLife (0018,1075)", remediation="re-export with the radionuclide half-life", recoverable="YES"),
    "HALF_LIFE_RADIONUCLIDE_MISMATCH": _S(severity="BLOCKING", field="RadionuclideHalfLife / RadionuclideCodeSequence", remediation="confirm the radionuclide with the site", recoverable="MAYBE"),
    "MISSING_INJECTION_TIME": _S(severity="BLOCKING", field="RadiopharmaceuticalStartTime/DateTime", remediation="provide injection time from the site record", recoverable="YES"),
    "INVALID_INJECTION_TIME": _S(severity="BLOCKING", field="RadiopharmaceuticalStartTime/DateTime", remediation="correct the injection time format/value", recoverable="YES"),
    "INJECTION_TIME_CONFLICT": _S(severity="BLOCKING", field="RadiopharmaceuticalStartTime vs StartDateTime", remediation="resolve the conflicting injection times with the site", recoverable="YES"),
    "INVALID_SERIES_DATETIME": _S(severity="BLOCKING", field="SeriesDate/SeriesTime", remediation="re-export with valid series date/time", recoverable="YES"),
    "INVALID_ACQUISITION_DATETIME": _S(severity="BLOCKING", field="AcquisitionDate/AcquisitionTime", remediation="re-export with valid acquisition date/time", recoverable="YES"),
    "SCAN_REFERENCE_AMBIGUOUS": _S(severity="BLOCKING", field="SeriesTime / AcquisitionTime / FrameReferenceTime", remediation="supply the original series; confirm the scan reference time per bed", recoverable="MAYBE"),
    "SERIES_TIME_AFTER_ACQUISITION": _S(severity="BLOCKING", field="SeriesTime vs AcquisitionTime", remediation="supply the original (not re-saved) series", recoverable="MAYBE"),
    "NEGATIVE_DECAY_INTERVAL": _S(severity="BLOCKING", field="injection vs scan time", remediation="correct injection/scan times (possible date rollover or de-identification shift)", recoverable="YES"),
    "IMPLAUSIBLE_DECAY_INTERVAL": _S(severity="BLOCKING", field="injection vs scan time", remediation="confirm uptake interval with the site record", recoverable="YES"),
    "DECAY_FACTOR_INCONSISTENT": _S(severity="BLOCKING", field="DecayFactor (0054,1321) vs FrameReferenceTime (0054,1300)", remediation="supply vendor documentation of the decay reference, or the original export; do not override", recoverable="MAYBE"),
    "INVALID_TIMEZONE": _S(severity="BLOCKING", field="TimezoneOffsetFromUTC", remediation="correct the timezone offset", recoverable="YES"),
    "TIMEZONE_AMBIGUOUS": _S(severity="BLOCKING", field="TimezoneOffsetFromUTC", remediation="state the timezone of injection and scan times", recoverable="YES"),
    "RADIOPHARMACEUTICAL_ITEMS": _S(severity="BLOCKING", field="RadiopharmaceuticalInformationSequence", remediation="supply exactly one radiopharmaceutical item", recoverable="MAYBE"),
    "MISSING_RESCALE": _S(severity="BLOCKING", field="RescaleSlope/RescaleIntercept", remediation="re-export with rescale attributes", recoverable="YES"),
    "NONPOSITIVE_RESCALE_SLOPE": _S(severity="BLOCKING", field="RescaleSlope (0028,1053)", remediation="supply the original quantitative series", recoverable="MAYBE"),
    # ---- validator warnings (WARNING) --------------------------------------------------
    "DECAY_FACTOR_UNVERIFIED": _S(severity="WARNING", field="DecayFactor / FrameReferenceTime", remediation="request DecayFactor/FrameReferenceTime (Type 1C when DecayCorrection != NONE)", recoverable="MAYBE"),
    "INJECTION_DATE_FROM_SERIES": _S(severity="WARNING", field="RadiopharmaceuticalStartDateTime", remediation="supply the injection date explicitly", recoverable="YES"),
    "INJECTION_DATE_ROLLOVER": _S(severity="WARNING", field="injection date", remediation="confirm injection date across midnight", recoverable="YES"),
    "CORRECTIONS_NOT_DECLARED": _S(severity="WARNING", field="CorrectedImage (0028,0051)", remediation="confirm applied corrections", recoverable="YES"),
    "RADIONUCLIDE_UNIDENTIFIED": _S(severity="WARNING", field="RadionuclideCodeSequence", remediation="provide the radionuclide code", recoverable="YES"),
    "SERIES_PRECEDES_ACQUISITION": _S(severity="WARNING", field="SeriesTime vs AcquisitionTime", remediation="confirm the scan reference time", recoverable="MAYBE"),
    "SHORT_DECAY_INTERVAL": _S(severity="WARNING", field="uptake interval", remediation="confirm the uptake interval", recoverable="YES"),
    "UNUSUAL_PATIENTWEIGHT": _S(severity="WARNING", field="PatientWeight", remediation="confirm patient weight", recoverable="YES"),
    # ---- preflight-specific -------------------------------------------------------------
    "NOT_PET_MODALITY": _S(severity="INFO", field="Modality (0008,0060)", remediation="none (not a PET series)", recoverable="NO"),
    "SECONDARY_CAPTURE": _S(severity="BLOCKING", field="SOPClassUID / ImageType", remediation="supply the original PET Image Storage series (screen captures are not quantitative)", recoverable="MAYBE"),
    "DERIVED_IMAGE": _S(severity="WARNING", field="ImageType (0008,0008)", remediation="confirm the series is the original reconstruction, not a re-saved/processed copy", recoverable="MAYBE"),
    "MISSING_PATIENTSIZE": _S(severity="WARNING", field="PatientSize (0010,1020)", remediation="provide height (needed for SUL/PERCIST; retain patient characteristics, PS3.15 E.3.7)", recoverable="YES"),
    "UNSUPPORTED_PATIENTSEX_FOR_SUL": _S(severity="WARNING", field="PatientSex (0010,0040)", remediation="LBM formulas need M/F; provide sex if available (SUL refused otherwise)", recoverable="MAYBE"),
    "TRACER_UNKNOWN": _S(severity="WARNING", field="Radiopharmaceutical / RadiopharmaceuticalCodeSequence", remediation="provide the radiopharmaceutical; pair rules need tracer identity", recoverable="YES"),
    "RECONSTRUCTION_INCOMPLETE": _S(severity="WARNING", field="ReconstructionMethod / iterations / subsets / kernel / TOF / PSF", remediation="re-export standard reconstruction attributes or supply a reconstruction record/attestation", recoverable="YES"),
    "SCANNER_UNKNOWN": _S(severity="WARNING", field="Manufacturer / ManufacturerModelName", remediation="provide scanner manufacturer and model", recoverable="YES"),
    "SOFTWARE_UNKNOWN": _S(severity="WARNING", field="SoftwareVersions (0018,1020)", remediation="provide scanner software version", recoverable="YES"),
    "NO_VENDOR_PRIVATE_PARSER": _S(severity="INFO", field="Manufacturer", remediation="none required for the standard BQML path; vendor private timing checks unavailable", recoverable="NO"),
    "ANONYMIZATION_LOSS": _S(severity="WARNING", field="(see evidence)", remediation="ask the de-identifier to retain patient characteristics / device identity (PS3.15 E.3.7, E.3.8)", recoverable="MAYBE"),
    "NO_PET_SERIES": _S(severity="BLOCKING", field="scan directory", remediation="supply the PET series", recoverable="YES"),
    "MULTIPLE_PET_SERIES": _S(severity="NEEDS_REVIEW", field="scan directory", remediation="select the attenuation-corrected PET series to quantify", recoverable="YES"),
    "CT_NOT_IN_PET_FRAME": _S(severity="WARNING", field="FrameOfReferenceUID (0020,0052)", remediation="supply the CT acquired with the PET (same frame of reference); reference regions unavailable otherwise", recoverable="MAYBE"),
    "CT_FRAME_AMBIGUOUS": _S(severity="WARNING", field="FrameOfReferenceUID (0020,0052)", remediation="supply exactly one CT series in the PET frame of reference", recoverable="YES"),
    "CT_NOT_VOLUMETRIC": _S(severity="WARNING", field="CT instance count", remediation="supply the volumetric CT (a single-image CT/localizer cannot guide reference regions)", recoverable="YES"),
}  # fmt: skip

GENERIC_REFUSAL = _S(severity="BLOCKING", field="(validator)", remediation="see the strict SUV validator refusal message", recoverable="MAYBE")  # fmt: skip
GENERIC_WARNING = _S(severity="WARNING", field="(validator)", remediation="see the strict SUV validator warning message", recoverable="MAYBE")  # fmt: skip


def spec(code: str, *, refusal: bool | None = None) -> ReasonSpec:
    if code in CATALOG:
        return CATALOG[code]
    return GENERIC_REFUSAL if refusal else GENERIC_WARNING
