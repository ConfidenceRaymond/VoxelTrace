# Storage / containment audit (read-only, 2026-10-09)

| Path (under /home/dell/voxeltrace_hackathon) | Size | Contents |
|---|---|---|
| `voxeltrace/` (excluding .git and .venv) | 5.9 MB | repository |
| `voxeltrace/.git` | 5.2 MB | history |
| `voxeltrace/.venv` | 835 MB | project virtualenv |
| `data/` | 3.4 GB | `fdg_pet_ct_lesions` 1.6 GB, `acrin_longitudinal` 976 MB, `external_longitudinal` 824 MB (3 pairs, this session), `census` 63 MB |
| `models/` | 17 GB | local VLM weights (explanatory features only) |
| `outputs/` | 2.9 GB | mostly `synthetic_comparability` 2.9 GB; real-data namespaces 13 MB or less each |
| `logs/` | 0.5 MB | developer logs |
| `tmp/` | 7.9 GB | `vlm-venv` 5.6 GB, `pip-cache` 1.1 GB, `crosscheck-venv` 687 MB, `census-venv` 470 MB, `cuda-cache` 119 MB, `pytest` 22 MB |
| **Total** | **32 GB** | disk free: 3.4 TB of 3.6 TB |

## Containment

**Incident, fixed:** the fresh-install test of this session ran `pip` without the project
cache directory and created `~/.cache/pip` (95 MB, 165 files). Every file in it postdated its
creation at 2026-10-09 00:09 (no pre-existing user files), and it was removed.
- Future installs: `PIP_CACHE_DIR=/home/dell/voxeltrace_hackathon/tmp/pip-cache`.

Nothing else project-related was found outside the workspace:
- no `voxeltrace` entries in `~` other than the workspace;
- no project files in `/tmp` (pytest uses `../tmp/pytest`);
- no Hugging Face cache under `~/.cache`.

## Candidates for later cleanup (NOT done; user decision)

- `tmp/vlm-venv` (5.6 GB) and `models/` (17 GB): only needed for the explanatory VLM
  features.
- `outputs/synthetic_comparability` (2.9 GB): synthetic fixtures (regenerable).
- `tmp/pip-cache` (1.1 GB).
