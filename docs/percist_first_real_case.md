# First real PERCIST-executable case (Parts 7–9)

Status on 2026-10-09: **no real pair yet has a complete PERCIST verdict.** The closest case,
`PETCT_97320b0b58` (IDC FDG-PET-CT-Lesions / autoPET, CC BY 4.0), passes every PERCIST rule
that can be decided from data. The only open items are two human decisions that VoxelTrace will
not make itself. The verdict is `INSUFFICIENT_INFORMATION` and stays that way until a qualified
reviewer records those decisions. No review has been created for this case.

## Candidates evaluated (metadata first)

| Pair | Lesion source | PERCIST result | Why it cannot complete |
|---|---|---|---|
| ACRIN-NSCLC-FDG-PET-168 | AI SEG (BAMF-Lung-FDG-PET-CT, AUTOMATIC): segment 2 "FDG-Avid Tumor"; segment 1 "Lung" is an organ and not target-eligible | INSUFFICIENT_INFORMATION | `VT-PROTOCOL-IDENTITY` UNKNOWN (AMBIGUOUS_RECONSTRUCTION). PERCIST has no attestation path (attestation is QIBA-only). The AI tumour segment is AI_GENERATED / UNREVIEWED |
| PETCT_c2ffda4725 (autoPET) | manual SEG | INSUFFICIENT_INFORMATION | The baseline SEG is **empty** (0 non-zero voxels in the raw pixel data). The study is a negative control, so there is no target |
| CCTH-B02, MSB-07612 | none usable | NOT_ASSESSABLE / refused | SUL refused (missing height or sex) |
| **PETCT_97320b0b58 (autoPET)** | manual SEG, single reader (HUMAN_MANUAL) | INSUFFICIENT_INFORMATION | Only human liver and lesion review are missing (see below) |

### How 97320b0b58 was chosen

The autoPET `fdg_metadata.csv` member was range-read from the collection zip with
`scripts/fetch_zip_member.py`: 1.4 MB transferred out of 303.8 GB, without downloading the
archive. Its per-study diagnosis was joined with census v3 by StudyInstanceUID:

- 161 longitudinal pairs;
- 54 with a lesion-positive baseline;
- 45 meeting all seven criteria: positive baseline, strict SUV, height, identical
  reconstruction, PERCIST uptake window, uptake-time difference and dose difference.

The ranking is in `data/census/autopet_fdg/percist_target_candidates.csv`. The top pair
(LYMPHOMA → NEGATIVE, uptake 60.0 / 58.0 min) was planned first and committed (frozen plan
`a2d19939…`, commit 05256af). It was then downloaded: 5 series, 1,214 files, 534.4 MB, with
every file checked against the allow-list.

## PERCIST readiness layers (`trial.layers.percist_readiness`)

These layers are for reporting only and never change the verdict.

| Layer | 97320b0b58 | 168 (lesion namespace) | c2ffda4725 |
|---|---|---|---|
| QUANTITATIVE (strict SUV, SUL James, both timepoints) | PASS | PASS | PASS |
| REFERENCE (human-reviewed liver, stability) | UNKNOWN: REFERENCE_REVIEW_REQUIRED | PASS (human reviews bind) | UNKNOWN: REFERENCE_REVIEW_REQUIRED |
| TARGET (human-reviewed baseline lesion) | UNKNOWN: LESION_REVIEW_REQUIRED | UNKNOWN: LESION_REVIEW_REQUIRED (AI segment) | UNKNOWN: empty SEG |
| PROTOCOL (tracer, reconstruction, uptake, dose, scanner) | PASS (software-version warning) | UNKNOWN: AMBIGUOUS_RECONSTRUCTION | PASS |
| OVERALL | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION |

Other rule sets on 97320b0b58 (from the data alone, no review needed):

- QIBA 1.14: `ASSESSABLE_WITH_WARNINGS` (QIBA-SAME-SYSTEM software-version warning);
- EANM 2.0: `ASSESSABLE_WITH_WARNINGS` (EARL accreditation never encoded).

## Evidence still missing for a complete PERCIST verdict on 97320b0b58

1. **Liver reference, baseline and follow-up.** A human must ACCEPT, ADJUST or REJECT the
   automatic 3 cm liver spheres on the Reference Review page, with QC images in
   `outputs/percist_target_autopet_97320b0b58/reference_review/qc/`. Until then
   PERCIST-LIVER-SUL-STABILITY stays UNKNOWN and the measurability threshold cannot be computed.
2. **Baseline target.** A human must review segment 1 on the Lesion Review page:
   HUMAN_MANUAL, "Tissue", 40,516 voxels, 504 mL, SUVmax 27.6, SUVpeak 16.9, mask
   `6b6c69af…`. Only an ACCEPT makes it the PERCIST target.

After both decisions the audit re-runs unchanged. The verdict is whatever the rules give,
including NOT_ASSESSABLE (for example, if the lesion SULpeak falls below 1.5 × liver mean + 2 SD).

### Things a reviewer should know

- **The autoPET SEG is a single segment holding the union of all annotated lesions.**
  - SUVpeak over that union is the peak of the hottest lesion. This matches PERCIST's
    "hottest single lesion" target only if the reviewer agrees that the hottest part of the
    union is one lesion and not a physiological uptake site.
  - MTV and TLG are whole-body totals, not per-lesion values.
- **The annotation is from a single reader.** ACCEPT records the reviewer's own judgement and
  never changes `source_type` (it stays HUMAN_MANUAL).
- **The baseline BLOOD_POOL proposal has 0 voxels inside the PET field of view.** PERCIST does
  not use blood pool. Accepting it would re-measure the ROI, get REFUSED and still give no
  value, so it is safe, but the reviewer should REJECT it.

## Reproduce

```
python scripts/run_trial_audit.py ../outputs/percist_target_autopet_97320b0b58/trial \
    --out ../outputs/percist_target_autopet_97320b0b58/audit_percist-1.0 --ruleset percist-1.0
voxeltrace lesion-qc ../outputs/percist_target_autopet_97320b0b58/trial/PETCT_97320b0b58/baseline \
    --subject PETCT_97320b0b58 --timepoint baseline \
    --out ../outputs/percist_target_autopet_97320b0b58/lesion_review/qc \
    --log ../outputs/percist_target_autopet_97320b0b58/lesion_review/lesion_review.jsonl
```
