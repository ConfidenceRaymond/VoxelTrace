# Protocol comparability

`compare_protocols(protocol_a, protocol_b)` returns a `ComparabilityAssessment`
(`src/voxeltrace/evidence/comparability.py`).

**It assesses protocol comparability only.** It never establishes biological change, treatment
response or any clinical conclusion.

## Checks

| Check | Impact | Rule |
|---|---|---|
| tracer (radiopharmaceutical code, else name) | blocking | exact match (case and whitespace normalised) |
| radionuclide | blocking | exact |
| manufacturer, scanner model | blocking | exact |
| software version | warning | exact |
| image units, decay-correction state | blocking | exact |
| correction state (ATTN, SCAT, RAN, DECY, NORM, DTIM) | blocking | identical applied sets |
| uptake interval | blocking | \|ΔB−A\| ≤ 600 s (QIBA FDG-PET/CT Profile: follow-up within ±10 min of baseline) |
| injected activity | warning | ≤ 20 % relative (activity changes noise, not SUV calibration) |
| frame (bed) duration | warning | ≤ 1 % relative |
| voxel size (i, j, k) | blocking | ≤ 0.01 mm per axis |
| matrix rows and columns | info | exact |
| slice thickness | warning | exact |
| ReconstructionMethod text | blocking | exact |
| iterations, subsets, TOF, PSF | blocking if they differ; warning if unknown | an identical ReconstructionMethod text on both scans counts as SAME |
| post-filter (ConvolutionKernel) | blocking if it differs; warning if unknown | exact |
| reconstruction diameter | info | exact |

## Categories

Rules are applied in this order:

1. **NOT_COMPARABLE**: any blocking check is `DIFFERENT`.
2. **INSUFFICIENT_INFORMATION**: any blocking check is `UNKNOWN`.
3. **COMPARABLE_WITH_WARNINGS**: any warning-level check is `DIFFERENT` or `UNKNOWN`.
4. **COMPARABLE**: none of the above.

- `WITHIN_TOLERANCE` (for example an uptake difference of 5 min) does not create a warning.
- **Tolerances** are VoxelTrace defaults. Only the uptake tolerance comes from a published
  profile (QIBA). The others are conservative engineering choices and should be reviewed for
  any specific study.
- **Reconstruction differences are blocking:** reconstruction method, iterations/subsets, TOF,
  PSF, filter and voxel size are all known to change SUVmax and SUVpeak. Harmonisation (for
  example EARL) is not modelled, so such differences are not "corrected away".
