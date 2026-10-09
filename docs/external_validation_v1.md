# External real-pair validation v1 (outside ACRIN; 2026-10-09)

REAL public data (IDC, CC BY 4.0). RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.
- The validator, rules and thresholds are unchanged.
- No review or decision was created; every reference proposal awaits a human.

## Selection and download (frozen before download)

**Census:** census v3 ([census_v3_public_pet.md](census_v3_public_pet.md)). Three pairs were
chosen to cover three different verdict paths. No GE, Philips or United Imaging pair is
decidable in the open data, so all three are Siemens, from three collections, sites and
software generations.

**Frozen before any byte was downloaded** (commit `b06cfd9`): plans, sha256 hashes and
allow-lists, in `configs/external_longitudinal/frozen_plans/` and
`configs/external_longitudinal/allowlist_*.json`.

| Plan | Collection / subject | Series | Files | Bytes downloaded | Purpose |
|---|---|---|---|---|---|
| `4244451c…` | fdg_pet_ct_lesions / PETCT_c2ffda4725 | PET×2, CT×2, baseline SEG | 1,065 | 468,597,972 | full QIBA/EANM/PERCIST path, structured reconstruction |
| `ce68f3b0…` | cc_tumor_heterogeneity / CCTH-B02 | PET×2, CT×2 | 1,059 | 348,568,168 | older software (syngo 2011A), no height (real SUL refusal) |
| `566af5f9…` | cmb_mel / MSB-07612 | PET×2, CT×2 | 486 | 41,911,702 | negative control: predicted decided NOT_ASSESSABLE (uptake) |
| **Total** | | | **2,610** | **859,077,842** | budget: ≤ 3 pairs, ≤ 2.5 GB |

**Fetcher:** `scripts/fetch_bounded_series.py`, which:
- reads exact series prefixes only;
- checks instance count and size against the plan before download;
- checks PatientID, Study, Series and Modality on every file;
- records a per-file sha256 and ETag in
  `../data/external_longitudinal/<collection>/provenance_manifest__<subject>.json`.

**Known plan limitation, recorded before download:** the cmb_mel plan's "smallest CT in the PET
frame" rule picked a 1-instance CT (a localizer). That plan was not modified. The rule is fixed
for future plans (≥ 20 instances).

## Results (`scripts/analyze_external_longitudinal.py`; outputs in `../outputs/external_longitudinal/`)

| | autoPET PETCT_c2ffda4725 | cc_tumor CCTH-B02 | cmb_mel MSB-07612 |
|---|---|---|---|
| Scanner / software | Siemens Biograph128 mCT, VG60A / VG60A | Siemens Biograph64, syngo MI.PET/CT 2011A ×2 | Siemens Biograph40 mCT, VG62B ×2 |
| Ingestion | OK / OK | OK / OK | PET OK; CT is a 1-slice localizer |
| Strict SUV | **PASS / PASS** | **PASS / PASS** | **PASS / PASS** |
| DecayFactor cross-check | **VERIFIED / VERIFIED** (242/242 slices) | **VERIFIED / VERIFIED** | **VERIFIED / VERIFIED** |
| SUL (James) | **PASS / PASS** | REFUSED (no PatientSize) | REFUSED (PatientSex `O`) |
| Uptake (min) | 60.05 / 60.12 | 71.12 / 66.22 | 82.67 / 79.08 |
| Dose (MBq) | 320 / 319 | 376 / 371 | 462 / 444 |
| Reconstruction | PSF+TOF 2i21s (structured), same | PSF 3i24s, same | PSF 3i12s, same |
| Protocol comparability | COMPARABLE | COMPARABLE | COMPARABLE |
| **QIBA 1.14** | **ASSESSABLE** | **ASSESSABLE** | **NOT_ASSESSABLE** (uptake window) |
| **EANM 2.0** | **ASSESSABLE_WITH_WARNINGS** (EARL never encoded) | **ASSESSABLE_WITH_WARNINGS** | **NOT_ASSESSABLE** (uptake window) |
| PERCIST 1.0 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION |
| PERCIST blockers | liver review pending; lesion SEG withheld (no lesion review gate) | liver review pending; no SUL | SUL refused; no volumetric CT → no reference region |
| Reference proposals | liver + blood pool PROPOSED_REQUIRES_REVIEW (both timepoints) | liver + blood pool PROPOSED_REQUIRES_REVIEW | AUTO_NOT_FOUND (localizer CT) |

**These are the first real pairs in the project with fully decided, evidence-backed QIBA and
EANM verdicts:**
- two ASSESSABLE pairs;
- one decided NOT_ASSESSABLE pair.

Before this, every real pair was INSUFFICIENT_INFORMATION or NOT_ASSESSABLE (ACRIN).

## Census accuracy (frozen prediction vs full-series truth)

**30 compared fields: 29 match, 1 miss.**

| Pair | Miss | Cause |
|---|---|---|
| cmb_mel | **SUL eligibility** (predicted PASS from height; actual REFUSED) | `PatientSex = O`. Census v3 checked height but not sex. |

**Fix:** preflight now reports `UNSUPPORTED_PATIENTSEX_FOR_SUL`. A future census revision should
add sex to SUL prediction.

**Matches:**
- every QIBA, EANM and PERCIST verdict;
- strict SUV;
- DecayFactor (sampled check → VERIFIED);
- uptake (within 0.1 min);
- CT frame of reference;
- reconstruction description.

## Findings and limitations

**1. A supplied SEG would be used as a lesion without review** (product gap, not a changed
result).
- `trial/timepoint.py` measures any SEG present in a scan folder as a lesion. An unreviewed
  annotation could therefore resolve PERCIST-BASELINE-MEASURABLE.
- No earlier real result is affected: no real SEG was ever in an audited folder.
- Here the SEG was withheld: the trial links only PET and CT.
- A lesion review gate is required (ledger: next dependency of human adjudication).

**2. Directory symlinks nested inside a scan folder are not followed by DICOM discovery.** The
analysis links files individually.

**3. Liver/blood-pool proposals need human review** on the Reference Review page before PERCIST
can move. No decision was created.
