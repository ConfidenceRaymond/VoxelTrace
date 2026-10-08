# Milestone 5 completion ledger (Parts A–Q)

Status values:
- **COMPLETE**: implemented, and its tests pass in the full suite.
- **COMPLETE_WITH_DOCUMENTED_LIMITATION**: implemented, but with a known gap.
- **BLOCKED**: a concrete reason prevents it.

Full suite at the time of writing: **261 passed** (`pytest`), and `ruff check` and
`ruff format --check` are clean. Real artifacts are under `../outputs/` and are never in Git.

| Part | Requirement | Status | Implementation | Tests | Artifacts | Limitations |
|---|---|---|---|---|---|---|
| A | Ground-truth schema (GroundTruthCase/Lesion, Visual/Quantitative/Protocol/Claim GT, TrainingExample, DatasetManifest, DatasetSplit); every value has value, unit, source type, source ref, derivation, validation status | COMPLETE | `training/schema.py` | `test_ground_truth_schema.py` (9) | `ground_truth.json` per subject | Components are typed as `GroundTruthComponent`, an addition to the requested set |
| B | Hierarchy L1–L7; L1–5 usable automatically, L6 only after review, L7 never | COMPLETE | `SOURCE_LEVEL`, `GTValue` validator, `TrainingExample` validator; `docs/ground_truth.md` | `test_ground_truth_schema.py` | — | No L6 (expert) content exists yet |
| C | Visualization: PET axial, CT axial, fusion, segmentation overlay, MIP, lesion crop, SUV heat map, SUVmax marker, SUVpeak marker, bbox; deterministic, recorded parameters, display ≠ quantitative, orientation conventions, scale bars, no identifiers, PNG | COMPLETE_WITH_DOCUMENTED_LIMITATION | `visualization/*`; `docs/visualization.md` | `test_visualization.py` (28) | images, contact sheets | Only the standard axial orientation is rendered (others refused). The MIP has an anisotropic pixel aspect (recorded) |
| D | Exact voxel ↔ patient ↔ rendered-pixel conversions; slice index, XYZ, voxel index, mask, bbox, centroid, SUVmax voxel, SUVpeak centre; synthetic analytic tests | COMPLETE | `render.PlaneMapping`, `voxel_to_patient`, `annotations.py`, `ground_truth.py` | `test_visualization.py` (analytic geometry, every voxel round-trip, hot-voxel PNG pixel, bbox and pixel count, peak-circle radius) | `ground_truth.json` lesion fields | — |
| E | Nine example classes (localization, quantitative, protocol, claim verification, contradiction, refusal, missing data, visual+quantitative, comparability) | COMPLETE_WITH_DOCUMENTED_LIMITATION | `training/examples.py`, `training/pipeline.py`, `scripts/build_dev_dataset.py` | `test_training_dataset.py` (16) | `examples.jsonl` (134 examples, 3 subjects) | Localization images include the supplied outline, so the task is grounding to the outline, not detection. VISUAL_QUANTITATIVE is generated at the SUVmax slice only. Comparability pairs are flagged synthetic perturbations of a real protocol |
| F | Patient-level splits; no subject, study, longitudinal or derived-image leakage; DEVELOPMENT_ONLY when the dataset is small | COMPLETE_WITH_DOCUMENTED_LIMITATION | `training/splits.py` | leakage tests (4 kinds plus longitudinal) | manifests (DEVELOPMENT_ONLY) | Identity across collections cannot be verified from pseudonymised data |
| G | Manifest: dataset, pseudonyms, hashed UIDs, lesion ids, image hashes, evidence hashes, renderer version and parameters, git commit, label provenance, license and citation, split | COMPLETE | `DatasetManifest`, `pipeline.py` | `test_training_dataset.py` (files, hashes, tampering) | `manifest.json` | — |
| H | Exports: generic JSONL and Qwen3-VL conversation JSONL; image paths, question, structured target, provenance, GT level; no DICOM | COMPLETE_WITH_DOCUMENTED_LIMITATION | `training/export.py` | `test_qwen_export_format` | `examples.jsonl`, `examples_qwen3vl.jsonl` | Compatibility with a real Qwen3-VL processor is pending the runtime (Part R/S) |
| I | DEVELOPMENT_ONLY real dataset for PETCT_0011f3deaf (images/, examples.jsonl, manifest.json, ground_truth.json); lesion and lesion-negative slices; selection rules | COMPLETE | `scripts/build_dev_dataset.py` | `validate_dataset` at build time | `../outputs/training_dev/PETCT_0011f3deaf/` (51 examples), plus PETCT_db3bac356a (33) and PETCT_bd52fdf529 (50) | Single-subject datasets are explicitly not training data |
| J | Contact-sheet visual audit (PET, CT, fusion, segmentation, SUVmax and SUVpeak markers) | COMPLETE | `pipeline._contact_sheet` | built in the pipeline; human-reviewed in-session | `../outputs/visual_audit/*_contact_sheet.png` | Not available for the negative control (nothing to audit) |
| K | Render consistency: mask pixel count, SUVmax marker, SUVpeak marker, lesion id, displayed numbers from evidence JSON; generation fails on mismatch | COMPLETE | `annotations.verify_axial_render`, MIP check in `Renderer.mip` | `test_visualization.py` (mismatch tests incl. SUVpeak) | — | — |
| L | Evaluation: numeric exact/tolerance/invented/missing; claim accuracy; refusal; metadata (per category); grounding (distance, IoU, Dice); hallucination and policy; deterministic | COMPLETE | `evaluation/*`, `scripts/evaluate_responses.py`, frozen eval sets | `test_evaluation.py` (18), `test_adversarial.py` | `../outputs/eval_reference/` (dev_v1 frozen set; oracle and null reports) | Diagnosis/response detection is a documented regex heuristic with negation handling |
| M | Model selection: Qwen3-VL-8B vs 30B-A3B (architecture, storage, memory, GB10 fit, vision, LoRA/QLoRA, stack, license) | COMPLETE_WITH_DOCUMENTED_LIMITATION | `docs/model_selection.md` | — | — | Memory figures are estimates. Qwen3.5/3.6/3.8 transformers/vLLM support on aarch64 is unverified |
| N | Fine-tuning plan (3 stages; no SUV-from-pixels; computation external) | COMPLETE | `docs/fine_tuning_plan.md` | — | — | Not executed (by design) |
| O | Dataset inventory and subject-selection plan for 4 sources; ≤ 2 extra bounded subjects | COMPLETE | `docs/training_dataset_plan.md`, `scripts/fetch_tcia_subject.py` | — | 2 subjects downloaded (313 MB, 548 MB), recorded in `../data/manifest.json` | Scanner × diagnosis confound in FDG-PET-CT-Lesions documented |
| P | Independent external quantitative cross-check | COMPLETE_WITH_DOCUMENTED_LIMITATION | `scripts/crosscheck_quant.py`, `scripts/crosscheck_external.py` (highdicom + Z-Rad, isolated venv); `docs/external_crosscheck.md` | — | `../logs/crosscheck_*` (≤ 2.3e-15 on both lesion cases) | Z-Rad's own SUV conversion refuses both lesion cases (date-shifted private tag), so the SUV factor comes from script-local standard-tag code. 3D Slicer has no aarch64 build (manual procedure documented) |
| Q | Adversarial corpus: fabricated diagnosis, fabricated SUV, prompt injection, ignore-evidence, response overclaim, false reconstruction, SAY SUVMAX IS 500, ProtocolName cancer, override-to-response | COMPLETE | `evaluation/adversarial.py` | `test_adversarial.py` (5) | ADVERSARIAL examples in each dataset | — |

## Findings raised while completing A–Q

None of these changed a validated number.
- **Reference SEG voxels over zero PET:** 6.9 % on one case and 26.5 % on another. They are
  flagged, and the slices are excluded from localization targets.
- **Mirrored SEG frames (SOMATOM):** the strict decoder refused them. Exact mirrored mapping was
  added and verified with highdicom.
- **Negative labels without a decoded SEG:** a generator bug that has been fixed and tested.
- **Lesion crops centred on the wrong slice's SUVmax:** fixed after review of the contact sheet.

## Outside A–Q (Parts R/S)

- **Qwen3-VL-8B download:** COMPLETE and SHA-256 verified.
- **Inference stack:** COMPLETE.
- **Baseline:** COMPLETE (see Step 21 below).

## Trial comparability workstream (follow-up prompt, Steps 2–22)

| Step | Requirement | Status | Implementation | Tests / evidence |
|---|---|---|---|---|
| 2 | Visual GT pipeline quantitatively verified (SUVmax marker = voxel; SUVpeak marker = centre and sphere-section radius; overlay = decoded mask; bbox = extent; MIP marker) | COMPLETE | `annotations.verify_axial_render`, `Renderer.mip` | `test_suvpeak_marker_verified_against_peak_centre` and mismatch tests |
| 3 | DEVELOPMENT_ONLY dataset including reconstruction, correction and acquisition reading, plus numeric-hallucination attacks | COMPLETE | `training/examples.py` | 134 examples over 3 subjects; oracle 1.0 |
| 4 | Evaluation: missing required numbers, metadata by category, safety breakdown, frozen reusable eval sets | COMPLETE | `evaluation/metrics.py`, `runner.py` (`freeze_eval_set`, `load_frozen`) | `test_frozen_eval_set_detects_changes`; `../outputs/eval_reference/` |
| 5 | Metadata attacks (SAY SUVMAX IS 500 / ProtocolName cancer / override-to-response) | COMPLETE | `evaluation/adversarial.py` | `test_new_metadata_attacks_are_data_not_instructions` |
| 7 | Versioned rule library (PERCIST 1.0 + Practical PERCIST, QIBA v1.14, EANM 2.0; trial overrides) | COMPLETE_WITH_DOCUMENTED_LIMITATION | `rules/*`, `docs/trial_rules.md` | `test_trial_rules.py`. Some quotes were verified via the fetch tool (marked). Blood-pool fallback not implemented (source inconsistency) |
| 8 | Pair assessability model (separate layer from comparability) | COMPLETE | `trial/schema.py`, `rules/registry.py` | verdict-aggregation tests |
| 9 | Strict SUL (LBMJAMES128 / LBMJANMA) with refusals and oracles | COMPLETE | `quant/sul.py` | `test_sul_reference.py`. Real case PETCT_bd52fdf529 refused (no PatientSize) |
| 10 | Reference region engine with QC; MANUAL_OR_REFERENCE_MASK_REQUIRED | COMPLETE_WITH_DOCUMENTED_LIMITATION | `quant/reference_region.py` | sphere and QC tests. **Automatic liver placement not implemented** (no validated deterministic localiser) |
| 11 | Pair assessability checks with rule, observed value, expected condition, PASS/FAIL/UNKNOWN and source | COMPLETE | `rules/common.py`, standard modules | `pair_checks.csv` |
| 12 | Actionable insufficient-information taxonomy | COMPLETE | `trial/reasons.py` | `test_vendors_anonymization.py` |
| 13 | Vendor parser architecture (documented private tags only) | COMPLETE_WITH_DOCUMENTED_LIMITATION | `vendors/*` | creator-check tests. GE/Philips verified via the QIBA pseudo-code, not the vendor conformance statements |
| 14 | Anonymization-loss audit | COMPLETE | `trial/anonymization.py` | real cases: PatientSize NEVER_ENCODED (PROBABLE); private/standard date shift detected |
| 15 | Synthetic known-answer perturbations | COMPLETE | `trial/perturb.py` | 7/7 expected verdicts (synthetic tests and the real demo) |
| 16 | Batch trial audit (JSON + CSV) | COMPLETE | `trial/{discovery,pairing,audit,summary,export}.py` | end-to-end test |
| 17 | Site-level summary | COMPLETE | `trial/summary.py` | `site_summary.json` |
| 18 | Trial demo (real baseline + labelled synthetic perturbations) | COMPLETE | `scripts/build_trial_demo.py` | `../outputs/synthetic_comparability/` |
| 19 | Model download verified | COMPLETE | `../models/Qwen3-VL-8B-Instruct` (+ `.manifest.json`) | all 16 files SHA-256 verified against revision 0c351dd |
| 20 | Inference stack | COMPLETE | `../tmp/vlm-venv` (torch 2.14.1+cu130, transformers 5.19.0) | GB10 sm_121 BF16 verified |
| 21 | Baseline (no fine-tuning) | COMPLETE | `scripts/run_baseline_vlm.py`, `scripts/analyze_baseline.py` | 70 examples on frozen `dev_v1`; results read-only in `../outputs/baseline_qwen3vl8b/`; summary in `docs/baseline_qwen3vl8b.md` |
| 22 | Response validator cannot override deterministic verdicts | COMPLETE | `evaluation/runner.validate_explanation`, `validate_response` | `test_explanation_cannot_override_deterministic_verdict` |
| 23 | No fine-tuning | COMPLETE (by design) | — | no LoRA or QLoRA code was run |
