# External PET-physicist validation protocol (VT-EXPERT-VALIDATION-1)

**Purpose:** measure agreement between VoxelTrace pair verdicts and independent expert
judgement.

**No expert labels have been collected yet.** VoxelTrace never generates them. Scoring ignores
empty forms and, by default, any record marked `simulated`.

## Procedure

1. **Run the audit:** `voxeltrace audit --input <trial> --output <dir>`, then
   `voxeltrace verify-bundle <dir>/audit_bundle`.
2. **Export a BLINDED package:**
   `voxeltrace export-validation --bundle <dir>/audit_bundle --out <pkg> --mode BLINDED`.
   - `cases/CASE-nnn.json` holds the evidence only: preflight findings, quantitative status,
     timing, scanner/software, fingerprint fields with trust levels, and reference-region
     status. No VoxelTrace verdicts are included.
   - `responses/CASE-nnn.response.yaml` are EMPTY forms.
   - `COORDINATOR_ONLY_answer_key.json` holds VoxelTrace's verdicts. The coordinator keeps
     it; it is never sent to reviewers in BLINDED mode.
3. **Reviewers fill one form per case.** Fields:
   - `reviewer_id` and `reviewer_role`;
   - an independent verdict per rule set (ASSESSABLE / ASSESSABLE_WITH_WARNINGS /
     NOT_ASSESSABLE / INSUFFICIENT_INFORMATION);
   - `confidence` and `reason`;
   - `missing_evidence`;
   - `rules_disagreed` and `disagreement_reason`;
   - `review_time_min`.

   Reviewers may consult the images, but not VoxelTrace output.
4. **Optional UNBLINDED round:** export with `--mode UNBLINDED`. Reviewers then see
   VoxelTrace's verdicts and record disagreement reasons.
5. **Score:** `voxeltrace score-validation --package <pkg> [--responses <dir>]`.

## Metrics (per rule set)

The full, pre-specified list is in
[external_validation/analysis_plan.md](external_validation/analysis_plan.md). It adds
weighted agreement, linear-weighted κ, false-safe counts by severity, false-unsafe counts and
INSUFFICIENT_INFORMATION agreement. In BLINDED mode the export refuses to write a packet
that contains any verdict, rule ID, reason code or preflight state produced for the bundle.

| Metric | Definition |
|---|---|
| Raw agreement | identical verdicts / cases |
| Cohen's κ | over the four verdict categories; reported only when at least 2 categories occur |
| False-safe rate | among cases VoxelTrace calls ASSESSABLE*, the fraction the expert calls NOT_ASSESSABLE or INSUFFICIENT_INFORMATION (**safety-critical**) |
| False-unsafe rate | among cases VoxelTrace calls NOT_ASSESSABLE / INSUFFICIENT_INFORMATION, the fraction the expert calls ASSESSABLE* (cost: lost data) |
| INSUFFICIENT_INFORMATION rates | VoxelTrace vs expert |
| Rule-level disagreement | counts of `rules_disagreed` |
| Review time | median and range |

## Design notes

- **Sample size:** at least 30–50 pairs with at least 2 independent reviewers are needed
  before κ is meaningful. Report confidence intervals; with fewer cases, report raw counts
  only.
- **Cases:** use real pairs only (see [external_validation_v1.md](external_validation_v1.md)
  for the current 3 external + 5 ACRIN pairs). Synthetic fixtures may be used for reviewer
  training, labelled as such.
- **Gating:** a non-zero false-safe rate on real cases blocks any claim of pilot readiness
  until explained.
