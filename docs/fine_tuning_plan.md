# Fine-tuning plan (not executed)

**No fine-tuning has been performed.** The current data are DEVELOPMENT_ONLY: 3 subjects,
pipeline testing only.

## Principle

The model learns to **use** evidence, never to **produce** measurements.

- SUV, SUVmax/mean/peak, MTV, TLG, geometry and comparability are computed by deterministic
  VoxelTrace code. The model receives them as structured evidence.
- **The model must not be trained to calculate SUV from screenshots.** Rendered PNG pixels are
  display-normalised (window 0–8 g/mL) and are not quantitative. Quantitative targets are
  always paired with the evidence JSON in the prompt.
- The model should learn to:
  - read structured evidence;
  - connect evidence to images (which outlined region is segment 1, where SUVmax lies);
  - localise *supplied* segmentations;
  - describe measured findings with exact numbers copied from the evidence;
  - recognise insufficient evidence (INSUFFICIENT_INFORMATION);
  - refuse unsupported conclusions (NOT_ESTABLISHED for diagnosis, response, prognosis and
    noise);
  - understand scanner, protocol and reconstruction context and comparability.
- All outputs pass `validate_response` (invented numbers, contradicted metric statements,
  blocked assertions, injection echoes) **at inference time**, whether or not the model was
  fine-tuned.

## Stage 1: prompt + tools only (next)

- Qwen3-VL-8B-Instruct with the VoxelTrace system prompt (`training/export.py`) and evidence JSON
  in context. No weight updates.
- Measure with `scripts/evaluate_responses.py` on the development set and the adversarial
  corpus.
- **Exit criteria**:
  - zero blocked assertions and zero injection echoes on the adversarial corpus;
  - invented-number rate below 1 % of numbers;
  - refusal accuracy at least 0.95.

## Stage 2: visual and instruction LoRA on curated examples

Prerequisites, all required:
- At least 20 subjects with patient-level TRAIN/VALIDATION/LOCKED_TEST splits
  (`assign_patient_splits`; `check_leakage` returns no violations), including negative
  controls and both scanner models.
- A LOCKED_TEST set that is frozen, hashed in the manifest, and never used for tuning or prompt
  iteration.
- Stage-1 baseline measured on LOCKED_TEST.
- Targets are levels 1–5 only. Level-6 text is used only after documented human review. Level 7
  is never used.

Recipe (initial):
- LoRA on the language model and projector, with the vision tower frozen at first.
- r = 16, alpha = 32, dropout 0.05, BF16, gradient checkpointing.
- 1–3 epochs, early stopping on VALIDATION.
- Tooling: LLaMA-Factory (`qwen3_vl` template) or PEFT + transformers, inside a venv in the
  hackathon tree.

Report on LOCKED_TEST, before vs after:
- every `EvaluationReport` metric;
- per-class accuracy;
- grounding IoU and point distance;
- adversarial pass rate.

Regression on any safety metric rejects the adapter.

## Stage 3: domain adaptation (optional, conditional)

Only if Stage 2 plateaus **and** the dataset reaches hundreds of subjects across scanners and
vendors **and** a held-out external collection is available. Otherwise it is skipped. Any
domain-adapted model repeats the full Stage-2 evaluation, including the adversarial corpus.

## Hard constraints

- No training on a single subject.
- No model-generated labels.
- No cloud APIs.
- No patient data in Git.
- All weights, caches and adapters stay under `../models`.
