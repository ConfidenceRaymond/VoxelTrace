# Validation log

Records of what has actually been verified. Do not add claims that were not run.

## Milestone 0/1 - project foundation (2026-10-07)

| Check | Command | Result |
|---|---|---|
| Unit tests | `make test` | `18 passed in 0.14s` |
| Lint | `make lint` / `ruff format --check .` | `All checks passed!` / `15 files already formatted` |
| App import / render | Streamlit `AppTest` headless run of `app/Home.py` | no exceptions; title, disclaimer, synthetic-data banner, AI-status warning rendered |
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
