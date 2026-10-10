# Pilot delivery checklist

The operator ticks every line before sending; the partner uses it to check receipt. The package
is produced by `voxeltrace run-pilot` (or `voxeltrace deliver`) and contains derived outputs
only.

| # | Required item | File(s) in the package | Check |
|---|---|---|---|
| 1 | Executive summary | `executive_summary.pdf`, `executive_summary.json` | first page shows readiness, comparability per rule set, pairing status, sites requiring action, unresolved review |
| 2 | Pair table | `pair_results.csv` | every pair × rule set; `pairing_status`, `reconstruction_evidence`, plain-language reasons present |
| 3 | Site / scanner summary | `site_summary.csv` | sites declared (no unintended `UNASSIGNED`); counts reconcile |
| 4 | Unresolved items | `unresolved_items.csv` | each row names who can resolve it |
| 5 | Reason / remediation table | `remediation_matrix.csv` | present |
| 6 | Evidence trace | `pair_evidence_trace.csv` | present |
| 7 | Evidence bundle | `evidence_bundle/` | byte copy of the audit bundle |
| 8 | Verification report | `verification_report.json` | `"status": "OK"` |
| 9 | Methodology / limitations | `methodology_and_limitations.md` | states external validation PENDING and the TEXT_IMPLIED limitation |
| 10 | Pilot acceptance | `pilot_acceptance.json` | status `AUDIT_COMPLETE` or `AUDIT_COMPLETE_WITH_REVIEW_PENDING`; `inputs_sha256` matches the received data |
| 11 | DRAFT site queries | `recommended_site_queries/` | labelled DRAFT; nothing sent |
| 12 | Versions | `software_version.txt` | code, rule bundle and schema versions |
| 13 | Privacy scan | `privacy_scan.json` | `"status": "CLEAN"` |
| 14 | Package checksums | `DELIVERY_CHECKSUMS.sha256`, `DELIVERY_MANIFEST.json` | `voxeltrace verify-delivery` → `"status": "OK"` |

Before sending, the operator also:
- [ ] opens `executive_summary.pdf` and `README_FIRST.md` in the package and reads them;
- [ ] confirms no DICOM, no identifiers and no local paths (the privacy scan is a safety net, not
      a substitute for looking);
- [ ] sends the package through the agreed encrypted channel with its `DELIVERY_CHECKSUMS.sha256`
      hash in the covering message.

Partner, on receipt:

```bash
cd <package> && sha256sum -c DELIVERY_CHECKSUMS.sha256
cd evidence_bundle && sha256sum -c checksums.sha256
```
