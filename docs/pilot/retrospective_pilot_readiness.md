# Readiness reassessment (2026-10-09, 0.4.0)

**Classification: RETROSPECTIVE_PILOT_READY** (previously DESIGN_PARTNER_READY).
**External expert validation: PENDING.** **Not PAID_PILOT_READY.**

## RETROSPECTIVE_PILOT_READY criteria

| Criterion | Met? | Evidence |
|---|---|---|
| Reproducible external-style intake | yes | `intake-map` on a simulated multi-site drop with naming, extra files, NAC and duplicate-recon ambiguity; ambiguity held as NEEDS_REVIEW; 21/21 verdict rows identical to source (`pilot_workflow.md` §4) |
| Complete audit workflow | yes | `run-pilot` on the real 9-pair cohort and on the staged drop, operator-only commands |
| Sanitized delivery package | yes | `deliver` + fail-closed privacy scan; `verify-delivery` and plain `sha256sum -c` both work |
| Evidence verification | yes | bundle and package checksums; tamper tests; all pre-existing bundles verify |
| No known critical false-safe bug | yes, with a disclosed design risk | FS-01 (text-implied reconstruction identity) is documented, disclosed per pair (`reconstruction_evidence = TEXT_IMPLIED`) and pinned by a test; no defect contradicting the rule design is known (`../validation/false_safe_risk_register.md`) |
| Deployable on a clean environment | yes | fresh venv on x86_64: install, 716 tests, run-pilot, verify-delivery |
| Limitations explicit | yes | README_FIRST §7–8, methodology file in every package, risk registers |

## Conditions attached to the classification

1. Every pilot report states that external expert validation is pending.
2. Verdicts marked `TEXT_IMPLIED` in `pair_results.csv` are reviewed by the partner's
   physicist before use.
3. GE / Philips data are expected to yield INSUFFICIENT_INFORMATION more often; this is
   stated before data are sent (`../validation/non_siemens_gap_analysis.md`).
4. Reference-region and lesion review are done by the partner's qualified staff; VoxelTrace
   records none.

## Why not PAID_PILOT_READY

- No expert agreement figure (0 reviewer forms returned).
- 0 discovery interviews, 0 design partners, no budget owner identified.
- No non-Siemens quantitative validation.
- No hash-locked deployment artefact for customer infrastructure; CI hardening not yet
  active; no quality-system or contractual basis for accepting payment.

## Remaining blockers by stage

| Stage | Blockers |
|---|---|
| Design partner | none technical; needs a partner (0 interviews so far) |
| Retrospective pilot (unpaid) | a partner and a DUA; partner physicist available for review items |
| Paid pilot | external validation results (≥ 2 independent physicists), at least one completed unpaid pilot against `pilot_success_criteria.md`, GE/Philips evidence if the partner uses them, contract/DPA and company setup (`../commercialization/company_setup_checklist.md`), activated CI and a locked deployment |
