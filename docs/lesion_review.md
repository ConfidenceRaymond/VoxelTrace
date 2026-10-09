# Lesion / target segmentation review gate

**Module:** `src/voxeltrace/trial/lesion_review.py`, schema `voxeltrace.lesion-review/1`.
**Interfaces:**
- UI: app page **6 Lesion Review**;
- CLI: `voxeltrace lesion-qc` (images and status, no decision) and `voxeltrace lesion-review
  ... --confirm` (one human decision).

## Rule

No supplied mask is quantitative ground truth by itself: DICOM SEG, NIfTI, RTSTRUCT-derived,
AI-generated or external.
- Under the default policy **REVIEW_REQUIRED**, a segment is used as the PERCIST baseline
  target only if a named human ACCEPTED that **exact** mask.
- Otherwise PERCIST-BASELINE-MEASURABLE is UNKNOWN with `LESION_REVIEW_REQUIRED`.
- When several segments are accepted, the target is the one with the highest SUVpeak.
- SUVmax, SUVmean, SUVpeak, MTV and TLG are still measured for every segment, but they are
  reported with the segment's review status and used for no rule unless the segment is
  ACCEPTED.

## Binding

A review binds to:
- subject and timepoint;
- study, PET series and SEG series (pseudonymised hashes);
- the SEG file sha256;
- the segment number;
- the **mask sha256** (mask on the PET grid);
- the source type.

## Outcomes

| Situation | State |
|---|---|
| ACCEPT | ACCEPTED |
| REJECT / REJECT_AND_REPLACE_REQUIRED | REJECTED |
| mask or SEG file changed | OUTDATED |
| review for another PET series or study | INVALID |
| source type differs | INVALID |
| simulated review in a production audit | not used (UNREVIEWED, `SIMULATED_REVIEW_REJECTED`) |
| edited, removed or reordered log line (hash chain broken) | every review INVALID; appending refused |

**ADJUSTED** is reserved. There is no safe voxel-editing workflow, so it is never produced;
a wrong mask is `REJECT_AND_REPLACE_REQUIRED`.

## Source types (never changed by review)

| Source type | Rule |
|---|---|
| HUMAN_CORRECTED | description says a human (radiologist / expert / reader) corrected it |
| HUMAN_MANUAL | SegmentAlgorithmType MANUAL |
| ALGORITHM_GENERATED | SEMIAUTOMATIC, or AUTOMATIC without AI wording |
| AI_GENERATED | AUTOMATIC with AI wording (e.g. AIMI, nnU-Net, deep, model) |
| UNKNOWN | otherwise |

Example: "AI_GENERATED + ACCEPTED" means a human accepted an AI proposal. It is never
relabelled HUMAN_MANUAL.

## Policies

- `REVIEW_REQUIRED` (default; mandatory for real data).
- `LEGACY_UNREVIEWED_ALLOWED`:
  - reproduces the historical behaviour (first non-empty segment, unreviewed);
  - accepted **only** in trials that declare `synthetic_perturbations`;
  - used by the synthetic demo trials to keep their frozen expectations;
  - labelled `UNREVIEWED_LEGACY_POLICY` in every output.

## Outputs

- `TrialAudit.lesion_evidence` (only when masks were supplied).
- `lesion_review_status.csv`.
- PERCIST check `observed.target_evidence`.

Trials without lesion masks produce byte-identical outputs to before the gate (ACRIN 168
verified).
