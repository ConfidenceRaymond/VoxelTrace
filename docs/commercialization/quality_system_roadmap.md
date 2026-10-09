# Quality system roadmap (future; no compliance claimed)

**VoxelTrace has no quality-management system today.** Nothing here claims conformity with
ISO 13485, IEC 62304, ISO 14971, 21 CFR Part 11, GAMP 5, ICH GCP or any other framework.
This roadmap lists what commercial deployment would need, the existing assets to build on,
and the gaps.

| Area | What would be needed | Existing assets to build on | Gap |
|---|---|---|---|
| Requirements traceability | user/system requirements → design → code → tests → release, per version | rules cite sources; reason catalogue; tests map to behaviours (`../failure_injection_coverage.md`) | no formal requirements set; no trace matrix |
| Risk management | hazard analysis focused on **false-safe** verdicts; risk controls and residual-risk review | false-safe paths documented (`../design_partner_readiness.md` Q7); refusal-first design; hash-bound reviews | no formal risk file; no severity/probability scheme |
| Software lifecycle | planned development, documented architecture, coding standards, reviews | ruff, 600+ tests, architecture docs, versioned schemas | no documented lifecycle plan; single developer; no independent review |
| Verification / validation | verification per requirement; validation for intended use with users and real data | tests; real-data cohort; blinded validation package; locked tag | external validation pending (`../external_validation_pending.md`); no IQ/OQ/PQ templates |
| Change control | impact assessment for every change to rules, schemas or verdict logic; regression evidence | rule-bundle hash; schema versions; CHANGELOG; "validated results must not silently change" practice | no formal change requests or approvals |
| Issue management | intake, triage, CAPA for defects (especially false-safe) | git history; issue notes in docs | no issue tracker process; no CAPA |
| Release management | release criteria, signed tags, release notes, distribution control | annotated tag `v0.3.0-external-validation`; CHANGELOG | no signed releases; no release checklist enforced by tooling |
| Security | threat model; dependency scanning; secure development; vulnerability disclosure | local-first; no network in audit; secret scan (`../public_repo_audit.md`); path pseudonyms | no threat model; no SBOM; bundles not signed |
| Supplier / dependency management | approved dependency list; licence and vulnerability monitoring; pinned builds | licence inventory; declared dependencies | no pinning/lock file policy for releases; no monitoring |
| Computerized system validation for trials | customer-facing CSV package: intended use, risk assessment, test evidence, audit trail, access control, e-records/e-signature assessment | immutable checksummed bundles; hash-chained review/adjudication logs | no user authentication or access control; no e-signatures; no validation package template |

## Suggested order (only if commercial deployment proceeds)

1. A risk file centred on false-safe, plus a release checklist. Both are cheap and the most
   protective.
2. Requirements and trace matrix for the audit core: rules, verdicts, bundle.
3. Change-control and issue/CAPA process.
4. Security: threat model, SBOM, signed releases.
5. A customer CSV package template (IQ/OQ against the sample audit).
6. Decide with QA/RA counsel whether, and when, to adopt a formal QMS standard.
