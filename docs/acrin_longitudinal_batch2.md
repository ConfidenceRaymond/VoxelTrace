# Real longitudinal validation, batch 2: ACRIN-NSCLC-FDG-PET-167 and -050 (2026-10-08)

REAL public data (ACRIN 6668 via IDC; CC BY 3.0). RESEARCH PROTOTYPE - NOT FOR CLINICAL
DIAGNOSIS. No response assessment. The validator, SUV formula, rules and thresholds are
unchanged.

- **Allow-list:** `configs/acrin_longitudinal/allowlist_batch2.json`.
- **Manifest:** `configs/acrin_longitudinal/provenance_manifest_batch2.json` (series level);
  per-file sha256 and S3 ETag are in `../data/acrin_longitudinal/provenance_manifest_batch2.json`.
- **Outputs:** `../outputs/acrin_longitudinal_batch2/`.
- **Command:** `scripts/analyze_acrin_longitudinal.py --subjects … --out-name
  acrin_longitudinal_batch2`.

## Download

Eight user-approved series: PET plus the AC CT that shares its FrameOfReferenceUID, at both
timepoints. **2,017 files, 523,329,660 bytes.** The fetcher now refuses to overwrite an existing
manifest or subject directory; 094 and 153 are untouched.

| Subject | Timepoint | PET | CT |
|---|---|---|---|
| 167 | baseline | 163 files, GE Discovery LS, software 16.01 | 163 files, Discovery LS CT |
| 167 | follow-up | 195 files | 195 files |
| 050 | baseline | 390 files, CPS 1080, software PS4.0.3 | 390 files, SIEMENS Emotion 6, VB10B |
| 050 | follow-up | 390 files | **131 files** |

All four timepoints passed ingestion: volumes load, slice order is unambiguous, spacing is
uniform, and PET and CT share the frame of reference.

## Strict SUVbw: **PASS on all four**, the first real SUV values

| Scan | SUV | Decay-factor cross-check | Warnings | Weight kg | Dose MBq | T½ s | Uptake min | SUV range |
|---|---|---|---|---|---|---|---|---|
| 167 baseline | PASS | **NOT_AVAILABLE** (DecayFactor absent on 163/163 slices) | STORED_DECAY_FACTOR_NOT_AVAILABLE, NEGATIVE_SUV, INJECTION_DATE_FROM_SERIES | 62 | 469.0 | 6588 | 56.5 | −0.08 … 12.17 |
| 167 follow-up | PASS | **NOT_AVAILABLE** (0/195) | same | 65 | 436.0 | 6588 | 84.2 | −0.45 … 17.22 |
| 050 baseline | PASS | **VERIFIED** (390/390 slices) | INJECTION_DATE_FROM_SERIES | 77.6 | 451.4 | 6586.2 | 120.4 | 0 … 66.74 |
| 050 follow-up | PASS | **VERIFIED** | INJECTION_DATE_FROM_SERIES | 81.7 | 495.8 | 6586.2 | 66.8 | 0 … 30.13 |

- **Common inputs:** all four use BQML, START, and ATTN/SCAT/DECY in CorrectedImage. The scan
  reference is SeriesDate/Time, concordant within 1 s with the earliest acquisition time.
- **PASS vs VERIFIED:** PASS is never reported as VERIFIED. For 167 SUV is calculable, but the
  vendor's stored decay scaling cannot be cross-checked.
- **NEGATIVE_SUV (167):** small negative voxel values are present in the stored images. This is
  reported, not interpreted.

## SUL

| Subject | Result |
|---|---|
| 167 | **PASS** with DICOM anthropometrics: male, 1.51/1.52 m, 62/65 kg. LBM (James) 46.6 / 48.1 kg; LBM (Janmahasatian) 45.8 / 47.2 kg |
| 050 | **REFUSED, `MISSING_PATIENTSIZE`**, both formulas, both timepoints. Height was not inferred |

## Protocol fingerprints and differences

**167 (GE Discovery LS 16.01, both timepoints):**
- **PRESENT and SAME:** FDG/¹⁸F, matrix 128², voxel 3.906 × 3.906 × 4.25 mm, START, BQML,
  corrections (DECY, ATTN, SCAT, DTIM, RAN, …), measured attenuation correction.
- **MISSING at both timepoints:** ReconstructionMethod (absent entirely, unlike 094's "OSEM"),
  algorithm family, iterations, subsets, TOF, PSF, kernel, filter, scatter method.
- **DIFFERENT:** uptake 56.5 → 84.2 min; dose 469 → 436 MBq.

**050 (CPS 1080, software PS4.0.3, both timepoints):**
- **PRESENT and SAME:** "OSEM2D 2i8s" (iterations 2, subsets 8), kernel "X-Y-Z Gaussian F",
  matrix 168², voxel 4.064 × 4.064 × 2.5 mm, ¹⁸F, START, BQML, corrections, CT-derived μ-map,
  model-based scatter.
- **MISSING:** tracer code (radiopharmaceutical not identified as FDG), TOF, PSF, filter type.
- **DIFFERENT:** uptake 120.4 → 66.8 min; dose 451 → 496 MBq.

**Harmonization/EARL:** UNKNOWN for both (not in DICOM, not configured).

## Pair verdicts (all decided; no rule weakened)

| Subject | QIBA | EANM | PERCIST |
|---|---|---|---|
| 167 | **NOT_ASSESSABLE** | **NOT_ASSESSABLE** | **NOT_ASSESSABLE** |
| 050 | **NOT_ASSESSABLE** | **NOT_ASSESSABLE** | **NOT_ASSESSABLE** |

**167:**
- **QIBA:** QIBA-UPTAKE-WINDOW FAIL (84.2 > 75) and QIBA-UPTAKE-DIFF FAIL (27.7 > 10 min).
  VT-PROTOCOL-IDENTITY UNKNOWN (AMBIGUOUS_RECONSTRUCTION). Tracer and SUV both PASS.
- **EANM:** the same uptake failures, plus SAME-SYSTEM-SETTINGS UNKNOWN; EARL UNKNOWN (warning).
- **PERCIST:** UPTAKE-DIFF FAIL (27.7 > 15 min); window warning.
  - Liver stability: UNKNOWN (review required).
  - Baseline measurable: UNKNOWN (no lesion segmentation downloaded, plus review required).

**050:**
- **QIBA and EANM:** uptake window FAIL (120.4 min) and uptake diff FAIL (53.7 min).
  VT-TRACER-SAME UNKNOWN (tracer code missing). VT-PROTOCOL-IDENTITY **PASS**.
- **PERCIST:** UPTAKE-DIFF FAIL; liver rules UNKNOWN.

The uptake failures already decide every rule set. **Reference review cannot change any of these
verdicts.** It would only make the PERCIST liver rules informative.

## Reference regions (new real namespace `outputs/acrin_longitudinal_batch2/reference_review/`)

| Scan | Liver | Blood pool |
|---|---|---|
| 167 baseline | PROPOSED (SUVmean preview 1.57, SUL 1.18) | PROPOSED (SUV 1.14, SUL 0.86) |
| 167 follow-up | PROPOSED (SUV 1.79, SUL 1.32) | NOT_FOUND (no consistent aorta segment) |
| 050 baseline | PROPOSED (SUV 1.46; SUL refused) | NOT_FOUND |
| 050 follow-up | NOT_FOUND: lungs not found on CT | NOT_FOUND |

- **New proposals:** **4** await human review on the Reference Review page:
  - trial dir `outputs/acrin_longitudinal_batch2/trial`;
  - audit dir `outputs/acrin_longitudinal_batch2/audit_percist-1.0`.
- **No decision was made.** Preview values are not used by any rule.
- **050 follow-up CT:** the only CT in the PET frame of reference covers z −611.5 … −286.5 mm.
  That is 325 mm of the PET's −611.5 … 361.0 mm range, the inferior third, with no lungs, so
  no proposal is possible.

## Census v2 external validation (first out-of-sample test)

The census v2 prediction matched the full-series result on every field for all four timepoints:

- SUV;
- decay cross-check (NOT_AVAILABLE ×2, VERIFIED ×2);
- SUL (167 pass, 050 refuse);
- CT frame of reference;
- tracer;
- reconstruction description and iterations;
- QIBA verdict (NOT_ASSESSABLE ×2).

Details: `census_v2_crosscheck.csv`.

**Pair category:** 167 was HIGH_CONFIDENCE_ANALYZABLE and 050 ANALYZABLE_WITH_WARNINGS. Both
were decided, as predicted.

## Question 10: can SUV be computed defensibly for 167 without a stored DecayFactor?

**DICOM (PS3.3 C.8.9.4):**
- **Decay Factor (0054,1321):** "The decay factor that was used to scale this image", Type 1C,
  **required if Decay Correction (0054,1102) is other than NONE**.
- **Frame Reference Time:** the time the pixel values occurred, as an offset from Series
  Date/Time.

167 declares DecayCorrection = START but omits DecayFactor on every slice, so **it does not
conform to that 1C condition**.

**What the strict path uses:**
- SUVbw = activity (BQML) × weight / (dose × 2^(−Δt/T½)), with Δt = series reference −
  injection. This uses Units, DecayCorrection, CorrectedImage, dose, injection time, half-life,
  weight and Series/Acquisition time. All are present and consistent for 167.
- DecayFactor is **not** an input. It is the vendor's record of the scaling applied, and
  VoxelTrace uses it only as an **independent cross-check** that the images really are
  decay-corrected to the series reference.

**Answer:**
- **Calculable:** SUV is calculable from complete, standard, internally consistent inputs. This
  is the existing PASS, with the existing `DECAY_FACTOR_UNVERIFIED` warning.
- **Not verifiable:** the assumption that pixel values are decay-corrected to SeriesTime rests
  only on DecayCorrection = START. It cannot be independently confirmed, and the 1C attribute
  is absent.
- **Reporting:** `SUV_STATUS = PASS`, `DECAY_FACTOR_CROSSCHECK = NOT_AVAILABLE`,
  `QUANTITATIVE_WARNING = STORED_DECAY_FACTOR_NOT_AVAILABLE`. Reduced confidence and the DICOM
  1C gap are noted.
- **Context, not evidence:** the same model and software (094) stored DecayFactor values
  consistent with correction to the series start. That export's FrameReferenceTime semantics,
  however, are unverified, so 094 is **not** used to validate 167.
- **No implementation change.** The documentation supports neither refusing (the formula does
  not need DecayFactor) nor upgrading to VERIFIED. A future strict-trial option "require stored
  DecayFactor" could be added as a versioned, configurable policy if a trial asks for it.

## Question 11: answers for 050

1. **Does strict SUV genuinely pass?** Yes, on all 390 slices at both timepoints, and the
   DecayFactor cross-check is **VERIFIED**: DecayFactor = 2^(FRT/T½) within 1e-3 on every slice.
   This is the first VERIFIED real pair. Uptake was 120.4 and 66.8 min.
2. **Does missing height block SUL?** Yes: `MISSING_PATIENTSIZE` for both formulas at both
   timepoints. Nothing was inferred.
3. **Does the missing tracer code matter?** The radionuclide is ¹⁸F, but the radiopharmaceutical
   (FDG) is not identified, so VT-TRACER-SAME is UNKNOWN (blocking) in every rule set. QIBA,
   EANM and PERCIST are FDG-specific, so their applicability cannot be confirmed from the data.
   Here the uptake failures already make the pair NOT_ASSESSABLE. Otherwise it would be
   INSUFFICIENT_INFORMATION, not assessable.
4. **Is the reconstruction metadata sufficient for protocol identity?** Yes for VoxelTrace's
   identity rule: "OSEM2D 2i8s" plus the kernel → VT-PROTOCOL-IDENTITY PASS. TOF/PSF/filter
   remain MISSING but did not block. This contrasts with 167 (no ReconstructionMethod →
   UNKNOWN).

## New vendor-specific findings

- **GE Discovery LS 16.01 exports differ by study:** 094 had DecayFactor (inconsistent with
  FRT); 167 has none. Same model and software.
- **CPS 1080 / PS4.0.3 (050):** DecayFactor and FrameReferenceTime are consistent, unlike CPS
  1023 (153).
- **050 follow-up:** the AC CT in the PET frame covers only the inferior third of the PET range.
