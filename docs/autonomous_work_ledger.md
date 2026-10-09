# Autonomous work ledger

Started 2026-10-08. Updated throughout the run. Status values: NOT_STARTED, IN_PROGRESS,
COMPLETE, COMPLETE_WITH_LIMITATION, BLOCKED.

The only remaining occurrences of the word "hackathon" are the fixed workspace directory name
(`/home/dell/voxeltrace_hackathon`). Renaming it would break every path, so it is left as is.

| # | Workstream | Status | Files | Tests | Commit | Pushed | Limitations | Next dependency |
|---|---|---|---|---|---|---|---|---|
| 0 | Close QIBA attestation + cross-collection census | COMPLETE | evidence/attestation.py, rules/qiba_identity.py, scripts/census_v3_*.py, docs/census_v3_public_pet.md | 488 pass | 57bc8d4, c580a25, f4b25d8 | yes | census verdicts assume voxel size confirmed on download | WS1 |

CURRENT_ASSIGNMENT_COMPLETE = YES
| 1 | External real-case selection | COMPLETE | scripts/census_v3_public_pet.py (per-rule-set classes), docs/census_v3_public_pet.md | test_census_v3 (19) | b06cfd9 | yes | no decidable GE/Philips/UIH pair exists in open data | WS2 |
| 2 | Conditional external downloads | COMPLETE | configs/external_longitudinal/ (frozen plans + hashes, allow-lists), scripts/plan_external_download.py, scripts/fetch_bounded_series.py | plan-only checks | b06cfd9 (plans frozen before download) | yes | 3 pairs, 859,077,842 bytes; cmb_mel plan picked a localizer CT (recorded before download) | WS3 |
| 3 | Full external validation | COMPLETE_WITH_LIMITATION | scripts/analyze_external_longitudinal.py, docs/external_validation_v1.md | full suite | e1b7f40 | yes | PERCIST needs human liver review; lesion SEG withheld (no lesion review gate) | WS11 lesion/pair review |
| 4 | Quantitative Preflight + CLI | COMPLETE | src/voxeltrace/preflight/, src/voxeltrace/cli.py | test_preflight (18) | ffa7ba5 | yes | header-only; multi-bed timing via validator only | WS5 |
| 5 | Protocol fingerprint v1 (VT-PROTOCOL-FP-1) | COMPLETE | evidence/fingerprint.py | test_fingerprint_drift (15) | d663541 | yes | acquisition_mode_2d_3d never extracted (explicit MISSING) | WS6 |
| 6 | Protocol difference engine | COMPLETE | evidence/fingerprint.py (compare_protocol_fingerprints, identity_view) | parametrized agreement with VT-PROTOCOL-IDENTITY; 8/8 real pairs agree | d663541 | yes | uptake/dose are WARNING here (blocking in compare_protocols category) | WS7 |
| 7 | Site drift engine (VT-DRIFT-1) | COMPLETE | trial/drift.py | test_fingerprint_drift | d663541 | yes | uptake/dose outlier thresholds heuristic (labelled) | WS8 |
| 8 | Whole-trial audit v2 | COMPLETE_WITH_LIMITATION | pilot.py | test_pilot_bundle (15) | 33962d5 | yes | no PDF (Markdown/JSON/CSV only) | WS10 |
| 9 | Schema versioning | COMPLETE | versions.py, docs/schema_versioning.md | test_pilot_bundle | 33962d5 | yes | none | — |
| 10 | Immutable evidence bundle + verify-bundle | COMPLETE_WITH_LIMITATION | bundle.py | tamper tests (4 kinds) | 33962d5 | yes | integrity only, not a signature | — |
| 11 | Pair-level human adjudication | COMPLETE | trial/adjudication.py, cli adjudicate | test_pilot_bundle | 33962d5 | yes | no UI page yet (CLI only); no lesion review gate yet | — |
| 12 | Site query generator | COMPLETE | trial/site_queries.py | test_pilot_bundle | 33962d5 | yes | template set covers main codes only | — |
| 13 | Pilot CLI | COMPLETE | cli.py (preflight, inspect, audit, verify-bundle, summarize, list-reviews, adjudicate) | CLI tests | 33962d5 | yes | — | WS21 install test |
| 15 | Failure-injection suite + coverage matrix | COMPLETE | tests/test_failure_injection.py, scripts/reason_coverage.py, docs/failure_injection_coverage.md | 117/117 emittable codes | 620dfd9 | yes | 4 pixel-stage guards are GUARD_ONLY; 3 catalog codes never emitted | — |
| 20 | CI | COMPLETE | .github/workflows/ci.yml | GitHub run 37864931413 success (3.11, 3.12) | 56e6e88 | yes | synthetic data only by design | — |
| 21 | Package/install hardening | COMPLETE | pyproject.toml (Pillow declared) | fresh venv: install + CLI + 567 tests | 56e6e88 | yes | Python 3.12 verified locally, 3.11 in CI | — |
| 14 | Performance benchmark | COMPLETE_WITH_LIMITATION | scripts/benchmark.py, docs/performance.md | measured | 69e0cda | yes | single machine; repeated per-rule-set ingestion | WS28 debt |
| 10 | Reconstruction attestation operational workflow | COMPLETE | cli attestation-template / validate-attestations, docs/attestation_workflow.md | test_qiba_attestation (42) | 95e0fbc | yes | QIBA only by design | — |
| 16 | Vendor/scanner knowledge base | COMPLETE_WITH_LIMITATION | configs/vendor_kb.yaml, scripts/build_vendor_kb.py, docs/vendor_knowledge_base.md | test_vendor_kb | 9067022, bb9287b | yes | many models NOT_OBSERVED; conformance docs only where actually read | — |
| 17 | External physicist validation package | COMPLETE | expert_validation.py, cli export-validation / score-validation, docs/expert_validation_protocol.md | test_expert_validation | 06114d3 | yes | no expert labels collected yet | external reviewers |
| 18 | Pilot SOP / data requirements / checklist / limitations / deployment | COMPLETE | docs/pilot_sop.md, data_requirements.md, pilot_validation_checklist.md, known_limitations.md, deployment.md | — | 28ec777 | yes | — | — |
| 19 | Security/privacy review | COMPLETE_WITH_LIMITATION | scripts/privacy_scan.py, bundle path pseudonymisation, docs/security_and_privacy.md | test_pilot_bundle | e4d12c2 | yes | no signature; no compliance claimed | — |
| 26 | AI architecture freeze | COMPLETE | docs/ai_policy.md, tests/test_ai_freeze.py, voxeltrace/ids.py | test_ai_freeze | 0be7288 (red), 47a0cbc (fix) | yes | INCIDENT: 0be7288 was pushed with a failing test (pytest exit masked by a pipe); fixed in 47a0cbc; commit gate now checks the real exit code | — |
| 29 | End-to-end dry run | COMPLETE | docs/end_to_end_example.md | real ACRIN 168 via CLI; review hash unchanged | 28ec777 | yes | — | — |
| 22 | Brain PET / OpenNeuro metadata census | COMPLETE_WITH_LIMITATION | scripts/brain_pet_census.py, docs/brain_pet_census.md | — | c00dcee | yes | ≤ 3 sidecars per dataset; 15 datasets UNKNOWN static/dynamic (sidecar beyond listing cap) | — |
| 23 | Local brain-study intake | COMPLETE | brain_intake.py, cli inspect-brain | test_brain_intake | c00dcee | yes | inventory only by design | — |
| 24 | PET/MR future architecture | COMPLETE (planning) | docs/pet_mr_architecture.md | — | c00dcee | yes | no implementation by design | — |
| 25 | Commercial pilot package | COMPLETE | docs/commercial/* | — | c00dcee | yes | no discovery interviews held | customer discovery |
| 27 | Product readiness scorecard | COMPLETE | docs/product_readiness.md | — | e216066 | yes | — | — |
| 28 | Technical debt audit | COMPLETE_WITH_LIMITATION | docs/technical_debt.md, app path fixes | full suite | cc8ba5d | yes | repeated per-rule-set ingestion and lesion review gate remain | — |
| 30 | Storage / cleanup audit | COMPLETE | docs/storage_audit.md | — | 0c18f2b | yes | INCIDENT: ~/.cache/pip created by the install test, removed | — |

## Session closure (2026-10-09)

- Final validation: pytest 580 passed (exit 0); ruff check and format clean; git diff --check
  clean; working tree clean; main == origin/main; no history rewritten.
- Invariants since session start f4b25d8: no change to `quant/`, the QIBA/EANM/PERCIST/common/
  VT rule modules, `evaluation/` or `configs/expectations` (manifest 603df5ef); the 168 review
  file is unchanged (6433b89f); frozen evaluation outputs have no newer files.
- Downloads: 3 pairs, 859,077,842 bytes (budget ≤ 3 pairs, ≤ 2.5 GB), plans frozen before
  download (b06cfd9).

## Design-partner cycle (2026-10-09, from 286c11c)

| # | Workstream | Status | Files | Tests | Commit | Pushed | Limitations | Next dependency |
|---|---|---|---|---|---|---|---|---|
| P1 | Lesion evidence review gate, source trust, page, CLI | COMPLETE | trial/lesion_review.py, lesion_review_context.py, visualization/lesion_qc.py, app/pages/6_Lesion_Review.py, cli.py | 25 (test_lesion_review) | 2a3a388, ca9d5eb, 54b8349, 2c9c074, f584c93 | yes | ADJUST not offered (no safe voxel editing) | human reviews |
| P2 | 168 AI SEG (frozen plan, 225,734 B), imported AI_GENERATED/UNREVIEWED | COMPLETE | configs/.../frozen_plans/*AI_SEG.json | — | 0869831 | yes | not approved (by design) | human review |
| P3 | PERCIST target ranking + PETCT_97320b0b58 (frozen plan a2d19939, 534 MB) | COMPLETE_WITH_LIMITATION | docs/percist_first_real_case.md, scripts/fetch_zip_member.py | — | 05256af, c9b598b | yes | complete verdict needs human liver + lesion review | reviewer |
| P4 | PERCIST readiness layers | COMPLETE | trial/layers.py | 4 | c9b598b | yes | reporting only | — |
| P5 | Blinded validation hardening + scoring + docs; 9-pair real cohort | COMPLETE | expert_validation.py, docs/external_validation/* | 7 | 05ce424 | yes | no forms returned | reviewers |
| P6 | Vendor matrix + non-Siemens strategy | COMPLETE | docs/vendor_validation_matrix.md, docs/non_siemens_validation_strategy.md | — | 9b46e74 | yes | GE/Philips not quantitatively validated | design partner / phantom |
| P7 | Report top page, executive summary, reproducible PDF | COMPLETE | executive.py, pdf.py, pilot.py | 4 | e00ed78, 1567002 | yes | text-only PDF | — |
| P8 | validate-input, data-inventory | COMPLETE | validate_input.py, inventory.py | 13 | 32674ff | yes | — | — |
| P9 | Versioning 0.3.0, RC proposal, repo + licence audits | COMPLETE | CHANGELOG.md, CITATION.cff, docs/*audit*.md, docs/release_candidate_proposal.md | 1 | 1567002, bf2463d | yes | tag not created (owner decision) | owner |
| P10 | Design-partner readiness, discovery guides, brain plans | COMPLETE | docs/design_partner_readiness.md, docs/commercial/discovery_*.md, docs/brain_future_validation_plans.md | — | 0e35244 | yes | no partner yet | outreach |

- **Invariants since 286c11c:**
  - no change to `quant/`, `evaluation/` or `configs/expectations`;
  - the only rule-module change is `rules/percist.py`: a LESION_REVIEW_REQUIRED reason and a
    target-evidence label, with an unchanged threshold;
  - the 168 reference review file is unchanged (6433b89f);
  - the 168 audits regenerate with identical values, statuses, hashes and verdicts;
  - the synthetic demo matches its frozen manifest (explicit synthetic-only legacy lesion
    policy).
- **Downloads this cycle:**
  - 168 AI SEG, 225,734 B;
  - PETCT_97320b0b58, 534,373,170 B;
  - autoPET `fdg_metadata.csv`, 1.38 MB range-read from a 303.8 GB archive.

  Every series download was planned and committed before the fetch.
- **No review of any kind was created.** SIMULATED reviews exist only inside tests.
