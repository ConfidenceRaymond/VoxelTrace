# Validation log

Records of what has actually been verified. Do not add claims that were not run.

## Milestone 0/1 - project foundation (2026-10-07)

| Check | Command | Result |
|---|---|---|
| Unit tests | `make test` | `18 passed in 0.14s` |
| Lint | `make lint` / `ruff format --check .` | `All checks passed!` / `15 files already formatted` |
| App import / render | Streamlit `AppTest` headless run of `app/Home.py` | no exceptions; product overview, disclaimer and workflow rendered; system status and the synthetic smoke test sit in a collapsed expander (`tests/test_product_workflow.py`) |
| App server | `scripts/run_app.sh` on port 8599, `GET /_stcore/health` | `200 ok`; server stopped afterwards |

### `compute_image_stats` verified behaviours (tests/test_image_stats.py)

- Finite arrays: min/max/mean/std(ddof=0)/median/p1/p99 against hand-computed values.
- NaN / +inf / -inf counted separately and excluded from intensity statistics; input not modified.
- All-zero arrays.
- Arrays with no finite voxels: intensity fields are `None`.
- Integer arrays computed in float64 (no overflow).
- Rejected: non-ndarray, string, bool, complex, empty arrays.
- Determinism: identical results on repeated calls.

## Milestone 2: PET/CT/SEG ingestion (2026-10-07)

### Automated tests (synthetic fixtures generated at runtime; no real images)

`pytest` reports **47 passed**:

- `tests/test_ingest_dicom.py`:
  - Non-DICOM files are ignored, including a fake `.dcm`.
  - Modality comes from the header, not the directory name.
  - Malformed DICOM produces a warning.
  - Series are grouped by UID.
  - Slices are ordered by geometry even when filenames and InstanceNumber are scrambled.
  - The loader matches **SimpleITK** in size, spacing, origin and pixels.
  - Duplicate slice positions, inconsistent orientation and missing geometry are refused.
  - Non-uniform slice spacing produces a warning.
  - Mixed series are flagged.
  - Complete PET metadata is extracted.
  - Missing PET fields are reported and never defaulted.
  - Invalid `PatientWeight` values (NaN, `abc`, 0, negative, inf) are reported as invalid.
  - A missing radiopharmaceutical sequence is reported.
  - The case serialises to JSON and no PatientID is copied.
- `tests/test_ingest_nifti_seg.py`:
  - NIfTI images load and non-finite voxels are flagged.
  - Mask label values and counts are preserved.
  - Mask grid mismatches (shift, shape) are detected.
  - Non-integer masks are rejected.
  - DICOM and NIfTI grids compare equal through the LPS→RAS conversion.
  - SEG metadata is parsed.
  - BINARY SEG decodes onto the PET grid.
  - SEG decoding is refused for a wrong reference series, for FRACTIONAL type, and for an
    off-grid frame.
- `tests/test_inspect_cli.py`: all CLI text sections are present, and JSON mode works with
  `--load-pixels`.

### Real public case: FDG-PET-CT-Lesions `PETCT_0011f3deaf` (defaced, CC BY 4.0)

Logs are in `../logs/inspect_PETCT_0011f3deaf.txt` and
`../logs/sitk_crosscheck_PETCT_0011f3deaf.txt`.

**Discovery**
- 725 files were scanned: 718 DICOM, 7 non-DICOM ignored, 0 unreadable.
- 1 study and 3 series were found.
- Instance counts are 391 CT, 326 PT and 1 SEG, matching the NBIA metadata.

**PET metadata**
- All required fields are present: `Units`=BQML, `DecayCorrection`=START, `CorrectedImage`
  includes ATTN and DECY, `PatientWeight`, `RadionuclideTotalDose`, `RadionuclideHalfLife` and
  `RadiopharmaceuticalStartDateTime`.
- `ReconstructionDiameter` is absent. It is optional and shown as missing.
- There are 326 distinct per-slice `RescaleSlope` values, reported as an info-level warning.

**Geometry**
- CT is 512×512×391 at 0.797×0.797×2.5 mm; PET is 400×400×326 at 2.036×2.036×3 mm.
- Both have uniform slice spacing and an identity direction matrix.

**SimpleITK cross-check (independent reader)**
- CT and PET match exactly in size, spacing, origin and direction.
- The maximum absolute pixel difference is **0.0** for both, including PET with per-slice slopes.

**DICOM SEG**
- The file was written by dcmqi. It is BINARY, has 326 frames and references the PT series.
- It has 1 segment ("Tissue", MANUAL).
- It decoded onto the PET grid with 1,299 voxels in segment 1.

**Streamlit**
- `AppTest` runs on the Home page and on the ingestion page with both the synthetic and the real
  case raised no exceptions, including PET + SEG overlay.
- A live server on port 8599 answered `/_stcore/health` with `ok`. The server was stopped
  afterwards.

### Not yet validated (Milestone 2 scope)

- SUV and lesion metrics were not part of Milestone 2. They are now covered in the Milestone 3
  section below.
- Nothing has been tested yet on multi-frame (enhanced) PET/CT, other vendors, FRACTIONAL SEG,
  SEG on CT grids, or BIDS PET.

## Planned datasets

| Dataset | Source | Status |
|---|---|---|
| FDG-PET-CT-Lesions | TCIA | 1 subject (`PETCT_0011f3deaf`), see `../data/manifest.json` |
| NSCLC-Radiogenomics | TCIA | not downloaded |
| ACRIN-NSCLC-FDG-PET | TCIA | not downloaded |
| OpenNeuro PET | OpenNeuro | not downloaded |

## Milestone 3: strict SUVbw, lesion metrics, evidence (2026-10-07)

Quantitative correctness is validated **only for the implemented DICOM path** (BQML / START /
ATTN+DECY), not for all vendor PET DICOM variants.

### Automated tests: `pytest` reports 144 passed

- **`tests/test_dicom_time.py`**
  - Accepts DA, TM, DT, fractional seconds (1 to 6 digits) and UTC offsets.
  - Rejects reduced precision (`HHMM`), the colon form, out-of-range values, more than 6
    fraction digits and invalid dates.
- **`tests/test_suv.py`: hand-calculated oracles.** Expected values are literals computed by
  hand, not by the module.
  - Formula, Δt = 0: W = 70 kg, D = 3.5e8 Bq gives a factor of 2e-4 g/Bq, so 5000 Bq/mL is
    SUV 1.0.
  - Formula, Δt = T½: decay factor 0.5, factor 4e-4 g/Bq, so SUV 2.0.
  - Formula, Δt = 2·T½: SUV [0.8, 2.0], and the input array is unchanged.
  - End to end, zero interval with a non-zero intercept: stored 2500 × 2 + 100 = 5100 Bq/mL
    gives SUV **1.02**.
  - End to end, one half-life with fractional seconds: injection 09:00:00.000 and scan
    10:49:46.200 give Δt = 6586.2 s and SUV **2.0**.
  - End to end, per-slice slopes 1.0 / 0.5 / 2.0 with intercepts 0 / 0 / 100 give SUV
    **0.2 / 0.1 / 0.42**.
  - End to end, midnight with explicit DT dates: Δt = 3600 s, decay factor
    **0.68463291957200212** (40-digit decimal hand calculation), SUV **1.4606367462218285**.
  - The midnight rule with TM only gives the same SUV and records an `INJECTION_DATE_ROLLOVER`
    warning.
  - Series earlier than acquisition is accepted only when FrameReferenceTime confirms it.
  - **Tolerances:** rel 1e-12 for pure formula tests; 1e-13 to 1e-14 for midnight cases;
    1e-9 for the fractional-second case; and abs 1e-6 s on Δt.
- **`tests/test_suv.py`: 33 parametrised refusal cases plus 6 more.** Covered:
  - Units: CNTS, missing.
  - Weight, dose and half-life: missing, zero, negative, NaN, inf, implausible.
  - Half-life inconsistent with F-18.
  - DecayCorrection ADMIN and NONE; missing ATTN.
  - Injection DT or TM: invalid or conflicting; injection timing missing.
  - Acquisition time: invalid (`1015`) or missing.
  - Invalid series time.
  - Negative Δt; Δt over 12 h.
  - Series time after acquisition; ambiguous series time.
  - Rescale slope missing or zero.
  - Missing radiopharmaceutical sequence.
  - Timezone ambiguity.
  - Inconsistent per-slice weight, units, decay correction, series time and dose.
  - Vendor DecayFactor inconsistent.
- **`tests/test_lesions.py`**
  - SUVpeak radius is 6.2035 mm (1 cm³ exactly; not 1 cm diameter).
  - The sphere kernel matches a brute-force voxel count for isotropic and anisotropic spacing.
  - The kernel volume converges to 1 mL at 0.5 mm.
  - Metrics on 8-voxel and anisotropic phantoms: volume, SUVmax, mean, median, population SD,
    TLG.
  - Multiple labels, components and summary; empty segment.
  - SUVpeak on phantoms:
    - uniform hot region: the exact value;
    - single hot voxel: value / kernel count;
    - the centre stays inside the segment even when a hotter blob lies outside it;
    - image-edge exclusion;
    - small-segment warning.
- **`tests/test_quantify_cli.py`**
  - A PASS run writes all output files, with values matching the hand-calculated factor and
    lesion SUVs.
  - A refusal exits with code 2, writes `suv_refusal.json` and removes a stale
    `suv_result.json`.

### Real case: FDG-PET-CT-Lesions `PETCT_0011f3deaf` (outputs in `../outputs/PETCT_0011f3deaf/`)

- **Eligibility:** PASS.
  - Every check passed: per-slice consistency (14 fields × 326 slices), Units, DecayCorrection,
    CorrectedImage, weight, dose, half-life (F-18), scan reference, injection, interval,
    vendor decay factor and rescale.
- **Inputs:**
  - Units BQML; DecayCorrection START; CorrectedImage NORM/DTIM/ATTN/SCAT/DECY/RAN.
  - Weight 68 kg; dose 3.27e8 Bq; T½ 6586.2 s (F-18, code C-111A1).
- **Timing:**
  - Injection: 2003-03-23T12:10:00, from the DT, which agrees with the TM. Dates are
    TCIA-shifted.
  - Scan reference: 2003-03-23T13:10:23, from SeriesDate/Time, equal to the earliest
    AcquisitionTime across 14 bed positions.
  - **Δt = 3623 s**.
- **Vendor check:** DecayFactor = 2^(FrameReferenceTime/T½) on all 326 slices (max relative
  deviation 2.78e-5). FrameReferenceTime − (AcqTime − SeriesTime) is 59.94–60.92 s, matching
  the theoretical decay-weighted mid-frame of 59.94 s for 120 s frames.
- **Scale:** dose decay factor 0.68297772; SUV per Bq/mL 3.04477093e-4 g/Bq.
- **Rescale:** 326 distinct per-slice slopes (0.0104–1.2103), intercept 0.
- **SUV volume:** min 0.0000, max 20.0379, mean 0.0538, p99 1.1702 g/mL.
- **Segment 1 "Tissue"** (dcmqi SEG, BINARY, on the PET grid):
  - 1299 voxels in 5 components.
  - **MTV 16.161 mL**; **SUVmax 19.113**; **SUVmean 5.955**; SUVmedian 4.774; SD 4.013.
  - **TLG 96.234 g**.
  - **SUVpeak 12.235**, using a 73-voxel sphere (0.908 mL).
- **Independent cross-check** (`scripts/crosscheck_quant.py`, no shared code):
  - SimpleITK pixels, strptime timing, separate SEG decoding by z-matching, FFT-convolution
    SUVpeak.
  - Agrees on Δt, the factor, SUVmax (volume and lesion), SUVmean, MTV, TLG, SUVpeak and the
    kernel size, with a **maximum relative difference of 7.3e-16**
    (`../logs/crosscheck_quant_PETCT_0011f3deaf.txt`).

### Refusal on real-world-like data

The Milestone 2 synthetic fixture has SeriesTime 10:15:00 and acquisition 10:15:30, with no
FrameReferenceTime. It is **refused** with `SCAN_REFERENCE_AMBIGUOUS`, as designed.

### Streamlit

- `AppTest` on the Quantitative PET page:
  - Real case: PASS, with metrics shown (SUVmax 19.11, SUVmean 5.955, SUVpeak 12.24,
    MTV 16.16, TLG 96.23).
  - Old fixture: REFUSED, with reasons shown and no SUV image.
  - Synthetic M3 case: PASS, SUVpeak N/A because the grid is smaller than the sphere.
- No exceptions on the Home or Ingestion pages.
- Live server: `/_stcore/health` = ok and the page returned HTTP 200. The server was
  time-limited and stopped.

### Not yet validated

- Other vendors (GE, Philips, Canon/United Imaging).
- DecayCorrection ADMIN or NONE; non-BQML units.
- Dynamic or Enhanced multi-frame PET.
- SUVlbm/SUVbsa.
- Lesions near image edges (SUVpeak excluded there).
- Inter-software agreement with established tools (e.g. 3D Slicer PET-IndiC, LIFEx). This is
  recommended next.

## Milestone 4: protocol and reconstruction evidence, comparability, claim gating (2026-10-07)

### Automated tests: `pytest` reports 183 passed

- **`tests/test_protocol_evidence.py` (25 tests)**
  - Free-text parsing, including `<N>i<M>s` edge cases. An absent TOF/PSF token gives MISSING,
    never False.
  - Structured Enhanced-PET attributes take precedence over free text.
  - Missing scanner metadata: QC flags it, and only cross-scan comparison is blocked.
  - Missing reconstruction info.
  - CorrectedImage absent gives MISSING (not False); an unlisted flag gives False.
  - Site and device identifiers are never copied.
  - Uptake outside the QIBA window gets a QC warning.
- **Comparability scenarios (part of the same file):**
  - same scanner and reconstruction: COMPARABLE;
  - different scanner: NOT_COMPARABLE;
  - changed voxel size, filter or iterations: NOT_COMPARABLE;
  - uptake +5 min: COMPARABLE (within ±10 min); uptake +20 min: NOT_COMPARABLE;
  - correction mismatch (SCAT): NOT_COMPARABLE;
  - missing model and method: INSUFFICIENT_INFORMATION;
  - software and activity differences: COMPARABLE_WITH_WARNINGS.
- **`tests/test_claims.py` (14 tests)**
  - Value claims: supported, contradicted, and the stated-precision tolerance.
  - Unmeasured value or refused SUV: NOT_ESTABLISHED.
  - Protocol facts: supported, contradicted, unknown.
  - Uptake change:
    - SUPPORTED: comparable protocols, confirmed target, −50 %;
    - CONTRADICTED: an increase;
    - NOT_ESTABLISHED: no target correspondence, NOT_COMPARABLE, or a single scan;
    - PARTIALLY_SUPPORTED: comparable with warnings.
  - Treatment response stays NOT_ESTABLISHED even when a decrease is SUPPORTED.
  - A diagnosis claim is NOT_ESTABLISHED.
- **`tests/test_quantify_cli.py`**
  - Protocol, QC and claim JSON files are written for both PASS and refused cases.
  - On a refused case, no quantitative claim is SUPPORTED.

### Real case PETCT_0011f3deaf

- **Protocol QC:**
  - 61 PRESENT, 3 PRESENT_BUT_AMBIGUOUS, 12 MISSING, 0 UNSUPPORTED fields.
  - Usable for SUV, lesion metrics and cross-scan comparison.
- **Claims:**
  - 6 value claims SUPPORTED: SUVmax 19.113, SUVmean 5.955, SUVmedian 4.774, SUVpeak 12.235,
    MTV 16.161 mL, TLG 96.234 g.
  - Attenuation, scatter and randoms correction SUPPORTED (standard CorrectedImage flags).
  - TOF and PSF PARTIALLY_SUPPORTED (from vendor free text).
  - Uptake change, treatment response, diagnosis and image noise NOT_ESTABLISHED.
  - The wrong-value demonstration (SUVmax 23.89) is CONTRADICTED.
- **Streamlit:** AppTest of the Protocol & Claims page on the real case and the refused
  fixture shows no exceptions. The other three pages also show no exceptions.

## Milestone 5: ground truth, visualization, multimodal evaluation foundation (2026-10-07)

### Automated tests: `pytest` reports 258 passed

- **Ground-truth schema:**
  - hierarchy levels are fixed by source type;
  - MODEL_GENERATED is rejected;
  - EXPERT_ANNOTATION requires review;
  - unvalidated sources are rejected as targets;
  - the example level equals the highest source level.
- **Visualization (27 tests):**
  - analytic voxel↔patient mapping;
  - every voxel's pixel block round-trips, with and without flips and crops;
  - a hot-voxel point annotation lands on the exact PNG pixel (radiological and neurological,
    cropped and full);
  - bbox and pixel count equal the rendered mask;
  - PNGs are deterministic and the data are unaltered;
  - non-standard orientation is refused;
  - MIP orientation is checked;
  - CT resampling is checked, including the FrameOfReference guard;
  - the SUVpeak circle radius is checked;
  - the footer leaves the image region untouched;
  - the verifier fails on 5 kinds of injected mismatch.
- **Training dataset:**
  - end-to-end build on a synthetic case;
  - targets equal ground truth;
  - the SUVmax pixel maps back to the SUVmax voxel;
  - injected text is not copied into contexts;
  - no raw UIDs or identifiers;
  - Qwen export format;
  - tampering is detected;
  - splits are deterministic and patient-level;
  - 4 kinds of leakage are detected;
  - longitudinal studies stay with their patient;
  - zero-SUV QC fires without any metric change;
  - no negative labels without a decoded SEG.
- **Evaluation:**
  - number extraction ignores identifiers;
  - precision-aware exact matching;
  - invented numbers;
  - claim parsing;
  - refusal and blocked assertions, where a disclaimer does not count as a negation;
  - grounding: IoU, distance, Dice;
  - metadata accuracy;
  - gate and report.
- **Adversarial:**
  - injected DICOM text leaves claim statuses unchanged;
  - free-text injection can never make a fact fully SUPPORTED;
  - obeying an injection is scored wrong and rejected by the gate.
- **SEG:**
  - mirrored frames decode voxel-exactly;
  - off-grid, rotated and outside-grid frames are refused.

### Real development datasets (DEVELOPMENT_ONLY; not a training set)

| Subject | Diagnosis (CSV) | Scanner | SUV | Segment | Examples |
|---|---|---|---|---|---|
| PETCT_0011f3deaf | melanoma | Biograph128_mCT | PASS (Δt 3623 s) | 1299 voxels, 5 components; 89 voxels (6.9 %) SUV = 0 | 45 |
| PETCT_db3bac356a | negative control | Biograph128_mCT | PASS (Δt 3601 s) | decoded, EMPTY | 28 |
| PETCT_bd52fdf529 | lung cancer | SOMATOM Definition AS_mCT | PASS (Δt 3608 s; TM-only injection, documented rule) | mirrored SEG frames decoded; 1182 voxels, 3 components; 313 (26.5 %) SUV = 0 | 44 |

- **Total:** 117 examples. A perfect oracle (ground-truth targets submitted as answers) scores
  1.0 in every class with 0 invented numbers.
- **External cross-check** (highdicom SEG + Z-Rad IBSI global peak) on both lesion cases:
  max relative difference ≤ 2.3e-15.
- **Milestone 3 numbers** for PETCT_0011f3deaf are unchanged: bit-identical; internal
  independent check 7.26e-16.

### Findings

- **Reference masks over zeroed PET:** some reference segment voxels lie where the PET is
  exactly 0 (masked outside the body).
  - They are flagged (`SEGMENT_VOXELS_ZERO_SUV`).
  - Metric definitions are unchanged.
  - Such slices are excluded from localization targets.
- **Mirrored SEG frames on the SOMATOM cases:** the strict decoder correctly refused them.
  Exact mirrored mapping has now been added and validated externally.
- **Z-Rad timing refusal:** Z-Rad refuses SUV conversion on both lesion cases because the
  Siemens private acquisition-start tag is date-shifted by one day. VoxelTrace uses standard
  tags only, cross-validated by FrameReferenceTime and DecayFactor.
