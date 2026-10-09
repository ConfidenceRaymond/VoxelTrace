# Design-partner readiness (VoxelTrace 0.3.0, 2026-10-09)

VoxelTrace checks, before analysis, whether quantitative FDG PET/CT measurements can be
compared across timepoints, scanners and sites under QIBA FDG-PET/CT 1.14, EANM FDG 2.0 or
PERCIST 1.0. It explains every "cannot decide" with a reason code and produces an immutable
evidence bundle. It is a research prototype, not a medical device, and does not assess
treatment response.

**External expert agreement is still pending.** The blinded package exists, but no reviewer
form has been returned. No agreement, sensitivity or false-safe figure exists yet, and none
may be quoted.

## 1. What can an external PET physicist do today?

- **Blinded validation.** Review the 9-pair real cohort (4 public collections, 6 scanner
  models, all four verdict categories in the answer key).
  - The package (`outputs/external_validation_cohort_v1/package_blinded/`) holds facts only:
    no verdicts, rule names or reason codes. A leak guard refuses to export a packet that
    contains any of them.
  - Instructions, form, adjudication protocol and the pre-specified analysis plan are in
    `docs/external_validation/`.
- **Record hash-bound human decisions** in the Streamlit app.
  - *Reference Review* page: accept, adjust or reject liver and blood-pool proposals.
  - *Lesion Review* page: accept, reject, or reject-and-replace each supplied segmentation.
  - On PETCT_97320b0b58, these two decisions are the only missing evidence for the first
    complete real PERCIST verdict (`docs/percist_first_real_case.md`).
- **Run it on their own de-identified data**, entirely locally:
  1. `pip install` from the repository;
  2. `voxeltrace validate-input <folder>`;
  3. `voxeltrace audit --input <trial> --output <dir>`.

  No data leaves the machine, and no model or network service is used by the audit.

## 2. What can a core lab give us today?

- **A de-identified trial folder:** `<subject>/<timepoint>/<DICOM>` plus a short `trial.yaml`
  naming the rule set and timepoint order. An optional site map enables per-site drift.
- **Retained header fields.** For a decidable result the export must keep:
  - PatientWeight, and PatientSize and PatientSex for SUL;
  - RadionuclideTotalDose and the injection date/time;
  - acquisition and series times, Units = BQML, DecayCorrection = START, CorrectedImage;
  - the reconstruction attributes;
  - CT in the PET frame of reference.

  `voxeltrace validate-input` says per scan whether the folder is ACCEPT_FOR_AUDIT,
  ACCEPT_WITH_WARNINGS, NEEDS_REEXPORT or UNSUPPORTED, with the catalogued fix.
- **Optional inputs:**
  - site-signed reconstruction attestations (QIBA only), from
    `voxeltrace attestation-template`;
  - lesion DICOM SEGs for PERCIST targets (they count only after human review).

## 3. What output will they receive?

An immutable, checksum-verified evidence bundle (`voxeltrace verify-bundle`):

- **Verdicts:** per-pair verdicts per rule set, and per-rule checks with observed values,
  thresholds, sources and reason codes.
- **Scan-level evidence:**
  - preflight per scan;
  - protocol fingerprints and drift events;
  - reference-region and lesion review status;
  - attestation and adjudication status.
- **Draft site queries** (never sent automatically).
- **Reports:** an executive summary (counts, top blocking reasons, catalogued remediations) as
  Markdown, JSON and a byte-reproducible PDF.
- **Manifest:** software version, rule versions, rule-bundle hash, schema versions, git commit
  and input hashes.

## 4. What requires human review?

| Item | Who | Effect until reviewed |
|---|---|---|
| Liver / blood-pool reference proposals | qualified reviewer, Reference Review page | dependent rules (PERCIST liver stability, measurability) stay UNKNOWN |
| Lesion / target segmentations, including human-drawn ones | qualified reviewer, Lesion Review page | no PERCIST target; PERCIST-BASELINE-MEASURABLE stays UNKNOWN |
| Disputed pair verdicts | adjudicator (hash-chained log) | the automated verdict is never changed; the adjudication is reported beside it |
| Reconstruction attestation | site (signed) | QIBA only, at most ESTABLISHED_WITH_WARNING |
| Site queries | coordinator | drafts only, never sent |

Every review binds to an exact hash (proposal or mask). Changed data makes the review OUTDATED.
No review is ever created automatically, and no model output is ever accepted as evidence.

## 5. What vendors are validated?

See `docs/vendor_validation_matrix.md`. In short:

- **Siemens** Biograph128 mCT, Biograph64, Biograph40 mCT and CTI/CPS 1080: PAIR_VALIDATED.
- **GE** Discovery LS: INGESTION_VALIDATED only (SUV PASS without an independent cross-check;
  one export correctly refused).
- **Philips:** metadata only.
- **United Imaging and Canon:** not tested.

No vendor is EXPERT_VALIDATED. Public GE and Philips exports are almost all refused by strict
SUV (`docs/non_siemens_validation_strategy.md`). Validating them needs a design partner's own
exports and, ideally, a phantom scan.

## 6. What tracers are supported?

- **FDG only**, for all three rule sets.
- Known non-FDG tracers (PSMA, amyloid, tau) are UNSUPPORTED at intake.
- Unrecognised tracer names need confirmation (NEEDS_REEXPORT).
- Brain PET is inventory-only: `voxeltrace inspect-brain` reads metadata and quantifies
  nothing.

## 7. What could produce a false-safe result?

A false-safe is VoxelTrace saying ASSESSABLE when the pair should not be compared. Known
paths:

1. **Plausible but wrong header values.** Weight, dose or injection time entered wrongly at
   the site but internally consistent. Range and consistency checks catch implausible values,
   not plausible errors.
2. **Unencoded protocol differences.** Reconstruction identity is judged only from encoded
   standard fields; undocumented private tags are never interpreted. Two exports with
   identical encoded fields but a different unencoded setting would pass.
3. **Decay correction assumed from DecayCorrection = START** when no DecayFactor is stored
   (for example the GE Discovery LS pairs). SUV PASS is then reported with
   DECAY_FACTOR_UNVERIFIED, never as VERIFIED.
4. **Patient preparation outside the images.** Fasting and blood glucose are not in DICOM and
   are not evaluated; the rules say so explicitly.
5. **Human review errors.** An ACCEPT of a misplaced liver ROI or a wrong lesion mask is
   trusted as recorded. For example, the autoPET SEG is a union of all lesions, and its
   hottest region is taken as the target once accepted.
6. **Site attestation errors.** A wrong signed attestation (QIBA only) is trusted at LEVEL_C
   and flagged as a warning.
7. **Rule-encoding errors.** Thresholds are VoxelTrace's reading of the cited guidelines; an
   encoding mistake would affect every pair. This is what the blinded expert study measures.
   Its analysis plan treats any CRITICAL false-safe as blocking.

Synthetic shortcuts cannot reach real data. The legacy unreviewed-lesion policy is refused
unless the trial declares synthetic perturbations, and SIMULATED reviews are refused outside
tests.

## 8. What is still research-only?

Everything:

- no regulatory clearance;
- no response assessment;
- no claim of expert agreement.

Particularly early:

- the automatic reference-region proposals (they always need review);
- census predictions;
- the vendor knowledge base;
- the brain intake;
- the optional local explanatory model, which is never part of the audit and never overrides
  a rule, review or verdict.

## 9. What exact feedback do we need?

**From PET physicists (blinded round, `docs/external_validation/`):**

- One completed form per case: verdict per standard, confidence, reason, missing evidence and
  minutes spent.

Then, in the unblinded round:

1. Should AMBIGUOUS_RECONSTRUCTION (free-text or missing parameters) be
   INSUFFICIENT_INFORMATION, or would you accept a site attestation under EANM or PERCIST?
2. Is SUV PASS with DECAY_FACTOR_UNVERIFIED acceptable, or should a trial be able to require
   a stored DecayFactor?
3. Are the encoded uptake-window and uptake-difference thresholds what you apply in practice?
4. Liver ROI: is a 3 cm sphere placed automatically and accepted by you adequate? What makes
   you adjust it?
5. For union lesion masks, is "hottest region of the union" an acceptable PERCIST target
   after your review?

**From core labs and sponsors:**

1. Can your exports pass `validate-input`? Which reason codes appear, and how often?
2. Is the bundle (CSV/JSON/PDF) acceptable to your QC process? What is missing?
3. How long does the current comparability check take per pair, and who does it?
4. Are the draft site queries worded so a site can act on them?
5. Would you run the tool locally, or share de-identified data under an agreement?

## Readiness against the DESIGN_PARTNER_READY criteria

| Criterion | Evidence |
|---|---|
| Installable independently | clean venv `pip install` (no cache, inside the workspace), `voxeltrace --version` 0.3.0 |
| One-command audit works | `voxeltrace audit` from the clean install on PETCT_97320b0b58: bundle verified OK, summary printed |
| External validation package exists | blinded 9-pair real cohort, leak guard, docs, scoring with severity |
| Lesion and reference review gates exist | hash-bound, human-only, tested (lesion gate: 25 tests) |
| Evidence bundle works | `verify-bundle` OK on the cohort and the clean-install run |
| Deterministic reports usable | executive summary + byte-identical PDF across runs (tested) |
| Known limitations documented | `docs/known_limitations.md`, this file (Q7), vendor matrix |
| External expert agreement | **pending: not required for design-partner engagement, and not claimed** |
