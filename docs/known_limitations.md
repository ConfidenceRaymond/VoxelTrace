# Known limitations (2026-10-09)

**Scientific / validation**
- **Real-data validation is small.**
  - 9 real longitudinal pairs (5 ACRIN, 4 external; cohort `external_validation_cohort_v1`).
  - QIBA: 2 ASSESSABLE and 1 ASSESSABLE_WITH_WARNINGS, all Siemens.
  - No GE, Philips or United Imaging pair is decidable in the open data examined (census v3).
- **No external expert validation yet.** The blinded physicist package exists (9 real pairs,
  with a leak guard); no reviewer form has been returned, so no agreement figure exists.
- **No real pair has a complete PERCIST verdict yet.**
  - The lesion review gate exists (`docs/lesion_review.md`), but no lesion has been reviewed.
  - The closest case, PETCT_97320b0b58, passes every data-decidable PERCIST rule and waits
    only on human liver and lesion review (`docs/percist_first_real_case.md`).
  - Human liver reviews exist only for ACRIN 168, whose reconstruction identity is unresolved.
  - The autoPET SEG is a single union segment of all lesions; see the reviewer notes.
- **Vendor coverage.**
  - The strict BQML/START path only.
  - Philips CNTS and GE GML exports are refused.
  - GE DecayFactor timing (094) and CPS FRT = 0 (153) are refused rather than modelled.
  - No United Imaging module.
- **EANM and PERCIST never accept external reconstruction attestations** (the standards are
  silent). QIBA accepts them at most as ESTABLISHED_WITH_WARNING.

**Engineering**
- The full audit repeats ingestion for each rule set (about 3× slower than needed).
- Memory grows with subject count (about 2.4 GB at 8 subjects). Batch large trials.
- The PDF report is plain text (no images); it is byte-reproducible.
- Bundles are integrity-checked, not signed.
- The census predicts from 12 sampled slices.
  - Voxel size is unknown until download.
  - It does not model PatientSex for SUL (1 miss in 30 fields).
- Discovery does not follow directory symlinks nested inside scan folders.

**False-safe risks** (inputs VoxelTrace cannot detect; see `docs/design_partner_readiness.md` Q7)
- Plausible but wrong header values (weight, dose, times) entered at the site.
- Fasting and blood glucose are not in image metadata and are not evaluated.
- Reconstruction identity is judged from the encoded fields only.
- A human ACCEPT of a wrong liver ROI or lesion mask.

**Product**
- No regulatory clearance; research use only.
- No commercial validation: no design partner, no willingness-to-pay evidence.
- Not tested on a sponsor's real multicentre trial.
