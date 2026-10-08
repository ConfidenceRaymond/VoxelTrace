# Cross-collection public PET census v3 (metadata only, 2026-10-08)

RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. **No image volume was downloaded.** Rules,
thresholds, the SUV validator and every verdict are unchanged.

| Item | Location |
|---|---|
| Scripts | `scripts/census_v3_index.py` (census venv), `scripts/census_v3_public_pet.py sample / analyse` |
| Data | `../data/census/public_pet_v3/` |
| Data files | `series_index.csv`, `collections.csv`, `pet_series_v3.jsonl`, `ct_series_v3.jsonl`, `candidates_v3.csv`, `census_v3_summary.json` |
| Tests | `tests/test_census_v3.py` |

## Method

**Universe:** IDC v25. 43 collections contain PET (`collections.csv`). Excluded:
- ACRIN-NSCLC-FDG-PET (already censused, [census_v2.md](census_v2.md));
- a mouse collection.

**Selected for header sampling** (every PT series of patients with PET on at least two dates,
plus the two phantom collections for reconstruction metadata):

| Measure | Count |
|---|---|
| PT series selected | 2,167 |
| Skipped by description (MIP/movie/NAC/fused …) or < 20 instances | 132 |
| Header-sampled | 2,035 |
| CT series in those studies, one header each | 1,648 |

**Sampling** (same machinery as census v2):
- object listing, then evenly spaced slice headers read by HTTP byte range;
- 12 headers per series, or 4 for the FLT/NaF/PSMA collections (budget only);
- **631 + 20 MB transferred** (cap 2.5 GB);
- 2,026 / 2,035 series parsed. The 9 failures are tcga_ucec headers that pydicom cannot
  parse (`BytesLengthException`).
- A first pass failed on 68 cc_tumor_heterogeneity series because a zero-byte "folder" object
  in the bucket prefix was sampled. That object is now skipped and the series were re-sampled.

**Rules:** the unchanged strict SUV validator and protocol extractors run on the samples. For
every ordered pair of a subject's series with different study dates, the unchanged
`assess_pair` runs for QIBA 1.14, EANM 2.0 and PERCIST 1.0. The best pair per subject is kept.

**Tracer handling:**
- The tracer comes **from DICOM only**: FDG / PSMA / AMYLOID / TAU / OTHER (e.g. FLT, NaF) /
  UNKNOWN.
- FDG rule sets are applied only to FDG/FDG pairs.
- Known non-FDG pairs are marked **REQUIRES_TRACER_SPECIFIC_RULESET**; no rule was applied.
- A missing tracer, height or reconstruction field is never treated as a pass.

**Sampling limitation: voxel size.**
- Sampled headers carry no full slice geometry, so `voxel_size` is always UNKNOWN in the census.
  The raw census verdict therefore stays INSUFFICIENT_INFORMATION.
- The census also reports `*_if_voxel_confirmed` verdicts, computed **only** when PixelSpacing
  and SliceThickness are known and identical at both timepoints. That header proxy says
  nothing about whether the voxel sizes will match; a download must confirm it.

**CT matching mirrors the pipeline** (`trial/timepoint.py`): any CT-modality series in the PET
frame of reference counts, whatever its ImageType. Census v2 excluded DERIVED CTs, which was
stricter than the pipeline. That mattered here: the autoPET CTs are `DERIVED\SECONDARY` but
share the PET frame of reference.

**Classes** (precedence order):

| Class | Meaning |
|---|---|
| FULLY_DECIDABLE_LIKELY | FDG/FDG; strict SUV PASS at both timepoints with a sampled DecayFactor ↔ FrameReferenceTime check; QIBA and EANM have no blocking UNKNOWN, except the voxel-size sampling artefact with a matching header proxy. This includes pairs that will be **decided NOT_ASSESSABLE** (e.g. uptake window); `predicted_assessable` separates them. |
| DECIDABLE_WITH_WARNING | as above, but SUV passes only with DECAY_FACTOR_UNVERIFIED |
| PERCIST_POSSIBLE | FDG; SUV, height and CT in the PET frame at both timepoints; no PERCIST blocking FAIL; a non-AI or human-corrected lesion SEG at baseline |
| LIKELY_INSUFFICIENT | otherwise |
| UNKNOWN | no evaluable pair (phantoms; sampling failure) |
| REQUIRES_TRACER_SPECIFIC_RULESET | known non-FDG tracer at both timepoints |

**PERCIST readiness** uses the earlier classes. An autoPET "Segmentation" counts as a
**collection annotation**: per the dataset record, it was manually segmented by a single reader.
It still needs VoxelTrace human review before use. Unreviewed AI (BAMF AIMI) SEGs never count.

## Access status of the requested collections

| Collection | Status |
|---|---|
| RIDER Lung PET-CT | IDC, open. 22 longitudinal patients; **0 / 139 series pass strict SUV** (GE Advance: Units GML / DECAY_FACTOR_INCONSISTENT) |
| Head-Neck-PET-CT | **Not anonymously accessible** (TCIA API returns nothing; absent from IDC v25) |
| ACRIN-HNSCC-FDG-PET-CT | **GATED**: only RTSTRUCT anonymously listed |
| QIN PET Phantom / RIDER Phantom | IDC, open; phantoms, no pairs (UNKNOWN by design) |
| HECKTOR (2025) | **GATED** (registration/approval), **NIfTI only**: no DICOM headers, not usable by the strict path |
| PSMA-PET-CT-Lesions (autoPET) | IDC, open; 164 longitudinal patients; PSMA → REQUIRES_TRACER_SPECIFIC_RULESET (79), or tracer missing at a timepoint (85) |
| FDG-PET-CT-Lesions (autoPET) | IDC, open; 81 longitudinal patients; **all 81 FULLY_DECIDABLE_LIKELY** |
| autoPET IV / V | challenge copies are NIfTI; the DICOM originals are the two IDC collections above |
| Other longitudinal FDG (IDC) | qin_breast, anti_pd_1_lung, cc_tumor_heterogeneity, varepop_apollo, cmb_*, tcga_*, breast_diagnosis (results below) |
| Brain PET | none in IDC PET. OpenNeuro has 37 BIDS PET datasets (metadata only; [brain_pet_roadmap.md](brain_pet_roadmap.md)) |

**United Imaging:**
- IDC v25 contains one UIH series (cmb_pca, uMI 550, "MIP MOVIE: PET AC PYLARIFY"): derived,
  PSMA, not quantitative.
- **uEXPLORER, uMI and uPMR: NO_OPEN_DICOM_IDENTIFIED.** uEXPLORER is available only GATED via
  UDPET (DTA; simulated low-dose).

**Scanner architecture:** every sampled series is **CONVENTIONAL_AFOV**. No LONG_AFOV,
TOTAL_BODY or PET_MR series is open in IDC PET.

## Results

**454 subjects. Class counts:**

| Class | Subjects | Notes |
|---|---|---|
| FULLY_DECIDABLE_LIKELY | **99** | 86 predicted assessable under QIBA and EANM; 13 predicted decided NOT_ASSESSABLE |
| DECIDABLE_WITH_WARNING | 0 | |
| PERCIST_POSSIBLE | 0 as a primary class | the autoPET subjects carry PERCIST readiness inside FULLY_DECIDABLE_LIKELY |
| LIKELY_INSUFFICIENT | 229 | |
| REQUIRES_TRACER_SPECIFIC_RULESET | 104 | |
| UNKNOWN | 22 | |

**PERCIST readiness (best pair per subject):**

| Readiness | Subjects |
|---|---|
| PERCIST_READY (pending human review of liver and lesion) | **77** (all autoPET FDG) |
| PERCIST_LIVER_READY_BUT_LESION_MISSING | 7 |
| PERCIST_BLOCKED_BY_SUL | 60 |
| PERCIST_BLOCKED_BY_REFERENCE | 0 after the CT-matching fix |
| PERCIST_BLOCKED_BY_RECON | 3 |
| UNKNOWN (SUV refused) | 181 |

**QIBA attestation path:** no SUV-passing FDG pair is blocked *only* by reconstruction
parameters. The new LEVEL_C path would not unlock any candidate here. It matters for GE-style
data (iterations/subsets never encoded) once SUV passes.

**Vendor finding:** every FULLY_DECIDABLE_LIKELY subject is **Siemens**.
- **GE** (148 same-vendor pairs): no decidable pair. Strict SUV refusals dominate
  (DECAY_FACTOR_INCONSISTENT, non-BQML units), and iterations/subsets are never encoded.
- **Philips** (16 same-vendor pairs): no decidable pair (non-BQML / missing corrections).
- **United Imaging:** none.
- The 184 series with an **empty Manufacturer** (models 1080/1094/1093) are reported as
  UNKNOWN_MANUFACTURER. The vendor is not inferred from the model number.

**Timing note (verify on download):** 54 / 195 autoPET FDG series have an uptake of exactly
60.0 min (± 0.05). This is plausible for minute-precision clinical timing, but it is not
verified.

`*` QIBA/EANM columns below are the `*_if_voxel_confirmed` predictions. The raw sampled verdict
is INSUFFICIENT_INFORMATION until voxel size is confirmed on download. EANM is
ASSESSABLE_WITH_WARNINGS because EANM-EARL-RECON (warning) is never encoded.

### Top 10 overall

| # | Collection | Subject | Scanner (B / F) | Software | Uptake min | Δ days | Height | SUV | Recon (method; TOF; PSF) | CT in PET frame | Lesion SEG (baseline) | QIBA* | EANM* | PERCIST readiness | Main blockers | MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | varepop_apollo | AP-ANXW | SIEMENS Biograph64_mCT / SIEMENS Biograph64_mCT | VG51C / VG51C | 57.3 / 56.7 | 277.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | none | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | PERCIST_LIVER_READY_BUT_LESION_MISSING | voxel size: confirm on download | 409.8 |
| 2 | varepop_apollo | AP-GEH6 | SIEMENS Biograph64_mCT / SIEMENS Biograph64_mCT | VG51C / VG62B | 62.3 / 58.8 | 399.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | none | ASSESSABLE_WITH_WARNINGS | ASSESSABLE_WITH_WARNINGS | PERCIST_LIVER_READY_BUT_LESION_MISSING | voxel size: confirm on download | 413.8 |
| 3 | fdg_pet_ct_lesions | PETCT_c2ffda4725 | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG60A / VG60A | 60.0 / 60.1 | 161.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 463.6 |
| 4 | fdg_pet_ct_lesions | PETCT_e9feb1135e | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG70A / VG70A | 60.1 / 60.0 | 70.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 519.4 |
| 5 | fdg_pet_ct_lesions | PETCT_97320b0b58 | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG60A / VG70A | 60.0 / 58.0 | 102.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE_WITH_WARNINGS | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 528.5 |
| 6 | fdg_pet_ct_lesions | PETCT_5e339b2ecf | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG60A / VG70A | 60.4 / 62.2 | 953.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE_WITH_WARNINGS | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 534.7 |
| 7 | fdg_pet_ct_lesions | PETCT_b4247b8ecd | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG70C / VG70C | 60.0 / 60.0 | 219.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 541.4 |
| 8 | fdg_pet_ct_lesions | PETCT_5fa9d9a820 | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG60A / VG60A | 60.0 / 60.6 | 190.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 543.6 |
| 9 | fdg_pet_ct_lesions | PETCT_0410759456 | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG60A / VG60A | 60.0 / 66.6 | 288.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 543.7 |
| 10 | fdg_pet_ct_lesions | PETCT_2f9aec0275 | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG60A / VG60A | 60.0 / 63.0 | 139.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 543.7 |

### Top 5 GE (same-vendor pairs: 148; classes {'LIKELY_INSUFFICIENT': 130, 'REQUIRES_TRACER_SPECIFIC_RULESET': 18})

| # | Collection | Subject | Scanner (B / F) | Software | Uptake min | Δ days | Height | SUV | Recon (method; TOF; PSF) | CT in PET frame | Lesion SEG (baseline) | QIBA* | EANM* | PERCIST readiness | Main blockers | MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 148 | acrin_flt_breast | ACRIN-FLT-Breast_022 | GE MEDICAL SYSTEMS Discovery LS / GE MEDICAL SYSTEMS Discovery LS | None / None | 76.0 / 17.9 | 117.0 | True / True | UNSUPPORTED_UNITS;DECAY_FACTOR_INCONSISTENT / PASS | OSEM / OSEM; TOF None / None; PSF None / None | False / False | none | NOT_ASSESSABLE | NOT_ASSESSABLE | UNKNOWN | EANM-UPTAKE-DIFF;QIBA-UPTAKE-DIFF;VT-SUV-BOTH;EANM-SAME-SYSTEM-SETTINGS;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-WINDOW;VT-PROTOCOL-IDENTITY | 8.0 |
| 163 | acrin_flt_breast | ACRIN-FLT-Breast_057 | GE MEDICAL SYSTEMS Discovery ST / GE MEDICAL SYSTEMS Discovery ST | None / None | 0.1 / 0.2 | 154.0 | True / True | UNSUPPORTED_UNITS;UNSUPPORTED_DECAY_CORRECTION;MISSING_CORRECTION;NONPOSITIVE_RESCALE_SLOPE / UNSUPPORTED_UNITS;MISSING_CORRECTION;DECAY_FACTOR_INCONSISTENT;NONPOSITIVE_RESCALE_SLOPE | 3D IR / 3D IR; TOF None / None; PSF None / None | True / True | none | NOT_ASSESSABLE | NOT_ASSESSABLE | UNKNOWN | EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-SUV-BOTH;EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY;DECAY_FACTOR_UNVERIFIED | 4.7 |
| 164 | acrin_flt_breast | ACRIN-FLT-Breast_061 | GE MEDICAL SYSTEMS Discovery ST / GE MEDICAL SYSTEMS Discovery ST | None / None | 0.4 / None | 11.0 | True / True | DECAY_FACTOR_INCONSISTENT / UNSUPPORTED_UNITS;MISSING_CORRECTION;IMPLAUSIBLE_DECAY_INTERVAL;NONPOSITIVE_RESCALE_SLOPE | 3D IR / 3D IR; TOF None / None; PSF None / None | True / True | none | NOT_ASSESSABLE | NOT_ASSESSABLE | UNKNOWN | EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-SUV-BOTH;EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY | 4.7 |
| 165 | acrin_flt_breast | ACRIN-FLT-Breast_069 | GE MEDICAL SYSTEMS Discovery ST / GE MEDICAL SYSTEMS Discovery ST | None / None | 0.2 / 0.5 | 14.0 | True / True | UNSUPPORTED_UNITS;MISSING_CORRECTION;DECAY_FACTOR_INCONSISTENT;NONPOSITIVE_RESCALE_SLOPE / DECAY_FACTOR_INCONSISTENT | 3D IR / 3D IR; TOF None / None; PSF None / None | True / True | none | NOT_ASSESSABLE | NOT_ASSESSABLE | UNKNOWN | EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-SUV-BOTH;EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY | 4.7 |
| 166 | acrin_flt_breast | ACRIN-FLT-Breast_075 | GE MEDICAL SYSTEMS Discovery ST / GE MEDICAL SYSTEMS Discovery ST | None / None | 0.8 / None | 164.0 | True / True | UNSUPPORTED_UNITS;MISSING_CORRECTION;DECAY_FACTOR_INCONSISTENT;NONPOSITIVE_RESCALE_SLOPE / IMPLAUSIBLE_DECAY_INTERVAL | 3D IR / 3D IR; TOF None / None; PSF None / None | True / True | none | NOT_ASSESSABLE | NOT_ASSESSABLE | UNKNOWN | EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-SUV-BOTH;EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY | 4.7 |

### Top 5 Siemens (same-vendor pairs: 211; classes {'FULLY_DECIDABLE_LIKELY': 99, 'REQUIRES_TRACER_SPECIFIC_RULESET': 73, 'LIKELY_INSUFFICIENT': 39})

| # | Collection | Subject | Scanner (B / F) | Software | Uptake min | Δ days | Height | SUV | Recon (method; TOF; PSF) | CT in PET frame | Lesion SEG (baseline) | QIBA* | EANM* | PERCIST readiness | Main blockers | MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | varepop_apollo | AP-ANXW | SIEMENS Biograph64_mCT / SIEMENS Biograph64_mCT | VG51C / VG51C | 57.3 / 56.7 | 277.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | none | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | PERCIST_LIVER_READY_BUT_LESION_MISSING | voxel size: confirm on download | 409.8 |
| 2 | varepop_apollo | AP-GEH6 | SIEMENS Biograph64_mCT / SIEMENS Biograph64_mCT | VG51C / VG62B | 62.3 / 58.8 | 399.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | none | ASSESSABLE_WITH_WARNINGS | ASSESSABLE_WITH_WARNINGS | PERCIST_LIVER_READY_BUT_LESION_MISSING | voxel size: confirm on download | 413.8 |
| 3 | fdg_pet_ct_lesions | PETCT_c2ffda4725 | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG60A / VG60A | 60.0 / 60.1 | 161.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 463.6 |
| 4 | fdg_pet_ct_lesions | PETCT_e9feb1135e | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG70A / VG70A | 60.1 / 60.0 | 70.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 519.4 |
| 5 | fdg_pet_ct_lesions | PETCT_97320b0b58 | SIEMENS Biograph128_mCT / SIEMENS Biograph128_mCT | VG60A / VG70A | 60.0 / 58.0 | 102.0 | True / True | PASS / PASS | PSF+TOF 2i21s / PSF+TOF 2i21s; TOF True / True; PSF True / True | True / True | COLLECTION_ANNOTATION | ASSESSABLE_WITH_WARNINGS | ASSESSABLE_WITH_WARNINGS | PERCIST_READY (pending human review of liver + lesion) | voxel size: confirm on download | 528.5 |

### Top 5 Philips (same-vendor pairs: 16; classes {'LIKELY_INSUFFICIENT': 9, 'REQUIRES_TRACER_SPECIFIC_RULESET': 7})

| # | Collection | Subject | Scanner (B / F) | Software | Uptake min | Δ days | Height | SUV | Recon (method; TOF; PSF) | CT in PET frame | Lesion SEG (baseline) | QIBA* | EANM* | PERCIST readiness | Main blockers | MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 179 | acrin_flt_breast | ACRIN-FLT-Breast_039 | Philips Medical Systems GEMINI TF Big Bore / Philips Medical Systems GEMINI TF Big Bore | None / None | 0.1 / None | 16.0 | True / True | UNSUPPORTED_UNITS;MISSING_CORRECTION;DECAY_FACTOR_INCONSISTENT / INVALID_ACQUISITION_DATETIME | 3D-RAMLA / BLOB-OS-TF; TOF None / None; PSF None / None | True / True | none | NOT_ASSESSABLE | NOT_ASSESSABLE | UNKNOWN | EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-SUV-BOTH;EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY | 51.6 |
| 185 | acrin_flt_breast | ACRIN-FLT-Breast_040 | Philips Medical Systems GEMINI TF TOF 16 / Philips Medical Systems GEMINI TF TOF 16 | None / None | None / None | 9.0 | True / True | INVALID_ACQUISITION_DATETIME / UNSUPPORTED_UNITS;MISSING_CORRECTION;SCAN_REFERENCE_AMBIGUOUS | BLOB-OS-TF / 3D-RAMLA; TOF None / None; PSF None / None | True / True | none | NOT_ASSESSABLE | NOT_ASSESSABLE | UNKNOWN | EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-SUV-BOTH;EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY | 159.9 |
| 192 | acrin_flt_breast | ACRIN-FLT-Breast_038 | Philips Medical Systems GEMINI TF Big Bore / Philips Medical Systems GEMINI TF Big Bore | None / None | None / None | 182.0 | True / True | SCAN_REFERENCE_AMBIGUOUS / UNSUPPORTED_UNITS;MISSING_CORRECTION;INVALID_ACQUISITION_DATETIME | BLOB-OS-TF / 3D-RAMLA; TOF None / None; PSF None / None | True / True | none | NOT_ASSESSABLE | NOT_ASSESSABLE | UNKNOWN | EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-SUV-BOTH;EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY | 256.3 |
| 195 | acrin_flt_breast | ACRIN-FLT-Breast_033 | Philips Medical Systems GEMINI TF Big Bore / Philips Medical Systems GEMINI TF Big Bore | None / None | None / None | 14.0 | True / True | UNSUPPORTED_UNITS;MISSING_CORRECTION;SCAN_REFERENCE_AMBIGUOUS / SCAN_REFERENCE_AMBIGUOUS | 3D-RAMLA / BLOB-OS-TF; TOF None / None; PSF None / None | True / True | none | NOT_ASSESSABLE | NOT_ASSESSABLE | UNKNOWN | EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-SUV-BOTH;EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY | 280.3 |
| 196 | acrin_flt_breast | ACRIN-FLT-Breast_052 | Philips Medical Systems GEMINI TF Big Bore / Philips Medical Systems GEMINI TF Big Bore | None / None | None / None | 187.0 | True / True | SCAN_REFERENCE_AMBIGUOUS / UNSUPPORTED_UNITS;MISSING_CORRECTION;INVALID_ACQUISITION_DATETIME | BLOB-OS-TF / 3D-RAMLA; TOF None / None; PSF None / None | True / True | none | NOT_ASSESSABLE | NOT_ASSESSABLE | UNKNOWN | EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-SUV-BOTH;EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY | 284.2 |

### Classes by collection

| collection | FULLY_DECIDABLE_LIKELY | LIKELY_INSUFFICIENT | REQUIRES_TRACER_SPECIFIC_RULESET | UNKNOWN |
|---|---|---|---|---|
| acrin_flt_breast | 0 | 52 | 18 | 0 |
| anti_pd_1_lung | 1 | 11 | 0 | 0 |
| breast_diagnosis | 0 | 1 | 0 | 0 |
| cc_tumor_heterogeneity | 10 | 13 | 0 | 0 |
| cmb_lca | 1 | 1 | 0 | 0 |
| cmb_mel | 1 | 0 | 0 | 0 |
| fdg_pet_ct_lesions | 81 | 0 | 0 | 0 |
| naf_prostate | 0 | 1 | 7 | 0 |
| psma_pet_ct_lesions | 0 | 85 | 79 | 0 |
| qin_breast | 0 | 38 | 0 | 0 |
| qin_pet_phantom | 0 | 0 | 0 | 2 |
| rider_lung_pet_ct | 0 | 22 | 0 | 0 |
| rider_phantom_pet_ct | 0 | 0 | 0 | 20 |
| tcga_luad | 0 | 3 | 0 | 0 |
| tcga_ucec | 0 | 2 | 0 | 0 |
| varepop_apollo | 5 | 0 | 0 | 0 |

### Reconstruction evidence completeness by vendor (sampled AC PET series)

|  | series | reconstruction_method | iterations | subsets | convolution_kernel | time_of_flight | psf_resolution_modelling |
|---|---|---|---|---|---|---|---|
| GE | 1038 | 1038 | 0 | 0 | 134 | 0 | 0 |
| Philips | 177 | 177 | 0 | 0 | 0 | 0 | 0 |
| Siemens | 627 | 606 | 582 | 582 | 602 | 405 | 566 |
| UNKNOWN_MANUFACTURER | 184 | 181 | 175 | 175 | 176 | 0 | 20 |

### Series by tracer class (from DICOM)

|  | n |
|---|---|
| FDG | 928 |
| OTHER | 391 |
| UNKNOWN | 489 |
| PSMA | 218 |

### Series by vendor

|  | n |
|---|---|
| GE | 1038 |
| UNKNOWN_MANUFACTURER | 184 |
| Siemens | 627 |
| Philips | 177 |

### Strict SUV pass / height present by collection (sampled series)

|  | suv_pass | height |
|---|---|---|
| acrin_flt_breast | 76/865 | 621/865 |
| anti_pd_1_lung | 6/36 | 32/36 |
| breast_diagnosis | 0/4 | 4/4 |
| cc_tumor_heterogeneity | 30/68 | 36/68 |
| cmb_lca | 2/5 | 0/5 |
| cmb_mel | 4/4 | 4/4 |
| fdg_pet_ct_lesions | 195/195 | 189/195 |
| naf_prostate | 0/127 | 127/127 |
| psma_pet_ct_lesions | 261/383 | 177/383 |
| qin_breast | 0/105 | 105/105 |
| qin_pet_phantom | 2/44 | 22/44 |
| rider_lung_pet_ct | 0/139 | 113/139 |
| rider_phantom_pet_ct | 0/20 | 0/20 |
| tcga_luad | 1/8 | 2/8 |
| tcga_ucec | 0/5 | 5/5 |
| varepop_apollo | 18/18 | 18/18 |

### Top refusal codes

|  | n |
|---|---|
| DECAY_FACTOR_INCONSISTENT | 886 |
| UNSUPPORTED_UNITS | 439 |
| IMPLAUSIBLE_DECAY_INTERVAL | 49 |
| MISSING_RADIONUCLIDETOTALDOSE | 74 |
| MISSING_INJECTION_TIME | 64 |
| SERIES_TIME_AFTER_ACQUISITION | 106 |
| MISSING_CORRECTION | 344 |
| SCAN_REFERENCE_AMBIGUOUS | 57 |
| MISSING_UNITS | 4 |
| MISSING_DECAYCORRECTION | 4 |

## Why these are worth downloading

**fdg_pet_ct_lesions (autoPET FDG, Siemens Biograph128 mCT)** are the first public pairs
predicted to be decidable end to end:
- BQML/START, coded FDG, height, DecayFactor and FrameReferenceTime on every sampled slice;
- **structured reconstruction** (PSF+TOF 2i21s, Gaussian kernel, TOF and PSF);
- CT in the PET frame of reference;
- a manual lesion annotation at baseline, to be reviewed.

They exercise QIBA ASSESSABLE, EANM ASSESSABLE_WITH_WARNINGS and the full PERCIST path,
including the liver review and a reviewed baseline lesion.

**varepop_apollo and cc_tumor_heterogeneity:**
- They add other Siemens generations (Biograph64 mCT, Biograph64 syngo 2011A).
- cc_tumor_heterogeneity has no height, so it is PERCIST_BLOCKED_BY_SUL.
- varepop has no lesion SEG.

**cmb_lca MSB-07864** is the cheapest decidable pair (12.4 MB; no height). It is a quick
pipeline check, not a PERCIST case.

**Single recommended next download: FDG-PET-CT-Lesions `PETCT_c2ffda4725`**:
- both PET series plus the CT in the PET frame of reference, about 464 MB;
- the baseline SEG (small), for review only.

It is the top-ranked pair with a full PERCIST path:
- predicted QIBA ASSESSABLE, EANM ASSESSABLE_WITH_WARNINGS;
- uptake 60.0 / 60.1 min; 161 days apart; same software VG60A.

**Before any download:** a bounded allow-list and provenance manifest, as for ACRIN.
