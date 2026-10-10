# Schema versioning and migration

Every exported artefact names the schema it was written with (`src/voxeltrace/versions.py`).

| Artefact | Version | Defined in | Notes |
|---|---|---|---|
| Protocol evidence | `VT-EVIDENCE-1` | `evidence/protocol.py` (ProtocolEvidence, EvidenceField) | values never guessed; MISSING carries no value |
| Protocol fingerprint | `VT-PROTOCOL-FP-1` | `evidence/fingerprint.py` | fixed field list; canonical JSON; two sha256 hashes |
| Preflight result | `VT-PREFLIGHT-1` | `preflight/schema.py` | per series / scan / batch |
| Trial audit | `VT-TRIAL-AUDIT-1` | `trial/audit.py` (TrialAudit) | files written before this table existed are v1 |
| Audit package (v2) | `VT-AUDIT-PACKAGE-1` | `pilot.py` | outputs of `voxeltrace audit` |
| Drift report | `VT-DRIFT-1` | `trial/drift.py` | reporting only |
| Reconstruction attestation | `voxeltrace.recon-attestation/2` | `evidence/attestation.py` | v1 (report-only prototype) was never used in production |
| Pair adjudication | `VT-ADJUDICATION-1` | `trial/adjudication.py` | append-only, hash-chained JSON lines |
| Evidence bundle | `VT-BUNDLE-1` | `bundle.py` | manifest + checksums.sha256 |
| Site queries | `VT-SITE-QUERY-1` | `trial/site_queries.py` | DRAFT only, never sent |
| Pairing audit | `VT-PAIRING-AUDIT-1` | `trial/pairing_audit.py` | `pairing/pairing_audit.json`; reporting only, never re-pairs |
| Site rollup | `VT-SITE-ROLLUP-1` | `trial/rollup.py` | `reports/site_summary.csv`; reconciles with pair results |
| Executive summary | `VT-EXECUTIVE-SUMMARY-2` | `executive.py` | v2 adds readiness, comparability, sites requiring action, pairing status, unresolved review; v1 pages remain readable |
| Pilot acceptance | `VT-PILOT-ACCEPTANCE-1` | `pilot_run.py` | `pilot_acceptance.json` from `voxeltrace run-pilot` |
| Delivery package | `VT-DELIVERY-1` | `delivery.py` | sanitized package + `DELIVERY_CHECKSUMS.sha256` |
| Privacy scan | `VT-PRIVACY-SCAN-1` | `privacy_scan.py` | conservative pattern scan; not a de-identification method |
| Remediation matrix | `VT-REMEDIATION-MATRIX-1` | `remediation.py` | documentation layer; never changes a verdict |
| Reference review | `voxeltrace.reference-review/2` | `trial/reference.py` | hash-bound human decisions |

**Rule bundle.** `versions.rule_bundle()` lists every rule set's rules with id, version, impact
and parameters. `rule_bundle_sha256` is a hash over that list. Any threshold or rule change
changes the hash, and the bundle manifest records it.

## Policy

1. **New meaning or new required field means a new version string.** Adding an optional field
   with a default that does not change existing outputs keeps the version. Example: TrialAudit's
   attestation fields are excluded from export when unused, so old and new files are
   byte-identical.
2. **Old outputs stay readable.** Readers accept files without the newer optional fields;
   `tests/test_pilot_bundle.py::test_old_trial_audit_json_still_readable` covers this.
3. **No silent migration.** A migration is an explicit script that reads version N and writes
   version N+1 to a new location, records both versions, and never overwrites the source.
4. **Bundles are immutable.** A re-run writes a new bundle; `voxeltrace verify-bundle`
   detects modified, missing or unlisted files and a changed checksum list.

## Version record for 0.3.0

`voxeltrace --version` prints everything below. Every bundle manifest also records it
(`voxeltrace_version`, `schema_versions`, `rule_versions`, `rule_bundle_sha256`).

| Component | Version |
|---|---|
| Code / CLI | 0.3.0 (`pyproject.toml`, `voxeltrace.__version__`, `voxeltrace --version`); 0.x series (see `CHANGELOG.md`) |
| Rule sets | `qiba-fdg-1.14` QIBA-FDG-PETCT-1.14, `eanm-fdg-2.0` EANM-FDG-2.0, `percist-1.0` PERCIST-1.0/PRACTICAL-2016; each rule also carries its own version |
| Rule bundle sha256 | `413186131a357163959cb161358e9193899c9675278bcc1a8a8c8d194f9d411d` (unchanged by 0.3.0) |
| Evidence | VT-EVIDENCE-1, VT-PROTOCOL-FP-1, VT-PREFLIGHT-1, `voxeltrace.recon-attestation/2` |
| Review logs | `voxeltrace.lesion-review/1` (lesions), hash-bound reference reviews (proposal algorithm `vt-refauto-1`), VT-ADJUDICATION-1 |
| Audit outputs | VT-TRIAL-AUDIT-1, VT-AUDIT-PACKAGE-1, VT-BUNDLE-1, VT-DRIFT-1, VT-SITE-QUERY-1 |
| Reports | VT-EXECUTIVE-SUMMARY-2 (`reports/executive_summary.json`; Markdown and PDF have the same content; bundles before 0.4.0 carry VT-EXECUTIVE-SUMMARY-1) |
| Other tools | VT-EXPERT-VALIDATION-1, VT-VALIDATE-INPUT-1, VT-DATA-INVENTORY-1, VT-BRAIN-INTAKE-1 |

**Strategy:**
- 0.x minor versions mark research and external-validation milestones; patch versions are
  fixes with no change to any verdict.
- A change to a rule threshold or verdict logic needs a new rule version and a new rule-bundle
  hash, even inside 0.x.
- 1.0 is reserved for a release backed by completed external expert validation.
