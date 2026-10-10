# Partner packet index

Everything a design partner needs before, during and after a first retrospective pilot.
Fill every `<...>` placeholder before sending. RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.
External expert validation is pending.

## Send to the partner

| Document | Audience | Purpose |
|---|---|---|
| [README_FIRST.md](README_FIRST.md) | everyone | what VoxelTrace does and does not do, status, limitations, outputs, human review |
| [DATA_REQUIREMENTS.md](DATA_REQUIREMENTS.md) | person preparing the export | minimum necessary data; explicit "do not send" list |
| [partner_intake.yaml](partner_intake.yaml) | data contact | machine-readable declaration of what is sent (VT-PARTNER-INTAKE-1) |
| [GE_PHILIPS_DATA_REQUEST.md](GE_PHILIPS_DATA_REQUEST.md) | partners with GE or Philips scanners | what fails in public exports and what a re-export or phantom can fix |
| [TRANSFER_CHECKLIST.md](TRANSFER_CHECKLIST.md) | data manager / IT | encryption, folder structure, checksums, DUA placeholder, confirmation, retention |
| [PILOT_SCOPE_TEMPLATE.md](PILOT_SCOPE_TEMPLATE.md) | both parties | scope to agree and sign before any transfer |
| [PARTNER_REVIEW_GUIDE.md](PARTNER_REVIEW_GUIDE.md) | partner PET physicist | how to review reference regions, lesions, reconstruction evidence, TEXT_IMPLIED, II cases |
| [TEXT_IMPLIED_REVIEW_PACKET.md](TEXT_IMPLIED_REVIEW_PACKET.md) | partner PET physicist | the first scientific adjudication question (blinded Part A) |
| [PILOT_DELIVERY_CHECKLIST.md](PILOT_DELIVERY_CHECKLIST.md) | both | what is delivered and how to verify it |
| [PILOT_FEEDBACK_FORM.md](PILOT_FEEDBACK_FORM.md) | partner physicist and lead | correctness, false-safe/false-unsafe, usability, review time, next step |

## Internal (VoxelTrace operator / owner)

| Document | Purpose |
|---|---|
| [EXTERNAL_PILOT_GATE.md](EXTERNAL_PILOT_GATE.md) | go/no-go before accepting the first real dataset |
| [FIRST_PILOT_RUNBOOK.md](FIRST_PILOT_RUNBOOK.md) | exact commands from transfer receipt to verification |
| [../first_real_pilot_operations.md](../first_real_pilot_operations.md) | roles, logging, review handoff, incidents, retention |
| [../deployment_lock.md](../deployment_lock.md) | locked environment capture and verification |
| [dry_run_20261010.md](dry_run_20261010.md) | full simulated handoff on public data, with results |
| [privacy_scan_report.md](privacy_scan_report.md) | privacy/security scan of the shareable artefacts |

## Shareable bundle

The partner starter kit (`<workspace>/outputs/external_partner_starter_kit.zip`, built by
`scripts/build_starter_kit.py`) contains the "send to the partner" documents, a sanitized
sample delivery package on demonstration data, verification instructions and a version note.
Verify it with its `.sha256` file.
