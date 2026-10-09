# External validation: PENDING (formal release gate)

**External expert agreement is PENDING.** No independent reviewer form has been returned.
No agreement, κ, false-safe or false-unsafe figure exists. None may be quoted, estimated or
implied.

The validation target is fixed: tag `v0.3.0-external-validation` (tag object `7baabfe0`,
commit `a46526c`, pushed to origin). At that commit, the blinded package
`outputs/external_validation_cohort_v1/package_blinded/` reproduces all 27 answer-key verdicts
(checked 2026-10-09). The package is not modified by later work.

## What does not count as validation

Each item below is useful for development, but none is validation:

- unit and integration tests, and synthetic perturbation fixtures;
- agreement with census predictions;
- internal development decisions of any kind, including any future record marked
  DEVELOPMENT_ONLY or made by the project owner;
- design-partner enthusiasm, demos, or a customer accepting a report.

## Release gate: required before VoxelTrace is offered as validated trial software

Every item below must be complete and documented. This list is not reduced to meet a date.

| # | Requirement | Evidence that closes it |
|---|---|---|
| 1 | Independent PET physicist review | at least 2 qualified reviewers, independent of the project, complete the blinded forms per `docs/external_validation/reviewer_instructions.md` |
| 2 | Blinded agreement analysis | scored with `voxeltrace score-validation` exactly per the pre-specified `analysis_plan.md`: exact and weighted agreement, κ (≥ 30 pairs), inter-reader baseline |
| 3 | False-safe analysis | every CRITICAL and MAJOR false-safe explained case by case; none unresolved |
| 4 | Non-Siemens real validation | at least one GE and one Philips model at QUANT_VALIDATED or better (`docs/vendor_validation_matrix.md`), via partner exports or phantoms |
| 5 | External dataset dry run | one complete audit on a dataset VoxelTrace's developers have never seen, run by the data holder with the documented workflow |
| 6 | Adjudication | disagreements resolved per `adjudication_protocol.md`; reference answers locked before any unblinding |
| 7 | Locked software | scores reported against a tagged version; any later verdict-logic change gets a new version and is reported as a deviation |

Until all seven are closed, every external-facing document says "external expert validation
pending". This applies to sales material, the website, reports and pilot scopes.
