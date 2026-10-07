# Datasets

Each dataset has a **different purpose**. They differ in population, scanner, protocol,
reconstruction, units, annotation method and licence. They must **not be naïvely pooled**:
no combined statistics, no cross-dataset thresholds, and no model trained on one and reported
on another without an explicit harmonisation and validation plan.

All data live in `../data/<dataset>/` (never in Git) and are recorded in `../data/manifest.json`.

| Dataset | Source | Planned role | Status |
|---|---|---|---|
| **FDG-PET-CT-Lesions** | TCIA, DOI [10.7937/gkr0-xv29](https://doi.org/10.7937/gkr0-xv29), CC BY 4.0 (defaced public variant) | **Primary lesion / PET-CT demonstration.** Whole-body FDG PET/CT with manual lesion DICOM SEG; drives ingestion, geometry, SEG decoding, and later SUV + lesion metrics. | 1 subject (`PETCT_0011f3deaf`) — see [first_demo_case_plan.md](first_demo_case_plan.md) |
| **NSCLC-Radiogenomics** | TCIA | **Later: radiomics + clinical context.** CT/PET with clinical and genomic tables; for feature extraction and evidence objects that include clinical context. | not downloaded |
| **OpenNeuro PET** | OpenNeuro (BIDS / PET-BIDS) | **Research / BIDS / QC.** Brain PET with BIDS sidecars (often kinetic, dynamic frames); for BIDS ingestion and metadata-QC, not lesion work. | not downloaded |
| **ACRIN-NSCLC-FDG-PET** | TCIA (ACRIN 6668 trial) | **Later: longitudinal response analysis.** Multi-timepoint FDG PET in NSCLC; for paired baseline/follow-up comparison with strict per-timepoint QC. | not downloaded |

## Rules

- Download only what the current milestone needs, subject-scoped, with a size bound.
- Record collection, subject, source URL, timestamp, file count, bytes, checksums and licence
  in `../data/manifest.json` at download time.
- Keep each dataset's own licence and citation requirements (see manifest and collection page).
- Never attempt to re-identify participants. Never push imaging data to GitHub.
