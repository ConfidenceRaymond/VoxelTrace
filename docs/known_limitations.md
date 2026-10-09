# Known limitations (2026-10-09)

**Scientific / validation**
- **Real-data validation is small.**
  - 8 real longitudinal pairs (5 ACRIN, 3 external).
  - Only 2 real pairs reach an ASSESSABLE verdict (QIBA), both Siemens.
  - No GE, Philips or United Imaging pair is decidable in the open data examined (census v3).
- **No external expert validation yet.** The physicist package exists; no labels have been
  collected.
- **PERCIST is never fully assessable yet.**
  - There is no lesion review gate.
  - Supplied SEGs would be measured without review, so they are withheld in validation runs.
  - Liver reviews exist only for ACRIN 168.
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
- No PDF report (Markdown/JSON/CSV only).
- Bundles are integrity-checked, not signed.
- The census predicts from 12 sampled slices.
  - Voxel size is unknown until download.
  - It does not model PatientSex for SUL (1 miss in 30 fields).
- Discovery does not follow directory symlinks nested inside scan folders.

**Product**
- No regulatory clearance; research use only.
- No commercial validation: no design partner, no willingness-to-pay evidence.
- Not tested on a sponsor's real multicentre trial.
