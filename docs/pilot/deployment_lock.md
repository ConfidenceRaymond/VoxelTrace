# Pilot deployment lock

**Goal:** every pilot runs on an environment that can be named exactly and checked again later,
without requiring Docker (the audit is pure Python, CPU-only, offline).

## What is locked

| Item | Locked value for the current release | Where it is recorded |
|---|---|---|
| Python | 3.12.x (3.11 supported, tested in CI) | lock `python` |
| VoxelTrace | 0.4.0 at a tagged, clean commit (`v0.4.0-rc2` or later) | lock `voxeltrace` (version, git commit, dirty flag) |
| Tested dependency set | `constraints/tested-py312-x86_64.txt` | lock `packages` (every installed package) |
| Rule bundle | sha256 `413186131a357163959cb161358e9193899c9675278bcc1a8a8c8d194f9d411d` (QIBA FDG 1.14, EANM FDG 2.0, PERCIST 1.0) | lock `rule_bundle_sha256`, `rule_versions`; every bundle manifest |
| Evidence / report schemas | `voxeltrace --version` → schemas line (e.g. VT-BUNDLE-1, VT-EXECUTIVE-SUMMARY-2, VT-PILOT-ACCEPTANCE-1) | lock `schemas`; every bundle manifest |
| Optional explanation model | Qwen3-VL-8B-Instruct revision `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`, separate venv (`constraints/vlm-runtime-x86_64-cu130.txt`) | lock `model` (provenance only; never used by the audit) |

## Install the locked environment

```bash
git clone <repository> voxeltrace && cd voxeltrace
git checkout <release tag>            # e.g. v0.4.0-rc2 or later
python3.12 -m venv .venv && . .venv/bin/activate
pip install -e ".[app,dev]" -c constraints/tested-py312-x86_64.txt
python -m pytest -q                   # must pass before any partner data is touched
```

## Capture the environment (once per pilot, before the first run)

```bash
voxeltrace deployment-lock capture <pilot_folder>/deployment_lock.json \
    [--model-manifest <workspace>/models/Qwen3-VL-8B-Instruct.manifest.json]
```

Exit 1 and the message `DIRTY TREE: not a valid pilot lock` mean there are uncommitted changes;
commit or check out the release tag first. A lock is never overwritten.

## Verify the environment (before every run and before re-running an old pilot)

```bash
voxeltrace deployment-lock verify <pilot_folder>/deployment_lock.json
```

| Status | Meaning | Action |
|---|---|---|
| `LOCK_MATCH` | identical | run |
| `LOCK_MATCH_WITH_WARNINGS` | only non-result packages, the Python patch level or the platform string differ | run; note the warnings in the pilot log |
| `LOCK_MISMATCH` (exit 1) | Python major.minor, VoxelTrace version/commit, dirty tree, rule bundle, a schema, or a result-relevant package (numpy, pydicom, pydantic, pydantic-settings, SimpleITK, nibabel, Pillow, PyYAML) differs | do not run; restore the locked environment |

## Why not Docker (now)

The audit has no system dependencies beyond Python wheels and makes no network calls; a
constraints file plus the lock reproduces it (clean-install verified, `docs/dependency_strategy.md`).
A container image is worth adding when a partner requires installation on their own
infrastructure under change control; that is listed in the paid-pilot gate.

## Evidence already in every output

Each evidence bundle's `manifest.json` records the VoxelTrace version, git commit and dirty
flag, rule bundle sha256, rule versions, schema versions, Python, platform and key package
versions. The deployment lock adds the full package list and makes the comparison explicit.
