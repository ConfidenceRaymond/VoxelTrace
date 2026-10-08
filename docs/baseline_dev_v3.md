# dev_v3 baseline: Qwen3-VL-8B-Instruct (no fine-tuning), scored with `vt-eval-2`

## Setup (identical to dev_v1 and dev_v2)

- **Model:** `Qwen/Qwen3-VL-8B-Instruct` @ `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`.
  - All four weight shards were re-verified by SHA-256 against the model manifest before the
    run.
- **Runtime:** torch 2.14.1+cu130 on an NVIDIA GB10, BF16 with SDPA. The runner script is
  unchanged (`scripts/run_baseline_vlm.py`).
- **Decoding:** greedy (`do_sample=False`, so no temperature or seed is involved), at most 384
  new tokens.
- **Images and prompts:** the same pre-rendered images (referenced, hash-verified at build time)
  and the same message construction and system prompt as dev_v2.
- **Dataset:** frozen dev_v3 `f705bf65…`, all 234 examples. dev_v1, dev_v2 and dev_v3 hashes
  are unchanged after the run.
- **Outputs:** `../outputs/baseline_qwen3vl8b_dev_v3/`:
  - `responses.jsonl`, `run_metadata.json`;
  - `evaluation_v3.json`, `comparison.json`;
  - `changes_v2_v3.csv`, `changes_v1_v2_v3.csv`;
  - `safety_adjudication.json`.
- **Scoring:** `scripts/score_dev_v3.py`. Correctness is `dev_v2.score_v2`, which is
  values-only for value tasks. Safety is `vt-eval-2`.

## dev_v3 overall (234 examples)

| Metric | Result |
|---|---|
| Structured-output compliance (strict schema) | 0.991 (2 responses truncated at 384 tokens) |
| Claim-label accuracy (n = 163) | 0.767 |
| SUPPORTED (n = 51) | **1.00** |
| NOT_ESTABLISHED (n = 27) | 0.926 |
| CONTRADICTED recall (n = 73) | 0.671 |
| PARTIALLY_SUPPORTED (n = 12) | **0.00**: always answered SUPPORTED |
| Pair-verdict fidelity (n = 18) | 0.833; blocking differences 0.889 |
| Kernel-changed pairs | 3/3 NOT_COMPARABLE (correct) |
| Numeric exactness (32 values) | exact 1.00, 0 omitted |
| Invented numbers (`vt-eval-2`) | **0**; 2 injected numbers quoted as disregarded; 20 geometry numbers excluded |
| Metadata accuracy | 0.955 |
| Refusal accuracy | 0.944 |
| Evidence-id validity | 0.988 |
| Prompt injection | 23/24 adversarial correct; **0 obeyed** |
| Safety (`vt-eval-2`) | 1 raw flag; manually adjudicated a false positive ("No … data supports a diagnosis of malignancy."); **0 true violations** |
| Visual grounding: presence | 1.00 |
| Visual grounding: mean bbox IoU | **0.005**; IoU ≥ 0.5 in 0 % |
| Visual grounding: SUVmax pixel | 0/2 answered |

## dev_v3 additions, by variant

| Variant (expected label) | Accuracy | Predicted labels |
|---|---|---|
| value exact (SUPPORTED, n = 12) | 1.00 | |
| value × 0.5 (CONTRADICTED, n = 12) | 0.50 | 4 NOT_ESTABLISHED, 1 PARTIALLY_SUPPORTED, 1 SUPPORTED |
| value × 2 (CONTRADICTED, n = 12) | 0.67 | 4 NOT_ESTABLISHED |
| protocol affirmative (SUPPORTED, n = 9) | 1.00 | |
| protocol affirmative (PARTIALLY_SUPPORTED, n = 6) | 0.00 | all SUPPORTED |
| protocol natural negation (CONTRADICTED, n = 15) | 0.53 | 7 SUPPORTED |

## dev_v2 → dev_v3 (the 104 examples run in both; same strict scorer)

**IMPROVED 6, REGRESSED 2, UNCHANGED_CORRECT 81, UNCHANGED_WRONG 15.**

- **Improvements and regressions:** all 8 changes are "NOT:" phrasings rewritten as natural
  negations. Across the 15 rewritten items, correct answers went from 7 to 11.
  - Improved: time-of-flight (3 subjects), attenuation correction (2 subjects) and scatter
    correction (1 subject).
  - Regressed: "Reconstruction did not use PSF / resolution modelling" (2 subjects). The
    explanation states that PSF was used, but the label is SUPPORTED.
- **Metrics:** claim accuracy rose from 0.824 to 0.882, and CONTRADICTED recall from 0.688 to
  0.813 (n = 32). Every other metric is identical.
- **Safety:** `vt-eval-2` finds 0 violations on both versions. The dev_v2 numbers here are
  re-scored for comparison only; official dev_v2 numbers stay `vt-eval-1`.
- **UNCHANGED_WRONG (15):**
  - 6 visual items (4 localisation, 2 SUVmax pixel);
  - 3 protocol readings;
  - 2 halved-MTV contradictions answered NOT_ESTABLISHED;
  - 2 scatter natural negations (2 subjects);
  - 1 adversarial and 1 refusal item, both truncated at 384 tokens.

## dev_v1 → dev_v2 → dev_v3 (the 70 examples run in all three; same semantic definition)

| Metric (semantic) | n | dev_v1 | dev_v2 | dev_v3 |
|---|---|---|---|---|
| claim accuracy | 16 | 0.750 | 0.875 | 0.875 |
| CONTRADICTED recall | 7 | 0.000 | 0.714 | 0.714 |
| numeric exactness (incl. SUVpeak definition text) | 10 | 0.80 | 0.80 | 0.80 |
| pair-verdict fidelity | 6 | 0.50 | 1.00 | 1.00 |
| prompt-injection cases | 24 | 0.625 | 1.00 | 1.00 |
| visual grounding | 8 | 0.00 | 0.25 | 0.25 |
| metadata / protocol reading | 12 | 0.75 | 1.00 | 1.00 |
| all | 70 | 0.586 | 0.857 | 0.857 |

| Change | dev_v1 → dev_v2 | dev_v2 → dev_v3 | dev_v1 → dev_v3 |
|---|---|---|---|
| IMPROVED | 19 | 0 | 19 |
| REGRESSED | 0 | 0 | 0 |
| UNCHANGED_CORRECT | 41 | 60 | 41 |
| UNCHANGED_WRONG | 10 | 10 | 10 |

The two SUVpeak items are wrong under the semantic rule in all three versions. That rule also
requires the definition text, which dev_v3 deliberately stopped asking for. Their values are
exactly right in dev_v3 (strict-correct).

## Findings that the dev_v2 subset did not show

1. **The deterministic verdict was overridden in 3/3 "scanner model missing" pairs.** The
   expected verdict is INSUFFICIENT_INFORMATION, supplied as authoritative evidence. The
   model answered NOT_COMPARABLE (2) and COMPARABLE_WITH_WARNINGS (1). These pairs were not in
   the dev_v2 run subset. This is exactly why AI text must pass `validate_explanation`, which
   rejects any verdict that differs from the deterministic one.
2. **PARTIALLY_SUPPORTED is never used** (0/12). Free-text-derived facts are labelled
   SUPPORTED.
3. **Label semantics for wrong values:** in 8 of 24 halved or doubled claims, the explanation
   gives the correct measured value but the label is NOT_ESTABLISHED instead of CONTRADICTED.
4. **Negation remains fragile:** the PSF negation regressed, and the scatter negation is wrong
   for 2 of 3 subjects.
5. **Visual grounding is unchanged and capability-limited:** bbox IoU is 0.005.
6. **Hallucination:** no invented PET values, and no injection obeyed.

## Interpretation

- **Where prompting helps:** clearer phrasing improved negated claims on balance (7 → 11 of 15).
  Nothing regressed on the 70 three-way-paired items.
- **Remaining errors are label-semantics and authority-following failures:**
  - PARTIALLY_SUPPORTED is never chosen;
  - NOT_ESTABLISHED is given for measured mismatches;
  - verdicts are overridden when information is missing.
- **Visual errors are capability failures.**
- **Implications:** the deterministic verdict and claim gates must stay authoritative, and
  model output must stay behind the validation gates. Nothing here justifies letting the
  model approve reference regions or produce verdicts.
- **Caveat:** these are development-only results on 3 subjects. They are not statistically
  conclusive.

Verdict: **PROMPTING_HELPS_SELECTIVELY_MODEL_LIMITATIONS_REMAIN**
