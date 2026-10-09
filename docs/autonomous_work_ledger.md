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
