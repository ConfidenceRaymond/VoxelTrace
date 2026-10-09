# Performance and scale (measured 2026-10-09)

**Machine:** 20 cores, 121 GB RAM, NVMe. The audit is single-process and CPU-bound; no GPU
is used.

**Harness:** `scripts/benchmark.py`. It builds trial folders from local real data with
file-level symlinks (no image duplication; SEG excluded) and times each command in a
subprocess with `/usr/bin/time -v`.

**Raw results:** `../outputs/benchmark/benchmark.json`.

| Dataset | Subjects / scans | DICOM files | Input |
|---|---|---|---|
| trial_1 (ACRIN 168) | 1 / 2 | 780 | 220 MB |
| trial_8 (5 ACRIN + 3 external pairs, GE/Siemens/CPS) | 8 / 16 | 6,853 | 1,869 MB |

| Step | trial_1 wall / peak RSS | trial_8 wall / peak RSS |
|---|---|---|
| `voxeltrace preflight` (headers only) | 1.0 s / 185 MB | 9.0 s / 215 MB |
| `voxeltrace audit` QIBA only, no input hashing | 7.0 s / 1.09 GB | 58.2 s / 2.38 GB |
| `voxeltrace audit` 3 rule sets + input hashing + bundle | 18.9 s / 1.10 GB | 155.5 s / 2.41 GB |

| Derived | trial_1 | trial_8 |
|---|---|---|
| Preflight throughput | 780 headers/s | 761 headers/s |
| Full audit throughput | 3.2 subjects/min, 12.7 series/min | 3.1 subjects/min, 12.4 series/min |
| Bundle size | 0.46 MB | 3.4 MB (QC images off) |

**Peak temp disk:** none beyond the output bundle. Volumes are processed in memory; the audit
writes no temporary image copies.

## Interpretation and limits

- **Throughput is linear** in scans at about 3 subjects/min for the full package. A
  300-subject × 2-timepoint retrospective audit would take about 1.6 h on this machine.
- **Repeated work:** the full audit runs the trial audit once per rule set. Ingestion, strict
  SUV and reference proposals are therefore repeated 3 times; QIBA alone is about 2.7× faster.
  Computing timepoints once and applying the three rule sets is the main optimisation
  (recorded as technical debt; not changed here to keep the validated audit path untouched).
- **Memory:** peak RSS (about 2.4 GB at 8 subjects) is dominated by holding loaded PET/CT
  volumes for the timepoints of a trial. It grows with subject count because the audit keeps
  timepoint objects until pairs are assessed. Very large trials should be audited in site or
  subject batches.
- **Metadata scale:** census v3 read about 13,000 sampled headers by HTTP byte range from IDC.
  That run was network-bound (about 651 MB, roughly 45 min with 8 threads), not CPU-bound.
- **Not measured:** multi-node or parallel execution, and image-volume reading over network
  storage.
