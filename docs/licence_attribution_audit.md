# Licence and attribution audit (2026-10-09)

This is a factual inventory, not legal advice. It records which licences the project's code,
dependencies, data and models declare, and what attribution each one asks for. Whether a given
use is permitted is for the user or their institution to decide.

## VoxelTrace code

MIT (`LICENSE`), citation metadata in `CITATION.cff` (updated to 0.3.0 and the current scope).

## Runtime dependencies (declared licence, installed version)

| Package | Version | Declared licence |
|---|---|---|
| numpy | 2.5.3 | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 (as declared in metadata) |
| pydantic / pydantic-settings | 2.13.5 / 2.15.0 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| PyYAML | 6.0.3 | MIT |
| pydicom | 3.0.2 | MIT (classifier) |
| nibabel | 5.4.2 | MIT |
| SimpleITK | 2.5.6 | Apache-2.0 |
| Pillow | 12.3.0 | MIT-CMU |
| streamlit (app extra) | 1.65.0 | Apache-2.0 |
| plotly (app extra) | 7.1.0 | MIT |
| pytest, ruff (dev extra) | 9.1.1, 0.16.10 | MIT |

None is copyleft. Apache-2.0 packages carry NOTICE obligations when *redistributed*. VoxelTrace
does not redistribute them; they are installed by the user from PyPI.

The PDF writer (`src/voxeltrace/pdf.py`) uses only the standard PDF base-14 fonts by name, and
no font files are embedded.

## Imaging data used (verified against the local IDC index, `source_DOI` and `license_short_name` per downloaded series)

| Collection | Series used | Source DOI | Licence |
|---|---|---|---|
| ACRIN-NSCLC-FDG-PET (ACRIN 6668), PET and CT | 18 | 10.7937/tcia.2019.30ilqfcl | CC BY 3.0 |
| ACRIN-NSCLC-FDG-PET AI segmentations (BAMF analysis result) | 1 SEG (subject 168) | 10.5281/zenodo.8345959 | CC BY 4.0 |
| FDG-PET-CT-Lesions (autoPET) | 10 (PET, CT, SEG) | 10.7937/gkr0-xv29 | CC BY 4.0 |
| CC-Tumor-Heterogeneity | 4 | 10.7937/erz5-qz59 | CC BY 4.0 |
| CMB-MEL | 4 | 10.7937/gwsp-wh72 | CC BY 4.0 |

Each allow-list's recorded licence matches IDC for every series. Note that the ACRIN images
(CC BY 3.0) and the ACRIN AI SEG (CC BY 4.0) have **different** DOIs and licences. The
autoPET `fdg_metadata.csv` was range-read from the collection's own download archive and is
covered by the same collection licence.

**Attribution:** CC BY requires credit to the source. Any publication, report or slide that
shows results from these data should:

- cite each collection DOI above;
- cite TCIA (Clark et al., J Digit Imaging 2013) and/or IDC (Fedorov et al.) as the collection
  pages ask, checking each page for its exact citation text;
- state that VoxelTrace changed nothing in the source images.

The audit reports name subjects but do not yet print these citations. Adding a data-citation
block to reports that use public data is a recommended follow-up.

## OpenNeuro references (metadata only)

The brain census read OpenNeuro dataset metadata and file listings only; no image data was
downloaded. All eight datasets named in `docs/brain_future_validation_plans.md` declare CC0 in
the census. CC0 needs no attribution, but scholarly citation of each dataset DOI and of
OpenNeuro is customary. The licence must be re-read at the pinned version before any future
download.

## Uncertainties

- **Exact citation text per collection:** taken from the collection pages at publication
  time; not reproduced here.
- **autoPET `fdg_metadata.csv`:** read from the collection's own archive and assumed to be
  covered by the collection licence (CC BY 4.0); the archive has no separate licence file
  that was checked.
- **Standards documents** (QIBA, EANM, PERCIST) are cited, not reproduced. Their own terms
  were not assessed.
- **Dependency licences** are taken from package metadata, which is self-declared by each
  project.

## Models

| Model | Location | Declared licence | Use |
|---|---|---|---|
| Qwen3-VL-8B-Instruct | `../models/` (not in the repository) | apache-2.0 (model card) | optional, explanatory only; never part of the audit |

Model weights are never committed or redistributed.

## Standards and guidelines referenced

The QIBA FDG-PET/CT Profile 1.14, the EANM FDG PET/CT guideline 2.0 and PERCIST 1.0 (Wahl et
al. 2009; O JH et al. 2016) are cited by reference in each rule. Thresholds are restated as
short facts with their source. No guideline text is reproduced at length.

## Open items

1. Add per-collection data citations to reports built from public data.
2. Confirm the exact citation wording on each collection page before external publication.
