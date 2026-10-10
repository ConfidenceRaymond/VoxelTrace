# False-unsafe risk register

**False-unsafe** = VoxelTrace returns `INSUFFICIENT_INFORMATION` (II) or `NOT_ASSESSABLE` (NA),
or refuses intake, for a pair that a qualified physicist would consider comparable. It costs
usefulness, not safety, so **no threshold is relaxed to reduce it**. The remedies below are
evidence (documentation, re-export, review), never looser rules.

Date: 2026-10-09. Measured on the 9 real pairs (`outputs/pilot_runs/e2e_x86_20261009`).

## Measured burden (real 9-pair cohort)

| Rule set | ASSESSABLE* | II | NA |
|---|---|---|---|
| QIBA FDG 1.14 | 3 | 3 | 3 |
| EANM FDG 2.0 | 3 | 3 | 3 |
| PERCIST 1.0 | 0 | 7 | 2 |

What drives the non-usable results (QIBA; pairs can have several causes):

| Cause | Pairs | Kind |
|---|---|---|
| Uptake time outside 55–75 min / difference > 10 min (decided measurement) | 3 NA (ACRIN-050, -167, MSB-07612) | **correct** per standard; not false-unsafe |
| Post-filter / reconstruction parameters not encoded (AMBIGUOUS_RECONSTRUCTION) | 3 II (ACRIN-094, -153, -168) | possibly false-unsafe; fixable by site documentation (QIBA attestation) |
| DecayFactor inconsistent with FrameReferenceTime (GE LS, CPS 1023) | 2 II (ACRIN-094, -153) | possibly false-unsafe (vendor convention, `../vendor_decay_timing.md`) |
| Tracer not recorded | 2 (ACRIN-050, -153) | fixable by re-export / CRF |

PERCIST adds human review (7 of 9 II involve REFERENCE_REVIEW_REQUIRED or LESION_REVIEW_REQUIRED
or a missing reference region): this is by design and resolves with review, not with code.

## Register

| ID | Cause | Where it bites | Control / remedy (no threshold change) | Residual usefulness cost |
|---|---|---|---|---|
| FU-01 | GE DecayFactor semantics (frame-start FRT, mid-frame DF) refused as DECAY_FACTOR_INCONSISTENT | all public GE models; ACRIN-094 | a new, versioned, model/software-specific check **only** with the GE conformance statement + phantom (`phantom_validation_plan.md`) | **High** for GE until then |
| FU-02 | CPS 1023 FrameReferenceTime = 0 with per-bed DecayFactor | ACRIN-153 | none without documentation (INTERNALLY_INCONSISTENT; FDA ECAT recalls) | Medium (legacy scanners) |
| FU-03 | Philips CNTS units | older Philips exports | ask for BQML export; no private-tag scaling without a published statement | High for older Philips |
| FU-04 | Reconstruction parameters / post-filter not in standard attributes | most GE/Philips, some legacy | QIBA: signed site attestation (LEVEL_C, ASSESSABLE_WITH_WARNINGS); protocol sheet in the partner data request; EANM/PERCIST: none (standards silent) | **High** commercially (largest II driver) |
| FU-05 | SoftwareVersions stripped by de-identification | GE LS/ST/STE, Philips Big Bore | retain device identity (PS3.15 E.3.8) in the re-export | Medium |
| FU-06 | Height/sex missing → SUL refused → PERCIST II | many anonymized sets | retain patient characteristics; CRF height via documented channel | Medium (PERCIST only) |
| FU-07 | Human reference-region / lesion review pending | every PERCIST pair | Reference Review and Lesion Review pages; review effort is measurable in `unresolved_items.csv` | by design |
| FU-08 | No CT in the PET frame of reference → no reference proposal | ACRIN-153, MSB-07612 (single-image CT) | supply the volumetric CT, or a supplied/reviewed region in trial.yaml | Medium (PERCIST) |
| FU-09 | Tracer free text not recognised as FDG | rare naming variants | `TRACER_NOT_RECOGNISED` (NEEDS_REEXPORT) with remediation; RadiopharmaceuticalCodeSequence | Low |
| FU-10 | Several PET series in one visit; intake will not choose | real core-lab drops | intake rules R1–R3 remove NAC, secondary capture, non-BQML copies; the rest goes to a person | Low (one question to the site) |
| FU-11 | Unrecognised visit names (`week 6`) | partner drops | `intake-map --timepoint-map` | Low |
| FU-12 | SAME_DAY_TIMEPOINTS for genuine same-day test–retest studies | test–retest designs | NEEDS_REVIEW, not BLOCKING; the coordinator confirms | Low |
| FU-13 | MULTIPLE_STUDIES_IN_SCAN for a visit legitimately split over two PET studies | rare split acquisitions | intake finding only; the audit still runs (default gate) | Low |
| FU-14 | INJECTION_DATE_FROM_SERIES, DERIVED_IMAGE, DECAY_FACTOR_UNVERIFIED | common | warnings, not refusals | none on verdict (ASSESSABLE_WITH_WARNINGS) |
| FU-15 | Anonymizer shifts times inconsistently → NEGATIVE/IMPLAUSIBLE_DECAY_INTERVAL | some GE public sets | re-export keeping times on one clock | Medium |
| FU-16 | Site not declared → spurious "drift" | any trial without `sites:` | warning on the first page; `intake-map --stage` writes sites | reporting only |

| FU-17 | Intake holds archives, zero-byte or malformed files, empty visits and duplicated series as NEEDS_REVIEW | messy transfers | one question to the data contact; never auto-resolved | Low (time) |
| FU-18 | Workspace relocation made synthetic-fixture inheritance fail (fixed 2026-10-10) | demonstration / test fixtures only | relocation-tolerant parent match; content hashes still required | none after the fix |

## What reduces false-unsafe results without reducing safety

1. The GE/Philips partner data request (`ge_philips_partner_data_request.md`): BQML export,
   retain options, a protocol sheet. Expected to remove FU-03/05/06/15 for a cooperative site.
2. QIBA reconstruction attestations from the site physicist (FU-04), reported as
   ASSESSABLE_WITH_WARNINGS, never as ASSESSABLE.
3. Vendor documentation + phantom for FU-01 (new versioned check, never a strict-path change).
4. Human review throughput for PERCIST (FU-07): measured, not automated.

## What is not false-unsafe

NOT_ASSESSABLE from a decided measurement (uptake window, uptake difference, different scanner or
reconstruction) is the intended result: the standard says those pairs should not be compared.
