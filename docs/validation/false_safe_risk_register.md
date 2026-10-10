# False-safe risk register

**False-safe** = VoxelTrace returns `ASSESSABLE` or `ASSESSABLE_WITH_WARNINGS` (or a strict SUV
PASS that feeds one) when the pair should not be interpreted. This is the failure that matters
most: it lets an SUV change be read when it should not be.

Date: 2026-10-09, code at the 0.4.0 pilot-hardening work. Residual risk: **H**igh / **M**edium
/ **L**ow, a judgement after the stated controls. "Test" names files in `tests/`. No external
expert validation exists yet, so no residual rating has been confirmed by an independent
physicist.

## Summary

| ID | Risk | Residual |
|---|---|---|
| FS-01 | Reconstruction parameters implied by identical vendor text | **H** (GE/Philips generic text), M (Siemens) |
| FS-02 | Plausible but wrong header values (weight, dose, times) | **H** (undetectable from DICOM) |
| FS-03 | Software defect in rules/validator; no independent validation yet | **H** until expert validation |
| FS-04 | Decay semantics misread where DecayFactor is absent | M |
| FS-05 | Anonymizer alters (not deletes) timing consistently-but-wrongly | M |
| FS-06 | Wrong PET series when only one (wrong) series is supplied | M |
| FS-07 | Two patients under one subject with one pseudonym | M |
| FS-08 | Site attestation wrong but formally valid (QIBA only) | M |
| FS-09 | Software version change treated as warning only | M |
| FS-10 | Human reviewer accepts a wrong liver ROI or lesion mask | M |
| FS-11 | Pairing BLOCKED finding ignored by someone using the raw bundle | M |
| FS-12 | Blood glucose / fasting not evaluated | M (scope) |
| FS-13 | Units say BQML but values were processed | L–M |
| FS-14 | Wrong scan reference time (per bed / re-saved series) | L |
| FS-15 | Reconstruction text parsed wrongly | L |
| FS-16 | Stale review record | L |
| FS-17 | Lesion mask bound to the wrong scan | L |
| FS-18 | Tracer mismatch missed | L |
| FS-19 | Anonymization deletes evidence | L |
| FS-20 | Undocumented vendor private semantics trusted | L |
| FS-21 | Timepoints in the wrong order | L |
| FS-22 | Synthetic data reported as real | L |
| FS-23 | Duplicate scan with new UIDs and re-reconstructed voxels | L |
| FS-24 | Human adjudication silently changing a verdict | L |

## Entries

### FS-01 Reconstruction parameters implied by identical vendor text — residual H/M
- **Cause:** `evidence/comparability.py` treats iterations, subsets, TOF and PSF as SAME when
  they are not encoded but the `ReconstructionMethod` text is identical on both scans
  (`fallback_same`). For Siemens texts such as `PSF+TOF 2i21s` the text encodes them. For a
  generic text such as GE `OSEM` it does not: a changed iteration count is invisible.
  VT-PROTOCOL-IDENTITY then PASSes if the post-filter is known.
- **Seen in data:** CCTH-B02 (Siemens Biograph64, `PSF 3i24s` on both scans) is QIBA
  ASSESSABLE with TOF not encoded on either scan (TOF judged SAME through the text). No
  ASSESSABLE pair in the real cohort rests on a *generic* text, because GE exports in the
  cohort lack the convolution kernel and stay UNKNOWN.
- **Detection control:** the fingerprint reports these fields at LEVEL_D / NONE; new in this
  session, `pair_results.csv → reconstruction_evidence = TEXT_IMPLIED: <fields>`; disclosed in
  README_FIRST and methodology of every package.
- **Test:** `test_false_safe_register.py::test_fs01_*` (characterization: pins current
  behaviour; different texts are never identity PASS).
- **Next validation:** ask the external physicists to judge CCTH-B02 and any TEXT_IMPLIED
  pair; propose VT-PROTOCOL-IDENTITY v2 (fallback only for parameters the text actually
  encodes, or vendor-specific documented dictionaries) as a **new rule version after the
  blinded validation**, not before, because it changes frozen validation answers.

### FS-02 Plausible but wrong header values — residual H
- **Cause:** weight, dose or times entered wrongly at the site but within plausible ranges.
- **Control:** implausibility limits (IMPLAUSIBLE_*, NEGATIVE/IMPLAUSIBLE_DECAY_INTERVAL);
  drift heuristics flag DOSE_OUTLIER / UPTAKE_OUTLIER per site (reporting only).
- **Test:** `test_suv.py`, `test_fingerprint_drift.py`.
- **Next:** site CRF cross-check (dose, weight, injection time) as an optional pilot input;
  cannot be solved from DICOM.

### FS-03 Software defect; no independent validation — residual H until validated
- **Control:** 700+ tests incl. failure injection for every emittable reason code
  (`docs/failure_injection_coverage.md`), rule bundle sha256, frozen outputs, byte-identical
  re-runs and cross-architecture verdicts (`reproducibility.md`), external SUV cross-check on
  2 Siemens scans (`docs/external_crosscheck.md`).
- **Next:** the blinded external physicist review (tag `v0.3.0-external-validation`).

### FS-04 Decay semantics where DecayFactor is absent — residual M
- **Cause:** with DecayFactor absent the decay cross-check cannot run (DECAY_FACTOR_UNVERIFIED,
  a warning) and strict SUV assumes DICOM START semantics. GE Discovery LS 16.01 was shown to
  store frame-start FrameReferenceTime (`docs/vendor_decay_timing.md`); ACRIN-167/168 pass
  without the cross-check.
- **Control:** UNVERIFIED is reported; where DecayFactor is present, any 1e-3 mismatch refuses.
- **Test:** `test_suv.py`, `test_failure_injection.py`.
- **Next:** phantom (`phantom_validation_plan.md`) + GE conformance statement.

### FS-05 Timing altered consistently-but-wrongly by de-identification — residual M
- **Cause:** an anonymizer shifts injection and scan times differently but keeps the interval
  plausible; the uptake rules then decide on wrong values.
- **Control:** NEGATIVE/IMPLAUSIBLE intervals catch gross shifts; anonymization audit marks
  declared profiles; INJECTION_DATE_FROM_SERIES warns.
- **Next:** request "Retain Longitudinal Temporal Information" exports; compare with CRF times.

### FS-06 Only one PET series supplied and it is the wrong one — residual M
- **Cause:** a re-saved, derived or NAC series supplied alone.
- **Control:** strict SUV refuses missing ATTN (MISSING_CORRECTION), non-BQML units, secondary
  capture; DERIVED_IMAGE is a warning; intake never chooses between several series (R1–R3 only).
- **Test:** `test_preflight.py`, `test_intake.py`.
- **Next:** decide with physicists whether DERIVED should block.

### FS-07 Two patients under one subject with one pseudonym — residual M
- **Control (new):** pairing audit compares hashed PatientID across timepoints and subjects,
  PET series UID and voxel content (SAME_SCAN_LINKED_TWICE, SCAN_LINKED_TO_MULTIPLE_SUBJECTS,
  INCONSISTENT_SUBJECT_PSEUDONYM, SUBJECT_PSEUDONYM_SHARED); BLOCKING → AUDIT_BLOCKED and no
  package; validate-input flags several patients or PET studies in one scan folder.
- **Residual:** an anonymizer that assigns the *same* pseudonym to two patients.
- **Test:** `test_pilot_run.py::test_pairing_*`, `test_intake.py`.

### FS-08 Formally valid but wrong site attestation — residual M
- **Control:** QIBA only; LEVEL_C; scan- and hash-bound; accepted roles; contradiction with
  DICOM refuses; result at most ASSESSABLE_WITH_WARNINGS; EANM and PERCIST never accept it.
- **Test:** `test_qiba_attestation.py`. **Next:** countersignature requirement in pilots.

### FS-09 Software version change is a warning — residual M
- **Cause:** QIBA-SAME-SYSTEM / PERCIST software checks are warnings by the standards' wording;
  a software upgrade that changed quantitation yields ASSESSABLE_WITH_WARNINGS.
- **Control:** surfaced as a warning and in drift (SOFTWARE_CHANGE). **Next:** physicist view.

### FS-10 Human accepts a wrong reference region or lesion — residual M
- **Control:** proposals carry QC images and measurement QC (REFERENCE_QC_FAILED); decisions are
  hash-bound and attributable; VoxelTrace never records a decision.
- **Next:** second-reader option in pilots.

### FS-11 Pairing BLOCKED ignored via the raw bundle — residual M
- **Cause:** `voxeltrace audit` alone writes pair verdicts even when the pairing audit is
  BLOCKED (reporting only, by design).
- **Control:** `run-pilot` → AUDIT_BLOCKED and no delivery package; the executive first page
  shows the pairing status; `pair_results.csv` carries `pairing_status`.
- **Test:** `test_pilot_run.py::test_pairing_block_makes_audit_blocked_and_refuses_delivery`.

### FS-12 Glucose / fasting not evaluated — residual M (scope)
QIBA requires glucose checks that are not in image metadata. ASSESSABLE never covers them;
stated in methodology. **Next:** optional CRF input.

### FS-13 Units BQML but values processed — residual L–M
Control: DERIVED_IMAGE warning, rescale consistency checks, implausible SUV guards. Test:
`test_suv.py`.

### FS-14 Wrong scan reference time — residual L
Control: SCAN_REFERENCE_AMBIGUOUS, SERIES_TIME_AFTER_ACQUISITION, per-bed checks. Test:
`test_suv.py`, `test_vendors_anonymization.py`.

### FS-15 Reconstruction text parsed wrongly — residual L
Control: parsed values are LEVEL_D and never override structured ones; different texts never
PASS. Test: `test_recon_trust.py`, `test_protocol_evidence.py`, FS-01 test.

### FS-16 Stale review record — residual L
Control: reference reviews bound to `proposal_sha256` (REFERENCE_REVIEW_OUTDATED), lesion
reviews to `mask_sha256` + `seg_file_sha256`. Test: `test_reference_review.py`,
`test_lesion_review.py`.

### FS-17 Lesion mask bound to the wrong scan — residual L
Control: SEG must reference the PET series (SEG_REFERENCE_NOT_FOUND), geometry checks, human
acceptance. Test: `test_ingest_nifti_seg.py`, `test_lesion_review.py`.

### FS-18 Tracer mismatch missed — residual L
Control: VT-TRACER-SAME blocking; unknown tracer is UNKNOWN; intake marks non-FDG UNSUPPORTED.
Test: `test_trial_rules.py`, `test_validate_input.py`.

### FS-19 Anonymization deletes evidence — residual L
Control: missing evidence is UNKNOWN_OR_STRIPPED / STRIPPED_BY_ANONYMIZATION → never a pass.
Test: `test_vendors_anonymization.py`.

### FS-20 Undocumented private semantics — residual L
Control: private tags only with documented provenance (UNSUPPORTED_PRIVATE_TAG). Test:
`test_vendors_anonymization.py`, `test_vendor_kb.py`.

### FS-21 Timepoints in the wrong order — residual L
Control (new): TIMEPOINT_ORDER_ANOMALY (BLOCKING), TIMEPOINT_ORDER_UNDECLARED,
UNDECLARED_TIMEPOINT; most rules are symmetric. Test: `test_pilot_run.py`.

### FS-22 Synthetic data reported as real — residual L
Control: data_origin on every row; synthetic only via explicit `synthetic_perturbations`;
LEGACY_UNREVIEWED lesions refused for real data. Test: `test_synthetic_reference.py`.

### FS-23 Duplicate scan with new UIDs and re-reconstructed voxels — residual L
Neither UID nor voxel hash matches; SAME_DAY_TIMEPOINTS catches same-date duplicates.

### FS-24 Adjudication changing a verdict — residual L
Control: adjudications are appended, hash-chained and reported separately; automated verdicts
are never modified. Test: `test_pilot_bundle.py`.

## Known critical false-safe bug?

No **known** defect contradicts the documented rule design. FS-01 is a known, documented
design risk with real-data exposure (CCTH-B02, Siemens text that encodes iterations/subsets
but not TOF). It is disclosed per pair from this session on and is the first item for the
external reviewers. It is not fixed now, because changing VT-PROTOCOL-IDENTITY would change
the frozen blinded-validation answers.
