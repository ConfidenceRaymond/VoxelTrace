# Reconstruction-provenance audit: ACRIN-NSCLC-FDG-PET-168

RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. Read-only audit. No rule loosened.

## PRE-AUDIT FROZEN STATE (recorded 2026-10-08, before any analysis)

**Git:** HEAD `807ece9` (clean working tree).

**Human review file** (`../outputs/acrin_longitudinal_168/reference_review/reference_review.yaml`):
- sha256 `6433b89fcac701af19d4217ebed3a0e4c034a503355bbd527aeb8516ad64413f`
- baseline LIVER: ACCEPT by `CR` at 2026-10-08T22:28:15Z (proposal `12ae1be66b73…`)
- follow-up LIVER: ACCEPT by `CR` at 2026-10-08T22:28:29Z (proposal `9759262d136e…`)
- not simulated; no superseded entries

**Audit outputs** (sha256):

| File | sha256 |
|---|---|
| `review_status.json` | `45d6ea98fab7cde200bc1716bbc31f46653db7efc9e0da386a0c6dab30001c53` |
| `audit_percist-1.0/trial_audit.json` | `dece84dd08894b8d59fcf66ceee3a7b860dfc34f5bd4f3907cdac0be7ee79962` |
| `audit_qiba-fdg-1.14/trial_audit.json` | `fa0d4a014f734afbbb42398dc9cd330bbce4e617364a414bbd003f68163ca3e9` |
| `audit_eanm-fdg-2.0/trial_audit.json` | `0b20395c07440e4a2793e22cd55b0d56b923ca6c34ca8612fa4479a392f7f209` |
| `audit_percist-1.0/pair_checks.csv` | `5f35a4b19057e77e2da633884617d804c1f24728b11213290d52979490a79ef2` |
| `audit_qiba-fdg-1.14/pair_checks.csv` | `b2fd4051e17733260162f5de77f2b166b84132d56c4e2508f1245f8a4fb8de2d` |
| `audit_eanm-fdg-2.0/pair_checks.csv` | `aaa2979e37e043cf3facd2fbee00f916315faa2d32f5db9abc22b6c277810648` |

**Reviewed result:**
- reviews applied: 2;
- liver SULmean 1.3617251654973266 → 1.6430295931926293;
- |Δ| 0.28130442769530273 SUL, 17.121081011614045 % of the larger value;
- PERCIST-LIVER-SUL-STABILITY **PASS**.

**Verdicts:** PERCIST, QIBA and EANM are all **INSUFFICIENT_INFORMATION**.

**Blockers:**
- VT-PROTOCOL-IDENTITY UNKNOWN (AMBIGUOUS_RECONSTRUCTION);
- EANM-SAME-SYSTEM-SETTINGS UNKNOWN;
- EANM-EARL-RECON UNKNOWN (warning);
- PERCIST-BASELINE-MEASURABLE UNKNOWN (no lesion segmentation).

## 1. Standard-field inventory (all 195 slices × 2 timepoints)

Script: `scripts/inventory_recon_metadata.py ACRIN-NSCLC-FDG-PET-168` →
`../outputs/acrin_longitudinal_168/recon_inventory.json` (machine-readable; UIDs and identifying
attributes reduced to sha256 prefixes).

Recon-relevant standard attributes: **29 MISSING_BOTH, 23 IDENTICAL, 1 DIFFERENT, 0 AMBIGUOUS.**

**MISSING_BOTH (absent on every slice at both timepoints):**
- reconstruction parameters: ReconstructionMethod (0054,1103), NumberOfIterations (0018,9739),
  NumberOfSubsets (0018,9740), ConvolutionKernel (0018,1210), FilterType,
  ReconstructionAlgorithmSequence, ReconstructionType;
- description: ProtocolName, DerivationDescription, ImageComments;
- corrections: ScatterCorrectionMethod, RandomsCorrectionMethod, DecayFactor,
  DoseCalibrationFactor, ScatterFractionFactor, DeadTimeFactor, SliceSensitivityFactor;
- acquisition: AxialAcceptance, AxialMash, TransverseMash, EnergyWindowRangeSequence;
- other: SpacingBetweenSlices, RealWorldValueMappingSequence, among others (full list in the JSON).

**IDENTICAL (structured unless noted):**

| Group | Fields |
|---|---|
| Scanner | Manufacturer `GE MEDICAL SYSTEMS`, ManufacturerModelName `Discovery LS`, SoftwareVersions `16.01` |
| Geometry | Rows/Columns 128, PixelSpacing 3.90625, SliceThickness 4.25, ReconstructionDiameter 500, GantryDetectorTilt 0 |
| Image | ImageType `ORIGINAL\PRIMARY`, SeriesType `STATIC\IMAGE`, Units BQML |
| Corrections | CorrectedImage list, DecayCorrection START, AttenuationCorrectionMethod `measured,, 0.096000 cm-1,` (free text) |
| Acquisition | CollimatorType RING, CountsSource EMISSION, ActualFrameDuration 240000, FrameReferenceTime 0, AcquisitionTerminationCondition TIME, TypeOfDetectorMotion NONE |
| Description | SeriesDescription `PET Attenuation Correction Recon` (free text, LEVEL_D) |

**DIFFERENT:** StudyDescription, baseline `PET/RT planningWhole` vs follow-up
`F-18 FDG PETWhole Bod` (free text, LEVEL_D, not interpreted). It names the study context, not
reconstruction parameters, so it cannot establish or refute recon identity. It is recorded as a
site query item.

**Expected per-study differences** (not reconstruction): dates/times, UIDs, height 1.57/1.54 m,
weight 54/57 kg, dose, image positions, RescaleSlope, window, ClinicalTrialTimePointID.
SeriesNumber and ReferringPhysicianName are absent at follow-up.

**Sufficient for identity:** no. None of the fields that define the reconstruction
(method, iterations, subsets, filter, TOF, PSF) is present at either timepoint.

## 2. Private-tag inventory

| Tag | Creator | VR | Baseline | Follow-up | Class |
|---|---|---|---|---|---|
| (0009,xx38) | GEMS_PETD_01 | FL | 355.2 | — | PRIVATE_UNSUPPORTED (MISSING_FOLLOWUP) |
| (0009,xx39) | GEMS_PETD_01 | DT | present | — | PRIVATE_UNSUPPORTED (MISSING_FOLLOWUP) |
| (0009,xx3B) | GEMS_PETD_01 | DT | present | — | PRIVATE_UNSUPPORTED (MISSING_FOLLOWUP) |
| (0009,xx3C) | GEMS_PETD_01 | FL | 0.4 | — | PRIVATE_UNSUPPORTED (MISSING_FOLLOWUP) |
| (0009,xx3D) | GEMS_PETD_01 | DT | present | — | PRIVATE_UNSUPPORTED (MISSING_FOLLOWUP) |
| (0013,xx10) | CTP | LO | identical bytes | identical bytes | PRIVATE_UNSUPPORTED (IDENTICAL) |
| (0013,xx13) | CTP | LO | identical bytes | identical bytes | PRIVATE_UNSUPPORTED (IDENTICAL) |
| (0013,xx15) | CTP | LO | identical bytes | identical bytes | PRIVATE_UNSUPPORTED (IDENTICAL) |

- **Datetime values are not reproduced** here; the JSON keeps digests only.
- **CTP** is the TCIA de-identification pipeline's own block (collection/site provenance). It
  is not scanner data.
- **GEMS_PETD_01:** pydicom 3.0.2's private dictionary names these elements tracer_activity,
  meas_datetime, admin_datetime, post_inj_activity and post_inj_datetime.
  - pydicom is a secondary source: a community dictionary, not a GE document.
  - None of the five names relates to reconstruction, so all are PRIVATE_UNSUPPORTED for
    reconstruction purposes.
  - The block is absent at follow-up (stripped or never written). It was not decoded further.

## 3. Documentation sources

| Source | Result |
|---|---|
| GE PET DICOM conformance statements index (https://www.gehealthcare.com/en/products/interoperability/dicom-conformance-statements/pet) | The Discovery LS statements (Direction 5101600GD0 / 2343444GSP) are listed. **Retrieval failed:** the PDF link returned HTTP 502 on two attempts (saved error page `../tmp/docs_probe/ge_dls.bin`, HTML not PDF). No content was used. |
| DICOM PS3.3 C.8.9.4 (https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.9.4.html) | PET Image module: ReconstructionMethod (0054,1103) is optional free text; ConvolutionKernel is optional. |
| DICOM PS3.3 C.8.22.5.6 (https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.22.5.6.html) | Enhanced PET reconstruction: NumberOfIterations (0018,9739) and NumberOfSubsets (0018,9740) are standard, conditional on Iterative Reconstruction Method (0018,9769) = YES. Not present here (classic PET IOD). |
| TCIA private-attribute audit (https://pmc.ncbi.nlm.nih.gov/articles/PMC8285420/table/Tab3) | Lists only (0009,"GEMS_PETD_01",37) "Batch Description". Not reconstruction. |
| Z-Rad technical note (https://arxiv.org/html/2410.13348v2) | Vendor-specific SUV timing from conformance statements. No reconstruction private tags named. |

## 4. Open-source implementation audit

| Tool | Finding | Provenance |
|---|---|---|
| dcm2niix 1.0.20260416 | Emits BIDS `ReconMethodName`, iterations and subsets from **standard** attributes (and Siemens/Philips text). No GE PET reconstruction private tag is decoded. | release notes (https://newreleases.io/project/github/rordenlab/dcm2niix/release/v1.0.20260416) |
| PET2BIDS (pypet2bids) | Delegates DICOM parsing to dcm2niix; reconstruction fields are user-supplied when absent. | https://pypi.org/project/pypet2bids/, https://training.incf.org/lesson/pet2bids-conversion |
| Z-Rad | SUV conversion; no reconstruction-parameter extraction found. | https://arxiv.org/html/2410.13348v2 |
| STIR | GE support (e.g. SIGNA PET/MR) reads **raw data / RDF headers**, not image-DICOM reconstruction parameters. Nothing applies to these DICOM images. | https://discovery-pp.ucl.ac.uk/10087274/1/IEEE_Conference_Article-MIC_2018-Palak.pdf |
| SIRF | Built on STIR; no DICOM reconstruction-header parsing found. | https://github.com/CCPPETMR/SIRF/releases |
| pydicom 3.0.2 | Private dictionary names for GEMS_PETD_01 (above). None is a reconstruction parameter. Secondary source only. | installed package `_private_dict.py` |

**Conclusion:** no documented source maps any element present in these files to
reconstruction parameters. LEVEL_B evidence is therefore unavailable.

## 5. Baseline / follow-up metadata diff

Machine-readable: `recon_inventory.json` (`standard[*].class`, `private[*].class`).

| Parameter | Class |
|---|---|
| reconstruction method / iterations / subsets / filter / TOF / PSF | MISSING_BOTH |
| scanner, software, matrix, voxel, recon diameter, corrections, units, frame duration | IDENTICAL |
| SeriesDescription (free text) | IDENTICAL |
| StudyDescription (free text) | DIFFERENT |
| GEMS_PETD_01 private block | PRIVATE_UNSUPPORTED (MISSING_FOLLOWUP) |
| CTP private block | PRIVATE_UNSUPPORTED (IDENTICAL) |

## 6. Image-derived corroboration (LEVEL_E; cannot close VT-PROTOCOL-IDENTITY)

Script: `scripts/recon_corroboration.py` → `recon_corroboration.json`. Measured in the
human-accepted liver spheres (read-only). Tolerances are heuristics, not validated thresholds.

| Feature | Baseline | Follow-up | Rel. diff | Heuristic tol | Class |
|---|---|---|---|---|---|
| voxel grid | 128×128×195 @ 3.906/3.906/4.25 | same | — | exact | IDENTICAL |
| liver CoV | 0.136 | 0.170 | 20.3 % | 25 % | CONSISTENT |
| liver high-pass noise / mean | 0.103 | 0.128 | 19.7 % | 25 % | CONSISTENT |
| liver lag-1 autocorrelation (smoothing proxy) | 0.457 | 0.561 | 18.5 % | 10 % | INCONCLUSIVE |
| body gradient sharpness | 0.279 | 0.266 | 4.7 % | 15 % | CONSISTENT |

**Overall: INCONCLUSIVE.**
- The follow-up is noisier and more autocorrelated. That fits a different count level (dose
  355 vs 425 MBq, different patient weight and uptake), but it is not specific to the
  reconstruction.
- Even an all-CONSISTENT result would mean only "no obvious reconstruction inconsistency
  detected". It would never establish identity.

## 7. Classification

**ACRIN-NSCLC-FDG-PET-168 reconstruction identity: NOT_ESTABLISHED.**

| Item | Value |
|---|---|
| Highest trust level present | LEVEL_D (free-text descriptions); LEVEL_E corroboration; LEVEL_U private tags |
| LEVEL_A | absent (all six required parameters MISSING_BOTH) |
| LEVEL_B | none (no documented private tag) |
| LEVEL_C | none (no attestation supplied; none created) |
| Unresolved | reconstruction_method, iterations, subsets, post_filter, time_of_flight, psf_resolution_modelling |
| Not used as evidence | same scanner/software, same SeriesDescription, similar image noise |
| To close the gap | site scanner protocol export or signed physicist/site attestation for BOTH timepoints, or a re-export with standard reconstruction attributes, or a documented GE private tag |

**VT-PROTOCOL-IDENTITY: unchanged (UNKNOWN).**
**Verdicts: unchanged** (PERCIST, QIBA, EANM all INSUFFICIENT_INFORMATION).
**Part 11 re-run: not performed**, because no documented path was found. All frozen hashes were
re-checked after the audit and are identical.
