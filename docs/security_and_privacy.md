# Security and privacy (review of 2026-10-09)

**Status:** RESEARCH PROTOTYPE. No compliance with HIPAA, GDPR, PIPEDA or any other regime is
claimed or has been assessed. This document records the design and a disclosure scan of real
outputs.

## Design

| Aspect | Design |
|---|---|
| **Local-first** | All processing runs on the operator's machine. No network access is needed for preflight, audit, bundle or verification. Network access is used only by the explicit census/fetch scripts (public IDC buckets) and is never needed for a sponsor's data. |
| **No cloud AI** | The audit uses no model (`ai_components: none` in every bundle manifest). The optional local VLM features are explanatory only and are not part of the audit. |
| **Data at rest** | Inputs are read-only: the audit never writes into the input folder (an external `--config` keeps `trial.yaml` outside it). Outputs go to a new directory; existing bundles are never overwritten, and bundle files are made read-only. Disk encryption, backups and access control are the operator's responsibility; VoxelTrace adds no encryption. |
| **Integrity** | Bundles carry sha256 checksums verified by `voxeltrace verify-bundle`. This proves integrity relative to the manifest, not authenticity: there is no signature yet. Adjudication logs are hash-chained, and reference reviews and attestations are hash-bound. |

## Identifiers: what outputs contain

The scan used `scripts/privacy_scan.py` on a real audit bundle and on `../logs`.

| Output | Contains | Policy |
|---|---|---|
| Reports, CSVs, `trial_audit.json` | subject IDs as given in the trial folder (pseudonymous trial IDs expected); series **pseudonyms** (`pet_…`, sha-derived); scan dates/times **as present in the (de-identified) DICOM** | Supply pseudonymised subject folders. VoxelTrace does not re-identify or re-date. |
| De-identification audit inside `trial_audit.json` | **attribute names** (e.g. "StationName absent"), never their values | Scan hits on PatientID / StationName were names only; no identifying values found. |
| `inputs_manifest.json` | sha256 of every input file; **paths pseudonymised by default** (`path_sha256`); `--input-paths-in-clear` opt-in | Changed in this review: site file names can carry identifiers. |
| Attestation records / `attestations.csv` | Study/Series Instance UIDs (needed for scan binding) | Allowed identifier class: DICOM UIDs of the de-identified data. |
| `../logs/` (developer logs) | absolute local paths (486 occurrences) and public TCIA UIDs | Local developer artefacts. Not part of a bundle; do not share. |

## Private DICOM tags

- Private tags are **read only** when listed with a cited document (`vendors/*.py`,
  `configs/vendor_kb.yaml`). They are otherwise reported as `UNSUPPORTED_PRIVATE_TAG` and
  never interpreted.
- The reconstruction inventory reduces identifying standard attributes and UIDs to sha256
  prefixes (`scripts/inventory_recon_metadata.py`).

## Pseudonyms and allowed identifiers

| Allowed | Not emitted by the audit code |
|---|---|
| Trial subject IDs; DICOM UIDs (de-identified sources); series pseudonyms; de-identified dates | names, birth dates, institution, operator, physician, accession, station or device serial **values** |

## Retention and deletion

- VoxelTrace deletes nothing.
- The operator decides retention of inputs, bundles and logs according to the data-use
  agreement.
- A bundle contains no pixel data: only derived statistics, hashes and copies of human
  review/attestation/adjudication records.

## Residual risks

1. A pre-identified input folder name (e.g. a patient name used as subject folder) would
   propagate into reports. **Preflight should warn about this in a future version.**
2. Exception traces may include local paths (logs only).
3. There is no signature on bundles yet. A party able to rewrite the bundle can rewrite its
   manifest.
