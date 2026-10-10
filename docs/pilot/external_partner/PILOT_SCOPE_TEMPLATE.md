# Pilot scope: `<PILOT-ID>` (template, to be agreed before any data transfer)

Fill every `<...>` field. Nothing here is agreed until both parties sign below.

| Field | Value |
|---|---|
| Organization | `<partner organisation>` |
| Partner contact roles | `<data manager role>`, `<PET physicist role>`, `<decision-maker role>` |
| Trial / study | `<public identifier or internal code; no participant information>` |
| Study type | retrospective; data already acquired |
| Number of subjects | `<n>` (suggested first pilot: 10–50 pairs) |
| Timepoints | `<e.g. baseline, follow-up 1>`; visit-order source: `<mapping table>` |
| Tracer(s) | `<FDG only in scope; others are reported UNSUPPORTED>` |
| Vendors | `<Siemens / GE / Philips / other>` |
| Scanner models and software | `<list, if known>` |
| Sites | `<n>`; site pseudonyms `<...>` |
| Endpoints the comparability audit supports | `<e.g. SUVmax / SULpeak change between baseline and follow-up>` (VoxelTrace does not compute or judge the endpoint itself) |
| Requested rule sets | `<QIBA FDG 1.14 / EANM FDG 2.0 / PERCIST 1.0>` |
| Expected outputs | delivery package per [PILOT_DELIVERY_CHECKLIST.md](PILOT_DELIVERY_CHECKLIST.md) |
| Turnaround target | `<n working days after accepted data>`; a target, not a guarantee; excludes human-review time |
| Exclusions | non-FDG tracers, PET/MR, brain PET, long-axial-FOV systems, NIfTI-only data, clinical interpretation, treatment response, `<other>` |
| Validation status (stated to the partner) | external expert validation PENDING; Siemens pair-validated, GE ingestion-only, Philips metadata-only; TEXT_IMPLIED is an open question |
| Success criteria | [../pilot_success_criteria.md](../pilot_success_criteria.md), thresholds marked PROVISIONAL to be confirmed here: `<...>` |
| Fees | `<none for this pilot / to be agreed>`; no price is proposed in this template |

## Human-review responsibilities

| Task | Responsible | Tool |
|---|---|---|
| Confirm intake mapping questions (`NEEDS_REVIEW`) | partner data manager | intake mapping report |
| Reference-region review (PERCIST) | partner PET physicist / nuclear-medicine physician | Reference Review page or worksheet |
| Lesion review (PERCIST) | partner PET physicist / nuclear-medicine physician | Lesion Review page |
| TEXT_IMPLIED adjudication | partner PET physicist | [TEXT_IMPLIED_REVIEW_PACKET.md](TEXT_IMPLIED_REVIEW_PACKET.md) |
| Verdict agreement / disagreement | partner PET physicist | [PILOT_FEEDBACK_FORM.md](PILOT_FEEDBACK_FORM.md) |
| Sending site queries | partner | DRAFT site queries |
| Running the audit, packaging, verification | VoxelTrace operator | [FIRST_PILOT_RUNBOOK.md](FIRST_PILOT_RUNBOOK.md) |

## Sign-off

| Party | Name / role | Date |
|---|---|---|
| Partner | | |
| VoxelTrace | | |
