# Changelog

VoxelTrace uses 0.x versions: interfaces, rule-set versions and output schemas may still
change between minor versions. Every rule set, schema and algorithm carries its own version
inside each output, so results remain traceable even within one software version. 1.0 is
reserved for a release backed by completed external expert validation.

## 0.3.0 (untagged; release-candidate proposal in docs/release_candidate_proposal.md)

- Lesion evidence review gate (`voxeltrace.lesion-review/1`):
  - six review states, with source trust kept separate from review status;
  - reviews bound to the exact mask hash; a changed mask makes the review OUTDATED;
  - Lesion Review page and `lesion-qc` / `lesion-review` CLI;
  - PERCIST targets require an ACCEPTED segment (synthetic fixtures declare
    LEGACY_UNREVIEWED_ALLOWED explicitly).
- PERCIST readiness layers (QUANTITATIVE / REFERENCE / TARGET / PROTOCOL / OVERALL), for
  reporting only.
- Blinded validation package hardened:
  - a leak guard refuses any packet that contains a verdict, rule ID, reason code or state;
  - scoring adds weighted agreement, weighted κ, false-safe counts by severity, false-unsafe
    count and INSUFFICIENT_INFORMATION agreement.
- Reports: audit top page, deterministic executive summary from reason codes, byte-reproducible
  PDF.
- `voxeltrace validate-input` and `voxeltrace data-inventory`.
- Real-data evidence:
  - 9-pair external validation cohort (4 collections, 6 scanner models);
  - first real pair (PETCT_97320b0b58) where every data-decidable PERCIST rule passes, pending
    human liver and lesion review.
- No change to SUV/SUL, rule thresholds or verdict logic. The ACRIN-168 audits (all three rule
  sets, with human liver reviews) regenerate with identical values, statuses, hashes and
  verdicts. Only the recorded software version and output-path fields differ.

## 0.2 series (development, never versioned separately; 2026-10-08 to 2026-10-09)

- Whole-trial audit v2, evidence bundle (VT-BUNDLE-1), `verify-bundle`, adjudication log,
  draft site queries.
- Quantitative preflight (VT-PREFLIGHT-1) and the `voxeltrace` CLI.
- QIBA reconstruction attestation path; protocol fingerprints and drift.
- Real ACRIN and external longitudinal pair analyses; census v2/v3 of public PET.
- Expert validation package (VT-EXPERT-VALIDATION-1).

## 0.1.0 (2026-10-07)

- Initial repository: DICOM ingestion, strict SUVbw validator, lesion quantification from
  DICOM SEG, Streamlit app.
