# Reviewer instructions

Thank you for taking part. This study measures how often an independent PET expert and a
software tool reach the same judgement on whether a baseline / follow-up FDG PET/CT pair can
be compared quantitatively. Your own judgement is what we need. There is no expected answer.

## What you receive

- `cases/CASE-nnn.json`: one file per pair, with facts extracted from the DICOM headers:
  - timing, uptake interval and injected activity;
  - scanner, software and reconstruction fields, each with its trust level and whether it
    was present;
  - units, corrections and decay correction;
  - raw observations about missing or unusual header fields;
  - whether any human reference-region review has been recorded.
- `responses/CASE-nnn.response.yaml`: one empty form per case.
- Access to the DICOM images for each pair, provided separately by the coordinator.

The case files intentionally contain **no software conclusions**: no verdicts, rule names,
status labels or reason codes. Where a free-text observation contained such a label it is
shown as `[label withheld]`.

## What to do for each case

1. Look at the facts and, wherever you want, at the images or the full DICOM headers.
2. For each listed standard (QIBA FDG-PET/CT 1.14, EANM FDG 2.0, PERCIST 1.0), choose one
   answer:
   - `ASSESSABLE`: the pair can be compared quantitatively under this standard;
   - `ASSESSABLE_WITH_WARNINGS`: it can, but with a deviation you would report;
   - `NOT_ASSESSABLE`: the available evidence shows the pair should not be compared;
   - `INSUFFICIENT_INFORMATION`: you cannot decide from the evidence available.
3. Fill in `confidence` (low / medium / high), `reason`, `missing_evidence` (what would let
   you decide) and `review_time_min`.
4. Fill in `reviewer_id` and `reviewer_role`. Leave `simulated: false`.

`rules_disagreed` and `disagreement_reason` are only used in the optional second (unblinded)
round. Leave them empty in the first round.

## Please do not

- discuss cases with other reviewers before every form has been returned;
- run VoxelTrace or any other automated tool on the cases;
- change a form after returning it. If you want to revise an answer, send a new note to the
  coordinator; the original stays on record.

Every answer, including `INSUFFICIENT_INFORMATION`, is equally useful.
