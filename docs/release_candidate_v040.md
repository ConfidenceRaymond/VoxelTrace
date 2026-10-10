# Release candidate 0.4.0: retrospective pilot hardening

**Decision:** a 0.4.0 version is justified. This session produced a coherent, tested
milestone that changes what an operator can do (run, deliver and verify a retrospective audit
without a developer), not just more features. It does **not** change any rule, threshold,
SUV/SUL computation or verdict, and it makes no claim of expert agreement (1.0 stays reserved
for completed external validation).

The frozen validation tag `v0.3.0-external-validation` (→ `a46526c`) is untouched; the blinded
reviewer package still refers to it.

## What 0.4.0 adds

| Area | Change | Evidence |
|---|---|---|
| Workflow | `voxeltrace run-pilot`; pilot acceptance contract VT-PILOT-ACCEPTANCE-1 | `docs/pilot/pilot_workflow.md`; `tests/test_pilot_run.py` |
| Delivery | `deliver` / `verify-delivery`, privacy scan, package checksums | 9-pair real cohort package verified; tamper and privacy-rejection tests |
| Intake | `intake-map` (explicit PET rules R1–R3, NEEDS_REVIEW on ambiguity), nested-layout detection | simulated partner drop: 21/21 verdict rows identical to source |
| Safety | pairing audit (BLOCKING → AUDIT_BLOCKED), FS-01 disclosure (`reconstruction_evidence`) | `docs/validation/false_safe_risk_register.md` |
| Explainability | `explain-pair`, `pair_evidence_trace.csv`, remediation matrix, plain-language intake | tests |
| Reproducibility | hash-seed and listing-order fixes and tests | `docs/validation/reproducibility.md` |
| Portability | no developer paths at runtime; tests from another HOME | `tests/test_portability.py` |
| Deployment | clean install on x86_64; tested constraints; dependency caps | `docs/dependency_strategy.md` |

## Readiness checklist (at the release commit)

| Item | State |
|---|---|
| `pytest`, `ruff check`, `ruff format --check`, `git diff --check` | pass (see final report) |
| Clean install in a fresh venv + run-pilot + verify-delivery | pass (`outputs/install_verification_20261009`) |
| Real-cohort verdicts unchanged | pair-verdict CSVs byte-identical to `audit_v2` and `audit_tagcheck_a46526c` |
| Pre-existing evidence bundles | all verify OK |
| Expert agreement | **pending** (no reviewer form returned) |
| CI hardening | prepared in `docs/ci/ci_proposed.yml`; **not active** (push token lacks `workflow` scope) |

## Schema changes

New: VT-PILOT-ACCEPTANCE-1, VT-DELIVERY-1, VT-PRIVACY-SCAN-1, VT-INTAKE-MAPPING-1,
VT-PAIRING-AUDIT-1, VT-SITE-ROLLUP-1, VT-REMEDIATION-MATRIX-1, VT-EVIDENCE-TRACE-1.
Changed: VT-EXECUTIVE-SUMMARY-1 → 2 (additive first-page fields). Unchanged: rule sets
(rule bundle sha256 `413186131a35…411d`), VT-TRIAL-AUDIT-1, VT-BUNDLE-1, VT-PREFLIGHT-1.

## Tag

Annotated tag `v0.4.0` on the release commit, created only after the final validation in
this session passed. It is a pilot-workflow release, not a validation release.

## Release candidate 2 (`v0.4.0-rc2`, 2026-10-10)

`v0.4.0-rc1` (`edc8f82`, created by the owner) is verified and left untouched. The changes since
rc1 are meaningful for a first partner pilot, so an rc2 tag is justified:

| Area | Change | Evidence |
|---|---|---|
| Partner intake | `validate-partner-intake` (VT-PARTNER-INTAKE-1), template | `tests/test_partner_intake.py`; dry run VALID |
| Deployment | `deployment-lock capture/verify` (VT-DEPLOYMENT-LOCK-1) | `tests/test_deployment_lock.py`; `docs/pilot/deployment_lock.md` |
| Intake safety | archives, zero-byte, malformed, empty visits, duplicates, mixed vendor | `tests/test_intake.py` |
| Validation tooling | reviewer-form scoring safeguards; synthetic forms never mixed with real | `tests/test_validation_scoring_safeguards.py` |
| Fixes | fixture relocation (synthetic-only, fail-safe); pairing fixture handling; NOT_ESTABLISHED label | demo verdicts byte-identical to the GB10 original |
| Partner material | packet index, starter kit (deterministic ZIP), dry run, privacy report, TEXT_IMPLIED blinded packet | `docs/pilot/external_partner/` |
| CI | active; `[app,dev]` install; 744 tests on 3.11/3.12; fresh-install smoke | `docs/ci/README.md` |

Conditions checked before tagging: full tests and lint pass, tree clean and synchronised, CI green
on the tagged commit, all pre-existing evidence bundles verify, the frozen tag unchanged, the
real-cohort verdicts unchanged.

**Note on tag order.** A `v0.4.0` tag (`a432dc9`) was created on 2026-10-09 before `v0.4.0-rc1`
(`edc8f82`, owner). Tags are not moved or deleted. Treat `v0.4.0` as the first pilot-workflow
snapshot and `v0.4.0-rc2` as the current pilot candidate; the next final release should use a
new version number (e.g. 0.4.1 or 0.5.0) to avoid ambiguity.
