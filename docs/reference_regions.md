# Reference regions: automatic proposals, human review, measurement

Code:
- `src/voxeltrace/quant/reference_auto.py` (proposer `vt-refauto-1`)
- `src/voxeltrace/quant/reference_region.py` (measurement)
- `src/voxeltrace/trial/reference.py` (review gate)
- `src/voxeltrace/visualization/reference_qc.py` (QC renders)
- `scripts/run_trial_audit.py` (batch CLI)

Everything is deterministic, and no learned model is involved. RESEARCH PROTOTYPE - NOT FOR
CLINICAL DIAGNOSIS.

## Regions (PERCIST 1.0)

| Region | VOI | Method |
|---|---|---|
| LIVER | 3 cm diameter sphere, right lobe | `SPHERE_AT_SUPPLIED_CENTRE` |
| BLOOD_POOL | 1 cm diameter × 2 cm long cylinder, descending thoracic aorta, axis along patient S-I | `CYLINDER_AT_SUPPLIED_CENTRE` |

- A region can also be supplied as a boolean mask on the PET grid (`SUPPLIED_MASK`).
- Measurement on the PET grid records SUV mean, SD, CoV and max, plus SUL mean and SD
  (LBMJAMES128).
- Measurement refuses a region that leaves the image, overlaps a supplied lesion, contains SUV
  0 voxels, or has fewer than 10 voxels.
- Masks are evaluated on their bounding box only. The voxel set is identical to the
  full-grid definition (tested by brute force).

## The review gate (the important part)

For each subject/timepoint and region, the first matching case applies.

1. **Supplied region** (`trial.yaml` `reference_regions`, one spec or a list per scan):
   measured, `source: SUPPLIED`.
2. **Automatic proposal** (`reference_proposals: auto`, the default):

   | Review in `reference_review.yaml` | Status | Usable by rules |
   |---|---|---|
   | none | `PROPOSED_REQUIRES_REVIEW` (values shown for the reviewer only) | **no** |
   | `ACCEPT`, same `proposal_sha256` | `COMPUTED` | yes |
   | `ADJUST` + moved `final_geometry` centre, same sha | `COMPUTED` at the reviewer's centre | yes |
   | `REJECT`, same sha | `REJECTED_BY_REVIEWER` | no |
   | any decision, different sha or proposal geometry | `REVIEW_OUTDATED` (never reused) | no |
   | record fails validation, is filed under another scan or region, or is SIMULATED | `REVIEW_INVALID` | no |
   | proposer failed | `AUTO_NOT_FOUND` | no |

3. **Proposals off** (`reference_proposals: off`): `MANUAL_OR_REFERENCE_MASK_REQUIRED`.

More rules:

- **Binding:** `proposal_sha256` hashes the region, method, centre, size, algorithm version,
  and the PET and CT series pseudonyms. A review therefore applies to exactly one proposal on
  exactly one scan. Changing the algorithm, or re-exporting the scan, makes the review
  OUTDA- **Review fields and recording:** see [reference_region_review.md](reference_region_review.md)
  (record schema `voxeltrace.reference-review/2`, review page, ADJUST workflow). one.
- **Ignored entries:** `PENDING` entries and the display-only worksheet fields are ignored.
- **Recording:** the audit records how many reviews were applied and lists review keys that
  match no scan.

### Reason codes (INSUFFICIENT_INFORMATION is always actionable)

| Code | When | Fix |
|---|---|---|
| `REFERENCE_REVIEW_REQUIRED` | a proposal exists but has not been reviewed | review the QC image, then record ACCEPT, ADJUST or REJECT |
| `REFERENCE_REVIEW_OUTDATED` | the review names another proposal | re-review the current proposal |
| `REFERENCE_REVIEW_INVALID` | the review record is unusable (see detail) | re-record it on the review page |
| `REFERENCE_REJECTED_BY_REVIEWER` | rejected | ADJUST with a centre, or supply a mask or centre |
| `REFERENCE_AUTO_NOT_FOUND` | the proposer failed (detail says why, e.g. no CT in the PET frame of reference) | supply a region, or provide the CT |
| `REFERENCE_QC_FAILED` | an accepted or supplied region failed measurement QC | move the region, or correct the mask |
| `MANUAL_OR_REFERENCE_MASK_REQUIRED` | proposals disabled, or no SUV at the timepoint | supply a region |

The PERCIST liver rules (`PERCIST-LIVER-SUL-STABILITY` and `PERCIST-BASELINE-MEASURABLE`)
use only `COMPUTED` liver regions. Their thresholds are unchanged.

The blood pool is measured and reported but **not** used by any rule. The PERCIST blood-pool
fallback stays `DOCUMENTED_NOT_IMPLEMENTED`, because PERCIST 1.0's text and table disagree on
the +2 SD term.

## Proposer `vt-refauto-1`

Input: the one CT series in the PET's frame of reference. If there is no such CT, or there are
several, the result is `AUTO_NOT_FOUND`. Only standard axial LPS grids with uniform slice
spacing are supported.

### Preprocessing

- Gaussian smoothing with σ = 2 mm, then linear resampling onto a 3 mm isotropic working grid.
- Body = the largest component of HU > −300, hole-filled per slice.
- Lungs = HU < −400 components inside the body, each ≥ 300 mL.
- Midline = the x of the body centroid.

### LIVER

- Candidate tissue: soft tissue (10 < HU < 150), right of the midline by ≥ 10 mm, from 150 mm
  below to 40 mm above the right-lung base, excluding supplied lesions.
- Centre: the deepest voxel of that tissue. The depth must be ≥ 18 mm.

### BLOOD_POOL

- Slices: those in 30–75 % of the lung z-range.
- Candidates: local maxima of the 2-D soft-tissue distance map, inside a window left-anterior
  of the vertebral body, with an inscribed radius of 6–18 mm and lung within (radius +
  10) mm.
- Chaining: candidates are chained between slices with steps ≤ 4.5 mm.
- Choice: the 2 cm run whose centres deviate ≤ 4.5 mm from their median, closest to 55 % of
  the lung range.

### QC for the reviewer

- **Image:** `reference_qc/<subject>_<timepoint>_<region>.png`. It shows zoomed axial and
  coronal CT and PET with the VOI outline, a coronal locator, and the proposal hash.
- **CT values:** HU mean and SD in the VOI.
- **Geometry:** depth (liver), and chain deviation and inscribed radius (blood pool).

### Development check (3 public subjects, 2026-10-08)

| Subject | Liver centre (LPS mm) | Liver CT HU | Liver SUVmean / CoV | Blood-pool CT HU | Blood-pool SUVmean / CoV |
|---|---|---|---|---|---|
| PETCT_0011f3deaf | (−98.6, −162.6, −725.0) | 96 | 2.39 / 0.14 | 180 | 1.87 / 0.15 |
| PETCT_bd52fdf529 | (−117.2, −168.2, −730.5) | 116 | 2.14 / 0.11 | 176 | 1.71 / 0.12 |
| PETCT_db3bac356a | (−88.6, −156.6, −681.0) | 111 | 2.20 / 0.15 | 154 | 2.20 / 0.17 |

- **Visual check:** inspection of the QC images placed every liver sphere in right-lobe
  parenchyma and every cylinder inside the descending aorta.
- **Contrast CT:** the blood HU of 150–180 indicates contrast-enhanced CT.
- **Unit tests:** a synthetic CT phantom checks placement (sphere fully inside the liver block,
  cylinder within 4.5 mm of the aorta axis), determinism, and the refusal paths.
- **Not validated:** this is a development check, **not** a validation. Three subjects is far
  too few to estimate a failure rate, and that is why every proposal requires review.

## Batch outputs (`scripts/run_trial_audit.py <trial> --out <dir>`)

- **Existing files:** `trial_audit.json`, `subject_timepoint_matrix.csv` (now with
  liver/blood-pool status), `pair_checks.csv` and `site_summary.json` (now with
  reference-region status counts).
- **`reference_regions.csv`:** one row per scan × region, with status, source, geometry, SUV
  and SUL statistics, `usable_by_rules`, the review, `proposal_sha256` and the QC image.
- **`reference_review_worksheet.yaml`:** pre-filled in the `reference_review.yaml` format. Every
  pending or stale proposal is listed with `decision: PENDING`. The reviewer edits it and saves
  it as `<trial>/reference_review.yaml`.
- **`reference_qc/*.png`:** the QC renders.
