# First demo case: FDG-PET-CT-Lesions, one subject

## Source

- **Collection:** FDG-PET-CT-Lesions (TCIA), Version 2 (2026-08-17), DOI
  [10.7937/gkr0-xv29](https://doi.org/10.7937/gkr0-xv29).
- **Variant:** the public **"Images – Defaced"** variant (CC BY 4.0). Verified on 2026-10-07: the
  anonymous NBIA API reports `Site = TUEBINGEN-Defaced`, and its total size matches the defaced
  variant. The non-defaced originals are under NIH controlled access and are **not** used.
  Defacing removes everything above the base of the neck, so head findings are not meaningful.
- **Licence:** Creative Commons Attribution 4.0 (`LicenseName` field on every series in the API).
- **Usage policy:** TCIA Data Usage Policy. Do not attempt to re-identify participants.

### Required attribution

- **Data:** Gatidis, S., Kuestner, T. (2022). *A whole-body FDG-PET/CT dataset with manually
  annotated tumor lesions (FDG-PET-CT-Lesions)* (Version 2) [dataset]. The Cancer Imaging Archive.
  https://doi.org/10.7937/gkr0-xv29
- **Publication:** Gatidis, S., Hepp, T., Früh, M., La Fougère, C., Nikolaou, K., Pfannenberg, C.,
  Schölkopf, B., Küstner, T., Cyran, C., & Rubin, D. (2022). *A whole-body FDG-PET/CT Dataset with
  manually annotated Tumor Lesions.* Scientific Data 9(1). https://doi.org/10.1038/s41597-022-01718-3

## Subject selection

- **Rule:** take the first PatientID in alphabetical order that has exactly one study. This is
  deterministic and was not chosen for its findings.
- **Collection size:** `getPatient` returns 900 patients. `getSeries` returns 3042 series in 1014
  studies; 81 patients have more than one study.
- **Selected subject:** **`PETCT_0011f3deaf`**, with one study,
  `1.3.6.1.4.1.14519.5.2.1.4219.6651.389860614478618826979455610445`
  (description "PET-CT (Ganzkoerper  primaer mit KM)", date-shifted).

| Modality | Description | SeriesInstanceUID | Images | NBIA FileSize (B) |
|---|---|---|---|---|
| CT | GK p.v.3 | 1.3.6.1.4.1.14519.5.2.1.239537544060707922869401739533283658263 | 391 | 206,547,620 |
| PT | PET corr. | 1.3.6.1.4.1.14519.5.2.1.250262599227532712559738773326631678839 | 326 | 105,881,940 |
| SEG | Segmentation | 1.3.6.1.4.1.14519.5.2.1.272081938480691888926338328195688355213 | 1 | 6,746,800 |

- **Expected total:** 319,176,360 bytes (about 319 MB). Download it as three per-series zips.
- **Expected modalities:** PT, CT and one DICOM SEG (written by QIICR/dcmqi).
- **SEG checks after download:** confirm from the file that the SEG references the PT series and
  that its `SegmentationType` is BINARY. The API cannot confirm either.

## Retrieval mechanism

- **API:** TCIA NBIA REST **v4**, anonymous: `https://services.cancerimagingarchive.net/nbia-api/services/v4`.
  - Use v4 rather than v1. TCIA's helpdesk support for the older APIs ends in October 2026.
  - v2 requires a token.
  - TCIA describes NBIA as legacy and is steering public data toward the Imaging Data Commons
    (`idc-index`). If NBIA stops serving this collection, the same three series should be fetched
    from IDC by their SeriesInstanceUIDs.
- **Script:** `scripts/fetch_tcia_subject.py`:

```bash
# Dry run: metadata only, prints the series and their sizes
.venv/bin/python scripts/fetch_tcia_subject.py --collection FDG-PET-CT-Lesions \
    --patient PETCT_0011f3deaf --out ../data/fdg_pet_ct_lesions --dry-run
# Download
.venv/bin/python scripts/fetch_tcia_subject.py --collection FDG-PET-CT-Lesions \
    --patient PETCT_0011f3deaf --out ../data/fdg_pet_ct_lesions
```

What the script does:

1. Calls `getSeries?Collection=…&PatientID=…`.
2. Keeps only the rows whose `PatientID` matches.
3. Refuses if the subject has more than one study and `--study` was not given.
4. Refuses if the total exceeds `--max-bytes` (default 1 GB).
5. Calls `getImage?SeriesInstanceUID=<uid>` once for each listed series and for nothing else.
6. Refuses to overwrite an existing subject directory.

## Verifying that only one subject was retrieved

- `../data/manifest.json` lists exactly one subject, one study and three series.
- Each zip's SHA-256 and extracted file count are recorded.
- `scripts/inspect_case.py ../data/fdg_pet_ct_lesions/PETCT_0011f3deaf` finds
  **1 study and 3 series**, and the instance counts match the table above (391 / 326 / 1).
- `du -sh ../data/fdg_pet_ct_lesions` is about 2 × 319 MB, because both the zips and the
  extracted files are kept.

## Provenance to record

- Collection, version and variant.
- Subject ID, StudyInstanceUID and SeriesInstanceUIDs.
- API base URL and endpoints.
- Download timestamp (UTC).
- Bytes and SHA-256 for each zip, and extracted file counts.
- SHA-256 of the saved NBIA series metadata JSON.
- Licence and the citation text.

## Outcome

See `../data/manifest.json` (kept outside Git) and `docs/validation.md`.
