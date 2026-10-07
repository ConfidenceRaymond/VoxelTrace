# Protocol evidence (scanner, acquisition, corrections, QC)

Code: `src/voxeltrace/evidence/{scanner,acquisition,corrections,protocol}.py`.

- **Inputs:** header-only. No pixel data is read.
- **Attributes:** standard DICOM attributes only. Vendor-private tags are not parsed.
- **No inference:** a value that is not recorded is reported as `MISSING` and never filled in.

## EvidenceField

Every protocol fact is an `EvidenceField`:

| Attribute | Meaning |
|---|---|
| `status` | `PRESENT`, `MISSING`, `PRESENT_BUT_AMBIGUOUS` or `UNSUPPORTED` |
| `value` / `unit` | the value exactly as recorded, converted only to a number or list |
| `source` | the DICOM tag(s) or the derivation rule |
| `derivation` | `standard_tag`, `standard_enumeration`, `free_text_pattern`, `derived_from_geometry`, `derived_from_timing` or `validated_suv_input` |
| `n_distinct_across_slices` | how many distinct values appear across slices |

`PRESENT_BUT_AMBIGUOUS` is used when any of these applies:
- the value cannot be converted to the expected type;
- the value is present on only some slices;
- the value varies across slices where it should be constant;
- the value is derived from a convention whose meaning DICOM does not state (for example a
  Gaussian width with no unit, or a bed duration that assumes one frame per bed).

## Scanner (`ScannerEvidence`)

- **Fields:** Modality, SOPClassUID, FrameOfReferenceUID, Manufacturer, ManufacturerModelName,
  SoftwareVersions, MagneticFieldStrength (PET/MR), CollimatorType, CountsSource,
  AxialAcceptance, AxialMash, and the energy window (lower and upper, keV).
- **Identifying attributes:** DeviceSerialNumber, StationName, InstitutionName,
  InstitutionAddress and InstitutionalDepartmentName are **never copied**.
  `identifying_attributes_recorded` lists only the *names* of the ones present.

## Acquisition (`AcquisitionProtocol`)

- **Tracer:**
  - tracer (`Radiopharmaceutical`);
  - radiopharmaceutical and radionuclide `CodeMeaning`;
  - injected activity in Bq, as recorded.
- **Timing:** injection datetime, uptake interval, reference time and acquisition start come
  **only from the strict Milestone 3 SUV timing validator** (`validated_suv_input`). If that
  validator refused, they are `MISSING` and the refusal codes are listed.
- **Durations:**
  - `AcquisitionDuration` (0018,9073), when present.
  - `frame_duration_ms` (ActualFrameDuration).
  - `bed_duration_s`: `PRESENT_BUT_AMBIGUOUS`, because it assumes one frame per bed in a
    static or whole-body series.
  - `acquisition_time_span_s` = latest − earliest slice acquisition start + one frame
    duration. `PRESENT_BUT_AMBIGUOUS`, because bed overlap and gaps are not resolved.
- **Bed positions:** `number_of_bed_positions` is always `MISSING`. It is not encoded in
  standard attributes, and the private data that might hold it is not parsed.
- **Series type:** SeriesType, and the temporal type taken from `SeriesType[0]` (STATIC,
  DYNAMIC, WHOLE BODY or GATED) as an `is_dynamic` flag.
- **Other fields:** NumberOfTimeSlices, NumberOfSlices, matrix, pixel spacing, slice spacing
  and axial coverage (both from geometry), PatientPosition, patient orientation and
  gantry-relationship code meanings, BodyPartExamined, Units, DecayCorrection.

## Corrections (`CorrectionEvidence`)

- **`CorrectedImage` (0028,0051)** is kept exactly. DICOM defines it as the list of corrections
  that **have** been applied, so:
  - if the attribute is present, an unlisted correction is `False` ("not declared applied");
  - if the attribute is absent, every correction is `MISSING` (unknown), never `False`.
- **Structured attributes take precedence when present.** Enhanced-PET YES/NO attributes
  (AttenuationCorrected, ScatterCorrected, RandomsCorrected, DecayCorrected,
  DetectorNormalizationCorrection, DeadTimeCorrected, SensitivityCalibrated), at top level or
  in PETReconstructionSequence, override the flags.
- **Also recorded:**
  - AttenuationCorrectionMethod, ScatterCorrectionMethod, RandomsCorrectionMethod;
  - DoseCalibrationFactor, ScatterFractionFactor, DeadTimeFactor, SliceSensitivityFactor
    (per-slice variation allowed);
  - other DICOM flags (UNIF, MOTN, DCAL, …) and unknown flags.

## Protocol QC (`ProtocolQC`)

- **Never fails a whole case.** Each gap is mapped to the downstream uses it blocks: `suv`,
  `lesion_metrics` or `cross_scan_comparison`.

| Code | Blocks |
|---|---|
| `MISSING_SCANNER_MODEL`, `MISSING_MANUFACTURER`, `MISSING_RECONSTRUCTION_ALGORITHM`, `MISSING_TRACER` | cross-scan comparison |
| `MISSING_VOXEL_SIZE` | lesion metrics, comparison |
| `MISSING_CORRECTIONS`, `MISSING_UPTAKE_TIME` | SUV, comparison |
| `MISSING_DOSE`, `MISSING_UNITS` | SUV |
| `MISSING_ITERATIONS/SUBSETS/TOF/PSF/FILTER/RECONSTRUCTION_DIAMETER`, `MISSING_SOFTWARE_VERSION` | nothing (informational) |
| `MISSING_ACQUISITION_DURATION` | nothing (warning) |
| `AMBIGUOUS_<FIELD>` | nothing (warning, one per ambiguous field) |
| `FREE_TEXT_DERIVED` | nothing (info, one per value parsed from vendor free text) |
| `PRIVATE_RECONSTRUCTION_METADATA_UNSUPPORTED` | nothing. Info level; a warning if `ReconstructionMethod` is missing, because details may then exist only in private tags |
| `UPTAKE_OUTSIDE_QIBA_WINDOW` | nothing (warning if the uptake is outside 55–75 min) |

- **Strict SUV refusal:** if the strict SUV validator refused, `suv` and `lesion_metrics` are
  marked unusable.
