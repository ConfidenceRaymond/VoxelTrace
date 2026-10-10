# Paid-pilot gate

**Current result: PAID_PILOT_READY = NO.** Status values: **PASS** (evidence exists and is
linked), **PENDING** (not yet done; nothing blocks starting it), **BLOCKED** (cannot progress
without an outside party or a prerequisite), **NOT_REQUIRED** (not needed for a first paid pilot).
Expert agreement, partner acceptance and real pilot completion are never marked PASS without
real evidence. State as of 2026-10-10.

| # | Section | Requirement | Status | Evidence / what is missing | Owner |
|---|---|---|---|---|---|
| 1 | Scientific validation | deterministic core tested; real-data cohort audited reproducibly | **PASS** | 741 tests; 9 real pairs; byte-identical verdicts across machines and to the frozen bundle (`../validation/reproducibility.md`) | — |
| 2 | Expert agreement | ≥ 2 independent PET physicists return the blinded forms; agreement scored with the locked plan | **BLOCKED** | 0 of 9 forms returned; needs reviewers to be recruited (`../external_validation_pending.md`) | user + external physicists |
| 3 | False-safe analysis | register complete; 0 CRITICAL false-safe in expert comparison | **PENDING** (register PASS; comparison BLOCKED by #2) | `../validation/false_safe_risk_register.md`; FS-01 TEXT_IMPLIED open (`../pilot/external_partner/TEXT_IMPLIED_REVIEW_PACKET.md`) | external physicists |
| 4 | False-unsafe analysis | register complete; rate measured against experts | **PENDING** (register PASS; measurement BLOCKED by #2) | `../validation/false_unsafe_risk_register.md` | external physicists |
| 5 | Vendor coverage | the partner's vendors validated at least to QUANT level, or the limitation accepted in writing | **PENDING** | Siemens PAIR_VALIDATED; GE ingestion only; Philips metadata only (`../vendor_validation_matrix.md`); depends on the partner's scanners | partner data / phantom |
| 6 | First external dataset | a real partner dataset received under a DUA and audited | **BLOCKED** | no partner yet; package ready (`../pilot/external_partner/`) | user |
| 7 | Unpaid pilot result | one unpaid pilot completed against `../pilot/pilot_success_scorecard.md`, 0 CRITICAL false-safe | **BLOCKED** | depends on #6 | user + partner |
| 8 | Security / data handling | local-first, offline audit; transfer checklist; privacy scan of every delivery; retention plan | **PASS** (process) / **PENDING** (partner-specific review) | `../pilot/external_partner/TRANSFER_CHECKLIST.md`, `../pilot/external_partner/privacy_scan_report.md`; no formal security assessment | user |
| 9 | Contracts | NDA, MSA/SOW or pilot agreement reviewed by counsel | **PENDING** | checklist only (`company_and_contract_readiness.md`) | user + legal counsel |
| 10 | Data-processing agreement | DUA/DPA template reviewed by counsel; signed per partner | **PENDING** | none drafted | user + legal counsel |
| 11 | Company setup | legal entity, bank, invoicing, insurance | **PENDING** | `company_setup_checklist.md` | user |
| 12 | Deployment locking | tagged release, constraints file, captured and verified lock | **PASS** | `../pilot/deployment_lock.md`, `voxeltrace deployment-lock`; clean install verified | — |
| 13 | Support process | named contact, response times, issue log | **PENDING** | described in `../pilot/first_real_pilot_operations.md`; no staffing commitment | user |
| 14 | Incident process | privacy/security incident and wrong-result incident procedures | **PENDING** | draft steps in `../pilot/first_real_pilot_operations.md` §incident; not reviewed by counsel | user + legal counsel |
| 15 | Version freeze | the pilot runs on one tagged release, unchanged during the pilot | **PASS** (mechanism) | tags `v0.4.0-rc1` (and later), deployment lock | — |
| 16 | Release provenance | every output names version, commit, rule bundle and schemas; bundles verify | **PASS** | bundle manifests; `verify-bundle`; `verify-delivery` | — |
| 17 | Deliverable acceptance | partner accepts a delivered package against agreed criteria | **BLOCKED** | no partner; criteria template exists (`../pilot/pilot_success_scorecard.md`) | partner |

## Decision rule

PAID_PILOT_READY = YES only when #2, #3, #6, #7, #9, #10 and #11 are PASS, and #5 is PASS for
the paying partner's vendors (or their written acceptance of the limitation is on file).
Today: **NO**. Technical sections (#1, #12, #15, #16) are PASS; the remaining items need
external reviewers, a partner and legal/company actions.
