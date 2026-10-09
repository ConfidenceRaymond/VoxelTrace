# Product definition: VoxelTrace Retrospective PET Comparability Audit

## Promise

> Determine whether quantitative PET scans across timepoints, sites, scanners and
> reconstruction protocols are sufficiently comparable before SUV changes are interpreted.

## Primary users

- **Imaging core labs:** QC before endpoint reads, and site queries.
- **PET physicists:** protocol and reconstruction comparability, and reference-region QC.
- **Radiopharmaceutical sponsors:** independent check of quantitative endpoint integrity.
- **Multicentre trial groups:** retrospective audit of completed or ongoing studies.

## What it does

- Checks every scan's headers before quantification: units, decay correction, dose, timing,
  anthropometrics, reconstruction, CT frame of reference and de-identification loss.
- Computes strict SUVbw and SUL only when the headers support it; otherwise it refuses with a
  reason.
- Fingerprints each scan's protocol and detects drift by site.
- Judges each baseline/follow-up pair under an explicitly chosen, source-cited rule set: QIBA
  FDG-PET/CT 1.14, EANM FDG 2.0 or PERCIST 1.0. The verdicts are ASSESSABLE /
  ASSESSABLE_WITH_WARNINGS / NOT_ASSESSABLE / INSUFFICIENT_INFORMATION, each with reasons.
- Routes the judgements that need a person (reference regions, lesion targets, disputed
  pairs) to hash-bound human review.
- Delivers an immutable, checksum-verified evidence bundle, plus reports.

## What it does NOT do

- **Diagnosis.**
- **Treatment response classification.** PERCIST is used only to check whether the
  *prerequisites* for a response read are met.
- **Lesion segmentation as ground truth.** Supplied masks are evidence only after human review.
- **Image harmonization.** Images are never modified.
- **Clinical decision making.**
- **Autonomous AI interpretation.** The audit uses no model. An optional local model may
  explain results in words, but it never changes a value, verdict or review.

## Provisional tiers (no prices; not commitments)

| Tier | Contents | Status |
|---|---|---|
| **A. VoxelTrace Research** | local research QC, provenance, preflight, `validate-input`, pair comparability, academic use | available as the open repository (MIT) |
| **B. VoxelTrace Trial Audit** | batch trial processing, site-level rollup, protocol drift, evidence bundle, audit reports (MD/JSON/CSV/PDF), attestation and adjudication workflow | available as software; offered as a pilot service |
| **C. VoxelTrace Enterprise / Core Lab** | CLI and API integration, deployment support, validation package, role-based workflow, audit trail, future integrations | partly available: CLI, hash-chained logs and validation package exist. **No API, no role-based access control, no integrations yet** |
| **D. Future modules** | Brain PET, PET/MR, PSMA and other tracer-specific packs, SPECT/CT | **NOT CURRENTLY AVAILABLE.** Brain is a metadata intake only, and PSMA is refused at intake |

## Commercial MVP: what a customer receives today

### Input

- A retrospective PET/CT DICOM dataset (`<subject>/<timepoint>/<DICOM>`), de-identified by
  the customer. The retained fields are listed in `customer_onboarding.md`.
- A trial rules file (`trial.yaml`). It can be generated with `voxeltrace init-trial`, and
  names the rule set and timepoint order.
- Optional: lesion segmentations (DICOM SEG), a site/scanner map, signed reconstruction
  attestations (QIBA only), and site imaging manuals.

### Process

| Step | Command / page |
|---|---|
| validate-input | `voxeltrace validate-input`, page *Intake and Audit* |
| quantitative preflight | inside the audit (VT-PREFLIGHT-1) |
| scan ingestion and quantitative validation | strict SUV/SUL with refusals |
| protocol fingerprint | VT-PROTOCOL-FP-1 |
| timepoint pairing and comparability rules | QIBA / EANM / PERCIST |
| human review where needed | Reference Review and Lesion Review pages |
| attestation and adjudication | `attestation-template`, `validate-attestations`, `adjudicate` |
| site-level rollup | site summary and drift events |

### Output

| Deliverable | File in the bundle |
|---|---|
| executive audit summary | `reports/EXECUTIVE_SUMMARY.md`, `executive_summary.json` |
| subject × timepoint matrix | `rules/<ruleset>/subject_timepoint_matrix.csv` |
| pair verdict table | `pair_verdicts/<ruleset>.csv` |
| site summary | `rules/<ruleset>/site_summary.json` |
| failure reasons | `rules/<ruleset>/failure_reasons.csv`, `pair_checks.csv` |
| protocol drift events | `protocol/drift_events.csv`, `drift.json` |
| PDF | `reports/AUDIT_PACKAGE_REPORT.pdf` (byte-reproducible) |
| draft site queries | `reports/site_queries.md` (never sent automatically) |
| immutable evidence bundle | `audit_bundle/` with `manifest.json` and `checksums.sha256` |
| verification report | `voxeltrace verify-bundle` output |

See `sample_audit/` for every deliverable on DEMONSTRATION DATA.
