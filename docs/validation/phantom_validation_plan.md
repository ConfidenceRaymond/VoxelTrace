# Vendor-neutral phantom validation plan for VoxelTrace

**Purpose:** validate VoxelTrace's quantitative-input handling and provenance logic against
physical ground truth, independently of disease, readers and patient metadata. It tests
VoxelTrace (does it read, refuse and compare correctly?), not the scanner. This is an
internal validation protocol; **it is not accreditation** (e.g. not EARL or ACR) and its
results must not be described as such.

## 1. Phantoms

| Phantom | Use |
|---|---|
| Uniform cylinder (e.g. ~6–20 L water, known volume) | activity-concentration recovery, decay-reference semantics, calibration chain |
| NEMA NU 2 / IEC 61675-1 body phantom (6 spheres, 10–37 mm; 4:1 or 10:1 sphere:background) | reconstruction-dependent recovery; protocol-difference detection (the quantity VoxelTrace's comparability rules protect) |

## 2. Activity documentation (per fill)

Recorded on a fill sheet, signed by the physicist, with no patient data:
- dose-calibrator model, calibration date, F-18 setting;
- syringe activity before and after (residual), each with **clock time and timezone**;
- phantom net volume (by weight, g → mL) and fill time;
- expected activity concentration at the calibration time (kBq/mL);
- scanner clock offset vs. dose-calibrator clock (measured, seconds).

Ground truth = (syringe − residual) / volume, decay-corrected to the reference time with
T½ = 6586.2 s (F-18). Stated uncertainty: dose calibrator ±5 % unless the site's own
measured value is available.

## 3. Acquisition and timing

- Start ~60 min after calibration (mimics FDG uptake), plus one later acquisition
  (~120–180 min) on the same fill to test decay handling across time.
- Clinical whole-body protocol (≥ 2 bed positions, so per-bed DecayFactor/FrameReferenceTime
  behaviour is visible) and, optionally, a single-bed acquisition.
- Record: acquisition start, frame durations, beds.

## 4. Scanner models

At least one per vendor family of interest, prioritised by the gap analysis:
GE (Discovery MI / Omni / 690/710; Discovery STE/LS if still in trial use),
Philips (Vereos / Vereos Digital / GEMINI TF), and one Siemens Biograph mCT or Vision as the
reference arm (already PAIR_VALIDATED on patient data). Record model and **software version**.

## 5. Reconstruction variants (same raw data, reconstructed several ways)

| Variant | Purpose |
|---|---|
| R0: the site's clinical trial protocol | baseline |
| R1: R0 with a different iteration count | must be detected as protocol change (DIFFERENT iterations) |
| R2: R0 with a different post-filter | DIFFERENT filter_kernel |
| R3: R0 without TOF (if available) | DIFFERENT time_of_flight |
| R4: R0 without PSF / resolution modelling (if available) | DIFFERENT psf_resolution_modelling |
| R5: EARL-harmonised reconstruction (if the site has one) | harmonization field |
| R6: a second export of R0 through the trial anonymizer | must be IDENTICAL protocol to R0 |

## 6. Metadata capture

Export every variant as DICOM through (a) the scanner/PACS export and (b) the trial
anonymizer. Keep the scanner protocol printout or console screenshot for each variant (no
patient data). VoxelTrace runs `intake-map`, `validate-input`, `preflight` and `audit`
with the phantom as one "subject" and each acquisition/variant as a "timepoint".

## 7. Expected comparisons

| Comparison | Expected VoxelTrace result |
|---|---|
| Strict SUV inputs of R0 (both exports) | PASS, or a refusal whose reason matches the headers exactly |
| Mean activity concentration in a large central VOI (uniform phantom) | within ±10 % of ground truth (PROVISIONAL; widen to the site's stated calibration uncertainty if larger) |
| DecayFactor vs FrameReferenceTime per bed | either verified, or the discrepancy explained by the vendor's documented decay reference |
| Early vs late acquisition, same fill | decay-corrected concentrations agree within ±5 % (PROVISIONAL) |
| R0 vs R1–R5 | `VT-PROTOCOL-IDENTITY` FAIL / DIFFERENT for the changed field, or UNKNOWN with the missing field named; **never PASS** |
| R0 vs R6 | identical protocol fingerprint (anonymizer does not destroy evidence), or the stripped fields named |

## 8. Failure-injection cases (on copies of the phantom DICOM)

Each must give the stated refusal/verdict and never ASSESSABLE:
remove RadionuclideTotalDose; set Units = CNTS; set DecayCorrection = ADMIN; remove ATTN from
CorrectedImage; shift injection time by +24 h and by −1 h; change RadionuclideHalfLife to
another isotope; remove SoftwareVersions on one timepoint; change iterations in
ReconstructionMethod text on one timepoint; give two series the same SeriesInstanceUID under
two timepoints (pairing audit BLOCKING); set PatientWeight = 0.
(The existing synthetic failure-injection suite already covers these on synthetic data:
`../failure_injection_coverage.md`; the phantom repeats them on real vendor encodings.)

## 9. Acceptance criteria (PROVISIONAL until reviewed by an independent physicist)

1. **Zero false-safe results:** no failure-injection case and no R0-vs-R1…R5 comparison is
   ASSESSABLE / ASSESSABLE_WITH_WARNINGS.
2. Every refusal names the correct attribute.
3. Activity-concentration recovery within the stated tolerance on every model where strict SUV
   passes, or a documented reason for refusal.
4. Results reproducible: two runs give the same evidence-bundle checksums.
5. Any new vendor path (e.g. GE decay reference) is added only as a new, versioned,
   model/software-specific check backed by the vendor document **and** this phantom result,
   with regression tests; the strict path is never relaxed.

## 10. Limitations

- A phantom tests quantitation and provenance handling, not patient-specific timing,
  anonymizer behaviour on clinical records, or biological variability.
- Recovery depends on reconstruction; the acceptance tolerances are PROVISIONAL and not EARL or
  ACR limits.
- One site and one software version per run; results do not transfer to other versions.
- A phantom alone can raise a model at most to QUANT_VALIDATED; PAIR_VALIDATED still needs real
  longitudinal pairs, and EXPERT_VALIDATED needs independent reviewers.

## 11. Output

Per model/software: a one-page result (pass/fail per criterion, measured vs expected), the
evidence bundle, and an update to `../vendor_validation_matrix.md` (at most QUANT_VALIDATED
from a phantom; PAIR_VALIDATED still needs patient pairs).
