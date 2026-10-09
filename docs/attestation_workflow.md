# Reconstruction attestation: operational workflow (QIBA only)

**Applies only to `qiba-fdg-1.14`.** EANM and PERCIST never use attestations; see
[reconstruction_attestation_policy.md](reconstruction_attestation_policy.md).

**What software never does:**
- VoxelTrace never creates, completes or signs an attestation.
- An attestation never turns into "DICOM-proven" identity. At best it gives
  `ESTABLISHED_WITH_WARNING` with the banner **EXTERNAL RECONSTRUCTION ATTESTATION USED**.

## Steps

1. **Find the gap.**
   - Run `voxeltrace audit`.
   - Pairs blocked only by reconstruction parameters show `VT-PROTOCOL-IDENTITY` UNKNOWN with
     `AMBIGUOUS_RECONSTRUCTION`.
   - The bundle's `reports/site_queries.md` contains a **DRAFT SITE QUERY**
     (`RECONSTRUCTION_INCOMPLETE` / `AMBIGUOUS_RECONSTRUCTION`). A human sends it, after
     editing.
2. **Generate an unsigned template per scan:**
   ```
   voxeltrace attestation-template --scan-dir <trial>/<subject>/<timepoint> \
       --subject <subject> --timepoint <timepoint> --out <subject>_<timepoint>.yaml
   ```
   - The template contains only binding facts read from the scan's DICOM: study/series UID,
     manufacturer, model, software.
   - Reconstruction values and attestor fields are empty. The template fails validation until
     completed.
3. **The site completes the template.** Who signs:
   - a QUALIFIED_PET_PHYSICIST;
   - a NUCLEAR_MEDICINE_PHYSICIST;
   - an IMAGING_CORE_QC_LEAD with documented PET QC responsibility (set
     `attestor_qc_responsibility_documented: true`);
   - a SITE_PET_TECHNOLOGIST, countersigned by one of the above.

   What they fill in:
   - every reconstruction parameter: method, iterations, subsets, post-filter, TOF, PSF, and
     corrections if relevant;
   - `confidence: CONFIRMED`;
   - `rule_scope: [qiba-fdg-1.14]`.

   They attach the source document (scanner protocol export, site protocol record or signed
   attestation) and record its `sha256`.
   - A **trial imaging charter alone is `EXPECTED_PROTOCOL_ONLY`**. It counts only with a
     `charter_binding` (site, model, software or period, scan-level applicability) **and** a
     hash-bound corroborating scanner export, site record or signed attestation.
4. **Validate before use:**
   ```
   voxeltrace validate-attestations --input <trial> --attestations <file.yaml>
   ```
   - Every record must be `VALID`.
   - `STALE` means a bound document, series, study, scanner or software changed.
   - `INVALID` means a role, schema, binding or simulated-record problem.
5. **Audit with the attestations:**
   ```
   voxeltrace audit --input <trial> --output <new dir> --attestations <file.yaml>
   ```
   or set `recon_attestation_file:` in `trial.yaml`; files are never picked up by default.
6. **Review the report.**
   - The QIBA pair shows `PASS_WITH_WARNING` / `ESTABLISHED_WITH_WARNING`, the attestation IDs,
     the source hash, the role and LEVEL_C.
   - The bundle contains `attestations/attestations.csv`.
   - `voxeltrace verify-bundle` checks the bundle integrity.

## Failure modes, all tested

| Situation | Result |
|---|---|
| Attestation for one timepoint only | NOT_ESTABLISHED |
| Out-of-scope rule set | not used |
| Attested values differ between timepoints | CONTRADICTED (FAIL) |
| Attestation vs DICOM disagreement | CONTRADICTED (FAIL) |
| Two attestations disagree | CONTRADICTED (FAIL) |
| Non-reconstruction unknowns (units, voxel size, corrections) | never filled; stays NOT_ESTABLISHED |
