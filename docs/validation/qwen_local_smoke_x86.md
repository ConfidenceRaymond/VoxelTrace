# Qwen3-VL local explanatory smoke test (x86_64, RTX 5090, 2026-10-09)

Scope: one product-relevant explanation, no evaluation set (no dev_v4), no image, no decision.
Script: `scripts/qwen_explain_smoke.py` (optional VLM venv only). Results:
`outputs/qwen_smoke_x86_20261009/` (`qwen_smoke_run1_FLAGGED.json`, `qwen_smoke.json`).

| Item | Result |
|---|---|
| Model | Qwen3-VL-8B-Instruct, local directory, revision 0c351dd (manifest-verified), BF16 |
| Local only | `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `local_files_only=True`; no network access attempted |
| Runtime | load 2.6 s (warm page cache), generate ≈ 2.0 s for ≈ 106 tokens |
| VRAM | peak allocated 16.6 GiB (torch); 19.4 GiB device total incl. desktop (nvidia-smi) |
| Input | VoxelTrace's evidence trace for PETCT_97320b0b58 (verdicts, open rules, reasons, plain-language text), computed deterministically |
| Deterministic values supplied by VoxelTrace | yes; the model's reply contained **no number absent from the evidence** (both runs) |

**Run 1 — FLAGGED, and wrong in substance.** The model called the warning-level software
difference (VG60A → VG70A) "non-negotiable failures". Root cause found in VoxelTrace's own
trace: a warning-impact check without a reason code was labelled `<RULE> FAIL` with the wording
of a decided blocking failure, and the rule impact was not given to the model. Fixed in the
trace (`<RULE> WARNING`, warning wording, impact column) with a regression test.

**Run 2 — FLAGGED by the conservative keyword check only** (the reply says "No diagnosis or
treatment is implied"). Content: warnings correctly described as warnings, pending liver and
lesion review correctly stated; but it opens with "This pair is assessable", which glosses
over PERCIST being INSUFFICIENT_INFORMATION.

**Conclusion.** The local model can produce useful explanatory prose from VoxelTrace evidence,
but even with complete deterministic evidence it can mis-summarise a verdict. It stays
**explanatory only**, labelled MODEL_GENERATED, never written into an evidence bundle or a
delivery package, and never used for any verdict, measurement, review or adjudication
(`docs/ai_policy.md`, `tests/test_ai_freeze.py`).

## Re-run 2026-10-10 (boundary audit)

Evidence: the dry run's `pair_evidence_trace.csv`, Subject007 (source CCTH-B02). Offline flags
set, local directory, revision `0c351dd`. Load 2.4 s, generation 2.0 s for 113 tokens, peak
16.6 GiB allocated. Result `outputs/qwen_smoke_x86_20261010/qwen_smoke.json`.

- **Invented numbers:** none. **Verdicts not in the evidence:** none.
- **Verdict-language drift:** yes. The reply attributes PERCIST INSUFFICIENT_INFORMATION partly
  to "a software warning", which is not a cause of that verdict, and says baseline SUVpeak should
  be "recorded in DICOM", which is wrong: it comes from a reviewed lesion segmentation. Flagged
  by the conservative keyword check (a negated "diagnosis").
- QIBA (ASSESSABLE, no open rule) was not in the evidence given, so the reply did not mention it.

Conclusion unchanged and reinforced: the model may only produce labelled, optional explanatory
prose; it is never shipped in a delivery, never used for a verdict, measurement, review or
adjudication, and tests enforce that the audit path cannot load it (`tests/test_ai_freeze.py`).
No dev_v4: the failure mode (cause mis-attribution) is already the reason the model is
explanation-only, and no product feature depends on it.
