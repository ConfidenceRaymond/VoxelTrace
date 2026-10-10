# Data request for GE and Philips design partners (minimum necessary)

**Purpose:** test whether VoxelTrace can establish quantitative PET and protocol identity on
GE and Philips exports, which public data cannot do (`non_siemens_gap_analysis.md`). This is
a validation request, not a clinical service. RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.

## What we ask for

Per scanner model and software version you want covered, exported **through your normal
trial pathway** (the same anonymizer and export settings you use for trials, because those
settings are what we are testing):

| # | Item | Why | Minimum |
|---|---|---|---|
| 1 | **Attenuation-corrected PET series**, DICOM PET Image Storage, **Units = BQML**, all slices | the only quantitative input on the strict path | 2–3 subjects × baseline + follow-up (same scanner); or a phantom only (item 9) |
| 2 | Quantitative PET attributes kept: Units, DecayCorrection, CorrectedImage, RescaleSlope/Intercept, **DecayFactor**, **FrameReferenceTime**, ActualFrameDuration, AcquisitionDate/Time, SeriesDate/Time | strict SUV and the decay cross-check (the open GE question) | as exported |
| 3 | **Radiopharmaceutical Information Sequence**: Radiopharmaceutical / code, RadionuclideTotalDose, RadionuclideHalfLife, RadiopharmaceuticalStartDateTime | injected activity and injection time | as exported |
| 4 | **Decay semantics**: one sentence from your physicist, per model/software: "images are decay-corrected to ___; DecayFactor refers to ___" (or the page of the vendor DICOM conformance statement that says so) | decides `DECAY_FACTOR_INCONSISTENT` without guessing | 1 statement per model/software |
| 5 | PatientWeight (and PatientSize, PatientSex if PERCIST/SUL is in scope) | SUVbw (SUL) | retain patient characteristics (PS3.15 E.3.7) |
| 6 | Reconstruction settings: algorithm, iterations, subsets, TOF, PSF/resolution modelling, post-filter, matrix/voxel size | protocol identity rules | DICOM if populated; otherwise the protocol sheet (PDF/screenshot of the protocol, no patient data) |
| 7 | Manufacturer, ManufacturerModelName, **SoftwareVersions** | same-system rules, vendor matrix entry | retain device identity (PS3.15 E.3.8) |
| 8 | CorrectedImage flags (ATTN, DECY, SCAT, RAN, NORM, DTIM) | correction state | as exported |
| 9 | *Optional, preferred first:* one **phantom acquisition** (NEMA IEC body or uniform cylinder) with the activity calibration record (activity, calibration time, volume, dose calibrator) | ground truth independent of patient metadata | see `phantom_validation_plan.md` |
| 10 | *Optional:* the protocol export from the scanner console | reconstruction evidence for attestation | 1 per protocol |
| 11 | *Optional:* the CT acquired with each PET (same frame of reference) | reference-region proposals (PERCIST) only | if PERCIST is in scope |

## What we do NOT need (please do not send)

- Names, MRNs, accession numbers, dates of birth, addresses, referring physicians, operator
  names, institution addresses.
- Real dates if you can shift them consistently per subject (keep injection and scan times on
  the same clock; shift whole dates only).
- Diagnoses, reports, outcomes or any clinical information.
- Raw sinograms, list-mode data, NAC series, MIPs, screen captures.
- Data from patients you are not authorised to share under your data-use agreement.

## How to send

Any folder layout (`site/subject/visit/...`), plus a short visit list (which folder is
baseline / follow-up, and the site). VoxelTrace runs `intake-map` and reports how each folder
was interpreted before any audit.

## What you get back

For each model/software: whether strict SUV can be established from your export, and if not
the exact attribute and the reason; whether protocol identity is provable from DICOM or needs
your protocol sheet; and, with a phantom, the measured vs. expected activity concentration.
We will not claim your model is validated beyond what the result shows, and we will not
change a rule because of one export without a documented vendor basis.
