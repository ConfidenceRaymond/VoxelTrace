# Internal KPI dashboard specification

Specification only: what to track, how to compute it, where the data come from. **No current
value is stated here unless it is measured; empty means not measured.** Measured technical
values on public data are in `kpi_framework.md`. Keep raw counts beside every rate; with small
numbers, rates mislead.

## Technical

| KPI | Definition | Source | Cadence |
|---|---|---|---|
| READY_TO_QUANTIFY % | scans READY_TO_QUANTIFY or READY_WITH_WARNINGS / all scans | `preflight/preflight.json` per bundle | per audit |
| II % | INSUFFICIENT_INFORMATION pairs / pairs, per rule set | `pair_verdicts/*.csv` | per audit |
| NOT_ASSESSABLE % | NOT_ASSESSABLE pairs / pairs, per rule set | same | per audit |
| False-safe | CRITICAL / MAJOR / MINOR counts vs real expert forms | `voxeltrace score-validation` (REAL_REVIEWER_FORMS only) | per validation round |
| False-unsafe | count vs real expert forms | same | per validation round |
| Vendor coverage | vendors per state in the vendor matrix | `../vendor_validation_matrix.md` | monthly |
| Scanner coverage | scanner models per state | same | monthly |
| Audit runtime | wall seconds per pair (all rule sets) | `pilot_run_log.json` | per audit |
| Review burden | items needing human review per pair; reviewer minutes | `unresolved_items.csv`, feedback form | per pilot |
| Intake ambiguity rate | scans NEEDS_REVIEW at intake / scans received | `intake_mapping.json` | per dataset |
| TEXT_IMPLIED share | usable verdicts resting on TEXT_IMPLIED / usable verdicts | `pair_results.csv` | per audit |

## Commercial

| KPI | Definition | Source |
|---|---|---|
| Interviews | completed discovery interviews, by segment | `customer_discovery_tracker.csv` |
| Partner conversations | conversations past discovery about a dataset | tracker |
| Design partners | signed design-partner agreements | contracts folder (outside the repository) |
| Unpaid pilots | pilots started / completed | pilot log |
| Paid pilots | signed paid scopes | contracts |
| Repeat datasets | partners sending a second dataset | pilot log |
| Conversion rate | pilots / offers; paid / unpaid | derived |
| Reasons for rejection | coded reasons per lost opportunity | tracker `objections` |
| Sales-cycle length | first contact → signed scope, days | tracker dates |

## Rules

- Synthetic (SYNTHETIC_TEST_ONLY) scoring results never enter the dashboard.
- Public-data results are labelled PUBLIC and kept apart from partner-data results.
- No KPI is shown externally without its denominator and date.
