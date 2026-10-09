# Vendor validation matrix

Status on 2026-10-09. Every entry is backed by an artefact in this repository or in
`../outputs`. Nothing is extrapolated from one scanner model to another.

## States

| State | Meaning |
|---|---|
| NOT_TESTED | No header or image from this vendor/model has been processed |
| METADATA_ONLY | Census header samples only (IDC v25 byte-range reads, `docs/census_v3_public_pet.md`); no full series processed |
| INGESTION_VALIDATED | Full real series ingested, preflight and strict SUV run, and the outcome (PASS or a specific refusal) matches the headers on manual inspection |
| QUANT_VALIDATED | INGESTION_VALIDATED, plus strict SUV PASS with an independent check: a stored DecayFactor VERIFIED on every slice, or agreement with an external implementation |
| PAIR_VALIDATED | A real baseline/follow-up pair, both timepoints QUANT_VALIDATED, audited end to end under all three rule sets, with reproducible verdicts |
| EXPERT_VALIDATED | VoxelTrace verdicts compared with locked independent expert answers (`docs/external_validation/analysis_plan.md`) |

The states are cumulative. **No vendor or model is EXPERT_VALIDATED**, because no reviewer
forms have been returned yet.

## Matrix (PET/CT, FDG, conventional axial field of view)

| Vendor | Model | State | Evidence | Gap |
|---|---|---|---|---|
| Siemens | Biograph128 mCT | **PAIR_VALIDATED** | PETCT_c2ffda4725 (DecayFactor VERIFIED) and PETCT_97320b0b58 (no unverified or inconsistent DecayFactor finding); external cross-check on PETCT_0011f3deaf (`docs/external_crosscheck.md`) | expert agreement |
| Siemens | Biograph64 | **PAIR_VALIDATED** | CCTH-B02 (DecayFactor VERIFIED; SUL refused, no PatientSize) | expert agreement |
| Siemens | Biograph40 mCT | **PAIR_VALIDATED** | MSB-07612 (DecayFactor VERIFIED; SUL refused, PatientSex `O`) | expert agreement |
| Siemens | SOMATOM Definition AS (PET/CT) | QUANT_VALIDATED | PETCT_bd52fdf529 external cross-check; single timepoint | no pair |
| Siemens / CTI (CPS) | 1080 | **PAIR_VALIDATED** | ACRIN-050 (DecayFactor VERIFIED on 390/390 slices) | expert agreement |
| Siemens / CTI (CPS) | 1023 | INGESTION_VALIDATED | ACRIN-153: refused DECAY_FACTOR_INCONSISTENT (1.2e-1) | refusal semantics unconfirmed |
| Siemens / CTI (CPS) | 1093, 1094 | METADATA_ONLY | census v3 (49 series) | — |
| GE | Discovery LS | INGESTION_VALIDATED | ACRIN-167 and -168: SUV PASS, DecayFactor absent (cross-check NOT_AVAILABLE); ACRIN-094: refused DECAY_FACTOR_INCONSISTENT (1.56e-2). Human liver reviews bind on 168 | no independent quantitative check; refusal semantics unconfirmed |
| GE | Discovery STE, ST, RX, 690, 710, Advance | METADATA_ONLY | census v3: 844 series, 3 SUV-eligible | see the non-Siemens strategy |
| Philips | GEMINI TF (16 / 64 / Big Bore), Allegro | METADATA_ONLY | census v3: 177 series, 0 SUV-eligible (CNTS units, DECAY_FACTOR_INCONSISTENT, INVALID_ACQUISITION_DATETIME) | no full series processed |
| United Imaging | uMI family | NOT_TESTED | no open FDG DICOM found (`docs/multivendor_validation_plan.md`) | data source |
| Canon / Toshiba | Celesteion, Cartesion | NOT_TESTED | not searched in detail | data source |

Out of scope for now:
- long-axial-FOV and total-body (Quadra, uEXPLORER): gated or simulated data only;
- PET/MR: not implemented, by design;
- non-FDG tracers: `REQUIRES_TRACER_SPECIFIC_RULESET`.

## How a cell moves

- **To INGESTION_VALIDATED:** process one full real series through `voxeltrace preflight` and
  `voxeltrace audit`, and document the outcome against its headers.
- **To QUANT_VALIDATED:** strict SUV PASS plus either
  - a VERIFIED DecayFactor on every slice, or
  - an external-tool cross-check, or
  - a phantom with known activity concentration (preferred for design-partner sites).
- **To PAIR_VALIDATED:** a real pair with both timepoints QUANT_VALIDATED, with audit
  verdicts reproduced byte-identically.
- **To EXPERT_VALIDATED:** the vendor's cases are scored under the pre-specified analysis plan
  with at least 2 reviewers. A CRITICAL false-safe blocks the state until explained.

Census statistics: `../data/census/public_pet_v3/census_v3_summary.json` (per-model counts
reproduced in `docs/non_siemens_validation_strategy.md`).
