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
