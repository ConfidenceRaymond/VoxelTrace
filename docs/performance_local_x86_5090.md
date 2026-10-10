# Performance baseline: local x86_64 machine with RTX 5090 (2026-10-09)

**The deterministic audit does not use the GPU.** Every number below is CPU-only; the RTX 5090
was idle (desktop only) during the runs. No GPU acceleration was added.

## Machine

| Item | Value |
|---|---|
| CPU | AMD Ryzen 9 9950X, 16 cores / 32 threads, max 5.76 GHz |
| RAM | 188 GB |
| Disk | NVMe, ext4 (`/`), 1.1 TB free |
| GPU | NVIDIA RTX 5090, 32 GB (not used by the audit) |
| OS / Python | Ubuntu 24.04, Linux 7.0, Python 3.12.3, numpy 2.5.3, pydicom 3.0.2, SimpleITK 2.5.6 |
| Code | VoxelTrace 0.3.0 + 0.4.0 pilot-hardening commits (`c4618c8`…) |

## Harness benchmark (`scripts/benchmark.py`, same datasets as the GB10 run)

Raw: `outputs/benchmark_x86_5090_20261009/benchmark.json`. Inputs are symlinked real public
data (SEG excluded); each command is timed in a subprocess with `/usr/bin/time -v`.

| Step | trial_1 (1 subject, 2 scans, 780 files, 220 MB) | trial_8 (8 subjects, 16 scans, 6,853 files, 1.87 GB) | GB10 trial_8 (`performance.md`) |
|---|---|---|---|
| `preflight` (headers only) | 1.2 s / 212 MB | 11.9 s / 242 MB | 9.0 s / 215 MB |
| `audit` QIBA only, no input hashing | 7.1 s / 1.14 GB | 63.6 s / 2.44 GB | 58.2 s / 2.38 GB |
| `audit` 3 rule sets + input hashing + bundle | 19.0 s / 1.15 GB | 175.5 s / 2.45 GB | 155.5 s / 2.41 GB |
| Throughput (full audit) | 3.2 subjects/min | 2.7 subjects/min | 3.1 subjects/min |
| Preflight header rate | 661 headers/s | 578 headers/s | 761 headers/s |
| Bundle size | 0.46 MB | 3.25 MB | 3.4 MB |

The x86 machine is within about 13 % of the GB10: the audit is a single Python process, so
core count does not help and per-core speed is similar. Some background activity (editing,
lint) ran during the x86 measurement; treat ±10 % as noise.

## Pilot-workflow timings (real data, this session)

| Operation | Data | Wall time | Peak RSS |
|---|---|---|---|
| DICOM discovery (`inspect`), one scan | ACRIN-168 baseline, 390 files | 0.56 s | 217 MB |
| `validate-input` | 9-pair cohort, 18 scans | 12–13 s | — |
| `intake-map` + stage | simulated partner drop, 16 scan folders, ~7,150 files | 4.4 s | — |
| single-pair `run-pilot` (all steps) | PETCT_97320b0b58 (with SEG) | 43 s | — |
| 9-pair `run-pilot` (all steps) | 9 real pairs, 18 scans, 2.3 GB | 3 min 49 s (audit 215 s) | 2.93 GB |
| 7-pair `run-pilot` | staged partner drop | 3 min 22 s (audit 190 s) | 2.92 GB |
| `verify-bundle` | 9-pair bundle, 60 files | < 0.3 s | — |
| delivery package build (incl. privacy scan) | 9-pair | 0.5–0.6 s | — |
| `verify-delivery` | 9-pair package, 80 files | 0.4 s | — |

Profile of a one-subject full audit (`cProfile`, overhead-inflated): building the timepoints
(DICOM ingest, strict SUV, reference-region proposals, lesion metrics) is about 92 % of the
time, repeated once per rule set; preflight about 7 %; pairing audit, site rollup, reports, PDF
and bundle finalisation together well under 1 %.

## Disk I/O

- Reads: every input file is read once per rule set (3×) plus once for input hashing; the
  page cache absorbs repeats (`/usr/bin/time` reported 0 file-system input blocks on warm
  runs).
- Writes: only the bundle and package (≈ 3–8 MB per 9 pairs); no temporary image copies.

## Implications

- About **25 s per pair** for the full three-rule-set pilot on this machine; a 300-pair
  retrospective audit ≈ 2 h, memory growing with subjects (batch large trials by site).
- The obvious optimisation (build timepoints once and apply the three rule sets) would cut the
  audit by roughly 2.5×; it is recorded as technical debt and deliberately not done in this
  session because it touches the validated audit path.

## Additions 2026-10-10 (pilot workflow commands, CPU only; GPU unused by the audit)

| Operation | Data | Wall | Peak RSS |
|---|---|---|---|
| `validate-partner-intake` | 16 entries, PET header check | 0.4 s | 194 MB |
| `validate-input` | nested simulated drop, 16 visit folders | 13.6 s | 408 MB |
| `intake-map` | same drop, ~7,150 files | 4.3 s | 301 MB |
| `intake-map --stage` | resolved drop | 4.5 s | 299 MB |
| `preflight` | 16 staged scans | 11.3 s | 254 MB |
| single-pair `run-pilot` | PETCT_97320b0b58 | 41–45 s | — |
| 8-pair `run-pilot` | staged public drop | 188 s | 2.93 GB |
| 9-subject demonstration `run-pilot` | 7 synthetic pairs + 2 single scans | 6 min 20 s (audit 360 s) | — |
| delivery package build | 8–9 pairs | 0.3–0.7 s | — |
| `verify-delivery` / `verify-bundle` | 80-file package / 60-file bundle | 0.9 s / 0.3 s | 200 MB |
| `deployment-lock capture` / `verify` | 55 packages | 0.3 s each | 195 MB |
| starter kit build (incl. privacy scan, deterministic ZIP) | 97 files | < 2 s | — |

Disk: inputs are read through symlinks and the page cache; outputs are a few MB per run. The
optional Qwen explanation smoke test used the GPU only (16.6 GiB) and is not part of the audit.
