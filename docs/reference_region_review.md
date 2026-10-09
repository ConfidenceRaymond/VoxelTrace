# Human review of reference regions

Code:
- `app/pages/4_Reference_Review.py` (review page)
- `src/voxeltrace/trial/reference.py` (records, hash binding, resolution)
- `src/voxeltrace/trial/review.py` (reviewer context and measurements)
- `src/voxeltrace/visualization/reference_qc.py` (panels)

See [reference_regions.md](reference_regions.md) for the proposer and the measurement.
RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.

## Why a review is required

PERCIST compares tumour uptake with uptake in a **reference region**. The reference is the
liver, or the blood pool in the descending aorta, where the liver cannot be used. Two
PERCIST checks depend directly on the liver region:

- **`PERCIST-LIVER-SUL-STABILITY`:** liver SULmean may change by at most 20 % of the larger
  value and by at most 0.3 SUL between baseline and follow-up.
- **`PERCIST-BASELINE-MEASURABLE`:** baseline SULpeak must be at least 1.5 × liver SULmean
  + 2 SD.

A misplaced region silently corrupts both checks:

- a sphere that clips the liver edge, a vessel or a focal hot spot gives a wrong mean and SD;
- a cylinder that touches the aortic wall, the spine or the heart gives a wrong blood-pool
  value.

VoxelTrace's proposer is deterministic and was checked on only 3 subjects. Its failure rate
is unknown, so its output is a **proposal**, never a measurement that rules may use.

## Proposal versus accepted reference region

| | Proposal | Accepted reference region |
|---|---|---|
| Created by | `vt-refauto-1`, deterministically from the CT | a human reviewer (ACCEPT or ADJUST) |
| Status in the audit | `PROPOSED_REQUIRES_REVIEW` | `COMPUTED` |
| Values shown | yes, as a preview for the reviewer | yes |
| Used by PERCIST rules | **never** | yes |
| Bound to | its `proposal_sha256` (region, method, centre, size, algorithm, PET and CT series) | that `proposal_sha256` plus `final_region_sha256` (final geometry) |

## What the reviewer checks

The page shows the following for each proposal:

- **Images:** PET, CT and fused PET/CT axial slices through the centre; fused axial slices
  ±6 and ±12 mm away; a fused coronal view; and a CT coronal locator. Every outline is the
  contour of the region mask itself.
- **Region values:** geometry, centre (LPS mm), radius, cylinder length, voxel count, volume,
  SUVmean, SD, CoV, SUVmax, SULmean and SD (LBMJAMES128), and CT HU mean and SD. These are
  measured on the original PET grid, by the same code the audit uses.
- **Hashes and QC:** the proposal hash, the measurement QC result, and advisory flags.

**Liver.** The sphere should lie entirely in normal-appearing right-lobe liver tissue. Check
that:

- it is clear of the liver boundary, the diaphragm, large vessels and the gallbladder;
- it contains no focal uptake and no supplied lesion outline;
- it is not in the kidney, lung or bowel.

**Blood pool.** The cylinder should lie entirely within the blood of the descending thoracic
aorta. Check that:

- it does not touch the wall, spine, oesophagus, heart or lung;
- it is aligned with the vessel on the coronal view.

**Advisory flags.** These are reviewer aids, not standards. They never block or decide
anything.

| Flag | Raised when |
|---|---|
| CoV | above 0.20 |
| Focal uptake | SUVmax / SUVmean above 1.5 |
| CT heterogeneity | CT HU SD above 30 |
| Lesion proximity | a supplied lesion lies within 15 mm of the region edge |

A region that fails **measurement QC** cannot be accepted. Measurement QC fails when the region
is outside the image, overlaps a supplied lesion, contains SUV 0 voxels, or has fewer than 10
voxels.

The page makes no diagnostic statement.

## Decisions

| Decision | Meaning | Final geometry |
|---|---|---|
| ACCEPT | the proposal is placed correctly | the proposal geometry, unchanged |
| ADJUST | the right structure, the centre moved by the reviewer | the moved centre; shape and size stay fixed by the rule |
| REJECT | not usable | none |

**ADJUST controls:**

- **Sliders:** z (slice) offset, then x and y offsets, each within ±30 mm.
- **Live update:** measurements, the overlay and `final_region_sha256` are recomputed live.
- **No snapping:** the centre is recorded at 0.1 mm and never snapped or moved by the
  software.

**Recording a decision.** The page writes nothing until all of these hold:

1. a decision has been chosen (nothing is pre-selected);
2. the reviewer has entered a name or identifier;
3. the reviewer has ticked the confirmation;
4. the reviewer has pressed **Record decision**.

Changing an existing decision also needs **replace** to be ticked; the old decision is kept
under `superseded`.

## The review record (`<trial>/reference_review.yaml`)

Schema `voxeltrace.reference-review/2`. Each record contains:

- **Identity:** subject pseudonym, timepoint, region type.
- **Decision and proposal:** the decision; `proposal_sha256`; the proposal algorithm version;
  the proposal geometry.
- **Final geometry:** the final geometry and `final_region_sha256`.
- **Reviewer:** the reviewer name or identifier (entered by the reviewer); an ISO-8601
  timestamp; an optional note.
- **Provenance:** the VoxelTrace version and git commit, and the rule context (rule set,
  version, region definition, rule ids).
- **Integrity:** `review_sha256`, the hash of the whole record.

The audit applies a record only if every one of these checks passes:

- **Location:** it is filed under the subject/timepoint and region it names. A record filed
  elsewhere is `REVIEW_INVALID`, for example a review for another subject, or a LIVER review
  filed under BLOOD_POOL.
- **Integrity:** it validates, and its hashes match. A record edited after saving is
  `REVIEW_INVALID`.
- **Hash binding:** its `proposal_sha256` and proposal geometry equal the current proposal's.
  If the proposal later changes (new algorithm version, re-exported scan, moved centre), the
  record becomes **`REVIEW_OUTDATED`** and is never reused.
- **Not simulated:** it is not SIMULATED. SIMULATED records exist only in tests, are refused by
  production audits, and cannot be written inside the project's `data/` or `outputs/` trees.

The exported `reference_review_worksheet.yaml` uses the same format, with `decision: PENDING`.
A hand-completed entry is accepted if it validates. The review page is the preferred route.

## Why VoxelTrace never auto-approves

- **A judgement is needed:** placement depends on anatomy and on visible uptake. The proposer
  has not been validated at a scale that would justify trusting it unseen.
- **No model decides:** no AI model (including the Qwen3-VL baseline) is consulted, and
  advisory flags never choose a decision. On dev_v2 the VLM could not localise targets (mean
  bounding-box IoU 0.004), so model judgement would not be a safeguard.
- **Responsibility stays visible:** every applied reference region carries the name of the
  person who reviewed it.

## Relationship to PERCIST assessability

- **Before a review:** a pair stays `INSUFFICIENT_INFORMATION`, with
  `REFERENCE_REVIEW_REQUIRED`. The reason detail names the subject, timepoint, region and
  proposal hash still awaiting a decision.
- **After ACCEPT or ADJUST at both timepoints:** the liver rules are evaluated with their
  unchanged thresholds. The verdict can then be ASSESSABLE or NOT_ASSESSABLE.
- **REJECT:** gives `REFERENCE_REJECTED_BY_REVIEWER`. Supply a region, or ADJUST it instead.
- **Blood pool:** it is reviewed and reported, but no rule uses it.

Re-run the audit after recording (`voxeltrace audit` into a new folder, the *Intake and Audit* page, or the button on this page).
