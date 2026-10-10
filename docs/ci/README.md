# Proposed CI hardening (not yet active)

`ci_proposed.yml` is the hardened workflow prepared on 2026-10-09: ruff pinned to 0.17.0,
`git diff --check` on each commit, and a `fresh-install-smoke` job (non-editable install with
`constraints/tested-py312-x86_64.txt`, then `scripts/ci_smoke_pilot.py`: synthetic run-pilot ->
verify-delivery). It could not be pushed from the development session because the GitHub
token lacks the `workflow` scope.

To activate (repository owner):

```bash
cp docs/ci/ci_proposed.yml .github/workflows/ci.yml
git commit -am "ci: fresh-install smoke and whitespace check" && git push
```

The smoke script and the constraints file were verified locally (`SMOKE OK AUDIT_COMPLETE`).
