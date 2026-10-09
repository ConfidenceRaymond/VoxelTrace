# Sample deliverables (from real public-data runs)

| Deliverable | Example |
|---|---|
| Audit package report | `outputs/pilot_runs/e2e_168/audit_bundle/reports/AUDIT_PACKAGE_REPORT.md` (ACRIN 168: INSUFFICIENT_INFORMATION with human-reviewed liver regions) |
| Pair verdict tables | `audit_bundle/pair_verdicts/<ruleset>.csv` |
| Preflight table | `audit_bundle/preflight/preflight.csv` |
| Drift timeline | `audit_bundle/protocol/drift_events.csv` |
| Draft site queries | `audit_bundle/reports/site_queries.md` |
| Evidence bundle verification | `voxeltrace verify-bundle <bundle>` → OK / TAMPERED |
| Decided real verdicts | `docs/external_validation_v1.md` (QIBA ASSESSABLE ×2, decided NOT_ASSESSABLE ×1) |

All examples are public research data (IDC, CC BY). No sponsor data has been processed.
