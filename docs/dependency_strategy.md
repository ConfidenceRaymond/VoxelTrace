# Dependency and reproducibility strategy

**Goal:** a normal `pip install` keeps working, while a pilot can be re-run later with the
exact dependency set that produced it.

## Current state (2026-10-09)

`pyproject.toml` declares **lower bounds** for all runtime dependencies and, from 0.4.0,
**major-version caps** for the three whose next major release is most likely to change
behaviour silently:

| Package | Bound | Why it matters to results |
|---|---|---|
| numpy | `>=1.26,<3` | voxel arithmetic, SUV statistics, float formatting in JSON |
| pydicom | `>=3.0,<4` | header parsing (value types, DS/IS handling, private tags); a major release changes APIs and coercion |
| pydantic | `>=2.6,<3` | every exported schema (serialization order, validation) |
| pydantic-settings, httpx, PyYAML, nibabel, SimpleITK, Pillow | lower bound only | settings, optional AI client, YAML I/O, NIfTI/SEG geometry, resampling, QC images |
| streamlit, plotly (`[app]`) | lower bound only | review UI only; never in a verdict |
| pytest, ruff (`[dev]`) | lower bound only; CI pins ruff | tests and lint |

No upper bound was added where none is justified; over-pinning makes installation fail on new
platforms without improving reproducibility.

## Where drift could change outputs

| Risk | Effect | Detection |
|---|---|---|
| numpy / SimpleITK numeric changes | last-digit differences in SUV statistics → different JSON bytes → different `checksums.sha256`; a value exactly at a rule threshold could in principle flip | re-run comparison of `checksums.sha256` (`validation/reproducibility.md`); thresholds are far from typical values but this is not proven for every case |
| pydicom value coercion (DS/IS, multi-valued, encodings) | a field read as missing or differently typed → different evidence status | tests on synthetic DICOM (`test_ingest_dicom.py`, `test_suv.py`, failure injection) |
| pydantic serialization | changed key order or number formatting in exported JSON | byte-identity tests (`test_fs_order.py`) |
| ruff formatter | CI-only formatting failures, no effect on results | CI pins `ruff==0.17.0` |

## Tested version matrix

| Python | Platform | Dependency set | Evidence |
|---|---|---|---|
| 3.12.3 | x86_64, Ubuntu 24.04 (Ryzen 9 9950X) | `constraints/tested-py312-x86_64.txt` (numpy 2.5.3, pydicom 3.0.2, pydantic 2.14.0, SimpleITK 2.5.6, nibabel 5.4.2, …) | clean install 2026-10-09: 710 tests, run-pilot, verify-delivery (`outputs/install_verification_20261009`) |
| 3.12.3 | aarch64 (NVIDIA GB10) | numpy 2.5.3, pydantic 2.13.5, pydicom 3.0.2 (see `environment_snapshot.md`) | 637 tests at the migration freeze; 9-pair verdicts byte-identical to x86 |
| 3.11 | ubuntu-latest (CI) | floating within bounds | CI matrix |
| 3.12 | ubuntu-latest (CI) | floating within bounds, and pinned via the constraints file (fresh-install job) | CI |

## Policy

1. **Normal install** (`pip install -e ".[app,dev]"`) stays floating within the bounds.
2. **Pilot install:** use the tested set and record it in the pilot log:
   `pip install -e ".[app,dev]" -c constraints/tested-py312-x86_64.txt`.
   Every evidence bundle already records Python, platform and the key package versions
   (`manifest.json → runtime_environment`).
3. **New constraints file** per platform or Python version only after a clean install passes
   the full test suite and the reproducibility comparison; name it
   `constraints/tested-py<ver>-<arch>.txt` and add it to the matrix above.
4. **Upgrading a capped major version** (numpy 3, pydicom 4, pydantic 3) is a deliberate
   change: run the full suite, re-run the real cohort, and compare pair-verdict CSVs and
   `checksums.sha256` with the previous constraints before raising the cap.
5. **The optional VLM runtime** is a separate environment and lock:
   `constraints/vlm-runtime-x86_64-cu130.txt` (torch 2.14.1+cu130, transformers 5.19.0,
   qwen-vl-utils 0.0.14; CUDA 13.0 wheel index). It is never installed into the audit
   environment and no audit result depends on it.
6. A full hash-locked lockfile (`pip-compile --generate-hashes` or `uv lock`) is
   **recommended before a paid pilot** that requires installation on customer
   infrastructure; it is not added now because the project has no lock tooling installed and
   the constraints file already reproduces the tested set.
