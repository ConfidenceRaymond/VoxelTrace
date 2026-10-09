# Retrospective audit: scope of a pilot

**In scope**
- FDG PET/CT, baseline and ≥ 1 follow-up, de-identified DICOM (PET + CT acquired with it).
- Rule sets QIBA FDG-PET/CT 1.14, EANM FDG 2.0, PERCIST 1.0 (PERCIST needs human liver review
  and a reviewed lesion target).
- Preflight, pair verdicts, protocol fingerprints and drift, II reasons, draft site queries,
  evidence bundle.

**Out of scope**
- Response assessment, diagnosis, lesion detection.
- Non-FDG tracers (flagged REQUIRES_TRACER_SPECIFIC_RULESET).
- PET/MR.
- NIfTI-only data.
- Vendor exports outside the strict BQML/START path (refused and reported, not converted).

**Partner provides**
- data under a data-use agreement;
- pseudonymous subject IDs and site mapping;
- a reviewer for reference regions;
- optionally, site reconstruction records (QIBA attestation path).

**VoxelTrace provides**
- audit runs;
- bundles;
- a summary of findings and a limitations statement;
- the BLINDED expert-validation package on request.
