# Quantification: strict SUVbw, lesion metrics and evidence

> **RESEARCH PROTOTYPE. NOT FOR CLINICAL DIAGNOSIS.**
> Quantitative correctness has been validated **only for the implemented DICOM path** described
> below, using synthetic oracles and one public FDG PET/CT case (Siemens Biograph mCT). It is
> **not** validated for all vendor PET DICOM variants. Anything outside the supported path is
> refused.

Code: `src/voxeltrace/quant/{dicom_time,suv,lesions,evidence}.py`.
CLI: `scripts/quantify_case.py`.
UI: Streamlit page *Quantitative PET*.

## 1. Supported SUV path

SUVbw is computed only if **all** of the following hold:

| Requirement | DICOM | Rule |
|---|---|---|
| Activity units | `Units` (0054,1001) | `BQML` exactly |
| Decay-correction state | `DecayCorrection` (0054,1102) | `START` exactly (ADMIN and NONE are not implemented, so they are refused) |
| Corrections | `CorrectedImage` (0028,0051) | contains `ATTN` and `DECY` (a missing SCAT/RAN/DTIM/NORM gives a warning) |
| Radiopharmaceutical | `RadiopharmaceuticalInformationSequence` (0054,0016) | exactly one item |
| Patient weight | `PatientWeight` (0010,1030), kg | finite and > 0. Refused outside 1–500 kg (unit error); warning outside 20–300 kg |
| Injected activity | `RadionuclideTotalDose` (0018,1074), Bq | finite and > 0. Refused outside 1 MBq–100 GBq (unit error) |
| Half-life | `RadionuclideHalfLife` (0018,1075), s | finite and > 0. For F-18 (code C-111A1/77004003 or name) it must lie in 6570–6600 s. If the radionuclide is unidentified: warning |
| Injection time | `RadiopharmaceuticalStartDateTime` (0018,1078) / `…StartTime` (0018,1072) | see §3 |
| Scan reference time | Series and Acquisition Date/Time | see §3 |
| Pixel scaling | `RescaleSlope`/`RescaleIntercept` per slice | finite on every slice; slope > 0 |
| Consistency | all series-level fields above | identical on every slice |
| Geometry | IPP/IOP/PixelSpacing | valid, unambiguous, single-frame (Milestone 2 rules) |

## 2. Formula and units

```
C_PET[k,j,i]  = stored[k,j,i] × RescaleSlope_k + RescaleIntercept_k        Bq/mL
D_ref         = D_inj × 2^(−Δt / T½) = D_inj × exp(−ln2 · Δt / T½)         Bq
SUVbw[k,j,i]  = C_PET[k,j,i] × (W_kg × 1000) / D_ref                        g/mL
```

- Δt and T½ are in seconds.
- `suv_per_bqml = W_g / D_ref` has units of g/Bq.
- SUV is reported in g/mL. It is numerically "unitless" if tissue density is taken as
  1 g/mL.
- All arithmetic uses float64.
- Any non-finite intermediate or final value is refused.
- The SUV array is a new array aligned 1:1 with the PET volume (`[k, j, i]`, same geometry).
  The activity array is not modified.
- No CT information is used.
- No private vendor tags are used for the calculation.

## 3. Timing policy

One helper, `quant/dicom_time.py`, parses all DICOM date/time values.

- **DA** must be `YYYYMMDD`.
- **TM** must be `HHMMSS[.F{1,6}]`. Reduced precision (`HH`, `HHMM`) and the legacy
  `HH:MM:SS` form are rejected.
- **DT** must be `YYYYMMDDHHMMSS[.F{1,6}][&ZZXX]`.
- Fractional seconds are preserved.
- The helper never guesses a date.

**Scan reference time, T_ref (DecayCorrection = START).**
- DICOM defines the PET Series Date/Time as the reference for time-related PET attributes,
  including decay correction for START. VoxelTrace uses `SeriesDate+SeriesTime`, but **only if
  acquisition timing cross-validates it**:
  1. Compute the earliest acquisition datetime over **all** slices, from `AcquisitionDateTime`
     or from `AcquisitionDate+AcquisitionTime`. Every slice must parse.
  2. If |Series − earliest acquisition| ≤ 1 s, accept T_ref = SeriesDateTime.
  3. If Series is earlier than the earliest acquisition, accept it **only** if every slice's
     `FrameReferenceTime − (AcquisitionTime_k − Series)` lies in [−1 s, frame duration + 1 s].
     That is the check that FrameReferenceTime is measured from SeriesDateTime. A warning is
     recorded.
  4. If Series is later than the earliest acquisition (a post-processed series time), or the
     check in step 3 fails, **refuse**.
- Series Time is never used as a silent fallback. Its source and the cross-check are written to
  provenance.
- **Vendor decay-factor check.** If `FrameReferenceTime` and `DecayFactor` are present on every
  slice, VoxelTrace requires `DecayFactor = 2^(FrameReferenceTime / T½)` within a relative
  difference of 10⁻³. Otherwise it refuses (`DECAY_FACTOR_INCONSISTENT`). This independently
  confirms the vendor's reference time and half-life.

**Injection time, T_inj.**
- If `RadiopharmaceuticalStartDateTime` (DT) is present, use it. If
  `RadiopharmaceuticalStartTime` is also present, its time must equal the DT's time component;
  otherwise refuse (`INJECTION_TIME_CONFLICT`).
- If the DT carries a UTC offset, the series must have `TimezoneOffsetFromUTC`; otherwise
  refuse (`TIMEZONE_AMBIGUOUS`).
- If only the TM is present, use the documented rule:
  - T_inj = SeriesDate + TM.
  - If that is later than T_ref, the injection is taken to be on the **previous day** (midnight
    rule). This records `INJECTION_DATE_ROLLOVER` and is written to provenance.
  - Otherwise `INJECTION_DATE_FROM_SERIES` is recorded.
- Midnight with full dates (DT) needs no rule; it is handled by datetime arithmetic.

**Interval.** Δt = T_ref − T_inj.
- Refuse if Δt < 0.
- Refuse if Δt > 12 h.
- Warning if Δt < 60 s (possible dynamic scan).

## 4. Rescale policy

- The modality LUT is applied **per slice**: stored × RescaleSlope_k + RescaleIntercept_k.
  Slopes are never assumed constant (the real Siemens case has 326 distinct slopes).
- The volume loader keeps per-slice SOP UIDs, slopes and intercepts in volume order.
- SUV is refused (`RESCALE_AUDIT_MISMATCH`) if the factors used for the pixels differ from the
  audited headers.
- `suv_result.json → rescale.per_slice` lists (k, SOPInstanceUID, slope, intercept) for every
  slice.

## 5. Refusal policy

Refusals are structured (`SUVRefusalReason{code, message, field}`), never bare exceptions.
Codes include:

| Area | Codes |
|---|---|
| Units | `MISSING_UNITS`, `UNSUPPORTED_UNITS` |
| Decay correction and corrections | `MISSING_DECAYCORRECTION`, `UNSUPPORTED_DECAY_CORRECTION`, `MISSING_CORRECTION` |
| Weight | `MISSING_/INVALID_/NONPOSITIVE_/IMPLAUSIBLE_PATIENTWEIGHT` |
| Dose | `MISSING_/INVALID_/NONPOSITIVE_/IMPLAUSIBLE_RADIONUCLIDETOTALDOSE` |
| Half-life | `MISSING_/INVALID_/NONPOSITIVE_RADIONUCLIDEHALFLIFE`, `HALF_LIFE_RADIONUCLIDE_MISMATCH` |
| Radiopharmaceutical | `RADIOPHARMACEUTICAL_ITEMS` |
| Injection timing | `MISSING_INJECTION_TIME`, `INVALID_INJECTION_TIME`, `INJECTION_TIME_CONFLICT` |
| Scan timing | `INVALID_SERIES_DATETIME`, `INVALID_ACQUISITION_DATETIME`, `TIMEZONE_AMBIGUOUS`, `INVALID_TIMEZONE`, `SERIES_TIME_AFTER_ACQUISITION`, `SCAN_REFERENCE_AMBIGUOUS` |
| Interval | `NEGATIVE_DECAY_INTERVAL`, `IMPLAUSIBLE_DECAY_INTERVAL` |
| Vendor decay | `DECAY_FACTOR_INCONSISTENT` |
| Rescale | `MISSING_RESCALE`, `NONPOSITIVE_RESCALE_SLOPE`, `RESCALE_AUDIT_MISMATCH` |
| Consistency | `INCONSISTENT_<FIELD>` |
| Pixels and geometry | `GEOMETRY`, `PIXELS_NOT_LOADED`, `NONFINITE_SUV` |

## 6. Lesion definitions (supplied segmentation only)

- **Segment**: one DICOM SEG segment, decoded strictly onto the PET grid (Milestone 2).
  Metrics are computed per segment number. Multiple segments yield `list[LesionMetrics]` and a
  separate `LesionSummary`.
- **Components**: 26-connected components inside each segment (SimpleITK). They are reported
  per component (voxels, volume, SUVmax, SUVmean). Segment-level metrics pool all components,
  and a warning says so.
- **Voxel volume**: Δi × Δj × Δk / 1000 mL. Uniform slice spacing is required.
- **MTV**: physical volume of the **supplied** segment mask. No thresholding and no automatic
  segmentation.
- **SUVmin/max/mean/median/SD (ddof = 0)/p10/p25/p75/p90**: over voxels in the segment.
- **TLG = MTV [mL] × SUVmean [g/mL]**, in grams. It is based on the supplied segmentation and
  is not comparable with TLG from threshold-defined volumes.

## 7. SUVpeak (implemented, explicit definition)

This follows the QIBA FDG-PET/CT Profile and PERCIST ("maximum average SUV within a 1 cm³
spherical volume") and the IBSI voxel-centre inclusion rule.

| Aspect | Definition |
|---|---|
| Sphere volume | **1.0 cm³**. This is **not** a 1 cm diameter sphere (0.52 cm³) |
| Radius | r = (3 / 4π)^⅓ cm = **6.2035 mm** |
| Voxels in sphere | every image voxel whose **centre** is within r of the candidate centre, using physical mm with anisotropic spacing |
| Restriction to lesion | **none**. Sphere voxels may lie outside the segment; the fraction inside is reported |
| Centre search | exhaustive over **every voxel centre inside the segment**. No sub-voxel positions |
| Edge handling | candidates whose sphere would extend beyond the image are **excluded** (no padding). If none remain, the status is `NOT_AVAILABLE` |
| Value | maximum of the sphere means over the candidates |
| Discretisation | `kernel_voxel_count` and the effective volume are reported. Example: 73 voxels = 0.908 mL at 2.036 × 2.036 × 3 mm |
| Small lesions | if MTV < 1 mL, a warning `SEGMENT_SMALLER_THAN_PEAK_SPHERE` is recorded |

## 8. Evidence object (`QuantEvidence`, JSON)

- **MEASURED**: SUV status, SUV-volume statistics, per-segment lesion metrics and SUVpeak, and
  the lesion summary.
- **PROVENANCE**:
  - dataset and subject pseudonym;
  - PET and SEG SeriesInstanceUIDs;
  - quantitative inputs, each with its DICOM tag, per-slice consistency and source;
  - scale factors;
  - calculation version (`suvbw-strict-1`), VoxelTrace version, git commit and dirty flag;
  - assumptions and references.
- **WARNINGS**: metadata anomalies, geometry notes and unsupported features.
- **NOT_ESTABLISHED**: diagnosis, histology, treatment response, prognosis, lesion malignancy,
  and the clinical significance of any measurement.

Outputs go to `../outputs/<subject>/`:
- `suv_input_audit.json`
- `suv_result.json` or `suv_refusal.json`
- `lesion_metrics.json`
- `evidence.json`
- `quantitative_summary.txt`

Patient identifiers (name, ID, birth date, sex, age, accession) are never read into these files.

## 9. Unsupported (refused or not implemented)

- `DecayCorrection` ADMIN or NONE.
- Units other than BQML: CNTS, GML, PROPCPS (Philips SUV scale factors) and similar.
- Series time rewritten by post-processing without FrameReferenceTime confirmation. GE private
  scan-start tags are not used.
- Multiple radiopharmaceutical items.
- Dynamic or multi-frame (Enhanced) PET.
- Mixed-timezone timing.
- SUVlbm, SUVbsa and other normalisations.
- Threshold-based MTV and automatic segmentation.
- Partial-volume correction.
- FRACTIONAL SEG.
