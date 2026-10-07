# Validation log

Records of what has actually been verified. Do not add claims that were not run.

## Milestone 0/1 - project foundation (2026-10-07)

| Check | Command | Result |
|---|---|---|
| Unit tests | `make test` | `18 passed in 0.14s` |
| Lint | `make lint` / `ruff format --check .` | `All checks passed!` / `15 files already formatted` |
| App import / render | Streamlit `AppTest` headless run of `app/Home.py` | no exceptions; title, disclaimer, synthetic-data banner, AI-status warning rendered |
| App server | `scripts/run_app.sh` on port 8599, `GET /_stcore/health` | `200 ok`; server stopped afterwards |

### `compute_image_stats` verified behaviours (tests/test_image_stats.py)

- Finite arrays: min/max/mean/std(ddof=0)/median/p1/p99 against hand-computed values.
- NaN / +inf / -inf counted separately and excluded from intensity statistics; input not modified.
- All-zero arrays.
- Arrays with no finite voxels: intensity fields are `None`.
- Integer arrays computed in float64 (no overflow).
- Rejected: non-ndarray, string, bool, complex, empty arrays.
- Determinism: identical results on repeated calls.

### Not yet validated

No PET data has been processed. No SUV, lesion, or clinical metric is implemented or validated.

## Planned datasets

| Dataset | Source | Status |
|---|---|---|
| FDG-PET-CT-Lesions | TCIA | not downloaded |
| NSCLC-Radiogenomics | TCIA | not downloaded |
| ACRIN-NSCLC-FDG-PET | TCIA | not downloaded |
| OpenNeuro PET | OpenNeuro | not downloaded |
