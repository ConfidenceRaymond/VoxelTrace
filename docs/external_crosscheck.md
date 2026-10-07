# External quantitative cross-check

## Implementations compared

1. **Internal independent reimplementation**, `scripts/crosscheck_quant.py` (Milestone 3):
   - shares no code with VoxelTrace: SimpleITK pixels, its own timing, z-matched SEG and an
     FFT SUVpeak;
   - on PETCT_0011f3deaf: max relative difference **7.3e-16**.
2. **Third-party open-source tools**, `scripts/crosscheck_external.py`, run in an isolated venv
   at `../tmp/crosscheck-venv` (687 MB, pip cache in `../tmp`):
   - highdicom 0.28.2 (MIT): spatial DICOM SEG decoding via the volume affine, mapped to PET
     indices through the SimpleITK physical transform;
   - Z-Rad 26.9.0 (MIT, installed `--no-deps` because its GUI dependency PyQt5 has no aarch64
     wheel): vendor-aware DICOM SUVbw and IBSI local-intensity peak features.

### Results on PETCT_0011f3deaf (`../logs/crosscheck_external_PETCT_0011f3deaf.txt`)

| Quantity | External | VoxelTrace | Relative difference |
|---|---|---|---|
| lesion voxels (highdicom SEG) | 1299 | 1299 | 0 |
| SUVmax | 19.1130623398 | 19.1130623398 | 0 |
| SUVmean | 5.95473073571 | 5.95473073571 | 0 |
| MTV (mL) | 16.1608840047 | 16.1608840047 | 2.2e-16 |
| TLG (g) | 96.2337126991 | 96.2337126991 | 1.5e-16 |
| **SUVpeak vs Z-Rad IBSI global intensity peak** | 12.2351465187 | 12.2351465187 | **2.3e-15** |
| Z-Rad IBSI *local* peak (sphere at the max voxel; a different feature) | 11.7094 | — | information only |

### Results on PETCT_bd52fdf529 (SOMATOM Definition AS, mirrored SEG frames)

highdicom's spatial SEG decode gives 1182 voxels, identical to VoxelTrace.

| Quantity | External | VoxelTrace | Relative difference |
|---|---|---|---|
| SUVmax | 10.2546186607 | 10.2546186607 | 0 |
| SUVmean | 2.31480978119 | 2.31480978119 | 0 |
| MTV (mL) | 14.7052847526 | 14.7052847526 | 3.6e-16 |
| TLG (g) | 34.0399369803 | 34.0399369803 | 4.2e-16 |
| SUVpeak vs Z-Rad global peak | 7.34519145639 | 7.34519145639 | 2.2e-15 |

This independently validates the mirrored-frame SEG mapping. Z-Rad's own SUV conversion refused
this case too.

### Z-Rad SUV conversion refused this case

Z-Rad's own DICOM SUV conversion **refused** the case: "Reconstructed administration and
acquisition times are inconsistent with the decay-correction reference datetime".

- The cause is the Siemens private tag (0071,1022) = `20030322131023`, one day earlier than every
  standard date (SeriesDate 20030323). This is a de-identification date-shift inconsistency.
- VoxelTrace never uses private timing tags. Its strict path uses SeriesDate/Time,
  cross-validated by the earliest AcquisitionTime and by per-slice
  DecayFactor = 2^(FrameReferenceTime/T½).
- The external check therefore used a script-local SUV factor from standard tags. SEG decoding
  and SUVpeak remained fully third-party.
- Z-Rad's refusal is consistent with VoxelTrace's conservative philosophy.

## Not automated

- **3D Slicer** (PETDICOMExtension SUVFactorCalculator, PET-IndiC): there is no official Linux
  aarch64 build.
  - Manual procedure on x86_64 or macOS:
    1. Install the PETDICOMExtension, PET-IndiC and QuantitativeReporting extensions.
    2. Load PT with the "PET SUV" plugin and load the SEG.
    3. Run Segment Statistics with "PET Volume Segment Statistics".
    4. Export CSV.
  - Expected:
    - SUV factor 3.0448e-4 (SeriesTime rule);
    - identical SUVmax, SUVmean, volume and TLG;
    - SUVpeak a few percent different, because PET-IndiC uses partial-volume sphere weighting
      rather than the IBSI voxel-centre rule.
- **LIFEx**: closed-source freeware with an account requirement; aarch64 and batch mode
  unverified. Not used.
- **autoPET NIfTI SUV** (lab-midas TCIA_processing): uses AcquisitionTime from an arbitrary
  slice and ignores Units and DecayCorrection. On this multi-bed case its factor can be up to
  8.3 % higher than the DICOM-correct value. Usable only as a ratio check, not as a reference.
