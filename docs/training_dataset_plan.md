# Training/evaluation dataset plan

Verified on 2026-10-07 with the anonymous TCIA NBIA v4 metadata API, the collection pages, the
FDG-PET-CT-Lesions clinical CSV and the OpenNeuro GraphQL API. **No bulk downloads.** Datasets
serve different purposes and are **not pooled naïvely** (see datasets.md).

## Inventory

| | FDG-PET-CT-Lesions | NSCLC Radiogenomics | ACRIN-NSCLC-FDG-PET (ACRIN 6668) | OpenNeuro PET (e.g. ds004869, ds002898) |
|---|---|---|---|---|
| Reference labels | **DICOM SEG on the PET grid** (manual lesion masks, dcmqi); diagnosis in the clinical CSV (NEGATIVE / MELANOMA / LUNG_CANCER / LYMPHOMA) | DICOM SEG on the **diagnostic CT** (144 patients, separate CT study; not on the PET), AIM XML, clinical CSV (histology, mutations, survival) | **No SEG/RTSTRUCT**; clinical XLS with SUVmax/SUVpeak, follow-up, survival | BIDS sidecars (tracer, dose, frames, recon), blood data, kinetic derivatives; no lesion masks |
| Modalities | PET/CT (+SEG) | CT, PET/CT, SEG | PET/CT (+CT, MR, NM, CR) | PET + T1w MRI (ds002898 also BOLD) |
| Longitudinal | 81 of 900 patients have 2–5 studies; 30 patients have both positive and NEGATIVE studies | not longitudinal for PET (1 PET study per patient; CT and PET in separate studies) | **yes**: 189 of 241 patients have ≥ 2 PET studies (pre/post therapy) | test/retest or baseline/blocked sessions (ds004869) |
| Scanner diversity | Siemens only: Biograph128(_mCT) and SOMATOM Definition AS(_mCT); scanner confounded with diagnosis (no negatives on SOMATOM) | GE Discovery STE/690, Philips, Siemens (many model names missing) | very high: 37 sites, GE/Philips/Siemens/CPS; includes non-attenuation-corrected series | Siemens mCT / mMR |
| Tracers | FDG | FDG | FDG | [11C]MC1, [18F]FDG, others |
| Value for VoxelTrace | **primary**: localisation, lesion metrics, negatives, claims | radiomics and clinical context (needs CT→PET registration; not a PET-mask source) | longitudinal comparability and claim gating (protocol pairs) | BIDS ingestion and protocol QC; not lesions |
| Leakage risk | repeat studies, and the same patient appearing as both positive and negative → **split by patient** | the same patient in CT and PET studies; Stanford subset and derived collections reuse images | repeat timepoints → split by patient | repeated sessions → split by subject |
| License | CC BY 4.0 (defaced public variant) | CC BY 3.0 | CC BY 3.0 | CC0 |
| Footprint | 418.95 GB in total; per patient median 319 MB (196 MB–2.32 GB) | 98.0 GB; median 397 MB per patient | 145.5 GB; median 581 MB per patient | ds004869 8.4 GB; ds002898 52.5 GB (1.86 GB per subject) |

**Join pitfall:** the FDG-PET-CT-Lesions clinical CSV series UIDs are pre-defacing UIDs. Join on
StudyInstanceUID or Subject ID instead.

## Ranked future subjects (FDG-PET-CT-Lesions, single study, < 1 GB)

| Rank | Subject | Diagnosis (CSV) | Scanner | Size | Status |
|---|---|---|---|---|---|
| — | PETCT_0011f3deaf | MELANOMA | Biograph128 / _mCT | 319 MB | downloaded (Milestone 2) |
| 1 | PETCT_db3bac356a | NEGATIVE | Biograph128 / _mCT | 313 MB | **downloaded (this milestone)** |
| 2 | PETCT_bd52fdf529 | LUNG_CANCER | **SOMATOM Definition AS / _mCT** | 548 MB | **downloaded (this milestone)** |
| 3 | PETCT_0beb67c923 | LYMPHOMA | PT "Biograph128" (1 of 3 such) | 629 MB | candidate |
| 4 | PETCT_5e2da717db | LUNG_CANCER | Biograph128_mCT | 319 MB | candidate (scanner contrast with #2) |
| 5 | PETCT_e68c4577d8 | NEGATIVE, non-contrast CT | Biograph128 / _mCT | 313 MB | candidate |

## Path to a real training set

- Select at least 20 subjects (later 100+), balanced across:
  - diagnosis, including negatives;
  - scanner model;
  - contrast protocol.
- Patients with repeat studies are kept whole.
- Build each subject with `scripts/build_dev_dataset.py`.
- Assign splits with `assign_patient_splits` (salted hash, patient level).
- Freeze and hash LOCKED_TEST.
- Report the scanner × diagnosis confound explicitly. Do not let a model learn
  "SOMATOM = cancer".
