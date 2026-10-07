# VoxelTrace

**Local AI for Quantitative PET Intelligence**

> **RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.**
> VoxelTrace is not a medical device and must not be used for diagnosis or treatment decisions.

VoxelTrace is a local-first research prototype for quantitative PET imaging analysis,
built during an NVIDIA GB10 (DGX-Spark-class) hackathon.

## Core idea

```
deterministic quantitative imaging  +  structured evidence  +  local AI reasoning
```

**Why separate the numbers from the AI?** Language models can produce fluent but
fabricated numbers. In VoxelTrace, Python computes every quantitative measurement
deterministically and reproducibly. Those measurements, plus metadata and QC results,
are packed into typed evidence objects. The local LLM only *interprets* that evidence;
it is never asked to produce or estimate a measurement.

**Why local?** Imaging data and model inference stay on the workstation. The AI client
talks only to a loopback OpenAI-compatible endpoint (default `http://127.0.0.1:8000/v1`,
e.g. vLLM on the GB10), refuses non-local endpoints by default, has no cloud fallback,
and needs no API key.

## Hackathon status: milestone 2 (PET/CT/SEG ingestion)

Currently implemented:

- `voxeltrace.quant.compute_image_stats`: deterministic whole-array statistics
  (shape, counts, NaN/±inf/zero counts and fractions, finite min/max/mean/std,
  median, 1st/99th percentiles) returning a typed `ImageStats` model.
- `voxeltrace.ai.LocalAIClient`: local endpoint health / model-list check that fails
  cleanly when no server is running; reasoning payload builder. `reason_structured()`
  is a placeholder that raises `NotImplementedError`.
- Streamlit landing page showing runtime info, local AI status and a smoke test on a
  **synthetic** array.
- `voxeltrace.ingest` (milestone 2):
  - **DICOM discovery:** recursive, header-only, grouped by Study/Series UID. Series are
    classified PET/CT/SEG/OTHER from `Modality`/`SOPClassUID` only, never from file paths.
    Malformed files produce warnings rather than crashes.
  - **PET metadata extraction:** fields are recorded exactly as found. Absent, empty, invalid
    and inconsistent fields are reported. Nothing is defaulted and units are not converted.
  - **PET/CT volume loading:** slices are sorted by `ImagePositionPatient` along the slice
    normal. The loader records affine, spacing and extent. It refuses duplicate slice positions
    and missing or inconsistent geometry, and warns on non-uniform slice spacing. The output was
    cross-checked against SimpleITK in tests.
  - **NIfTI:** images and label masks are loaded with nibabel. Mask content is validated and the
    mask grid is compared to the target image without resampling.
  - **DICOM SEG:** segment metadata and references are read. **BINARY** SEG is decoded strictly
    onto the referenced PET/CT grid; FRACTIONAL SEG and anything ambiguous is refused.
- `scripts/inspect_case.py`: a CLI inspector with text or JSON output. Pass `--load-pixels`
  to also load volumes and decode SEG.
- Streamlit **Imaging Ingestion** page.
- `scripts/fetch_tcia_subject.py`: a bounded download of one subject from TCIA.

**Not yet implemented:** SUV (see [docs/suv_requirements.md](docs/suv_requirements.md)),
lesion/ROI metrics, BIDS ingestion, multi-frame (enhanced) image loading, and AI
interpretation. No model has been downloaded. One public subject from FDG-PET-CT-Lesions is
stored locally, outside Git.

## Datasets

These datasets serve different purposes and must not be naïvely pooled. See
[docs/datasets.md](docs/datasets.md).

- FDG-PET-CT-Lesions (TCIA): the primary lesion and PET/CT demonstration. One subject is stored
  locally; see [docs/first_demo_case_plan.md](docs/first_demo_case_plan.md).
- NSCLC-Radiogenomics (TCIA): later, for radiomics with clinical context.
- OpenNeuro PET: for research use, BIDS ingestion and QC.
- ACRIN-NSCLC-FDG-PET (TCIA): later, for longitudinal response analysis.

## Architecture

```
PET/CT/SEG/BIDS
      |
      v
VoxelTrace ingestion                 (DICOM PET/CT/SEG + NIfTI)
      |
      v
Deterministic quantitative engine    (initial stats implemented)
      |
      v
Structured evidence object           (Pydantic schemas)
      |
      v
Local AI on GB10                     (client skeleton)
      |
      v
Evidence-grounded interpretation     (planned)
```

See [docs/architecture.md](docs/architecture.md).

## Installation

Requires Python ≥ 3.11 (developed on 3.12.3, aarch64, Ubuntu 24.04).

```bash
cd /home/dell/voxeltrace_hackathon/voxeltrace
make install          # creates .venv and installs -e ".[app,dev]"; pip cache -> ../tmp/pip-cache
```

Configuration: `configs/default.yaml`, overridable with `VOXELTRACE_*` environment
variables (see `.env.example`; load with `set -a; source .env; set +a`).

## Tests and lint

```bash
make test             # pytest
make lint             # ruff check
```

## Launch the app

```bash
make app              # http://127.0.0.1:8501
```

## Inspect a case

```bash
.venv/bin/python scripts/inspect_case.py ../data/fdg_pet_ct_lesions/PETCT_0011f3deaf
.venv/bin/python scripts/inspect_case.py <dir> --load-pixels --json > ../outputs/case.json
```

## Other scripts

- `scripts/check_environment.sh` - regenerate `docs/environment_snapshot.md` (`make env-snapshot`).
- `scripts/cleanup_audit.sh` - **read-only** inventory of hackathon material (`make audit`).

## Safety and limitations

- Research prototype; no clinical validation of any kind.
- The only quantitative function so far is generic array statistics; it is not a PET/SUV metric.
- AI outputs, once implemented, are interpretations of supplied evidence and may still be wrong.

## Data policy

No imaging data, model weights or secrets in Git. Data, models, outputs, logs and temp
files live in sibling directories (`../data`, `../models`, `../outputs`, `../logs`, `../tmp`).
See [docs/data_policy.md](docs/data_policy.md).

## License

MIT - see [LICENSE](LICENSE). Citation metadata in [CITATION.cff](CITATION.cff).
