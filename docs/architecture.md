# Architecture

```
DATA                                    DICOM PET/CT/SEG, NIfTI  (../data, never in Git)
  ↓
INGESTION                               voxeltrace.ingest       (discovery, geometry, SEG)
  ↓
QUANT ENGINE                            voxeltrace.quant        (strict SUVbw, lesions, SUVpeak)
  ↓
PROTOCOL / RECONSTRUCTION EVIDENCE      voxeltrace.evidence     (scanner, acquisition,
  ↓                                                              reconstruction, corrections, QC)
EVIDENCE OBJECT                         QuantEvidence + ProtocolEvidence (typed JSON)
  ↓
CLAIM GATING                            voxeltrace.evidence.claims / comparability
  ↓
LOCAL AI (planned)                      OpenAI-compatible endpoint on 127.0.0.1 (not yet used)
```

## Separation of concerns

| Layer | Package | Rule |
|---|---|---|
| Quantitative engine | `voxeltrace.quant` | Pure, deterministic NumPy. No AI. Same input gives the same output. Invalid data is counted or rejected, never silently repaired. |
| Quantification | `voxeltrace.quant` | `dicom_time.py` parses DA/TM/DT strictly. `suv.py` holds the eligibility validator, timing policy and SUVbw. `lesions.py` computes per-segment MTV/SUV statistics/TLG/SUVpeak. `evidence.py` builds the `QuantEvidence` and output files. See [quantification.md](quantification.md). |
| Protocol evidence and claims | `voxeltrace.evidence` | Header-only, standard tags only. `scanner`, `acquisition`, `reconstruction` and `corrections` produce `EvidenceField`s (PRESENT / MISSING / PRESENT_BUT_AMBIGUOUS / UNSUPPORTED). `protocol` holds the bundle and QC. `comparability` provides `compare_protocols`. `claims` holds the deterministic claim rules. See protocol_evidence.md, reconstruction_evidence.md, comparability.md and claims.md. |
| Evidence | `voxeltrace.schemas` | Typed, frozen Pydantic models. The only thing handed to the AI layer. |
| AI reasoning | `voxeltrace.ai` | Talks to a local OpenAI-compatible server (default `http://127.0.0.1:8000/v1`). Non-loopback endpoints are refused unless explicitly enabled. No cloud fallback. No API key required. The model interprets evidence; it never produces measurements. |
| Ingestion | `voxeltrace.ingest` | `dicom.py` handles discovery, PET metadata, geometry and volumes. `nifti.py` loads NIfTI. `segmentation.py` handles NIfTI masks and DICOM SEG. `case.py` builds a `VoxelTraceCase`. Header-first: pixels are read only on request. Missing means missing. Ambiguous geometry raises `IngestError`. |
| Config | `voxeltrace.config` | `configs/default.yaml`, overridden by `VOXELTRACE_*` env vars. |
| UI | `app/Home.py` | Streamlit. Currently a smoke-test landing page. |

## Geometry conventions

- Each DICOM volume is a NumPy array indexed `[k, j, i]`, meaning slice, row and column.
- `ImageGeometry.affine` maps `(i, j, k, 1)` to patient **LPS** millimetres:
  - column i: `RowDirection · ΔcolumnSpacing`
  - row j: `ColumnDirection · ΔrowSpacing`
  - slice k: `normal · slice spacing`
- Slices are ordered by `ImagePositionPatient · (row_dir × col_dir)`. Filenames and
  `InstanceNumber` are never used for ordering.
- A NIfTI geometry keeps the file's **RAS** affine.
- `ImageGeometry.affine_ras()` converts an LPS affine to RAS (`diag(-1,-1,1)`) for comparison.
- Grids are compared, never resampled.

## Implemented vs planned

Implemented: `compute_image_stats`, `ImageStats`/`AIServerStatus` schemas, `LocalAIClient.health()` / `list_models()` / `build_reasoning_request()`, Streamlit landing page.

Milestone 2 added: DICOM/NIfTI/SEG ingestion (see above).

Milestone 3 added: strict SUVbw, lesion metrics and the evidence object (see quantification.md).

Milestone 4 added: protocol, reconstruction and correction evidence, protocol QC, comparability and deterministic claim gating.

Planned: BIDS ingestion, ROI/segmentation-based metrics, QC checks, `LocalAIClient.reason_structured()` (currently raises `NotImplementedError`), vLLM deployment on GB10.
