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

### Not yet validated

- SUV and lesion metrics are not implemented (see `suv_requirements.md`).
- Nothing has been tested yet on multi-frame (enhanced) PET/CT, other vendors, FRACTIONAL SEG,
  SEG on CT grids, or BIDS PET.

## Planned datasets

| Dataset | Source | Status |
|---|---|---|
| FDG-PET-CT-Lesions | TCIA | 1 subject (`PETCT_0011f3deaf`), see `../data/manifest.json` |
| NSCLC-Radiogenomics | TCIA | not downloaded |
| ACRIN-NSCLC-FDG-PET | TCIA | not downloaded |
| OpenNeuro PET | OpenNeuro | not downloaded |
