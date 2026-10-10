# CI status

**Active** (`.github/workflows/ci.yml`; activated by the owner in `edc8f82`, extended in
`7c58dfe`). Jobs on every push and pull request:

| Job | What |
|---|---|
| `test (3.11)`, `test (3.12)` | `pip install -e ".[app,dev]"`, ruff 0.17.0 pinned, `ruff check`, `ruff format --check`, `git diff --check HEAD^ HEAD`, `pytest` (744 tests, none skipped), CLI help smoke |
| `fresh-install-smoke` | Python 3.12, clean venv, non-editable install with `constraints/tested-py312-x86_64.txt`, `voxeltrace --version`, synthetic `run-pilot` → `verify-delivery` (`scripts/ci_smoke_pilot.py`) |

No model downloads, no GPU, no real DICOM. `ci_proposed.yml` is the historical proposal that the
active workflow was created from.
