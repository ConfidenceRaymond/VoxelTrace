# End-to-end example (real data: ACRIN-NSCLC-FDG-PET-168; run 2026-10-09)

**Input:** a known validated real case with **human-reviewed** liver regions. The review file
is consumed **read-only**: sha256 `6433b89fcac701af…` before and after.

**Commands**, run from `/home/dell/voxeltrace_hackathon`:

```bash
voxeltrace preflight outputs/acrin_longitudinal_168/trial --out outputs/pilot_runs/e2e_168/preflight_only
voxeltrace audit --input outputs/acrin_longitudinal_168/trial --output outputs/pilot_runs/e2e_168 --qc-images
voxeltrace verify-bundle outputs/pilot_runs/e2e_168/audit_bundle
voxeltrace summarize   outputs/pilot_runs/e2e_168/audit_bundle
voxeltrace list-reviews outputs/pilot_runs/e2e_168/audit_bundle
```

**Wall time:** 20 s for all five commands.

## Result

| Step | Result |
|---|---|
| Preflight | READY_WITH_WARNINGS at both timepoints (DECAY_FACTOR_UNVERIFIED, RECONSTRUCTION_INCOMPLETE, INJECTION_DATE_FROM_SERIES, ANONYMIZATION_LOSS) |
| Quantitative evidence | strict SUV PASS ×2, SUL PASS (James) ×2 |
| Protocol fingerprint | 1 distinct protocol (GE Discovery LS, software 16.01); 16/24 fields present; no drift events |
| Pair rules | QIBA, EANM and PERCIST all **INSUFFICIENT_INFORMATION**; blocker VT-PROTOCOL-IDENTITY (AMBIGUOUS_RECONSTRUCTION); PERCIST also blocked by PERCIST-BASELINE-MEASURABLE (no reviewed lesion target) |
| Human-reviewed evidence | liver ACCEPT at both timepoints → PERCIST-LIVER-SUL-STABILITY **PASS** |
| Review tasks | 0 pending (blood pool AUTO_NOT_FOUND) |
| Attestations / adjudications | none / NOT_ADJUDICATED ×3 |
| DRAFT site queries | `reports/site_queries.md` (reconstruction record, lesion target, de-identification loss) |
| Bundle | `verify-bundle` → **OK**; manifest records git commit, schema versions, rule-bundle sha256, input hashes (paths pseudonymised) |

This reproduces the previously validated 168 result exactly
([acrin_longitudinal_168.md](acrin_longitudinal_168.md),
[reconstruction_audit_168.md](reconstruction_audit_168.md)). No review decision was modified.

For decided verdicts on real data, the same commands on the external pairs give:
- QIBA ASSESSABLE for autoPET PETCT_c2ffda4725 and cc_tumor CCTH-B02;
- decided NOT_ASSESSABLE for cmb_mel MSB-07612.

See [external_validation_v1.md](external_validation_v1.md).
