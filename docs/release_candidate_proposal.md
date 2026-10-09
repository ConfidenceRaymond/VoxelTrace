# Release-candidate proposal: `v0.3.0-external-validation`

**Status: proposed, not created.** No tag and no GitHub Release has been made. The repository
has no tags and no release policy, so this needs the owner's explicit decision.

## Why a tag is justified

The external validation analysis plan (`docs/external_validation/analysis_plan.md`) says scores
are reported **for the locked software version**. Reviewer answers are compared against
VoxelTrace verdicts, so the exact code that produced those verdicts must be fixed and citable
before any form goes out. An annotated tag gives that fixed point. Without one, the coordinator
would have to quote a commit hash.

This is a release candidate for validation, not a product release. It makes no claim of
agreement or clinical fitness, and 1.0 stays reserved (see `CHANGELOG.md`).

## Readiness checklist (state at proposal time)

| Item | State |
|---|---|
| `pytest`, `ruff check`, `ruff format --check`, `git diff --check` on `main` | pass (exit codes checked without pipes) |
| Clean install into a fresh virtual environment and one-command audit | verified in this cycle (see the readiness decision in `docs/design_partner_readiness.md`) |
| Public repository audit | no secret, no data, no weights (`docs/public_repo_audit.md`) |
| Licence and attribution inventory | done; no copyleft dependency (`docs/licence_attribution_audit.md`) |
| Validated results unchanged by 0.3.0 | ACRIN-168 audits regenerate with identical values, statuses, hashes and verdicts |
| Blinded validation package | built from the 9-pair real cohort, with a leak guard |
| Expert agreement | **pending: no reviewer form returned** |

## Proposed commands (owner runs them, or asks for them to be run)

```bash
git tag -a v0.3.0-external-validation -m "VoxelTrace 0.3.0 release candidate for blinded external validation (no agreement claimed)"
git push origin v0.3.0-external-validation
```

Do not create a GitHub Release from the tag. When the tag is made, add
`date-released: <tag date>` to `CITATION.cff`.

## If the code changes after reviewers start

Any change to verdict logic after forms are sent is a protocol deviation. It gets a new
version (0.3.1 or later), and the scores stay reported against `v0.3.0-external-validation`.
