"""Actionable remediation matrix (VT-REMEDIATION-MATRIX-1). Documentation layer only.

One row per reason code that preflight, intake, pair evaluation or the pairing audit can
emit. ``explanation``, ``severity`` and ``remediation`` come from the existing catalogues
(``preflight/reasons.py``, ``trial/reasons.py``); this module adds only the customer-facing
wording and four fix routes, each YES / NO / MAYBE:

  reexport_can_fix       a new DICOM export from the site can resolve it
  documentation_can_fix  a site record (protocol sheet, attestation, CRF value) can resolve it
  human_review_can_fix   a qualified reviewer's recorded decision can resolve it
  permanent              nothing can change it for this scan / pair (a decided measurement)

Nothing here changes a finding or a verdict. Where no remediation is established the row says
"No deterministic remediation established." rather than inventing one.
"""

from __future__ import annotations

from typing import Any

REMEDIATION_SCHEMA = "VT-REMEDIATION-MATRIX-1"
NONE_ESTABLISHED = "No deterministic remediation established."

# code -> (customer wording, reexport, documentation, human review, permanent)
_W: dict[str, tuple[str, str, str, str, str]] = {
    # ---- pair evaluation (trial/reasons.py) ------------------------------------------
    "NEVER_ENCODED": ("Information the rule needs was never recorded in the DICOM export.", "MAYBE", "MAYBE", "NO", "MAYBE"),
    "STRIPPED_BY_ANONYMIZATION": ("Information the rule needs was removed during de-identification.", "YES", "MAYBE", "NO", "NO"),
    "UNKNOWN_OR_STRIPPED": ("Information the rule needs is missing; it is unclear whether it was never recorded or removed during de-identification.", "MAYBE", "MAYBE", "NO", "MAYBE"),
    "MISSING_REQUIRED_TAG": ("A standard DICOM attribute required by this rule is missing or invalid.", "MAYBE", "MAYBE", "NO", "MAYBE"),
    "INCONSISTENT_METADATA": ("The scan's metadata contradicts itself (values differ between images or fields).", "YES", "NO", "NO", "NO"),
    "UNSUPPORTED_VENDOR": ("This scanner vendor needs vendor-specific handling that VoxelTrace has not validated.", "NO", "NO", "NO", "MAYBE"),
    "UNSUPPORTED_SOFTWARE_VERSION": ("This scanner software version has not been validated for VoxelTrace.", "NO", "MAYBE", "NO", "MAYBE"),
    "PRIVATE_TAG_NOT_AVAILABLE": ("A documented vendor-specific attribute that would settle the question is absent.", "MAYBE", "NO", "NO", "NO"),
    "UNSUPPORTED_PRIVATE_TAG": ("A vendor-specific attribute is present but its meaning is not documented, so VoxelTrace does not use it.", "NO", "MAYBE", "NO", "MAYBE"),
    "AMBIGUOUS_RECONSTRUCTION": ("The reconstruction settings (algorithm, iterations, subsets, TOF, PSF, filter) cannot be established from the export.", "YES", "YES", "NO", "NO"),
    "AMBIGUOUS_TIMING": ("The injection-to-scan timing cannot be established unambiguously.", "YES", "MAYBE", "NO", "NO"),
    "UNKNOWN_PROVENANCE": ("The processing history of the series is unknown (for example a derived or re-saved copy).", "YES", "MAYBE", "NO", "NO"),
    "MANUAL_OR_REFERENCE_MASK_REQUIRED": ("A liver / blood-pool reference region must be supplied or reviewed.", "NO", "YES", "YES", "NO"),
    "REFERENCE_REVIEW_REQUIRED": ("A proposed reference region is waiting for a qualified reviewer's decision.", "NO", "NO", "YES", "NO"),
    "REFERENCE_REVIEW_OUTDATED": ("The recorded reference-region review refers to an earlier proposal and must be redone.", "NO", "NO", "YES", "NO"),
    "REFERENCE_REVIEW_INVALID": ("A reference-region review record failed validation and must be re-recorded.", "NO", "NO", "YES", "NO"),
    "REFERENCE_REJECTED_BY_REVIEWER": ("A reviewer rejected the proposed reference region; a corrected region is needed.", "NO", "YES", "YES", "NO"),
    "REFERENCE_AUTO_NOT_FOUND": ("VoxelTrace could not place a reference region automatically.", "MAYBE", "YES", "YES", "NO"),
    "REFERENCE_QC_FAILED": ("The reference region failed measurement quality control.", "NO", "YES", "YES", "NO"),
    "REFERENCE_INHERITANCE_REFUSED": ("A test-fixture reference inheritance was refused (not applicable to real data).", "NO", "NO", "YES", "NO"),
    "ANTHROPOMETRICS_MISSING": ("Height and/or sex is missing, so lean-body-mass SUV (SUL, needed for PERCIST) cannot be computed.", "YES", "YES", "NO", "NO"),
    "SUV_REFUSED": ("Standardised uptake value (SUV) could not be computed safely; see the specific refusal reasons.", "MAYBE", "MAYBE", "NO", "MAYBE"),
    "EXTERNAL_RECONSTRUCTION_ATTESTATION": ("Reconstruction identity rests on a site attestation rather than on DICOM evidence.", "YES", "NO", "NO", "NO"),
    "RECONSTRUCTION_ATTESTATION_NOT_USABLE": ("A supplied reconstruction attestation could not be used (invalid, stale, out of scope or unsigned).", "NO", "YES", "NO", "NO"),
    "RECONSTRUCTION_ATTESTATION_CONTRADICTS": ("A reconstruction attestation disagrees with the DICOM or with another attestation.", "MAYBE", "YES", "NO", "NO"),
    "LESION_REVIEW_REQUIRED": ("Supplied lesion segmentations have not been accepted by a qualified reviewer.", "NO", "NO", "YES", "NO"),
    # ---- preflight (preflight/reasons.py) --------------------------------------------
    "MISSING_UNITS": ("PET pixel units are missing, so activity concentration cannot be established.", "YES", "NO", "NO", "NO"),
    "UNSUPPORTED_UNITS": ("PET pixel units are not activity concentration (Bq/mL); the series appears processed or normalised.", "MAYBE", "NO", "NO", "MAYBE"),
    "MISSING_DECAYCORRECTION": ("The decay-correction reference is missing.", "YES", "NO", "NO", "NO"),
    "UNSUPPORTED_DECAY_CORRECTION": ("The images are decay-corrected to a reference VoxelTrace does not support for strict SUV.", "MAYBE", "MAYBE", "NO", "MAYBE"),
    "MISSING_CORRECTION": ("The images do not declare attenuation and decay correction.", "MAYBE", "MAYBE", "NO", "MAYBE"),
    "IMPLAUSIBLE_PATIENTWEIGHT": ("The recorded patient weight is implausible.", "YES", "YES", "NO", "NO"),
    "MISSING_PATIENTWEIGHT": ("Patient weight is missing, so body-weight SUV cannot be computed.", "YES", "YES", "NO", "NO"),
    "NONPOSITIVE_PATIENTWEIGHT": ("Patient weight is zero or negative.", "YES", "YES", "NO", "NO"),
    "MISSING_RADIONUCLIDETOTALDOSE": ("Quantitative PET cannot be established because the injected activity is missing from the radiopharmaceutical metadata. Request a re-export containing the Radiopharmaceutical Information Sequence.", "YES", "YES", "NO", "NO"),
    "IMPLAUSIBLE_RADIONUCLIDETOTALDOSE": ("The recorded injected activity is implausible (check units: Bq expected).", "YES", "YES", "NO", "NO"),
    "MISSING_RADIONUCLIDEHALFLIFE": ("The radionuclide half-life is missing, so decay cannot be computed.", "YES", "NO", "NO", "NO"),
    "HALF_LIFE_RADIONUCLIDE_MISMATCH": ("The recorded half-life does not match the recorded radionuclide.", "MAYBE", "YES", "NO", "NO"),
    "MISSING_INJECTION_TIME": ("The injection time is missing, so uptake time and decay cannot be computed.", "YES", "YES", "NO", "NO"),
    "INVALID_INJECTION_TIME": ("The injection time is malformed.", "YES", "YES", "NO", "NO"),
    "INJECTION_TIME_CONFLICT": ("Two recorded injection times disagree.", "YES", "YES", "NO", "NO"),
    "INVALID_SERIES_DATETIME": ("The series date/time is malformed.", "YES", "NO", "NO", "NO"),
    "INVALID_ACQUISITION_DATETIME": ("The acquisition date/time is malformed.", "YES", "NO", "NO", "NO"),
    "SCAN_REFERENCE_AMBIGUOUS": ("The scan reference time cannot be established unambiguously.", "MAYBE", "MAYBE", "NO", "MAYBE"),
    "SERIES_TIME_AFTER_ACQUISITION": ("The series time is after the acquisition time, which suggests a re-saved series.", "MAYBE", "NO", "NO", "MAYBE"),
    "NEGATIVE_DECAY_INTERVAL": ("The scan appears to start before the injection (possible date rollover or date shift).", "YES", "YES", "NO", "NO"),
    "IMPLAUSIBLE_DECAY_INTERVAL": ("The injection-to-scan interval is implausible.", "YES", "YES", "NO", "NO"),
    "DECAY_FACTOR_INCONSISTENT": ("The recorded decay factor contradicts the recorded timing.", "MAYBE", "MAYBE", "NO", "MAYBE"),
    "INVALID_TIMEZONE": ("The timezone offset is malformed.", "YES", "NO", "NO", "NO"),
    "TIMEZONE_AMBIGUOUS": ("Injection and scan times may be in different timezones.", "YES", "YES", "NO", "NO"),
    "RADIOPHARMACEUTICAL_ITEMS": ("The radiopharmaceutical record does not contain exactly one item.", "MAYBE", "MAYBE", "NO", "MAYBE"),
    "MISSING_RESCALE": ("The pixel rescale attributes are missing, so voxel values cannot be converted.", "YES", "NO", "NO", "NO"),
    "NONPOSITIVE_RESCALE_SLOPE": ("The pixel rescale slope is zero or negative.", "MAYBE", "NO", "NO", "MAYBE"),
    "DECAY_FACTOR_UNVERIFIED": ("The decay reference could not be cross-checked (decay factor or frame reference time absent).", "MAYBE", "NO", "NO", "NO"),
    "INJECTION_DATE_FROM_SERIES": ("The injection date was taken from the series date by a documented rule.", "YES", "YES", "NO", "NO"),
    "INJECTION_DATE_ROLLOVER": ("Injection and scan straddle midnight; please confirm the injection date.", "YES", "YES", "NO", "NO"),
    "CORRECTIONS_NOT_DECLARED": ("The applied image corrections are not declared.", "YES", "YES", "NO", "NO"),
    "RADIONUCLIDE_UNIDENTIFIED": ("The radionuclide code is missing.", "YES", "YES", "NO", "NO"),
    "SERIES_PRECEDES_ACQUISITION": ("The series time precedes the acquisition time; please confirm the scan reference time.", "MAYBE", "MAYBE", "NO", "NO"),
    "SHORT_DECAY_INTERVAL": ("The injection-to-scan interval is unusually short; please confirm.", "YES", "YES", "NO", "NO"),
    "UNUSUAL_PATIENTWEIGHT": ("The patient weight is unusual; please confirm.", "YES", "YES", "NO", "NO"),
    "NOT_PET_MODALITY": ("This series is not PET and is not quantified.", "NO", "NO", "NO", "NO"),
    "SECONDARY_CAPTURE": ("This is a screen capture, not a quantitative PET image.", "MAYBE", "NO", "NO", "MAYBE"),
    "DERIVED_IMAGE": ("This series is marked as derived; please confirm it is the original reconstruction.", "MAYBE", "MAYBE", "NO", "NO"),
    "MISSING_PATIENTSIZE": ("Patient height is missing (needed for SUL/PERCIST).", "YES", "YES", "NO", "NO"),
    "UNSUPPORTED_PATIENTSEX_FOR_SUL": ("Patient sex is not M or F, so lean-body-mass formulas cannot be applied.", "MAYBE", "MAYBE", "NO", "MAYBE"),
    "TRACER_UNKNOWN": ("The tracer is not recorded, so tracer identity across timepoints cannot be checked.", "YES", "YES", "NO", "NO"),
    "RECONSTRUCTION_INCOMPLETE": ("Some reconstruction settings are not in the export.", "YES", "YES", "NO", "NO"),
    "SCANNER_UNKNOWN": ("The scanner manufacturer or model is not recorded.", "YES", "YES", "NO", "NO"),
    "SOFTWARE_UNKNOWN": ("The scanner software version is not recorded.", "YES", "YES", "NO", "NO"),
    "NO_VENDOR_PRIVATE_PARSER": ("Vendor-specific timing cross-checks are not available for this vendor (not needed for the standard path).", "NO", "NO", "NO", "NO"),
    "ANONYMIZATION_LOSS": ("De-identification removed patient characteristics or device identity that the audit uses.", "MAYBE", "MAYBE", "NO", "NO"),
    "NO_PET_SERIES": ("No PET series was found for this scan.", "YES", "NO", "NO", "NO"),
    "MULTIPLE_PET_SERIES": ("Several PET series were found; VoxelTrace will not choose one. Select the attenuation-corrected series to quantify.", "YES", "NO", "YES", "NO"),
    "CT_NOT_IN_PET_FRAME": ("No CT shares the PET frame of reference, so reference regions cannot be proposed.", "MAYBE", "NO", "NO", "NO"),
    "CT_FRAME_AMBIGUOUS": ("More than one CT shares the PET frame of reference.", "YES", "NO", "YES", "NO"),
    "CT_NOT_VOLUMETRIC": ("The CT is a single image or localizer and cannot guide reference regions.", "YES", "NO", "NO", "NO"),
    # ---- intake (validate_input.py) --------------------------------------------------
    "NON_FDG_TRACER": ("The tracer is not FDG; VoxelTrace's FDG rule sets do not apply.", "NO", "NO", "NO", "YES"),
    "TRACER_NOT_RECOGNISED": ("The tracer name is not recognised as FDG.", "YES", "YES", "NO", "NO"),
    "SINGLE_TIMEPOINT_SUBJECTS": ("Some subjects have only one timepoint, so no pair can be formed.", "NO", "NO", "NO", "NO"),
    "TRIAL_CONFIG_INVALID": ("The trial configuration file is invalid.", "NO", "YES", "NO", "NO"),
    "NO_SCANS_FOUND": ("No DICOM files were found.", "YES", "NO", "NO", "NO"),
    # ---- pairing audit (trial/pairing_audit.py) --------------------------------------
    "DUPLICATE_TIMEPOINT": ("Two timepoint folders of one subject have the same name after normalisation.", "NO", "YES", "YES", "NO"),
    "SAME_SCAN_LINKED_TWICE": ("The same PET scan appears under two timepoints of one subject.", "YES", "YES", "YES", "NO"),
    "SCAN_LINKED_TO_MULTIPLE_SUBJECTS": ("The same PET scan appears under two subjects.", "YES", "YES", "YES", "NO"),
    "TIMEPOINT_ORDER_ANOMALY": ("A follow-up was acquired before the baseline.", "NO", "YES", "YES", "NO"),
    "TIMEPOINT_ORDER_UNDECLARED": ("The chronological order of timepoints is not declared.", "NO", "YES", "NO", "NO"),
    "UNDECLARED_TIMEPOINT": ("A timepoint folder is not in the declared timepoint order.", "NO", "YES", "NO", "NO"),
    "INCONSISTENT_SUBJECT_PSEUDONYM": ("The DICOM patient identifier differs between timepoints of one subject.", "MAYBE", "YES", "YES", "NO"),
    "SUBJECT_PSEUDONYM_SHARED": ("Two subject folders carry the same DICOM patient identifier.", "MAYBE", "YES", "YES", "NO"),
    "SAME_DAY_TIMEPOINTS": ("Two timepoints of one subject were acquired on the same date.", "NO", "YES", "YES", "NO"),
    "MISSING_TIMEPOINT": ("A subject lacks a timepoint (no pair, or fewer pairs than declared).", "YES", "NO", "NO", "MAYBE"),
    "MIXED_TRACER": ("The tracer differs between timepoints of one subject.", "NO", "MAYBE", "NO", "MAYBE"),
    "ACQUISITION_DATE_UNKNOWN": ("The acquisition date is unknown, so timepoint order cannot be checked.", "YES", "YES", "NO", "NO"),
}  # fmt: skip
_INTAKE = {"NON_FDG_TRACER": ("UNSUPPORTED", "the FDG rule sets do not apply; no tracer-specific rule set exists"),
           "TRACER_NOT_RECOGNISED": ("BLOCKING", "confirm the tracer or re-export with RadiopharmaceuticalCodeSequence populated"),
           "SINGLE_TIMEPOINT_SUBJECTS": ("WARNING", "supply the missing timepoint if it exists"),
           "TRIAL_CONFIG_INVALID": ("BLOCKING", "correct trial.yaml (voxeltrace init-trial writes a valid starter file)"),
           "NO_SCANS_FOUND": ("BLOCKING", "supply the DICOM files")}  # fmt: skip
RULE_FAIL = {
    "code": "<RULE_ID> FAIL",
    "source": "pair evaluation",
    "severity": "BLOCKING",
    "explanation": "the evidence was decided and does not meet the rule's criterion (e.g. uptake time outside the window)",
    "customer_wording": "The scans were acquired in a way that does not meet the guideline criterion; the measured values are what they are.",
    "remediation": "a re-export cannot change measured values; the pair is not comparable under this rule set",
    "reexport_can_fix": "NO", "documentation_can_fix": "NO", "human_review_can_fix": "NO", "permanent": "YES",
}  # fmt: skip


def remediation_matrix() -> list[dict[str, Any]]:
    from voxeltrace.preflight.reasons import CATALOG as PF
    from voxeltrace.trial.pairing_audit import PAIRING_CODES
    from voxeltrace.trial.reasons import CATALOG as TR

    rows = []
    for code in sorted(_W):
        wording, rex, doc, rev, perm = _W[code]
        if code in TR:
            src, sev, expl, rem = (
                "pair evaluation",
                "per rule impact (blocking or warning)",
                TR[code].what,
                TR[code].remediation,
            )
        elif code in PF:
            src, sev, expl, rem = (
                "preflight",
                PF[code].severity,
                PF[code].field,
                PF[code].remediation,
            )
        elif code in _INTAKE:
            src, (sev, rem), expl = "intake", _INTAKE[code], wording
        else:
            src, (sev, rem), expl = "pairing audit", PAIRING_CODES[code], wording
        if rem.strip().lower().startswith("none"):
            rem = NONE_ESTABLISHED
        rows.append({"code": code, "source": src, "severity": sev, "explanation": expl, "customer_wording": wording,
                     "remediation": rem, "reexport_can_fix": rex, "documentation_can_fix": doc,
                     "human_review_can_fix": rev, "permanent": perm})  # fmt: skip
    return rows + [RULE_FAIL]


def customer_wording(code: str) -> str:
    if code.endswith(" FAIL"):
        return RULE_FAIL["customer_wording"]
    return _W.get(code, (f"{code}: see the technical detail.",))[0]
