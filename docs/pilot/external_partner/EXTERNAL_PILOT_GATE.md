# External pilot gate: go / no-go before accepting the first real dataset

All **GO** items must be ticked by the VoxelTrace owner before any partner data are received. A
single **NO-GO** condition stops the intake. This gate makes no legal or compliance
determination; it checks that the agreed prerequisites exist.

## A. Agreement and scope

- [ ] Data-use agreement signed by both parties (reference: `<...>`). **NO-GO without it.**
- [ ] [PILOT_SCOPE_TEMPLATE.md](PILOT_SCOPE_TEMPLATE.md) completed and signed off, including the
      validation-status statement and human-review responsibilities.
- [ ] The partner has acknowledged in writing that VoxelTrace is research software, that external
      expert validation is pending, and that results are not for clinical use.
- [ ] The partner has named a PET physicist (or nuclear-medicine physician) for review items.

## B. Data handling

- [ ] Transfer method, encryption and checksum procedure agreed ([TRANSFER_CHECKLIST.md](TRANSFER_CHECKLIST.md)).
- [ ] The partner confirms the export is de-identified under its own procedure and folder names are pseudonyms.
- [ ] Storage location for the data identified (encrypted; access limited to the operator).
- [ ] Retention/deletion plan agreed.
- **NO-GO** if the partner proposes sending identifiable data, or data outside the agreement.

## C. Software

- [ ] The release used is tagged (`v0.4.0-rc2` or later) and recorded; `voxeltrace deployment-lock verify` = LOCK_MATCH.
- [ ] On the audit machine, at that tag: `pytest`, `ruff check .`, `ruff format --check .` pass.
- [ ] CI on `main` is green for that commit (all jobs).
- [ ] A dry run of [FIRST_PILOT_RUNBOOK.md](FIRST_PILOT_RUNBOOK.md) on public data completed
      on the audit machine, with `verify-bundle` and `verify-delivery` OK.
- [ ] `v0.3.0-external-validation` unchanged (`git rev-parse v0.3.0-external-validation^{commit}` = `a46526c…`).
- **NO-GO** if any test fails, CI is red, or a known false-safe defect without disclosure exists.

## D. Scientific scope

- [ ] Tracer is FDG; scanners and vendors listed; expected GE/Philips limitations explained.
- [ ] The TEXT_IMPLIED packet has been sent to the partner physicist.
- [ ] The partner understands PERCIST needs their reference-region and lesion review.
- **NO-GO** if the partner expects clinical interpretation, treatment-response assessment,
  or validated non-FDG / PET/MR results.

## E. People

- [ ] The operator has a named contact at the partner for intake questions.
- [ ] Time for the partner's physicist review is planned (see review time in the feedback form).

## Decision

| Gate | Result | By (role) | Date |
|---|---|---|---|
| A–E | GO / NO-GO | | |

## Status at preparation (2026-10-10)

| Section | Status |
|---|---|
| A. Agreement and scope | **open**: no partner, no DUA, no scope signed |
| B. Data handling | **open**: depends on the partner |
| C. Software | **met** for `main` @ the commit adding this package: tests and lint pass locally; CI green on all three jobs after the fix in `a1cf044` (it had failed on every run since activation: streamlit-dependent tests under a `[dev]`-only install); runbook dry run on public PETCT_97320b0b58 completed 2026-10-10 (`outputs/runbook_dryrun_20261010`, verify-bundle and verify-delivery OK). Re-tick on the release actually used. |
| D. Scientific scope | **ready** to send; TEXT_IMPLIED blinded packet prepared, unanswered; external dry run 2026-10-10 passed (`dry_run_20261010.md`) |
| E. People | **open** |

Overall: **NO-GO until A, B and E are completed by the owner with a real partner.**
