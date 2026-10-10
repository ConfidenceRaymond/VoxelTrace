# Pilot success scorecard

Filled in at the end of each pilot from measured evidence. Thresholds marked **PROVISIONAL**
are starting points to be agreed with the partner in the pilot scope; they are not derived
from data. Criteria rationale: [pilot_success_criteria.md](pilot_success_criteria.md).
Each line: **MET / NOT MET / NOT MEASURED**, with the evidence file.

Pilot ID: `<...>` · Release: `<tag>` · Deployment lock: `LOCK_MATCH / …` · Date: `<...>`

## Technical

| Criterion | Threshold | Result | Evidence |
|---|---|---|---|
| Deployment successful | `run-pilot` completes on the agreed machine; `deployment-lock verify` = LOCK_MATCH* | | `pilot_run_log.json`, lock verify output |
| Intake successful | every scan MAPPED or listed NEEDS_REVIEW with a reason; partner intake VALID* | | `intake_mapping.json`, `validate-partner-intake` report |
| No critical false-safe | **0** CRITICAL false-safe findings (partner physicist or external reviewers) | | feedback form §3 |
| Expert agreement | PROVISIONAL: ≥ 80 % raw agreement on decidable pairs; every disagreement explained | | `score-validation` output (real forms only) |
| Bundle verified | `verify-bundle` OK and `verify-delivery` OK on both sides | | `verification_report.json`, partner confirmation |
| Runtime acceptable | PROVISIONAL: ≤ 1 min per pair, all rule sets, on an 8-core workstation | | `pilot_run_log.json` |

## Workflow

| Criterion | Threshold | Result | Evidence |
|---|---|---|---|
| Reduced manual metadata review | PROVISIONAL: partner reports a material reduction; before/after minutes recorded | | feedback form §9 |
| Actionable site queries | PROVISIONAL: ≥ 70 % of DRAFT queries usable with minor edits | | feedback form §7 |
| Report clarity | director can state the result from the executive summary alone | | feedback form §8 |
| Human review burden | measured (items and minutes); no threshold | | feedback form §9, `unresolved_items.csv` |

## Commercial

| Criterion | Evidence of MET |
|---|---|
| Partner wants a second dataset | written request or scheduled transfer |
| Budget owner identified | named role with budget and purchase path |
| Willingness to continue | agreed next step (second pilot, paid scope, introduction) |
| Procurement path understood | written description of their purchasing steps |

**Technical success** = every technical line MET with 0 CRITICAL false-safe. **Commercial
success** requires at least one commercial line MET. Technical success alone is not evidence
of demand.
