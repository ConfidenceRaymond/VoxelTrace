# Analysis plan

Fixed before any reviewer form is returned. The cohort is
`outputs/external_validation_cohort_v1`: 9 real public pairs from 4 collections and 6
scanner models (Siemens, CPS and GE). The answer key holds all four verdict categories.

## Comparisons

The unit of analysis is one (case, standard) pair. Each is analysed:

- **A:** VoxelTrace verdict vs the locked reference answer (after adjudication). Primary.
- **B:** VoxelTrace verdict vs each individual reviewer (round 1). Secondary.
- **C:** reviewer vs reviewer (round 1). This is the inter-reader baseline: VoxelTrace cannot
  be expected to agree with experts more closely than experts agree with each other.

## Metrics (`voxeltrace score-validation`)

| Metric | Definition |
|---|---|
| Exact agreement | identical verdicts / n |
| Weighted agreement | mean linear weight on the ordinal scale ASSESSABLE < ASSESSABLE_WITH_WARNINGS < INSUFFICIENT_INFORMATION < NOT_ASSESSABLE (1 = same, 0 = opposite ends) |
| Cohen's κ, linear-weighted κ | reported only when at least 2 categories occur |
| False-safe count, by severity | CRITICAL: VoxelTrace ASSESSABLE* vs expert NOT_ASSESSABLE. MAJOR: VoxelTrace ASSESSABLE* vs expert INSUFFICIENT_INFORMATION. MINOR: VoxelTrace INSUFFICIENT_INFORMATION vs expert NOT_ASSESSABLE |
| False-unsafe count | VoxelTrace NOT_ASSESSABLE / INSUFFICIENT_INFORMATION vs expert ASSESSABLE* |
| INSUFFICIENT_INFORMATION agreement | both / VoxelTrace only / expert only; positive agreement 2a / (2a + b + c) |
| Rule-level disagreement | counts of `rules_disagreed` (unblinded round) |
| Review time | median and range per case |

## Pre-specified decisions

- **Safety gate.** Any CRITICAL false-safe on a real case is reviewed case by case before any
  claim is made. It is reported even if every other metric is good.
- **Sample size.** With 9 pairs the results are descriptive. Counts are reported with exact
  (Clopper–Pearson) 95 % intervals, which the analyst computes; the tool reports counts, and κ is not interpreted. A claim of agreement needs at
  least 30 pairs with at least 2 reviewers; extending the cohort is planned in
  [vendor_validation_matrix.md](../vendor_validation_matrix.md).
- **No re-scoring.** Thresholds, categories and weights above are not changed after forms
  are returned. Any additional analysis is labelled exploratory.
- **Missing answers.** A form with no answer for a standard is excluded for that standard
  only, and the exclusions are reported.

## Current status

No reviewer forms have been returned. No agreement result exists, and none may be quoted.
