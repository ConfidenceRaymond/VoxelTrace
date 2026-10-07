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

## Hackathon status: milestone 0/1 (foundation)

Currently implemented:

- `voxeltrace.quant.compute_image_stats`: deterministic whole-array statistics
  (shape, counts, NaN/±inf/zero counts and fractions, finite min/max/mean/std,
  median, 1st/99th percentiles) returning a typed `ImageStats` model.
- `voxeltrace.ai.LocalAIClient`: local endpoint health / model-list check that fails
  cleanly when no server is running; reasoning payload builder. `reason_structured()`
  is a placeholder that raises `NotImplementedError`.
- Streamlit landing page showing runtime info, local AI status and a smoke test on a
  **synthetic** array.

**Not yet implemented:** DICOM/NIfTI/BIDS ingestion, SUV computation, segmentation/ROI
metrics, QC, AI interpretation. No model is downloaded; no dataset is downloaded.

## Planned datasets

- FDG-PET-CT-Lesions (TCIA)
- NSCLC-Radiogenomics (TCIA)
- ACRIN-NSCLC-FDG-PET (TCIA)
- OpenNeuro PET datasets

## Architecture

```
PET/CT/SEG/BIDS
      |
      v
VoxelTrace ingestion                 (planned)
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
