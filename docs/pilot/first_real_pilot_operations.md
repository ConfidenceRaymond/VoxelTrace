# First real pilot: operations runbook

For an operator who is not the original developer. Exact commands are in
[external_partner/FIRST_PILOT_RUNBOOK.md](external_partner/FIRST_PILOT_RUNBOOK.md); this
document is the operational frame around them: who does what, in which order, what is logged,
and what to do when something goes wrong. Keep a **pilot log** (one dated line per event) in
the pilot folder; never put partner identifiers or data in the repository.

RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. No AI is used in any step. VoxelTrace never
records a human review decision.

## Roles

| Role | Responsibility |
|---|---|
| Operator (VoxelTrace) | intake, runs, QA, delivery, log, retention |
| Owner (VoxelTrace) | gate decisions, agreements, escalation |
| Partner data contact | export, transfer, intake questions |
| Partner PET physicist | reference-region, lesion, TEXT_IMPLIED and verdict review |

## 1. Partner onboarding

1. Send the partner packet (`external_partner/PARTNER_PACKET_INDEX.md`) or the starter kit.
2. Agree the pilot scope (`external_partner/PILOT_SCOPE_TEMPLATE.md`); both sign.
3. Confirm the intake contact and the physicist (roles in the pilot log, names only in the
   agreement).
4. Pass the gate: `external_partner/EXTERNAL_PILOT_GATE.md` (all GO). **No data before GO.**

## 2. Agreement confirmation

Log: DUA reference, scope version and date, retention period. If anything is unsigned: stop.

## 3. Transfer

1. Agree the method and encryption (`TRANSFER_CHECKLIST.md`).
2. The partner sends `SHA256SUMS.txt` and `partner_intake.yaml` with the data.
3. Receipt: `sha256sum -c --quiet SHA256SUMS.txt`; fill in and return the transfer confirmation.
4. Make the data read-only (`chmod -R a-w`).

## 4. Environment

`voxeltrace deployment-lock verify <pilot>/deployment_lock.json` must be LOCK_MATCH (capture it at
the first run; see `deployment_lock.md`).

## 5. Intake

| Step | Command | Pass condition | If not |
|---|---|---|---|
| Partner declaration | `voxeltrace validate-partner-intake partner_intake.yaml` | VALID / VALID_WITH_WARNINGS | INVALID: return the findings to the data contact; NEEDS_REVIEW: resolve each item and log the answer |
| First look | `voxeltrace validate-input <data>` | ACCEPT_* (or NEEDS_REEXPORT with understood reasons) | nested layout → intake-map |
| Mapping | `voxeltrace intake-map <data> --out <ws>/intake_mapping.json --stage <ws>/trial --trial-id <ID>` | MAPPED / MAPPED_WITH_WARNINGS | NEEDS_REVIEW: see §6 |

## 6. Mapping review

For every `NEEDS_REVIEW` scan and every `drop_findings` item, ask the data contact one precise
question (e.g. "Visit FU1 of Subject003 has two attenuation-corrected PET series; which is the
trial series?"). Record the answer in the pilot log. Fix by an explicit `--timepoint-map`, by the
partner re-sending, or by the partner removing the extra series, then map again into a **new**
stage folder. VoxelTrace never chooses.

## 7. Trial setup and preflight

1. Check `<ws>/trial/trial.yaml`: trial ID, `timepoint_order`, `sites` (all subjects assigned).
2. `voxeltrace preflight <ws>/trial --out <ws>/preflight` → review DO_NOT_QUANTIFY scans; draft
   re-export requests if they are fixable (remediation matrix).

## 8. Audit

`voxeltrace run-pilot --input <ws>/trial --output <ws>/pilot_v1`; record exit code, status and
`pilot_run_log.json` timings. AUDIT_BLOCKED → §12.

## 9. Unresolved review queue and physicist handoff

1. `voxeltrace list-reviews <bundle>`; `unresolved_items.csv`; TEXT_IMPLIED rows in
   `pair_results.csv`.
2. Send the physicist the delivery package plus `PARTNER_REVIEW_GUIDE.md`,
   `TEXT_IMPLIED_REVIEW_PACKET.md` and `PILOT_FEEDBACK_FORM.md`.
3. The physicist records reference-region and lesion decisions themselves (review pages / CLI
   with `--confirm`). The operator never records or transcribes a decision.
4. After reviews, re-run into `pilot_v2` (never overwrite) and deliver again.

## 10. Issue logging

Every problem gets a pilot-log line: date, category (INTAKE / DATA / SOFTWARE / RESULT /
PRIVACY / PROCESS), description, action, resolution. Software defects also get a repository
issue with a minimal synthetic reproducer (never partner data).

## 11. Report QA, delivery generation and verification

1. Read `executive_summary.pdf` and `README_FIRST.md` in the package.
2. Check `PILOT_DELIVERY_CHECKLIST.md` line by line.
3. `voxeltrace verify-bundle …` and `voxeltrace verify-delivery …` = OK; privacy scan CLEAN.
4. Look at a sample of CSVs yourself for identifiers (the scan is a safety net).
5. Send through the agreed channel with the package checksum in the message.

## 12. Partner review and feedback

Collect the feedback form; score real reviewer answers only (`score-validation`; synthetic
forms are refused). Log disagreements, especially false-safe concerns, as RESULT issues.

## 13. Retention / deletion and evidence archive

1. Archive: deployment lock, pilot log, intake mapping, evidence bundles, delivery packages,
   feedback (no input DICOM). Compute a sha256 manifest of the archive.
2. Delete the input copy on the agreed date; log date, method, person; confirm to the partner
   on request.

## 14. Incident escalation

| Incident | Immediate action | Escalate to |
|---|---|---|
| PHI or identifiable data found in the input | stop processing; isolate the copy; do not forward | owner, same day; partner data contact; follow the DUA's notification clause (counsel) |
| Identifier found in a delivered package | ask the partner to delete the package; rebuild; record the root cause | owner, same day |
| A delivered verdict is wrong (false-safe) | notify the partner in writing with the affected pairs; keep the bundle; add a regression test | owner; record in the false-safe register |
| Bundle or package fails verification | do not deliver; investigate tampering vs software | owner |
| Lost or misdirected transfer | stop; inform the partner | owner; counsel |

The notification duties of a DUA/DPA are legal obligations to be confirmed by counsel
(`../commercialization/company_and_contract_readiness.md`).
