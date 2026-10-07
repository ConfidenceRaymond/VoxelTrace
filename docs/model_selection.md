# Model selection (multimodal baseline)

Status 2026-10-07. Sources are the official Hugging Face model cards and API, PyPI,
download.pytorch.org and the Qwen GitHub repositories. Values were verified by querying, unless
marked *estimate*.

## Candidates

| | **Qwen3-VL-8B-Instruct** | **Qwen3-VL-30B-A3B-Instruct** |
|---|---|---|
| HF repo, revision | `Qwen/Qwen3-VL-8B-Instruct` @ `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b` | `Qwen/Qwen3-VL-30B-A3B-Instruct` @ `9c4b90e1e4ba969fd3b5378b57d966d725f1b86c` |
| Architecture | dense, `Qwen3VLForConditionalGeneration`; 36 layers, hidden 4096, 32 query heads / 8 KV heads | MoE, `Qwen3VLMoeForConditionalGeneration`; 48 layers, 128 experts, 8 active (~3 B active) |
| Parameters | 8.77 B (BF16) | 31.07 B (BF16) |
| Vision | ViT (depth 27, patch 16, spatial merge 2, DeepStack); images, multi-image and video | same encoder |
| Context | 256 K native | 256 K native |
| Weights on disk | **17.53 GB** (4 safetensors) | **62.14 GB** (13 safetensors) |
| Official FP8 | `Qwen3-VL-8B-Instruct-FP8`, 10.6 GB | `Qwen3-VL-30B-A3B-Instruct-FP8`, 32.3 GB |
| Inference memory (BF16, 32 K context) | ~25 GB *estimate* (KV 144 KiB/token) | ~70 GB *estimate* (KV 96 KiB/token) |
| Fit on GB10 (128 GB unified memory, shared with the OS) | comfortable | fits; leave headroom (`--gpu-memory-utilization` ≤ 0.75) |
| LoRA (BF16) | ~30–45 GB *estimate*: comfortable | ~80–100 GB *estimate*: tight; no ZeRO-3 for the MoE; expert-LoRA less mature |
| QLoRA | possible; bitsandbytes on aarch64/SM121 **unverified** | ~35–50 GB *estimate*; same caveat |
| License | Apache-2.0 | Apache-2.0 |
| Medical disclaimer on the card | none (VoxelTrace adds its own research-only notice) | none |

One image token covers 32×32 px. A 800×800 VoxelTrace PNG is therefore about 625 visual tokens.

## Software stack (verified versions)

- **transformers**: Qwen3-VL support was added in 4.57.0; the current release is 5.19.0.
  `qwen-vl-utils` 0.0.14. Use `attn_implementation="sdpa"`: `flash-attn` is sdist-only on
  aarch64.
- **PyTorch**: cp312 `manylinux_2_28_aarch64` wheels for CUDA 13.0 exist (torch 2.9–2.14 on the
  cu130 index; PyPI torch ≥ 2.13 already depends on cuda-toolkit 13). They install into a venv
  with **no sudo and no system CUDA changes**.
- **vLLM**: Qwen3-VL support since 0.11.0. Version 0.31.0 ships an aarch64 cu130 wheel that pins
  torch 2.13.0. Open GB10 (SM121) issues exist (MoE backend illegal memory access, FlashInfer
  crashes, FP8/NVFP4 performance), so dense BF16 is the lowest-risk path.
- **Fine-tuning tools**:
  - the official `QwenLM/Qwen3-VL/qwen-vl-finetune` (LoRA via DeepSpeed; old version pins);
  - LLaMA-Factory 0.9.5 (template `qwen3_vl`);
  - ms-swift 4.5.3;
  - PEFT 0.21.2.

## Newer official releases (noted, not selected)

- Since Qwen3.5 the main Qwen models are natively image-text-to-text, all Apache-2.0:
  - Qwen3.5 0.8B–397B (2026-02/03);
  - Qwen3.6-27B and 35B-A3B (2026-04);
  - Qwen3.8-27B (2026-08).
- Their transformers and vLLM support on aarch64 was **not verified**.
- The text-only Qwen3.6 model discussed earlier is **not** assumed to be best for multimodal
  VoxelTrace.

## Recommendation

1. **Baseline: Qwen3-VL-8B-Instruct, BF16**, served by `transformers` (simplest, lowest risk).
   vLLM 0.31 is optional, for throughput.
2. **Later candidate: Qwen3-VL-30B-A3B** (or Qwen3.5/3.6 successors), evaluated with the
   same harness, only after the 8B baseline is measured.
3. Every model is evaluated **before and after** any fine-tuning with
   `voxeltrace.evaluation`, on a LOCKED_TEST split that does not exist yet (see
   training_dataset_plan.md).
