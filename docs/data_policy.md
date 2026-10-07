# Data policy

VoxelTrace runs on a **temporary** NVIDIA GB10 hackathon workstation. All project
material lives under `/home/dell/voxeltrace_hackathon/` so it can be removed cleanly.

## Never committed to Git

- **No medical imaging data** (DICOM, NIfTI, NRRD, MHA/MHD, RAW, etc.), whether patient or public.
- **No model weights** (`*.safetensors`, `*.gguf`, `*.pt`, `*.pth`, `*.ckpt`, `*.bin`).
- **No secrets** (API keys, tokens, passwords, `.env`).

These patterns are blocked in `.gitignore`; that is a safety net, not a substitute for care.
Patient or public imaging data must **never** be pushed to GitHub.

## Where things live (relative to the repo)

| Material | Location |
|---|---|
| Downloaded public datasets | `../data` |
| Model weights / model caches | `../models` |
| Generated outputs | `../outputs` |
| Logs | `../logs` |
| Project temporary files, pip cache | `../tmp` |

Dependency caches are redirected into this tree where practical
(`PIP_CACHE_DIR=../tmp/pip-cache`, `HF_HOME=../models/hf-cache`; see `.env.example`).

## Manifest and test fixtures

- Every real download is recorded in `../data/manifest.json` with collection, subject, source,
  timestamp, file count, bytes, SHA-256 checksums and licence.
- Tests create **synthetic** DICOM and NIfTI fixtures at runtime under `../tmp/pytest`. No real
  images are used in tests or committed.
- UI and CLI output never read or show PatientName, PatientID or BirthDate.

## Dataset licences

Public datasets (TCIA, OpenNeuro) are used under their own data-use terms.
Record dataset, version and licence for each download in `docs/validation.md` before use.

## Departure

Before leaving the workstation we will:

1. Run `scripts/cleanup_audit.sh` (read-only inventory).
2. Review anything reported outside `~/voxeltrace_hackathon`.
3. Push any code worth keeping (code only, never data or weights).
4. Delete hackathon-local data, models, caches, outputs and source.
