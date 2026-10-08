# VoxelTrace

**Local AI for Quantitative PET Intelligence**

> **RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.**
> VoxelTrace is not a medical device and must not be used for diagnosis or treatment decisions.

VoxelTrace is a local-first research prototype for quantitative PET imaging analysis.
It is an ongoing research and product project, developed on an NVIDIA GB10
(DGX-Spark-class) workstation.

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

## Status: milestone 5+ (multimodal evaluation foundation + trial comparability audit)

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

- `voxeltrace.quant` (milestone 3), documented in [docs/quantification.md](docs/quantification.md):
  - **Strict SUVbw** for one path only: Units BQML, DecayCorrection START, CorrectedImage
    including ATTN and DECY. The validator checks that path and returns structured refusal
    reasons.
  - **Timing:** times are parsed strictly. The decay reference time must be cross-validated
    against acquisition times, and midnight crossings follow an explicit documented rule.
  - **Rescale:** applied per slice, with every factor recorded for audit.
  - **Lesion metrics** per supplied segment: MTV, SUVmin/max/mean/median/SD/percentiles, TLG,
    connected components.
  - **SUVpeak:** a 1.0 cm³ sphere (r = 6.2035 mm) positioned to maximise the mean.
  - **Evidence object:** a typed `QuantEvidence` split into measured, provenance, warnings and
    not-established sections.
  - **Validation:** checked against hand-calculated oracles and an independent reimplementation
    (`scripts/crosscheck_quant.py`).
- `scripts/quantify_case.py` (CLI) and the Streamlit **Quantitative PET** page.
- `voxeltrace.evidence` (milestone 4). This step is header-only and reads standard DICOM tags
  only:
  - **Evidence types:** typed scanner, acquisition, reconstruction and correction evidence.
    Each field is PRESENT, MISSING, PRESENT_BUT_AMBIGUOUS or UNSUPPORTED, and records its
    DICOM source.
  - **Protocol QC:** maps each gap to what it blocks (SUV, lesion metrics, cross-scan
    comparison) instead of failing the whole case.
  - **`compare_protocols`:** classifies a pair of scans as COMPARABLE,
    COMPARABLE_WITH_WARNINGS, NOT_COMPARABLE or INSUFFICIENT_INFORMATION.
  - **Claim gating:** deterministic `ClaimEvidence` with the statuses SUPPORTED,
    PARTIALLY_SUPPORTED, NOT_ESTABLISHED and CONTRADICTED. Diagnosis, treatment response and
    image noise are always NOT_ESTABLISHED.
  - **Documentation:** [docs/protocol_evidence.md](docs/protocol_evidence.md),
    [docs/reconstruction_evidence.md](docs/reconstruction_evidence.md),
    [docs/comparability.md](docs/comparability.md) and [docs/claims.md](docs/claims.md).
  - **UI:** the Streamlit **Protocol & Claims** page.
- Milestone 5 adds four packages. **No model has been trained.**
  - `voxeltrace.training`:
    - a typed ground-truth hierarchy with provenance on every value;
    - `MODEL_GENERATED` is rejected as ground truth;
    - a generator for nine multimodal example classes plus an adversarial corpus;
    - patient-level splits with leakage checks;
    - generic and Qwen3-VL JSONL export.
  - `voxeltrace.visualization`:
    - deterministic PET, CT, fusion, MIP, crop, overlay and marker rendering;
    - exact voxel↔patient↔pixel mappings;
    - a verifier that rejects inconsistent renders.
  - `voxeltrace.evaluation`:
    - deterministic scoring (numeric exactness, invented numbers, claim, refusal and metadata
      accuracy, grounding, policy and hallucination checks);
    - a response gate.
  - **Development datasets:** three public subjects (melanoma, negative control, lung cancer on
    the second scanner model) are DEVELOPMENT_ONLY and **not** a training set.
  - See [docs/ground_truth.md](docs/ground_truth.md),
    [docs/visualization.md](docs/visualization.md),
    [docs/model_selection.md](docs/model_selection.md),
    [docs/fine_tuning_plan.md](docs/fine_tuning_plan.md),
    [docs/training_dataset_plan.md](docs/training_dataset_plan.md) and
    [docs/external_crosscheck.md](docs/external_crosscheck.md).
  - **Frozen evaluation sets:** dev_v1, dev_v2 ([docs/baseline_dev_v2.md](docs/baseline_dev_v2.md))
    and dev_v3 with the field-aware evaluator `vt-eval-2` ([docs/dev_v3.md](docs/dev_v3.md)).

Quantitative correctness is validated **only for the implemented DICOM path**, not for all
vendor PET DICOM variants.

**Not yet implemented:** DecayCorrection ADMIN/NONE, non-BQML units, SUVlbm/SUVbsa,
automatic segmentation, BIDS ingestion, multi-frame (enhanced) image loading, and AI
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
Deterministic quantitative engine    (strict SUVbw, lesion metrics)
      |
      v
Protocol / reconstruction evidence   (scanner, acquisition, recon, corrections, QC)
      |
      v
Structured evidence object           (Pydantic schemas)
      |
      v
Claim gating                         (deterministic, no LLM)
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

## Quantify a case (strict SUV + lesions)

```bash
.venv/bin/python scripts/quantify_case.py ../data/fdg_pet_ct_lesions/PETCT_0011f3deaf \
    --subject PETCT_0011f3deaf --dataset FDG-PET-CT-Lesions
# writes ../outputs/PETCT_0011f3deaf/{suv_input_audit,suv_result|suv_refusal,lesion_metrics,evidence}.json
# also writes scanner_evidence, acquisition_protocol, reconstruction_protocol,
#   correction_evidence, protocol_qc and claim_evidence JSON
# exit 0 = SUV computed, 2 = refused (reasons printed and written)
```

## Trial comparability audit (deterministic, no AI)

- Analysis covers subject × timepoint × site under **one explicitly selected, source-cited
  rule set**: `qiba-fdg-1.14`, `percist-1.0` or `eanm-fdg-2.0`. Each rule set also includes
  explicit VoxelTrace prerequisites.
- **Verdicts:** ASSESSABLE / ASSESSABLE_WITH_WARNINGS / NOT_ASSESSABLE /
  INSUFFICIENT_INFORMATION, each with actionable reason codes.
- **Also included:**
  - strict SUL (LBMJAMES128 / LBMJANMA);
  - liver and blood-pool reference measurement: supplied regions, or deterministic
    CT-guided proposals that count only after a hash-bound human review on the
    **Reference Review** app page ([docs/reference_regions.md](docs/reference_regions.md),
    [docs/reference_region_review.md](docs/reference_region_review.md));
  - an anonymization-loss audit;
  - creator-checked vendor private attributes.
- **Output:** JSON + CSV.
- **Not assessed:** biological or treatment response.
- **Documentation:** [docs/trial_audit.md](docs/trial_audit.md) and
  [docs/trial_rules.md](docs/trial_rules.md).

```bash
.venv/bin/python scripts/run_trial_audit.py <trial_dir> --ruleset percist-1.0 --out ../outputs/<name>
# -> trial_audit.json, subject_timepoint_matrix.csv, pair_checks.csv, site_summary.json,
#    reference_regions.csv, reference_review_worksheet.yaml, reference_qc/*.png
.venv/bin/python scripts/build_trial_demo.py   # real baseline + SYNTHETIC_PERTURBATION follow-ups
# -> ../outputs/synthetic_comparability/audit_<ruleset>/{trial_audit.json,
#    subject_timepoint_matrix.csv,pair_checks.csv,site_summary.json}
```

## Build a development example dataset (no model involved)

```bash
.venv/bin/python scripts/build_dev_dataset.py ../data/fdg_pet_ct_lesions/PETCT_0011f3deaf \
    --subject PETCT_0011f3deaf
# -> ../outputs/training_dev/<subject>/{images/,examples.jsonl,examples_qwen3vl.jsonl,
#    manifest.json,ground_truth.json} and ../outputs/visual_audit/<subject>_contact_sheet.png
.venv/bin/python scripts/evaluate_responses.py examples.jsonl responses.jsonl --out report.json
```

Derived PNGs are medical-image derivatives. They stay under the project root (`~/voxeltrace_hackathon`) and are never
committed.

## Other scripts

- `scripts/check_environment.sh` - regenerate `docs/environment_snapshot.md` (`make env-snapshot`).
- `scripts/cleanup_audit.sh` - **read-only** inventory of project-local material (`make audit`).

## Safety and limitations

- Research prototype; no clinical validation of any kind.
- SUVbw and lesion metrics are research measurements. They are validated only for the
  implemented DICOM path (BQML/START) on synthetic oracles and one public case, not for all
  scanners or vendors.
- MTV, TLG and SUVpeak depend on the supplied segmentation. No automatic segmentation is
  performed.
- AI outputs, once implemented, are interpretations of supplied evidence and may still be wrong.

## Data policy

No imaging data, model weights or secrets in Git. Data, models, outputs, logs and temp
files live in sibling directories (`../data`, `../models`, `../outputs`, `../logs`, `../tmp`).
See [docs/data_policy.md](docs/data_policy.md).

## License

MIT - see [LICENSE](LICENSE). Citation metadata in [CITATION.cff](CITATION.cff).
