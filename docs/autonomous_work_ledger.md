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
