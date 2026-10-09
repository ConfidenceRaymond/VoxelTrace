# AI architecture freeze (2026-10-09)

**Qwen3-VL (and any model) is EXPLANATORY ONLY.**

| Allowed | Not allowed (deterministic code or a named human only) |
|---|---|
| plain-language explanation of evidence already computed | SUV and SUL calculation |
| summaries of a bundle's evidence | hotspot localisation, lesion segmentation |
| draft wording of site queries (the deterministic reason code, evidence and request stay visible and unchanged) | reference-region review (human gate only) |
| | pair verdicts, protocol comparability, claim state |
| | attestation creation or validation |
| | adjudication or human override |
| | diagnosis or treatment response |

**Enforcement** (`tests/test_ai_freeze.py`):
- The audit-path packages (`quant`, `rules`, `trial`, `evidence`, `preflight`, `census`,
  `ingest`, `vendors`, `pilot`, `bundle`, `cli`, `expert_validation`, `versions`) must not
  import `voxeltrace.ai`, `voxeltrace.training`, `voxeltrace.evaluation`, `torch`,
  `transformers` or `httpx`.
- Every bundle manifest states `ai_components: none`.
- Adjudication records must come from a human channel (`HUMAN_CLI` / `HUMAN_UI`); records
  claiming an automated origin are rejected.

**Status:**
- No fine-tuning.
- No new evaluation set (dev_v4) unless a new product-relevant AI failure appears.
- The frozen evaluation assets (dev_v1/v2/v3, evaluator_v2) are unchanged.
