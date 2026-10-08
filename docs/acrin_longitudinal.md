# First real longitudinal validation: ACRIN-NSCLC-FDG-PET-094 and -153 (2026-10-08)

REAL public data (ACRIN 6668, via IDC; CC BY 3.0). RESEARCH PROTOTYPE - NOT FOR CLINICAL
DIAGNOSIS. No response assessment.

**Scripts:**
- `scripts/fetch_acrin_series.py` (bounded download);
- `scripts/analyze_acrin_longitudinal.py`.

**Provenance:**
- `configs/acrin_longitudinal/allowlist.json` (approved series);
- `configs/acrin_longitudinal/provenance_manifest.json` (series-level);
- per-file sha256 and S3 ETag in `../data/acrin_longitudinal/provenance_manifest.json`.

**Outputs:** `../outputs/acrin_longitudinal/`. DICOM and QC images are not in git.

## Download (bounded, user-approved)

- **Size correction:** the census estimate of about 45 MB was wrong. It priced each CT as the
  scout/topogram. The real AC CTs are 108–157 MB per timepoint.
- **153 CTs:** the CTs of 153 are **not** in the PET frame of reference at either timepoint.
- **Approved option:** PET ×4 + 094 CT ×2, exactly six series, **1,447 files, 272,271,326
  bytes**.
- **Guards:** each series is fetched only from its own object prefix. Before any download the
  file count and total size must match the allow-list. Every file's PatientID, study, series
  and modality were verified.

| Subject | Timepoint | Series | Files | Bytes | Scanner | Software |
|---|---|---|---|---|---|---|
| 094 | baseline | PET AC | 205 | 8,048,482 | GE Discovery LS | 16.01 |
| 094 | baseline | CT IMAGES | 205 | 108,357,300 | GE Discovery LS | LightSpeedApps…1.7 |
| 094 | follow-up | PET AC | 239 | 9,384,450 | GE Discovery LS | 16.01 |
| 094 | follow-up | CT IMAGES | 239 | 126,331,122 | GE Discovery LS | LightSpeedApps…1.7 |
| 153 | baseline | PET WB | 262 | 9,444,522 | CPS 1023 | (none) |
| 153 | follow-up | PET WB | 297 | 10,705,450 | CPS 1023 | (none) |

## Ingestion

All four timepoints passed ingestion:

- PET and CT volumes load;
- slice order is unambiguous and spacing uniform;
- 094 PET and CT share the frame of reference at both timepoints;
- 153 has no CT (excluded by design).

## Strict SUVbw: REFUSED on all four (validator unchanged)

| Scan | Units | Decay corr. | Weight kg | Dose MBq | T½ s | Uptake min | Refusal |
|---|---|---|---|---|---|---|---|
| 094 baseline | BQML | START | 56 | 521.3 | 6588 | 211.7 | `DECAY_FACTOR_INCONSISTENT` (1.56e-2) |
| 094 follow-up | BQML | START | 59 | 597.6 | 6588 | 87.6 | `DECAY_FACTOR_INCONSISTENT` (1.56e-2) |
| 153 baseline | BQML | START | 71.7 | 650.1 | 6586.2 | 55.6 | `DECAY_FACTOR_INCONSISTENT` (1.18e-1) |
| 153 follow-up | BQML | START | 64.0 | 639.4 | 6586.2 | 89.6 | `DECAY_FACTOR_INCONSISTENT` (1.37e-1) |

Read-only diagnosis:

- **094 (GE):**
  - SeriesTime = AcquisitionTime = the GE private scan datetime (0009,100D).
  - DecayFactor is 1.56 % above 2^(FrameReferenceTime/T½), consistently at both timepoints.
- **153 (CPS, multi-bed):**
  - FrameReferenceTime is 0 on every slice, but DecayFactor is ≠ 1 and varies by bed
    (1.134 at baseline, 1.0095 at follow-up). The header is internally inconsistent.
- **Not decidable:** whether the vendor used another decay reference or half-life cannot be
  established from the data, so refusal is the correct strict result.
- **094 uptake:** the baseline uptake of 211.7 min is reported as recorded (three timing
  sources agree) and is not interpreted.

## SUL

- **Not attempted:** SUL requires strict SUV, which was refused.
- **Anthropometrics:**
  - **094:** height 1.6 m, weight and sex present at both timepoints. SUL would be eligible on
    anthropometrics alone.
  - **153:** **PatientSize is absent** at both timepoints, so SUL would be refused
    (`MISSING_PATIENTSIZE`). Height was not filled or inferred.

## Protocol fingerprints and baseline → follow-up differences

- **094 (GE Discovery LS):**
  - **Same:** scanner, model, software 16.01, FDG/18F, matrix 128², voxel 3.906×3.906×4.25 mm,
    "OSEM" (family OSEM), corrections, START, BQML.
  - **UNKNOWN at both timepoints:** iterations, subsets, TOF, PSF, kernel, filter.
  - **Different:** uptake (211.7 → 87.6 min), dose (521 → 598 MBq).
- **153 (CPS 1023):**
  - **Same:** scanner, model, matrix 128², voxel 5.307×5.307×3.4 mm, "OSEM 2i8s"
    (iterations 2, subsets 8), corrections, START, BQML.
  - **UNKNOWN at both timepoints:** software, tracer and radionuclide codes, TOF, PSF, kernel,
    filter.
  - **Different:** uptake (55.6 → 89.6 min), dose (650 → 639 MBq).
- **Harmonization/EARL:** UNKNOWN for both (not in DICOM, not configured).
- **Engineering protocol comparability:** NOT_COMPARABLE for both, on uptake interval. This is
  independent of any reference review.

## Pair rules before any reference review

All three rule sets give **INSUFFICIENT_INFORMATION** for both pairs.

**No rule is blocked only by reference review.** Every liver-dependent rule is blocked first
by SUV refusal.

| Subject | Rule set | Unresolved, blocked by SUV refusal | Unresolved on its own evidence | PASS |
|---|---|---|---|---|
| 094 | PERCIST | VT-SUV-BOTH, uptake window/diff, liver stability, baseline measurable | VT-PROTOCOL-IDENTITY (AMBIGUOUS_RECONSTRUCTION) | tracer, dose diff, same scanner/software |
| 094 | QIBA/EANM | VT-SUV-BOTH, uptake window/diff | protocol identity / same settings (AMBIGUOUS_RECONSTRUCTION); EARL NEVER_ENCODED | tracer, same system (QIBA) |
| 153 | PERCIST | as for 094 | protocol identity; tracer (MISSING_REQUIRED_TAG); same scanner/software (software missing) | dose diff |
| 153 | QIBA/EANM | VT-SUV-BOTH, uptake | protocol identity, tracer, same system, EARL | none |

The uptake rules read uptake from the validated SUV path, so they are formally UNKNOWN. The
recorded uptake differences of 124 min (094) and 34 min (153) exceed every standard's limit,
and the engineering comparability layer already reports NOT_COMPARABLE.

## Reference regions (real; distinct namespace `outputs/acrin_longitudinal/reference_review/`)

| Scan | Liver | Blood pool |
|---|---|---|
| 094 baseline and follow-up | PROPOSED (2 new proposals; CT-only QC) | NOT_FOUND: no consistent 2 cm descending-aorta segment on this older, likely non-contrast CT |
| 153 | `REFERENCE_AUTO_NOT_FOUND` | `REFERENCE_AUTO_NOT_FOUND` |

- **153:** no CT shares the PET FrameOfReferenceUID. A CT from another frame is not
  substituted or resampled.
- **094 proposals:** no decision was created. The 2 proposals cannot be measured while strict
  SUV is refused, and the review page (which requires quantitative PET) does not list them.
  Reviewing them now cannot unblock any rule.

## Anonymization and private tags

- **De-identification:** declared (PS3.15 Annex E) for both subjects.
- **094 (GE):** `GEMS_PETD_01` scan datetime (0009,100D) present and equal to SeriesTime. No
  standard/private timing disagreement, unlike the Siemens FDG-PET-CT-Lesions date shift.
- **153 (CPS):**
  - the Siemens private decay-correction datetime (0071,xx22) is absent → `UNKNOWN_OR_STRIPPED`;
  - causality is not established;
  - tracer code and software version are absent.
- **Re-saved series:** none in the downloaded series (MIMvista series were not selected).

## Census validation (predicted vs actual, 4 timepoints)

- **Correct (4/4):** scanner, model, height availability, reconstruction description.
- **Wrong (4/4):** strict-SUV eligibility. The census predicted LIKELY_ANALYZABLE or
  WITH_WARNINGS; actual is REFUSED (`DECAY_FACTOR_INCONSISTENT`).
  - A one-header census cannot see slice-level DecayFactor/FrameReferenceTime consistency.
- **Not predicted:**
  - the CT frame-of-reference mismatch for 153;
  - the missing tracer code for 153.
- **Lesson:** the census II-risk labels are optimistic for strict SUV.
