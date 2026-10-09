# Migration checkpoint: 2026-10-09 (leaving the NVIDIA GB10)

This is a final freeze before moving to another local PC. No feature work, downloads or
experiments were done for this checkpoint. To resume, follow `docs/resume_on_new_machine.md`.
The full copy inventory is in `<workspace>/MIGRATION_MANIFEST_20261009.txt`.

## Machine and code

| Item | Value |
|---|---|
| Date/time (UTC) | 2026-10-09T19:30 |
| Host | promaxgb10-43ea (NVIDIA GB10) |
| OS / architecture | Ubuntu 24.04.4 LTS, Linux 6.17.0-1029-nvidia, **aarch64** |
| Workspace | `/home/dell/voxeltrace_hackathon` |
| Branch | `main`, tracking `origin/main`; 0 ahead, 0 behind; working tree clean before this document |
| Commit at freeze | `200b1ff` (the commit adding this document follows it) |
| Remote | https://github.com/ConfidenceRaymond/VoxelTrace.git |
| Tags | `v0.3.0-external-validation`: tag object `7baabfe`, commit `a46526c`; present on origin; **must not move** |
| Project version | 0.3.0 (`voxeltrace.__version__`). The GB10 venv's package metadata still says 0.1.0 from an old editable install; this does not matter because the venv is not migrated |
| Rule bundle sha256 | `413186131a357163959cb161358e9193899c9675278bcc1a8a8c8d194f9d411d` |
| Python | 3.12.3 |
| Key dependencies | numpy 2.5.3, pydantic 2.13.5, pydantic-settings 2.15.0, httpx 0.28.1, PyYAML 6.0.3, pydicom 3.0.2, nibabel 5.4.2, SimpleITK 2.5.6, Pillow 12.3.0, streamlit 1.65.0, plotly 7.1.0, pytest 9.1.1, ruff 0.16.10 |
| Model | Qwen/Qwen3-VL-8B-Instruct, revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`, apache-2.0, 17,545,915,883 bytes, `all_verified: true` (`models/Qwen3-VL-8B-Instruct.manifest.json`). Optional; never used by the audit |
| Tests at freeze | 637 passed; ruff check, ruff format --check and git diff --check all exit 0 |

## State

- **Readiness classification:** DESIGN_PARTNER_READY (software), with commercialization
  preparation complete.
- **Scientific state:**
  - Real-data evidence: 9 real public longitudinal pairs (4 collections, 6 scanner models) in
    the blinded cohort.
  - Vendor coverage: Siemens models PAIR_VALIDATED; GE Discovery LS INGESTION_VALIDATED;
    Philips METADATA_ONLY.
  - No real pair has a complete PERCIST verdict.
  - **PETCT_97320b0b58 remains INSUFFICIENT_INFORMATION** (QUANTITATIVE PASS, REFERENCE
    UNKNOWN, TARGET UNKNOWN, PROTOCOL PASS).
  - **The development-only internal reviews for PETCT_97320b0b58 (baseline liver, follow-up
    liver, baseline lesion) were NOT recorded.** They were blocked in-session pending the
    owner's direct confirmation. No review of any kind was created by the assistant.
- **Validation state:** the blinded package (`outputs/external_validation_cohort_v1/package_blinded/`)
  is unchanged. 0 reviewer forms returned. The release gate is in
  `docs/external_validation_pending.md`.
- **Commercial state:**
  - `docs/commercialization/` is complete: product definition, onboarding, pilot scope,
    pricing models (no prices), business model, discovery plan, design-partner program,
    website copy, one-pager, demo, DEMONSTRATION sample audit, company checklist, IP, intended
    use, quality roadmap, deployment, release gates, KPIs and readiness.
  - 0 interviews, 0 design partners, 0 customers.

```
COMMERCIALIZATION_PREPARATION_COMPLETE = YES
EXTERNAL_EXPERT_VALIDATION_PENDING = YES
DEVELOPMENT_ONLY_REVIEWS_FOR_PETCT_97320b0b58 = NOT RECORDED
```

## Outstanding blockers

1. **Owner decision:** either record the PETCT_97320b0b58 liver and lesion decisions yourself
   in the Reference Review and Lesion Review pages, or confirm directly that labelled
   DEVELOPMENT_ONLY internal acceptances should be implemented.
2. **External physicist review:** 0 forms returned; at least 2 independent reviewers needed.
3. **Customer discovery:** 0 of 20 interviews done. No design partner yet.
4. **Non-Siemens quantitative validation:** needs partner exports or phantoms.

## Next recommended action (on the new machine)

1. Restore the workspace and verify it: `docs/resume_on_new_machine.md` steps 1–7, which
   include `sha256sum -c MIGRATION_SHA256_20261009.txt` and `voxeltrace verify-bundle`.
2. Confirm 637 tests pass in a fresh venv.
3. Then, in this order:
   - (a) the owner's decision on the PETCT_97320b0b58 reviews;
   - (b) start the 20-interview discovery plan (`docs/commercialization/customer_discovery_plan.md`);
   - (c) send the blinded package at tag `v0.3.0-external-validation` to two independent
     PET physicists.
