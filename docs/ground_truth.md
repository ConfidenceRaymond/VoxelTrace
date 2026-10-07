# Ground truth

Code: `src/voxeltrace/training/schema.py` (models) and `ground_truth.py` (builder).

VoxelTrace training and evaluation targets come **only** from validated measurements,
supplied segmentations and metadata. They never come from model guesses.

## Hierarchy

| Level | Source type | Content | Use as target |
|---|---|---|---|
| 1 | `PRIMARY_IMAGE` | original image pixels | yes (input, not a label) |
| 2 | `PRIMARY_DICOM_METADATA` | scanner, acquisition, reconstruction and correction attributes | yes, when VALIDATED |
| 3 | `REFERENCE_SEGMENTATION` | the provided reference segmentation (DICOM SEG) | yes |
| 4 | `DETERMINISTIC_DERIVATION` | SUV, SUVmax, mean, median, peak, MTV, TLG, volume, geometry, connected components, rendered-pixel coordinates | yes, when VALIDATED |
| 5 | `RULE_DERIVATION` | protocol comparability, claim statuses, contradictions, insufficient-information answers | yes, when VALIDATED |
| 6 | `EXPERT_ANNOTATION` | human-reviewed natural-language descriptions | only with `REVIEWED` status |
| 7 | `MODEL_GENERATED` | any LLM/VLM output | **never**. Construction raises an error |

## GTValue

Every ground-truth value is a `GTValue` with:
- `value` and `unit`;
- `source_type` (sets the level);
- `source_ref` (an evidence JSON path, DICOM tag or rule id);
- `derivation` (e.g. `suv_strict`, `lesion_metric`, `geometry_transform`, `rule_engine`,
  `dicom_free_text_pattern`, `synthetic_perturbation`);
- `validation_status`.

Rules enforced in code:
- `MODEL_GENERATED` is rejected at construction.
- `EXPERT_ANNOTATION` requires `REVIEWED`, and `REVIEWED` is allowed only for
  `EXPERT_ANNOTATION`.
- `usable_as_target`:
  - for levels 1–5, only `VALIDATED` or `VALIDATED_ABSENT` (a verifiably absent field: the
    missingness is the fact);
  - for level 6, only `REVIEWED`.
- A `TrainingExample` is rejected if any of its `target_sources` is not usable as a target, or
  if its `ground_truth_level` is not the highest source level.

## Validation status by evidence type

- **Strict SUVbw and lesion metrics:** `VALIDATED`. They are covered by hand-calculated oracle
  tests and an independent reimplementation.
- **Standard DICOM attributes:** `VALIDATED`.
- **Absent attributes:** `VALIDATED_ABSENT`.
- **Values parsed from vendor free text and `PRESENT_BUT_AMBIGUOUS` fields:** `UNVALIDATED`.
  These are not used as targets. The raw text itself (e.g. ReconstructionMethod) can be a
  level-2 target.
- **Claims and comparability:** `VALIDATED` rule outputs (level 5).
- **Synthetic perturbations** of real evidence (for example, one field removed to create a
  missing-data question) are marked with `derivation=synthetic_perturbation` and
  `synthetic_perturbation=true` on the example.

## What a "lesion" is

- A **lesion** is one supplied reference segment (DICOM SEG segment).
- Its 26-connected components are listed separately as `GroundTruthComponent`s.
- VoxelTrace never infers lesion outlines.
- A slice without segment voxels is labelled `contains_segmented_target = false`. That means
  only that no reference-segmented target is present. It does **not** mean "normal" or
  "disease-free".

## Example generation rules (`training/examples.py`)

**Positive slices** (per supplied segment, at most 8):
- P1: the slice containing the SUVmax voxel;
- P2: the slice containing the SUVpeak centre;
- P3: for each 26-connected component, the slice where it has its largest in-slice area;
- a candidate within 3 slices of an already selected slice is skipped (no near-duplicates);
- a candidate is **excluded** if more than 50 % of the segment's voxels in that slice have
  SUV exactly 0 (the reference mask lies over masked or zeroed PET). Excluded slices appear only
  in the human-review contact sheet.

**Negative slices:**
- **only if the reference SEG was decoded** (possibly empty);
- no segment voxels, and at least 10 slices from any segmented slice;
- PET signal present and CT body present;
- 4 slices, taken at the 15/40/65/90 % quantiles of the eligible slices;
- the label means "no reference-segmented target", never "normal".

**Lesion crops** are centred on the segment's in-slice centroid, falling back to the SUVmax
voxel.

**Classes:**
- VISUAL_LOCALIZATION
- QUANTITATIVE_READING (from evidence JSON, never from pixels)
- PROTOCOL_READING (standard attributes only)
- CLAIM_VERIFICATION
- CONTRADICTION (wrong values at 4 significant digits, kept only if the rule engine says
  CONTRADICTED)
- REFUSAL
- MISSING_DATA (real absent fields plus one flagged synthetic removal)
- VISUAL_QUANTITATIVE (the SUVmax pixel)
- PROTOCOL_COMPARABILITY (real protocol against flagged synthetic perturbations)
- ADVERSARIAL (injected free text under `untrusted_metadata`)

**Splits:** fewer than 20 subjects means DEVELOPMENT_ONLY. Otherwise patients are split with a
salted hash. `check_leakage` rejects any subject, study, longitudinal study or derived image
that crosses splits.
