# Internal KPI framework

**No value is filled in unless it is measured.** "—" means not yet measured. Current values
are given only where they come from this repository's own outputs. They describe public and
synthetic data, not customer data.

## Technical

| KPI | Definition | Source | Current (2026-10-09) |
|---|---|---|---|
| READY_TO_QUANTIFY % | scans with preflight READY_TO_QUANTIFY or READY_WITH_WARNINGS / all scans | `preflight/preflight.json` | cohort v1: 14/18 READY_WITH_WARNINGS, 0 READY_TO_QUANTIFY, 4 DO_NOT_QUANTIFY |
| II % | INSUFFICIENT_INFORMATION pairs / pairs, per rule set | `pair_verdicts/*.csv` | cohort v1: QIBA 3/9, EANM 3/9, PERCIST 7/9 |
| false-safe | CRITICAL / MAJOR / MINOR counts vs locked expert answers | `voxeltrace score-validation` | — (no expert forms) |
| false-unsafe | count vs locked expert answers | same | — |
| census prediction accuracy | predicted vs actual verdict and SUV eligibility on downloaded pairs | census docs | recorded per batch in `../census_v3_public_pet.md`; not a rolling KPI yet |
| vendor coverage | models per state in the vendor matrix | `../vendor_validation_matrix.md` | PAIR_VALIDATED 4 models; QUANT 1; INGESTION 2; EXPERT 0 |
| audit runtime | wall time per subject per rule set | audit logs | not systematically measured |

## Commercial

| KPI | Definition | Current |
|---|---|---|
| interviews | completed discovery interviews per segment | 0 |
| design partners | signed partner agreements | 0 |
| audits offered | written pilot offers | 0 |
| pilots accepted | signed pilot scopes | 0 |
| paid pilots | paid scopes | 0 |
| conversion rate | pilots accepted / audits offered; paid / accepted | — |
| sales-cycle length | first contact → signed scope (days) | — |
| reasons for rejection | coded reasons per lost opportunity | — |

Review monthly. Keep the raw counts, not only rates; with small numbers the rates mislead.
