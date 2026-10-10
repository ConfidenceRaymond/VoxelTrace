# Reproducibility on the local x86_64 machine (2026-10-10)

Complements [reproducibility.md](reproducibility.md) (first study, 2026-10-09). Same method,
current code, plus the delivery ZIP and the partner starter kit.

## Two runs from scratch

- Pair: PETCT_97320b0b58 (public, Siemens Biograph128 mCT, with SEG).
- Code: commit `5e590f3`, clean tree. Command, run twice in separate processes:
  `voxeltrace run-pilot --input <trial> --output run_G|run_H --trial-id REPRO-97320 --timepoints baseline followup`
- Outputs and per-file comparison: `<workspace>/outputs/reproducibility_20261010/` (`comparison.json`).

| Class | Files | Which |
|---|---|---|
| **BIT_IDENTICAL** | 144 | every verdict JSON (`rules/*/trial_audit.json`), pair CSVs, `pair_results.csv`, `site_summary.csv`, `scan_preflight.csv`, `pair_evidence_trace.csv`, preflight, fingerprints, drift, pairing audit, executive summary JSON/MD, `AUDIT_PACKAGE_REPORT.pdf`, `executive_summary.pdf`, `pilot_acceptance.json`, the evidence bundle's `checksums.sha256`, the delivery README, methodology and privacy scan |
| **SEMANTICALLY_IDENTICAL** | 0 | — |
| **EXPECTED_DIFFERENCE** | 4 | `audit/audit_bundle/manifest.json` and its copy in the package (`started_at`, `finalized_at`, `runtime_environment`); `pilot_run_log.json` (timings); `DELIVERY_CHECKSUMS.sha256` (only the line for `evidence_bundle/manifest.json`) |
| DIFFERENT (unexpected) | **0** | — |

**Delivery ZIP:** a deterministic ZIP of each delivery package (fixed timestamps and
permissions, sorted entries) differs between the two runs, because it contains the
manifest; that is an EXPECTED_DIFFERENCE. To compare two deliveries, compare the evidence
bundle's `checksums.sha256` (identical) or the package files except the manifest and the
delivery checksum list.

## Other reproducibility evidence from this session

| Comparison | Result |
|---|---|
| 9 real pairs: release check `v0.4.0` (x86) vs the frozen tag-check bundle (`a46526c`, GB10) | pair-verdict CSVs byte-identical (3 rule sets) |
| Simulated partner drop, staged and audited (dry run) vs the same source pairs in the frozen tag-check bundle | 24 / 24 verdict + reason-code rows identical |
| Demonstration audit (x86, after the relocation fix) vs the original GB10 demo audit | pair-verdict CSVs byte-identical (3 rule sets) |
| Partner starter kit ZIP built twice | byte-identical (sha256 `7d1e8b38…`, first build) |
| Filesystem listing order reversed; two Python hash seeds | identical outputs (`tests/test_fs_order.py`) |

## Defect found by reproduction this session

Re-running the demonstration audit on this machine changed PERCIST verdicts of the synthetic
fixtures. Cause: fixture manifests store absolute parent paths from the old machine
(path-portability bug; declared synthetic fixtures only; fail-safe direction). Fixed in
`6f782d0`, after which the demonstration verdicts match the original GB10 audit byte for byte.
Reproducer: `<workspace>/outputs/bug_repro_fixture_relocation_20261010/`.

## Known non-deterministic fields

`manifest.json: started_at, finalized_at, runtime_environment`; `pilot_run_log.json`;
anything recording git state when the tree or commit differs. Nothing else.
