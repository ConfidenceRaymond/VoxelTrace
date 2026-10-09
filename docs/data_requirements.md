# Data requirements for a retrospective PET comparability audit

## Folder structure (read-only for VoxelTrace)

```
<trial>/
  trial.yaml                      # or pass --config outside the folder
  <subject_pseudonym>/
    <timepoint>/                  # e.g. baseline, followup (names listed in timepoint_order)
      <any DICOM files/folders>   # one attenuation-corrected PET series + the CT acquired with it
```

**Minimal `trial.yaml`:**

```yaml
trial_id: SPONSOR-TRIAL-01
ruleset: qiba-fdg-1.14          # a default; voxeltrace audit runs QIBA, EANM and PERCIST
timepoint_order: [baseline, followup]
sites: {SUBJ-001: SITE-A, SUBJ-002: SITE-B}   # needed for drift/site summaries
reference_proposals: auto
# optional, explicit only:
# reference_review_file: reference_review.yaml
# recon_attestation_file: attestations.yaml
```

## Per-scan DICOM content

| Needed for | Attributes | If absent |
|---|---|---|
| Strict SUVbw (all rule sets) | Units = BQML; DecayCorrection = START; CorrectedImage incl. ATTN and DECY; PatientWeight; RadionuclideTotalDose; RadionuclideHalfLife; RadiopharmaceuticalStartDateTime (or StartTime); SeriesDate/Time; AcquisitionDate/Time; rescale attributes | DO_NOT_QUANTIFY, SUV refused |
| Decay cross-check | DecayFactor and FrameReferenceTime on every slice | DECAY_FACTOR_UNVERIFIED (passes with warning) |
| SUL / PERCIST | PatientSize (height) and PatientSex = M or F | SUL refused; PERCIST INSUFFICIENT |
| Tracer identity | RadiopharmaceuticalCodeSequence or Radiopharmaceutical | VT-TRACER-SAME UNKNOWN |
| Reconstruction identity | ReconstructionMethod, iterations/subsets (standard or in the method text), ConvolutionKernel, TOF/PSF; or a QIBA-only site attestation | VT-PROTOCOL-IDENTITY UNKNOWN |
| Reference regions (PERCIST) | a volumetric CT in the **same FrameOfReferenceUID** as the PET | AUTO_NOT_FOUND |
| PERCIST baseline measurability | a baseline lesion target reviewed by a human (lesion review gate pending) | PERCIST-BASELINE-MEASURABLE UNKNOWN |
| Drift | Manufacturer, ManufacturerModelName, SoftwareVersions, acquisition date | UNKNOWN_PROTOCOL_DRIFT |

## De-identification expectations (DICOM PS3.15)

- **Retain Patient Characteristics (E.3.7):** weight, height, sex.
- **Retain Device Identity (E.3.8):** scanner, model, software.
- **Retain Longitudinal Temporal Information (E.3.6, full or consistently modified dates):**
  injection and scan times on the same clock.
- **Private tags (E.3.10 Retain Safe Private):** only documented vendor timing tags are used.
  Stripping them is acceptable but removes optional cross-checks.
- **Subject folder names must be pseudonyms.** They appear in reports.

## Not accepted as quantitative input

- Secondary captures and screen shots; MIP or movie series.
- Non-BQML units (e.g. Philips CNTS, GE GML) on the strict path.
- NIfTI-only data (no DICOM headers).
