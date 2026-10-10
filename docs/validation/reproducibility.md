# Cross-run reproducibility (2026-10-09, x86_64)

**Question:** if the same audit is run twice from scratch, which artefacts are bit-identical,
which are only semantically identical, and why?

## Setup

- Real pair: PETCT_97320b0b58 (FDG-PET-CT-Lesions, Siemens Biograph128 mCT; baseline has a
  DICOM SEG), staged as symlinks in `outputs/reproducibility_20261009/trial` (no trial.yaml).
- Command, run twice in separate processes on a **clean** working tree (commit `ad79201`):
  `voxeltrace run-pilot --input trial --output run_E|run_F --trial-id REPRO-97320 --timepoints baseline followup`
- Comparison: every file of both output folders, byte for byte; JSON files that differ are
  re-compared with timestamps, runtime record and timings removed.

## Result (runs E and F)

148 files per run. **144 bit-identical.** The 4 that differ:

| File | Why it differs | Semantically identical? |
|---|---|---|
| `audit/audit_bundle/manifest.json` | `started_at`, `finalized_at` (seconds), `runtime_environment` | yes |
| `delivery_package/evidence_bundle/manifest.json` | copy of the above | yes |
| `delivery_package/DELIVERY_CHECKSUMS.sha256` | lists the sha256 of the manifest above | yes (every other line identical) |
| `pilot_run_log.json` | step timings | yes |

Bit-identical in both runs, among others: `checksums.sha256` of the evidence bundle (sha256
`6cfa4abf…84b2bf` in both), every rule-set `trial_audit.json`, `pair_checks.csv`, pair-verdict
CSVs, preflight, fingerprints, drift, pairing audit, site rollup, executive summary JSON/MD,
`AUDIT_PACKAGE_REPORT.pdf`, `executive_summary.pdf`, `pilot_acceptance.json` (input sha256
`2dbc0a95…14f862`), the delivery README, CSVs and evidence trace. Verdicts in both runs:
QIBA ASSESSABLE_WITH_WARNINGS, EANM ASSESSABLE_WITH_WARNINGS, PERCIST INSUFFICIENT_INFORMATION
(reference and lesion review pending), as in the frozen cohort.

Integrity of a delivered package should therefore be checked with `verify-delivery` /
`sha256sum -c`, and **equality of two runs with `checksums.sha256` of the evidence bundle**
(identical across runs), not with the manifest hash.

## Defect found and fixed

The first pair of runs (A, B, at commit `54fed92`) differed in
`rules/percist-1.0/site_summary.json`: the `insufficient_information_by_reason` counts were
identical but two tied reason codes were listed in a different order. Cause:
`trial/summary.py` iterated a Python `set` of reason codes, whose order follows the
per-process string-hash seed, and `Counter.most_common` keeps insertion order for ties. The
change propagated into `checksums.sha256` and the acceptance file's bundle hash. No count,
verdict or rule input was affected. Fixed in `ff378e4` (sorted iteration); regression test
`tests/test_fs_order.py::test_outputs_do_not_depend_on_python_hash_seed` runs a full audit under
`PYTHONHASHSEED=1` and `=2` and fails on the previous code.

A second pair (C, D) differed only in `reference_review_worksheet.yaml`, which records
`git_commit …+dirty` because run D started while the working tree had uncommitted edits. That
is correct provenance, and is why reproducibility runs must use a clean tree.

## Other reproducibility evidence

- **Across machines/architectures:** the 9-pair real cohort audited on x86_64 (this session)
  gives pair-verdict CSVs byte-identical to the frozen bundle produced on the aarch64 GB10.
- **Across filesystem listing order:** `tests/test_fs_order.py` reverses every directory
  listing (`iterdir`, `glob`, `rglob`, `os.walk`, `os.listdir`) and requires identical
  preflight, discovery, intake mapping, validate-input, input hashes and audit-bundle bytes.
- **PDFs** carry no creation date or random ID (`pdf.py`), so identical audits give identical
  bytes.

## Known non-deterministic fields (explicit)

`manifest.json: started_at, finalized_at, runtime_environment`; `pilot_run_log.json`; and
anything that records the git state (`git_commit`, `git_dirty`, worksheet `git_commit`) when
the code or tree differs. Everything else is expected to be bit-identical for identical
inputs, code and dependency versions. Dependency drift (e.g. a different numpy) is outside
this test; see [../dependency_strategy.md](../dependency_strategy.md).
