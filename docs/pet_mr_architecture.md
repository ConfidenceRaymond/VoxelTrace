# PET/MR evidence architecture (future; planning only, 2026-10-09)

**Status:** no PET/MR rules are implemented. Whole-body PET/CT rules are unchanged. Stage
order: CURRENT PET/CT → NEXT multi-tracer PET/CT → THEN brain PET → **LATER PET/MR**.

## Evidence observed so far

| System | Where seen | Format |
|---|---|---|
| Siemens Biograph mMR | OpenNeuro ds001705, ds002898, ds003382, ds003397, ds004513, ds008786 (sidecars) | BIDS/NIfTI, not DICOM |
| Siemens BrainPET prototype insert | ds007135 | BIDS/NIfTI |
| United Imaging uPMR 790 | regulatory records only (FDA K183014 / K222540 / K234154); **NO_OPEN_DICOM_IDENTIFIED** | none |
| GE SIGNA PET/MR | not observed in open data examined | none |

## Planned evidence objects (each with value, status, trust level, source)

| Object | Fields | Why it matters for comparability |
|---|---|---|
| `MRACMethod` | method family (Dixon segmentation, atlas, UTE/ZTE, deep-learning pseudo-CT), vendor software version, bone handling | MRAC changes quantification; it must be identical across timepoints |
| `AttenuationMap` | series reference, hash, voxel grid, tissue classes or µ values | a changed µ-map means a changed quantification |
| `HardwareAttenuation` | coil and table templates included (which coils), template version | missing coil templates bias activity |
| `BoneRepresentation` | none / atlas / segmented / continuous | bone omission underestimates activity near bone |
| `TruncationCorrection` | method (MLAA, B0-homogenisation / HUGE, none), applied flag | arm truncation biases body uptake |
| `MotionCorrection` | MR-based / data-driven / none; frames affected | motion handling must match across timepoints |
| `PETMRRegistration` | inherent frame-of-reference vs post-hoc registration; residual QC | needed for MR-guided reference regions |
| `MRSequenceProvenance` | sequence name, TE/TR, field strength, coil | MR-derived ROIs depend on it |
| `LongitudinalMRACConsistency` | comparison of the above across timepoints → IDENTICAL / DIFFERENT / INSUFFICIENT_INFORMATION | the PET/MR analogue of VT-PROTOCOL-IDENTITY |

## Principles carried over

- **Missing evidence never equals identity.** An unknown MRAC method makes PET/MR identity
  INSUFFICIENT_INFORMATION.
- **Undocumented private tags are not interpreted.** Vendor MRAC details stay UNSUPPORTED
  until a conformance statement is read and cited.
- **Same core.** Ingestion, provenance, fingerprints (with the MRAC fields above as a new
  fingerprint version), drift, review gates and bundles are reused.
- **No United Imaging assumptions.** uPMR support requires a real DICOM export and its
  conformance statement.
