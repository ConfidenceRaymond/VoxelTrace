# SUV requirements

> **Status: implemented in Milestone 3** (`src/voxeltrace/quant/suv.py`, calculation version
> `suvbw-strict-1`). The exact implemented policy, including the timing rules, is in
> [quantification.md](quantification.md). Where the implementation is stricter than this
> original plan, the implementation applies:
> - `DecayCorrection` **ADMIN and NONE are refused** (not implemented), rather than handled.
> - The scan reference time is the PET Series Date/Time. It is accepted only when it agrees
>   with the earliest acquisition time (≤ 1 s), or when per-slice FrameReferenceTime confirms
>   it. Otherwise SUV is refused.
> - The vendor `DecayFactor`, when present, must equal 2^(FrameReferenceTime/T½) within 10⁻³.
> - Implausible dose (outside 1 MBq–100 GBq) and implausible weight (outside 1–500 kg) are
>   **refused** as probable unit errors. Weight outside 20–300 kg is a warning.

This document defines what VoxelTrace requires before computing body-weight SUV (SUVbw), and
when it must **refuse**.

SUVbw = C(t) / (D_inj · 2^(−Δt / T½) / W)

with C(t) the decay-corrected activity concentration, D_inj the injected activity, Δt the time
from injection to the decay-correction reference, T½ the radionuclide half-life, W the body
weight. All quantities come from headers; nothing is defaulted, guessed or user-"assumed".

## Required inputs

| Input | DICOM source | Requirement |
|---|---|---|
| Activity concentration units | `Units` (0054,1001) | Must be `BQML`. Other values (`CNTS`, `GML`, `PROPCPS`, …) → refuse (no silent conversion). |
| Pixel scaling | `RescaleSlope`, `RescaleIntercept` per instance | Present and finite on **every** slice; applied per slice. Per-slice slopes are allowed. |
| Patient weight | `PatientWeight` (0010,1030), kg | Present, finite, > 0. Plausibility range check (e.g. 20–300 kg) → warning, never edited. |
| Injected dose | `RadionuclideTotalDose` (0018,1074), Bq | Present, finite, > 0. Plausibility check against radionuclide (e.g. FDG 37–1000 MBq) → warning. |
| Radionuclide half-life | `RadionuclideHalfLife` (0018,1075), s | Present, finite, > 0. Cross-check with radionuclide code/name (F-18 ≈ 6586–6588 s); mismatch → refuse. |
| Injection time | `RadiopharmaceuticalStartDateTime` (0018,1078) preferred; else `RadiopharmaceuticalStartTime` (0018,1072) + a date | Must resolve to a full datetime. Time-only with no unambiguous date → refuse. |
| Decay-correction reference time | `DecayCorrection` (0054,1102) + `SeriesDate/SeriesTime` (START) or per-frame `AcquisitionDateTime`/`FrameReferenceTime` (ADMIN/NONE handling) | `START` → reference = series start. `ADMIN` → already corrected to injection, Δt = 0. `NONE` → refuse unless per-slice acquisition times allow explicit correction (later). |
| Correction state | `CorrectedImage` (0028,0051) | Must include `ATTN` and `DECY`; otherwise refuse. |
| Radiopharmaceutical | `RadiopharmaceuticalInformationSequence` | Exactly one item, or refuse (multiple tracers ambiguous). |

## Refusal cases (SUV must not be produced)

1. Any required field absent, empty, non-numeric, NaN/inf, or ≤ 0.
2. `Units` ≠ `BQML`.
3. Required field inconsistent across slices of the series (weight, units, dose, times, decay correction).
4. Injection datetime after the decay-correction reference time, or Δt > ~24 h for F-18 (likely date error).
5. Injection time without an unambiguous date (e.g. crossing midnight with only TM values).
6. `DecayCorrection` = `NONE` or unknown value.
7. `CorrectedImage` lacks `ATTN` or `DECY`.
8. Half-life inconsistent with the declared radionuclide.
9. Vendor private-tag dependence (e.g. Philips SUV scale factors, GE private decay data) without an explicit, tested vendor rule → refuse rather than guess.
10. More than one radiopharmaceutical item.
11. Geometry QC errors (duplicate/missing slices) for the series.

## Output contract (implemented)

The SUV result (`SUVResult`) and the `QuantEvidence` object carry every input value used, its
DICOM tag and per-slice consistency, the timing sources, the computed decay factor and scale
factor, the per-slice rescale factors, and all warnings. Each number can therefore be audited,
and the AI layer can cite these numbers but not alter them.
