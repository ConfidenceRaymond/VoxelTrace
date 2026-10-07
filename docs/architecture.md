# Architecture

```
PET/CT/SEG/BIDS
      |
      v
VoxelTrace ingestion                    (planned)
      |
      v
Deterministic quantitative engine       (voxeltrace.quant - whole-array stats implemented)
      |
      v
Structured evidence object              (voxeltrace.schemas - Pydantic models)
      |
      v
Local AI on GB10                        (voxeltrace.ai - client skeleton, health check)
      |
      v
Evidence-grounded interpretation        (planned)
```

## Separation of concerns

| Layer | Package | Rule |
|---|---|---|
| Quantitative engine | `voxeltrace.quant` | Pure, deterministic NumPy. No AI. Same input gives the same output. Invalid data is counted or rejected, never silently repaired. |
| Evidence | `voxeltrace.schemas` | Typed, frozen Pydantic models. The only thing handed to the AI layer. |
| AI reasoning | `voxeltrace.ai` | Talks to a local OpenAI-compatible server (default `http://127.0.0.1:8000/v1`). Non-loopback endpoints are refused unless explicitly enabled. No cloud fallback. No API key required. The model interprets evidence; it never produces measurements. |
| Config | `voxeltrace.config` | `configs/default.yaml`, overridden by `VOXELTRACE_*` env vars. |
| UI | `app/Home.py` | Streamlit. Currently a smoke-test landing page. |

## Implemented vs planned (milestone 0/1)

Implemented: `compute_image_stats`, `ImageStats`/`AIServerStatus` schemas, `LocalAIClient.health()` / `list_models()` / `build_reasoning_request()`, Streamlit landing page.

Planned: DICOM/NIfTI/BIDS ingestion, SUV conversion, ROI/segmentation-based metrics, QC checks, `LocalAIClient.reason_structured()` (currently raises `NotImplementedError`), vLLM deployment on GB10.
