# Changelog

VoxelTrace uses 0.x versions: interfaces, rule-set versions and output schemas may still
change between minor versions. Every rule set, schema and algorithm carries its own version
inside each output, so results remain traceable even within one software version. 1.0 is
reserved for a release backed by completed external expert validation.

## 0.4.0-rc2 (2026-10-10, partner-pilot preparation; see docs/release_candidate_v040.md)

- `validate-partner-intake` (VT-PARTNER-INTAKE-1): partner declaration checked against the files;
  review decisions refused.
- `deployment-lock capture|verify` (VT-DEPLOYMENT-LOCK-1).
- Intake safety: archives, zero-byte and malformed files, empty visits, duplicated instances, one
  series in several folders, mixed vendors.
- Reviewer-form scoring safeguards (malformed/duplicate/conflicting forms, abstentions,
  inter-reviewer agreement, SYNTHETIC_TEST_ONLY separation).
- Fixes: synthetic-fixture reference inheritance failed after workspace relocation (synthetic
  fixtures only, fail-safe); pairing audit fixture handling (demo no longer AUDIT_BLOCKED; two real
  subjects sharing a scan always block); `reconstruction_evidence` NOT_ESTABLISHED vs TEXT_IMPLIED.
- Partner packet, starter kit, dry run, paid-pilot gate, outreach, website, demo, operations.
- No change to SUV/SUL, thresholds or rule logic; real-cohort verdicts byte-identical to the frozen
  tag-check bundle.

## 0.4.0 (2026-10-09, retrospective pilot hardening; see docs/release_candidate_v040.md)

- One-command pilot: `voxeltrace run-pilot` (validate-input -> init-trial -> audit ->
  verify-bundle -> pilot acceptance VT-PILOT-ACCEPTANCE-1 -> delivery package).
- Sanitized delivery package (`deliver`, `verify-delivery`, VT-DELIVERY-1) with a
  fail-closed privacy scan (VT-PRIVACY-SCAN-1) and package checksums.
- Partner-drop intake mapping (`intake-map`, VT-INTAKE-MAPPING-1) with explicit PET
  selection rules and staging; nested-layout detection in `validate-input`.
- Longitudinal pairing audit (VT-PAIRING-AUDIT-1); site/scanner rollup (VT-SITE-ROLLUP-1);
  executive summary v2 (VT-EXECUTIVE-SUMMARY-2) first page.
- Evidence trust trace (`explain-pair`, `pair_evidence_trace.csv`), remediation matrix,
  `reconstruction_evidence` disclosure (false-safe risk FS-01).
- Fixes: set-order nondeterminism in per-rule-set site_summary.json; warning-level checks
  worded as refusals in the trace; hidden/__MACOSX folders treated as subjects;
  segmentation file names (UIDs) written in clear.
- No change to SUV/SUL, rule thresholds or verdict logic: the 9-pair real cohort gives
  byte-identical pair-verdict CSVs to the frozen cohort bundles (audit_v2 and audit_tagcheck_a46526c, checked at release).

## 0.3.0 (tagged v0.3.0-external-validation; release-candidate proposal in docs/release_candidate_proposal.md)

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
