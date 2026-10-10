# Success criteria for the first external retrospective pilot

Agreed with the partner **before** data arrive and recorded in the pilot scope
(`../commercialization/pilot_scope_template.md`). Thresholds marked **PROVISIONAL** are
starting points chosen for a first pilot of roughly 10–50 pairs; they are not derived from
data and must be revisited with the partner. Nothing here is a regulatory acceptance
criterion.

## Technical

| Criterion | Measure | Threshold | Basis |
|---|---|---|---|
| Install / deployment | `run-pilot` completes on the partner's (or the agreed) machine from a clean environment | completes; `verify-delivery` OK | binary; clean-install procedure in `../validation/` docs |
| Intake | every folder interpreted (`intake-map`) with no silent choice | 100 % of scans MAPPED or listed as NEEDS_REVIEW with a reason | binary by design |
| Intake rework | scans needing a site question at intake | reported, no threshold | depends on the partner's export; measured, not targeted |
| **False-safe findings** | pairs VoxelTrace called ASSESSABLE* that the partner's physicist (or the external reviewers) judge not comparable | **0 CRITICAL** (a judged-wrong ASSESSABLE that would change an interpretation) | the safety promise of the product; any CRITICAL stops the pilot for root-cause analysis |
| Expert agreement | agreement with the partner physicist's verdict per pair | PROVISIONAL: ≥ 80 % on decidable pairs, with every disagreement explained | first-pilot target; the locked external analysis plan (`../external_validation/analysis_plan.md`) governs formal claims |
| Evidence integrity | evidence bundle and delivery package verify on the partner's side | 100 % | binary |
| Reproducibility | re-run on the same inputs gives the same `checksums.sha256` | identical | shown in `../validation/reproducibility.md` |
| Runtime | wall time per pair, all three rule sets | PROVISIONAL: ≤ 1 min per pair on an 8-core workstation | measured ≈ 0.3–0.5 min/pair on a 16-core x86 (`../performance_local_x86_5090.md`) |
| Privacy | delivery package privacy scan | CLEAN; zero identifiers found by the partner's own check | binary |

## Workflow

| Criterion | Measure | Threshold |
|---|---|---|
| Fewer manual metadata checks | partner's staff time per pair before vs with VoxelTrace (their estimate, then measured on the pilot) | PROVISIONAL: a reduction the partner considers material; record both numbers |
| Site queries actionable | DRAFT queries the partner would send with no or minor edits | PROVISIONAL: ≥ 70 % |
| Report understood | the partner's director can state the result from `executive_summary.pdf` alone (walk-through) | yes / no, with what was unclear |
| Human review burden | reference-region, lesion and pairing items needing review, and minutes spent | measured and reported; no threshold |
| "Why" answerable | the partner can answer "why not comparable?" from `explain-pair` / `pair_evidence_trace.csv` without us | yes for the pairs they ask about |

## Commercial

| Criterion | Evidence |
|---|---|
| Wants a second dataset | written request or a scheduled second transfer |
| Willing to continue | agreement to a next step (second pilot, paid scope, introduction) |
| Budget owner identified | a named role with budget and a purchase path |
| Reasons recorded | if they decline: the coded reason (`../commercialization/kpi_framework.md`) |

A pilot is **technically successful** when every technical binary criterion is met and there
is no CRITICAL false-safe finding. It is **commercially successful** only with at least one
commercial signal above; technical success alone is not evidence of demand.
