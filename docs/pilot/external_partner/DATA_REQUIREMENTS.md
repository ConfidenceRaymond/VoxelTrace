# Data requirements (minimum necessary)

**Send only what is listed here. Please do not send unnecessary protected health information
(PHI) or personal data.** The export must already be de-identified under your own procedures
and data-use agreement; VoxelTrace does not de-identify data.

## Required

| # | Item | Details | If missing |
|---|---|---|---|
| 1 | **De-identified PET DICOM** | one attenuation-corrected PET series per visit, PET Image Storage, `Units = BQML`, all slices | the scan cannot be quantified (`DO_NOT_QUANTIFY`) |
| 2 | **Subject/timepoint mapping** | `partner_intake.yaml` (template in this folder; checked with `voxeltrace validate-partner-intake`), or a short table: subject pseudonym, visit folder → `baseline` / `followup`, site | visits are not paired, or the order is flagged for review |
| 3 | **Scanner / vendor / software** | DICOM `Manufacturer`, `ManufacturerModelName`, `SoftwareVersions` retained (DICOM PS3.15 "Retain Device Identity") | same-system rules become UNKNOWN |
| 4 | **Radiopharmaceutical metadata** | Radiopharmaceutical Information Sequence: tracer, `RadionuclideTotalDose`, `RadionuclideHalfLife`, `RadiopharmaceuticalStartDateTime` (or StartTime) | SUV refused |
| 5 | **Quantitative / timing attributes** | `DecayCorrection`, `CorrectedImage`, `RescaleSlope/Intercept`, `DecayFactor`, `FrameReferenceTime`, series and acquisition date/time; injection and scan times on the same clock (dates may be shifted consistently per subject) | SUV refused or decay cross-check unavailable |
| 6 | **Reconstruction metadata** | whatever the export carries: `ReconstructionMethod`, `ConvolutionKernel`, iterations/subsets, TOF, PSF, voxel size | protocol identity UNKNOWN (see item 10) |
| 7 | **Weight; height and sex where required** | `PatientWeight` always; `PatientSize` and `PatientSex` (M/F) if PERCIST/SUL is in scope (PS3.15 "Retain Patient Characteristics") | SUVbw refused (weight) / SUL and PERCIST refused (height, sex) |

## Required if applicable

| # | Item | When |
|---|---|---|
| 8 | **CT acquired with each PET** (same `FrameOfReferenceUID`, volumetric) | if PERCIST is in scope (reference-region proposals) |

## Optional

| # | Item | Use |
|---|---|---|
| 9 | **Segmentation** (DICOM SEG referencing the PET series) | PERCIST lesion targets, after your physicist accepts them |
| 10 | **Reconstruction protocol / site documentation** (protocol sheet or console screenshot without patient data, or a signed reconstruction attestation) | resolves reconstruction identity where DICOM is silent (QIBA only, reported with a warning) |

## Please do NOT send

- patient names, MRNs, accession numbers, dates of birth, addresses, phone numbers;
- referring/performing physician or operator names, institution addresses;
- real identifiers as folder names (folder names appear in the reports; use pseudonyms);
- diagnoses, reports, outcomes or any clinical information;
- raw/list-mode data, non-attenuation-corrected series, MIPs, screen captures, NIfTI-only data;
- scans of patients not covered by your data-use agreement.

## Folder layout

Either is accepted; any structure below the visit folder is fine:

```
<site>/<subject>/<visit>/...         or         <subject>/<visit>/...
```

Extra files (PDFs, notes, other series) are listed and ignored. Nothing in your copy is modified.
