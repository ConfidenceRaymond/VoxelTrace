# Real longitudinal validation: ACRIN-NSCLC-FDG-PET-168 (2026-10-08)

REAL public data (ACRIN 6668 via IDC; CC BY 3.0). RESEARCH PROTOTYPE - NOT FOR CLINICAL
DIAGNOSIS. No response assessment. Validator, SUV formula, rules and thresholds are unchanged.

| Item | Location |
|---|---|
| Allow-list | `configs/acrin_longitudinal/allowlist_batch3.json` |
| Series manifest | `configs/acrin_longitudinal/provenance_manifest_batch3.json` (per-file hashes in `../data/acrin_longitudinal/provenance_manifest_batch3.json`) |
| Outputs | `../outputs/acrin_longitudinal_168/` |
| Status after review | `scripts/pair_review_status.py acrin_longitudinal_168` |

## Download and ingestion

| Timepoint | Modality | Files | Bytes |
|---|---|---|---|
| baseline | PET "PET Attenuation Correction Recon" (GE Discovery LS, software 16.01) | 195 | 7,048,442 |
| baseline | CT "CT Atten Cor Head In" | 195 | 102,777,258 |
| follow-up | PET | 195 | 7,019,906 |
| follow-up | CT | 195 | 102,772,348 |
| **Total** | | **780** | **219,617,954** |

- **Ingestion:** OK at both timepoints. PET is 128×128×195 at 3.906×3.906×4.25 mm; CT is
  512×512×195. PET and CT share the FrameOfReferenceUID. Slice order is unambiguous and spacing
  uniform.

## Strict SUVbw (unchanged)

| | Baseline | Follow-up |
|---|---|---|
| SUV_STATUS | **PASS** | **PASS** |
| DECAY_FACTOR_CROSSCHECK | **NOT_AVAILABLE** (DecayFactor absent on 195/195 slices; DICOM Type 1C gap) | **NOT_AVAILABLE** (0/195) |
| QUANTITATIVE_WARNING | STORED_DECAY_FACTOR_NOT_AVAILABLE | same |
| Other warnings | NEGATIVE_SUV, INJECTION_DATE_FROM_SERIES | same |
| Units / decay / corrections | BQML / START / DECY, ATTN, SCAT, DTIM, RAN, … | same |
| Weight / dose / T½ | 54 kg / 355.0 MBq / 6588 s | 57 kg / 425.0 MBq / 6588 s |
| Uptake (series − injection) | **60.767 min** (09:24:00 → 10:24:46) | **63.283 min** (12:45:00 → 13:48:17) |
| SUV range | −0.041 … 25.35 | −0.015 … 15.34 |

The uptake values were independently re-derived from the raw headers. SeriesTime and the
earliest AcquisitionTime agree.

## Strict SUL (DICOM anthropometrics only)

| | Baseline | Follow-up |
|---|---|---|
| Sex / height / weight | F / 1.57 m / 54 kg | F / 1.54 m / 57 kg |
| LBM, James (LBMJAMES128; PERCIST) | 40.27 kg → **PASS** | 40.71 kg → **PASS** |
| LBM, Janmahasatian (LBMJANMA) | 35.44 kg → PASS | 36.08 kg → PASS |
| SUL range, James (SUV × LBM / W) | −0.031 … 18.90 | −0.011 … 10.96 |

## Protocol fingerprint (identical at both timepoints except timing and dose)

**PRESENT and SAME:**
- GE Discovery LS, software 16.01;
- FDG / ¹⁸F;
- matrix 128², voxel 3.906 × 3.906 × 4.25 mm;
- CorrectedImage, START, BQML;
- measured attenuation correction (0.096 cm⁻¹);
- reconstruction diameter 500 mm.

**MISSING on every slice at both timepoints:** ReconstructionMethod, ConvolutionKernel, iterations,
subsets, TOF, PSF, filter, ScatterCorrectionMethod, DecayFactor.

**DIFFERENT:** uptake 60.77 → 63.28 min (Δ 2.52 min); dose 355 → 425 MBq (19.7 %).

**Harmonization/EARL:** UNKNOWN (not in DICOM, not configured).

**Private tags:**
- GE scan datetime (0009,xx0D) is absent at both timepoints → `UNKNOWN_OR_STRIPPED`.
- The baseline carries the `GEMS_PETD_01` creator; the follow-up does not.
- Both carry `MAROTECH Inc.` (reported, not interpreted).

## Non-reference pair rules (before review)

| Rule | QIBA | EANM | PERCIST |
|---|---|---|---|
| VT-SUV-BOTH | PASS | PASS | PASS |
| VT-TRACER-SAME (FDG / FDG) | PASS | PASS | PASS |
| Uptake window (60.77, 63.28 min) | PASS (55–75) | PASS (55–75) | PASS (50–70, warning) |
| Uptake difference (2.52 min) | PASS (≤ 10) | PASS (≤ 10) | PASS (≤ 15) |
| Same scanner/software | PASS (warning) | — | PASS (warning) |
| Dose difference (19.7 % ≤ 20 %) | — | — | PASS (warning) |
| **VT-PROTOCOL-IDENTITY** | **UNKNOWN** | **UNKNOWN** | **UNKNOWN** |
| EANM-SAME-SYSTEM-SETTINGS | — | **UNKNOWN** | — |
| EANM-EARL-RECON | — | UNKNOWN (warning; NEVER_ENCODED) | — |

**Reconstruction identity: UNKNOWN.**
- The engineering comparability layer reports INSUFFICIENT_INFORMATION, with blocking unknown
  `reconstruction_method`. Iterations, subsets, TOF, PSF and post-filter are unknown.
- Missing reconstruction evidence is **not** treated as identity, so the verdict is not
  converted into PASS.

## Assessability layers (`trial/layers.py`; reporting only)

| Rule set | REFERENCE | PROTOCOL | OVERALL |
|---|---|---|---|
| PERCIST | UNKNOWN (liver review pending; baseline measurable needs a lesion SULpeak) | UNKNOWN (VT-PROTOCOL-IDENTITY) | **INSUFFICIENT_INFORMATION** |
| QIBA | not applicable | UNKNOWN (VT-PROTOCOL-IDENTITY) | **INSUFFICIENT_INFORMATION** |
| EANM | not applicable | UNKNOWN (protocol identity, same settings) | **INSUFFICIENT_INFORMATION** |

**Even after a human liver review, OVERALL stays INSUFFICIENT_INFORMATION** in every rule set,
because the reconstruction is unknown. The review can resolve PERCIST-LIVER-SUL-STABILITY to an
actual PASS or FAIL.

**PERCIST-BASELINE-MEASURABLE stays UNKNOWN** until a baseline lesion segmentation exists. IDC
lists an AI-generated "AIMI lung and FDG tumor AI segmentation" SEG for this subject. It was not
downloaded and is not reviewed ground truth.

## Reference regions (new real namespace `outputs/acrin_longitudinal_168/reference_review/`)

| Timepoint | Liver | Blood pool |
|---|---|---|
| baseline | **PROPOSED** (awaits review) | NOT_FOUND (no consistent descending-aorta segment) |
| follow-up | **PROPOSED** (awaits review) | NOT_FOUND |

- **2 new proposals, both LIVER.** No decision was created.
- **Pipeline check:** the post-review computation was verified only on a **scratch copy** with a
  SIMULATED acceptance, never in project outputs.
  - Preview liver SULs of the *unreviewed* proposals: 1.362 → 1.643 (Δ 0.281 SUL, 17.1 % of the
    larger value).
  - Both are close to the PERCIST limits (0.3 SUL, 20 %), so placement during review matters.
  - These numbers are not a result.

## Census v2 validation

Every predicted field matched the full series at both timepoints:
- SUV PASS;
- decay cross-check NOT_AVAILABLE;
- SUL eligible;
- CT in the PET frame of reference;
- tracer present;
- reconstruction description missing; iterations missing;
- uptake 60.8 / 63.3 min;
- QIBA INSUFFICIENT_INFORMATION (pair category LIKELY_INSUFFICIENT, driven by protocol
  identity).

**No miss.**
