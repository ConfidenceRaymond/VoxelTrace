# Trial comparability audit

Code: `src/voxeltrace/trial/`, `src/voxeltrace/vendors/`, `quant/sul.py`,
`quant/reference_region.py`. Demo: `scripts/build_trial_demo.py`.

The audit moves from one scan to **subject × timepoint × site**. It is deterministic and uses no
AI. **It does not assess biological or treatment response.**

## Layers (no renaming)

| Layer | States | Meaning |
|---|---|---|
| `ComparabilityAssessment` (protocol) | COMPARABLE / COMPARABLE_WITH_WARNINGS / NOT_COMPARABLE / INSUFFICIENT_INFORMATION | VoxelTrace engineering comparison of two protocols, including the QIBA uptake tolerance |
| `PairAssessabilityResult` (trial) | ASSESSABLE / ASSESSABLE_WITH_WARNINGS / NOT_ASSESSABLE / INSUFFICIENT_INFORMATION | whether a baseline/follow-up pair is assessable under **one selected, versioned rule set** |

The protocol category is reported alongside the trial verdict. The two concepts differ, so a
PERCIST audit can be INSUFFICIENT_INFORMATION (no liver region) while the protocols are
COMPARABLE.

## Inputs

```
<trial>/trial.yaml                    trial_id, ruleset, timepoint_order, sites,
                                      [parameter_overrides, disabled_rules, site_flags,
                                       reference_regions, synthetic_perturbations]
<trial>/<subject>/<timepoint>/...     DICOM (symlinks followed; originals read-only)
```

## What each timepoint provides (`trial/timepoint.py`)

- Strict SUVbw: status, uptake, weight.
- Lesion SUVpeak, from the supplied SEG.
- Protocol evidence.
- SUL under LBMJAMES128 and LBMJANMA. Missing anthropometrics give `ANTHROPOMETRICS_MISSING`.
- Liver and blood-pool reference regions ([reference_regions.md](reference_regions.md)):
  - a supplied mask or centre; or
  - a deterministic CT-guided proposal (`vt-refauto-1`), which is used only after a human
    ACCEPT/ADJUST review bound to its `proposal_sha256`.
  - Otherwise the status is a specific code such as `REFERENCE_REVIEW_REQUIRED` or
    `REFERENCE_AUTO_NOT_FOUND`.
- An anonymization-loss audit.

## Insufficient-information taxonomy (`trial/reasons.py`)

- Every reason states what is missing, why it matters, whether the site can fix it, and how.
- Causal codes carry a confidence and an evidence basis:
  - **NEVER_ENCODED (PROBABLE)** only when a declared PS3.15 retention option covers the absent
    attribute (E.3.7 patient characteristics, E.3.8 device identity).
  - **STRIPPED_BY_ANONYMIZATION** only when there is an explicit removal marker.
  - **UNKNOWN_OR_STRIPPED** in every other case.

## Vendor private attributes (`vendors/`)

- Read-only and creator-checked. They are never used by strict SUV.

| Vendor | Attribute | Source |
|---|---|---|
| Siemens | (0071,xx22) "SIEMENS MED PT" Decay Correction DateTime | Siemens Biograph TruePoint 6.7 conformance statement |
| GE | (0009,xx0D) "GEMS_PETD_01" scan date/time | QIBA vendor-neutral pseudo-code 2018 |
| Philips | (7053,xx00) and (7053,xx09) "Philips PET Private Group" | QIBA pseudo-code |

- Fields known only from secondary sources are reported as `UNSUPPORTED_PRIVATE_TAG`.

## Real finding

- On both downloaded lesion cases, the Siemens private decay-correction datetime is exactly
  **−86 400 s** (one day) from SeriesDate/Time.
- The audit reports this as `INCONSISTENT_METADATA`: a date shift applied to the standard
  attributes but not the private ones.
- This is the same inconsistency that makes Z-Rad refuse SUV conversion.

## Outputs (`trial/export.py`)

- `trial_audit.json`
- `subject_timepoint_matrix.csv`
- `pair_checks.csv`: per rule, observed / expected / PASS-FAIL-UNKNOWN / source / reasons.
- `site_summary.json`: counts, and verdicts by site, scanner, software and reconstruction;
  insufficient-information counts by reason; failures by rule; reference-region statuses.
- `reference_regions.csv`, `reference_review_worksheet.yaml`, `reference_qc/*.png`: see
  [reference_regions.md](reference_regions.md).
- Batch CLI: `scripts/run_trial_audit.py <trial> --out <dir> [--ruleset] [--reviews]`.
- `pair_verdicts.csv`, `rule_summary.csv` (PASS/FAIL/UNKNOWN per rule), `failure_reasons.csv`
  (every FAIL/UNKNOWN check, `TECHNICAL` or `MISSING_DATA`, with the differing fields) and
  `AUDIT_REPORT.md`.
  - **Origins:** every table carries `data_origin` (`REAL` or `SYNTHETIC_PERTURBATION`).
  - **No pooling:** REAL and SYNTHETIC findings are never pooled into one rate.
- Demo cross-rule-set report: `scripts/report_trial_demo.py`.
  - **QIBA:** synthetic verdicts are checked against the pre-declared `perturb.EXPECTED`.
  - **PERCIST/EANM:** these have no pre-declared expectations, so failures are labelled
    *post hoc*.

## Demo (`../outputs/synthetic_comparability/`)

- **BASELINE** is the real PETCT_0011f3deaf, as read-only links.
- **FOLLOWUP** is a **SYNTHETIC_PERTURBATION** copy. These are not real follow-up scans; each is
  labelled in its DICOM SeriesDescription and ImageComments, in `trial.yaml`, and in every
  result.

Expected QIBA verdicts (all reproduced):

| Case | Perturbation | Expected (QIBA) |
|---|---|---|
| A | identity (new UIDs only) | ASSESSABLE |
| B | 3-D Gaussian blur, 6 mm FWHM, plus kernel metadata | NOT_ASSESSABLE (VT-PROTOCOL-IDENTITY). The lesion SUVpeak drops 12.235 → 10.065 (−17.7 %) with no biological change |
| B2 | ReconstructionMethod 2i → 4i | NOT_ASSESSABLE |
| D | injection 30 min earlier (uptake 90 min) | NOT_ASSESSABLE (QIBA-UPTAKE-WINDOW/DIFF) |
| C | RadionuclideTotalDose removed | INSUFFICIENT_INFORMATION (MISSING_REQUIRED_TAG / SUV_REFUSED) |
| E | ReconstructionMethod, ConvolutionKernel and the Siemens private group removed | INSUFFICIENT_INFORMATION (AMBIGUOUS_RECONSTRUCTION) |
| F | SCAT removed from CorrectedImage | NOT_ASSESSABLE |

Under PERCIST every pair is INSUFFICIENT_INFORMATION or NOT_ASSESSABLE:

- Real baselines get liver and blood-pool proposals, but no human review has been recorded, so
  the reason is `REFERENCE_REVIEW_REQUIRED`. The worksheet and QC images are written with the
  audit.
- Synthetic follow-ups contain no CT in their frame of reference, so the reason is
  `REFERENCE_AUTO_NOT_FOUND`.
- No region is invented, and no unreviewed proposal is used.
