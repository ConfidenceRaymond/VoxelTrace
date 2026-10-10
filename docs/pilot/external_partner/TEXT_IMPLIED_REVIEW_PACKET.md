# TEXT_IMPLIED review packet: first scientific adjudication question

**For:** the partner's PET physicist. **Status:** open question. **Rule behaviour is unchanged**
by this packet; your answers inform a possible future, separately versioned rule change.

## The question

> When a reconstruction parameter (iterations, subsets, time-of-flight, PSF / resolution
> modelling) is **not encoded** in DICOM at one or both timepoints, may two scans be treated as
> having the **same** value because their `ReconstructionMethod` text is identical?

## Current interpretation (VT-PROTOCOL-IDENTITY v1)

- If a parameter is encoded at both timepoints, the values are compared directly.
- If it is not, and the `ReconstructionMethod` text is identical on both scans, VoxelTrace
  counts the parameter as SAME (a "text-implied" identity, trust LEVEL_D or lower).
- Different texts are never treated as identical (a changed text → identity FAIL).
- The post-filter (`ConvolutionKernel`) must be known; otherwise identity is UNKNOWN.
- Since 0.4.0 every such pair is labelled `reconstruction_evidence = TEXT_IMPLIED: <parameters>`
  in `pair_results.csv`, and the limitation is stated in every package's methodology.
  (Source: `src/voxeltrace/evidence/comparability.py`; risk FS-01 in
  `docs/validation/false_safe_risk_register.md`; pinned by `tests/test_false_safe_register.py`.)

## Why it matters

The rule protects against comparing SUVs from different reconstructions (iterations, TOF and
PSF change SUVmax/SUVpeak). If a site changed a parameter without changing the method text, the
change would be invisible and the pair could be reported `ASSESSABLE`: a **false-safe** result.
Conversely, refusing every pair with an unencoded parameter would turn many comparable
pairs into `INSUFFICIENT_INFORMATION` (false-unsafe).

How informative the text is depends on the vendor: Siemens texts such as `PSF+TOF 2i21s`
encode iterations, subsets, PSF and TOF; a generic text such as `OSEM` encodes none of them.

## Examples from existing validation (real public data)

| Pair | Scanner | Text (both timepoints) | Not encoded | Verdicts | Comment |
|---|---|---|---|---|---|
| **CCTH-B02** (CC-Tumor-Heterogeneity) | Siemens Biograph64, `syngo MI.PET/CT 2011A` (same at both) | `PSF 3i24s` | **time_of_flight** | QIBA `ASSESSABLE`; EANM `ASSESSABLE_WITH_WARNINGS`; PERCIST `INSUFFICIENT_INFORMATION` (review pending) | iterations 3, subsets 24, PSF parsed from the text (LEVEL_D); TOF is absent from the text and from DICOM, and judged SAME only through text identity; filter `XYZ Gauss4.00` structured |
| PETCT_c2ffda4725 (FDG-PET-CT-Lesions), for contrast | Siemens Biograph128 mCT, VG60A | `PSF+TOF 2i21s` | none | QIBA `ASSESSABLE` | all parameters parsed from the text (`FREE_TEXT`), not text-implied |
| Synthetic test (FS-01) | GE-like, `OSEM` | `OSEM` | iterations, subsets, TOF, PSF | identity PASS | demonstrates the risk with a generic text; synthetic, not real data |

In the 9-pair real cohort, 21 of 27 pair × rule-set rows carry TEXT_IMPLIED; only 2 of those
(CCTH-B02, QIBA and EANM) are `ASSESSABLE*`. The others are already `NOT_ASSESSABLE` or
`INSUFFICIENT_INFORMATION` for other reasons.

## Expert feedback needed

- **Q1.** For CCTH-B02: from your knowledge of the Biograph64 and of `PSF 3i24s` exports, is the
  TOF state of both scans determined (e.g. the system has no TOF capability, or the text would
  read `PSF+TOF` if TOF were used)? Would you accept the pair as comparable under QIBA?
  Yes / No / Need site protocol.
- **Q2.** For Siemens texts of the form `[PSF][+TOF] <n>i<m>s`: is the absence of `TOF` in the
  text sufficient evidence that TOF was off? On which systems / software versions?
- **Q3.** For generic texts (e.g. `OSEM`, `3D IR`, `VPFX`): should identical text ever imply
  identical iterations/subsets/TOF/PSF? Yes / No / Only with site documentation.
- **Q4.** Which evidence would you accept instead: site protocol sheet, console screenshot,
  signed attestation, vendor documentation?
- **Q5.** In your own datasets, how often do you expect reconstruction parameters to be
  unencoded, and how often do sites change them between visits?

## Possible future policy outcomes (none adopted)

| Option | Effect |
|---|---|
| A. Keep v1, keep the TEXT_IMPLIED flag | current behaviour; physician review of flagged pairs |
| B. Text implies only parameters the text actually encodes (vendor-specific grammar); otherwise UNKNOWN | fewer false-safe risks; CCTH-B02 would become INSUFFICIENT_INFORMATION unless Q1/Q2 support a documented Siemens rule |
| C. Text-implied identity downgrades the verdict to `ASSESSABLE_WITH_WARNINGS` | visible caveat without refusing |
| D. Text-implied identity only with a documented vendor dictionary or site attestation | strictest |

Any change would be a **new rule version** (VT-PROTOCOL-IDENTITY v2) with regression tests,
introduced after the blinded external validation (the frozen validation package at tag
`v0.3.0-external-validation` must keep its answers), and announced to partners.

## Your answer

| | Answer | Basis (experience / document / site protocol) |
|---|---|---|
| Q1 | | |
| Q2 | | |
| Q3 | | |
| Q4 | | |
| Q5 | | |
| Preferred option (A–D or other) | | |

Reviewer role: `<...>` · Date: `<...>`
