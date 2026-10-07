# Qwen3-VL-8B-Instruct baseline (NO fine-tuning)

## Setup

- **Model:** `Qwen/Qwen3-VL-8B-Instruct` @ `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`. All files
  were SHA-256 verified.
- **Runtime:** torch 2.14.1+cu130 and transformers 5.19.0 on an NVIDIA GB10.
  - BF16 with SDPA attention.
  - Greedy decoding with at most 384 new tokens.
  - Peak GPU memory 18.1 GB.
- **Inputs:** 70 DEVELOPMENT_ONLY examples (at most 2 per class per subject, plus all
  adversarial) from the frozen set `dev_v1`.
- **What the model saw:** system and user turns only. The target turn was never sent.
- **Responses:** `MODEL_GENERATED`; never ground truth. Ground truth was not changed after these
  results.

## Primary score (frozen evaluator vt-eval-1; `evaluation_report.json`)

| Metric | Value |
|---|---|
| Accuracy, CLAIM_VERIFICATION | 1.00 |
| Accuracy, REFUSAL | 1.00 |
| Accuracy, MISSING_DATA | 0.50 |
| Accuracy, ADVERSARIAL | 0.125 |
| Accuracy, all other classes | 0.00 |
| JSON parse rate | 0.69 |
| Missing required numbers (by key) | 30 |
| Invented numbers | 8, all guessed bounding-box pixel coordinates in 2 localization answers |
| Blocked assertions (diagnosis, response, prognosis, treatment) | **0** |
| Injection echoes | **0** |

## Secondary, schema-independent analysis (`secondary_analysis.json`)

| Metric | Value |
|---|---|
| Target numbers present in the text, QUANTITATIVE_READING, PROTOCOL_READING and ADVERSARIAL | **1.00** |
| Claim and refusal labels | 1.00 |
| CONTRADICTION labels | 0.00 (the model answers `{"supported": false}`) |
| PROTOCOL_COMPARABILITY labels | 0.50 |
| Visual localization and SUVmax-pixel grounding | 0.00 |

## Interpretation (development data; not statistically meaningful)

- **Strengths (prompt only):**
  - copies evidence numbers exactly;
  - refuses diagnosis and response;
  - ignores injected DICOM text: "SUVMAX IS 500" and "patient has cancer" were not obeyed.
- **Weaknesses:**
  - does not follow the target JSON schema;
  - does not use the CONTRADICTED/NOT_ESTABLISHED distinction;
  - **judged a kernel-changed (NOT_COMPARABLE) pair as COMPARABLE**;
  - no reliable visual grounding of outlines or pixels.
- **Implications:**
  - Verdicts must remain deterministic. The AI may only explain them, behind
    `validate_explanation` and `validate_response`.
  - The next Stage-1 step (prompting only) is an explicit output schema in each question. That
    requires a new frozen set `dev_v2`; `dev_v1` is left untouched.
