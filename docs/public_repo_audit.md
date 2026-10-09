# Public repository audit (2026-10-09)

Repository: https://github.com/ConfidenceRaymond/VoxelTrace (visibility **PUBLIC**, MIT
licence, default branch `main`). Scope: all 91 commits on all refs, plus the working tree.
History was neither rewritten nor deleted.

## Result: no secret found

| Check | Method | Result |
|---|---|---|
| Cloud and API keys (AWS `AKIA…`, GitHub `ghp_`/`github_pat_`/`gho_`, Hugging Face `hf_`, OpenAI/Anthropic `sk-`, Slack `xox?-`, Google `AIza…`) | regex over `git log --all -p` (2.4 MB of patches) | 0 matches |
| Private keys and certificates (`BEGIN … PRIVATE KEY`, `BEGIN CERTIFICATE`) | same | 0 |
| Literal `password=`, `secret=`, `token=`, `Bearer …` assignments | same | 0 |
| `.env` files, `*.pem`, `*.key`, `id_rsa` ever committed | `git log --all --name-only` (322 distinct paths) | none; only `.env.example`, which holds no values |
| Imaging data or model weights ever committed (`.dcm`, `.nii`, `.npz`, `.pt`, `.safetensors`, `.gguf`, archives, images, PDFs, CSVs) | same | none |
| Largest blob in history | `git cat-file --batch-check` | 34 KB (`src/voxeltrace/training/examples.py`); total pack 4.5 MB |
| `VOXELTRACE_AI_API_KEY` | code read | read from the environment as a `SecretStr`; never logged or committed |

## Personal and patient information

- **PHI:** no DICOM, image, mask or per-patient CSV is tracked. The docs name public,
  de-identified collection subjects (for example `ACRIN-NSCLC-FDG-PET-168`, `PETCT_97320b0b58`)
  together with header-derived values: weight, dose, uptake time and the collection-provided
  diagnosis category. These come from openly licensed public data. Data folders stay in
  `../data`, outside the repository.
- **Email addresses in tracked files:** one, `interop.standards@gehealthcare.com`, a public
  vendor contact in a standards note. Commit author email is the account owner's own address
  (public in commit metadata by the owner's choice).
- **Absolute local paths:** `/home/dell/voxeltrace_hackathon/...` appears in 9 tracked files
  (README, `.env.example`, `scripts/check_environment.sh` and 6 docs). This reveals a local
  username and directory layout only, so it is low severity. Optional clean-up: replace them
  with `<workspace>` in docs. Code reads `REPO_ROOT` and does not depend on these paths.
- **Wording:** the word "hackathon" occurs only as part of the fixed workspace directory name.

## Claims and derived images

- **Derived medical images:** none tracked, now or in history. QC PNGs and PDFs are written
  only to `../outputs`.
- **Product claims:** the README, docs and app were scanned for regulatory, clinical,
  performance and commercial claims (FDA/CE, "clinically validated", "guarantee", savings or
  speed percentages, ROI, customer or deployment claims).
  - The FDA mentions are factual citations of 510(k) records and decay-correction recall
    notices.
  - The commercial docs state "no regulatory clearance", "do not claim results, pricing or
    regulatory status", and make no AI pitch.
  - One stale count was corrected: the pilot one-pager said 8 real pairs; it is now 9, with
    "no expert agreement measured yet".
  - The old CITATION.cff title "Local AI for Quantitative PET Intelligence" (AI-first
    framing, a GB10 hardware keyword) was replaced with the current scope.

## Recommendations (none blocking)

1. Optionally replace absolute workspace paths in docs with `<workspace>`.
2. Keep the existing rule of never committing data. `.gitignore` already excludes `.env`,
   `.venv` and caches.
3. Repeat this scan before any release tag. The commands are in this file's table.
