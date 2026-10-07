# Reconstruction evidence

Code: `src/voxeltrace/evidence/reconstruction.py`.

## Precedence

1. **Structured standard attributes:**
   - NumberOfIterations (0018,9739)
   - NumberOfSubsets (0018,9740)
   - TimeOfFlightInformationUsed (0018,9755)
   - ReconstructionAlgorithm (0018,9315)
   - ReconstructionType (0018,9756)

   These are read at top level or inside PETReconstructionSequence (0018,9749).
2. **Documented patterns in the free text** of two standard attributes,
   ReconstructionMethod (0054,1103) and ConvolutionKernel (0018,1210):

| Pattern | Result | Status |
|---|---|---|
| `<N>i<M>s` (e.g. `2i21s`) | iterations N, subsets M | PRESENT (`free_text_pattern`). Several different matches: PRESENT_BUT_AMBIGUOUS |
| token `TOF` | time-of-flight used | PRESENT (`free_text_pattern`) |
| token `PSF` or `TrueX` | PSF / resolution modelling used | PRESENT (`free_text_pattern`) |
| `FBP`, `OSEM`/`OP-OSEM`, `BSREM`/`Q.Clear`, `RAMLA` | algorithm family | PRESENT. Conflicting tokens: PRESENT_BUT_AMBIGUOUS |
| `Gauss<w>` | Gaussian post-filter width w | **PRESENT_BUT_AMBIGUOUS**: the unit and the FWHM-vs-sigma convention are not stated in DICOM |

   **Patterns only assert positives.** If "TOF" is not in the text, TOF is `MISSING`
   (unknown), **never `False`**. Likewise, OSEM is not inferred from "PSF+TOF 2i21s".
3. **Vendor-private tags are not parsed.** Their private creator strings (never their values)
   are listed in `unsupported_private_metadata`.

## Other fields

- SeriesDescription, ConvolutionKernel (raw), FilterType, ReconstructionDiameter.
- Matrix rows and columns.
- Voxel size (i, j, k) from geometry.
- SliceThickness and SpacingBetweenSlices, as tags.
- SoftwareVersions.

## Real case (PETCT_0011f3deaf, Siemens Biograph128_mCT, VG60A)

| Field | Value | Status / source |
|---|---|---|
| ReconstructionMethod | `PSF+TOF 2i21s` | PRESENT (0054,1103) |
| iterations / subsets | 2 / 21 | PRESENT, free-text pattern |
| TOF / PSF | True / True | PRESENT, free-text pattern (so claims are at most PARTIALLY_SUPPORTED) |
| algorithm family | — | MISSING (not stated in the text) |
| ConvolutionKernel | `XYZ Gauss2.00` | PRESENT (0018,1210) |
| Gaussian width | 2.0 | PRESENT_BUT_AMBIGUOUS (unit not stated) |
| ReconstructionDiameter, FilterType, ReconstructionType, SpacingBetweenSlices | — | MISSING |
| matrix / voxel size | 400×400 / 2.036 × 2.036 × 3.0 mm | PRESENT |
| private creators | SIEMENS CSA HEADER, SIEMENS MED PT, GEIIS, GEIIS PACS, CTP | UNSUPPORTED (not parsed) |
