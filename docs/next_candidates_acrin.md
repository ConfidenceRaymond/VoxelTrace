# Next real longitudinal candidate: ACRIN-NSCLC-FDG-PET (metadata only, 2026-10-08)

RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. Nothing was downloaded. No rule, threshold,
validator or verdict was changed.

| Item | Location |
|---|---|
| Script | `scripts/rank_next_candidates.py` |
| Output | `../data/census/acrin_nsclc_fdg_pet_v2/next_candidates.{csv,json}` |

## Method

- **Input:** census v2 on disk, i.e. 12 sampled slice headers per AC PET series with protocol
  evidence and CT frame-of-reference matches, plus the v1 series index for SEG series.
- **Pairs:** census v2 paired only the first two study dates. Here **every** ordered pair of AC
  PET series with different study dates is evaluated: 407 pairs over 178 subjects.
- **Exclusions:** the five subjects already downloaded (050, 094, 153, 167, 168).
- **Rules:** the unchanged rule code (`assess_pair`, `compare_protocols`) runs per pair for QIBA
  1.14, EANM 2.0 and PERCIST 1.0.
- **DECIDABLE:** no blocking check is UNKNOWN.
- **Outcome classes:**
  - DECIDABLE_ASSESSABLE: decidable, with no blocking FAIL;
  - DECIDABLE_NOT_ASSESSABLE: decidable, with a blocking FAIL;
  - NOT_DECIDABLE: at least one blocking UNKNOWN.
- **Ranking (per subject, best pairing):**
  1. strict SUV predicted PASS at both timepoints;
  2. fewest blocking UNKNOWNs (QIBA ∪ EANM);
  3. fewest blocking FAILs;
  4. decay factor verified on the samples;
  5. reconstruction description present;
  6. height present;
  7. CT in the PET frame of reference;
  8. download size.

## Part A: fully decidable QIBA/EANM candidate

**Result: none. 0 of 407 pairs is DECIDABLE under QIBA or EANM, and none could become
ASSESSABLE.**

Only 31 pairs pass strict SUV at both timepoints, all of them Siemens/CTI. In all 31:

| Gap | Pairs | Notes |
|---|---|---|
| VT-TRACER-SAME UNKNOWN | **31 / 31** | Radiopharmaceutical name and code are absent |
| VT-PROTOCOL-IDENTITY UNKNOWN | 21 | |
| VT-PROTOCOL-IDENTITY FAIL | 10 | |
| EANM-SAME-SYSTEM-SETTINGS UNKNOWN | 21 | |
| QIBA/EANM uptake-window FAIL | 28 | |
| QIBA uptake-difference FAIL | 22 | |
| Pairs with **no** blocking FAIL | **0** | |

**The tracer gap is real, not a sampling artefact.** The fully downloaded Siemens/CTI pair 050
has a RadiopharmaceuticalInformationSequence with neither Radiopharmaceutical nor
RadiopharmaceuticalCodeSequence at either timepoint (checked on the local files).

**Structural blockers by vendor:**

| Vendor | Blocker |
|---|---|
| GE (310 series) | Strict SUV refuses 98 % (DECAY_FACTOR_INCONSISTENT, UNSUPPORTED_UNITS, IMPLAUSIBLE_RADIONUCLIDETOTALDOSE). The only SUV-eligible GE series are 167 and 168 (already downloaded) plus one unpaired series (213). |
| Siemens/CTI (185) | No tracer identity (VT-TRACER-SAME UNKNOWN on every SUV-eligible pair), no height (SUL impossible), and frequent uptake-window failures. |
| Philips (93) | Non-BQML / DecayCorrection NONE. Strict SUV refused. |

**Conclusion:** with the current (correct) rules, no remaining ACRIN-NSCLC-FDG-PET pair can
yield DECIDABLE_QIBA_EANM. The probability is 0 for every candidate, so the ranking below
orders by closeness only.

## Reconstruction evidence completeness (all 588 AC PET series)

| Vendor | Series | Recon description | Iterations | Subsets | Kernel/filter | TOF | PSF |
|---|---|---|---|---|---|---|---|
| Siemens/CTI | 185 | 185 | 185 | 185 | 103 | 0 | 8 |
| GE | 310 | 257 | 0 | 0 | 4 | 0 | 0 |
| Philips | 93 | 93 | 0 | 0 | 0 | 0 | 0 |

- GE iterations and subsets are never encoded.
- No vendor encodes TOF.
- 168's software 16.01 series lack even the description.

## Part C: top 10 scorecard (best pairing per subject; predictions from sampled headers)

| # | Subject | Scanner | Software | Tracer | Uptake B/F (min) | Δ | Height | SUV | Decay check | CT FoR | Recon | Iter | Subsets | Kernel | TOF | PSF | SEG B / F | MB | QIBA | EANM | PERCIST readiness | Main blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 172 | CPS 1080 / SIEMENS 1080 | PS4.1 / PET/CT 2007C | None / None | 71.0 / 65.7 | 5.4 | False / False | PASS / PASS | VERIFIED_SAMPLED / VERIFIED_SAMPLED | True / True | OSEM2D 2i8s / OSEM2D 2i8s | 2 / 2 | 8 / 8 | X-Y-Z Gaussian F / XYZ G5.00 | None / None | None / None | none / AI_UNREVIEWED | 414.7 | NOT_ASSESSABLE | NOT_ASSESSABLE | PERCIST_BLOCKED_BY_SUL | VT-TRACER-SAME |
| 2 | 210 | CPS 1080 / SIEMENS 1080 | PS4.0.3 / PET/CT 2007C | None / None | 76.6 / 68.9 | 7.8 | False / False | PASS / PASS | VERIFIED_SAMPLED / VERIFIED_SAMPLED | True / True | OSEM2D 2i8s / OSEM2D 4i8s | 2 / 4 | 8 / 8 | X-Y-Z Gaussian F / XYZ G5.00 | None / None | None / None | AI_UNREVIEWED / AI_UNREVIEWED | 447.9 | NOT_ASSESSABLE | NOT_ASSESSABLE | PERCIST_BLOCKED_BY_SUL | VT-TRACER-SAME |
| 3 | 102 | SIEMENS 1094 / SIEMENS 1094 | PET/CT 2007B / PET/CT 2008A | None / None | 91.5 / 88.3 | 3.1 | False / False | PASS / PASS | VERIFIED_SAMPLED / VERIFIED_SAMPLED | True / True | OSEM2D 4i8s / OSEM2D 4i8s | 4 / 4 | 8 / 8 | XYZ G5.00 / XYZ Gauss5.00 | None / None | None / None | AI_UNREVIEWED / AI_UNREVIEWED | 466.6 | NOT_ASSESSABLE | NOT_ASSESSABLE | PERCIST_BLOCKED_BY_SUL | VT-TRACER-SAME |
| 4 | 149 | SIEMENS 1094 / SIEMENS 1094 | PET/CT 2007B / PET/CT 2008A | None / None | 84.3 / 87.8 | 3.4 | False / False | PASS / PASS | VERIFIED_SAMPLED / VERIFIED_SAMPLED | True / True | OSEM2D 4i8s / OSEM2D 4i8s | 4 / 4 | 8 / 8 | XYZ G5.00 / XYZ Gauss5.00 | None / None | None / None | none / AI_UNREVIEWED | 466.7 | NOT_ASSESSABLE | NOT_ASSESSABLE | PERCIST_BLOCKED_BY_SUL | VT-TRACER-SAME |
| 5 | 103 | SIEMENS 1094 / SIEMENS 1094 | PET/CT 2007B / PET/CT 2008A | None / None | 84.0 / 84.8 | 0.8 | False / False | PASS / PASS | VERIFIED_SAMPLED / VERIFIED_SAMPLED | True / True | OSEM2D 4i8s / OSEM2D 4i8s | 4 / 4 | 8 / 8 | XYZ G5.00 / XYZ Gauss5.00 | None / None | None / None | AI_UNREVIEWED / AI_UNREVIEWED | 509.4 | NOT_ASSESSABLE | NOT_ASSESSABLE | PERCIST_BLOCKED_BY_SUL | VT-TRACER-SAME |
| 6 | 197 | CPS 1080 / SIEMENS 1094 | PS4.1 / PET/CT 2008A | None / None | 93.2 / 43.0 | 50.2 | False / False | PASS / PASS | VERIFIED_SAMPLED / VERIFIED_SAMPLED | True / True | OSEM2D 2i8s / OSEM2D 2i8s | 2 / 2 | 8 / 8 | X-Y-Z Gaussian F / XYZ Gauss5.00 | None / None | None / None | AI_UNREVIEWED / none | 414.7 | NOT_ASSESSABLE | NOT_ASSESSABLE | PERCIST_BLOCKED_BY_SUL | VT-TRACER-SAME |
| 7 | 187 | CPS 1080 / SIEMENS 1094 | PS4.0.3 / PET/CT 2008A | None / None | 83.8 / 46.3 | 37.5 | False / False | PASS / PASS | VERIFIED_SAMPLED / VERIFIED_SAMPLED | True / True | OSEM2D 2i8s / PSF 3i21s | 2 / 3 | 8 / 21 | X-Y-Z Gaussian F / XYZ Gauss4.00 | None / None | None / True | AI_UNREVIEWED / AI_UNREVIEWED | 419.6 | NOT_ASSESSABLE | NOT_ASSESSABLE | PERCIST_BLOCKED_BY_SUL | VT-TRACER-SAME |
| 8 | 077 | CPS 1080 / SIEMENS 1094 | PS4.0.3 / PET/CT 2007B | None / None | 76.9 / 47.1 | 29.8 | False / False | PASS / PASS | VERIFIED_SAMPLED / VERIFIED_SAMPLED | True / True | OSEM2D 2i8s / OSEM2D 2i8s | 2 / 2 | 8 / 8 | X-Y-Z Gaussian F / XYZ G5.00 | None / None | None / None | AI_UNREVIEWED / AI_UNREVIEWED | 447.2 | NOT_ASSESSABLE | NOT_ASSESSABLE | PERCIST_BLOCKED_BY_SUL | VT-TRACER-SAME |
| 9 | 120 | SIEMENS 1094 / SIEMENS 1094 | PET/CT 2007B / PET/CT 2007B | None / None | 93.0 / 89.6 | 3.5 | False / False | PASS / PASS | VERIFIED_SAMPLED / VERIFIED_SAMPLED | True / True | OSEM2D 4i8s / OSEM2D 4i8s | 4 / 4 | 8 / 8 | XYZ G5.00 / XYZ G5.00 | None / None | None / None | AI_UNREVIEWED / AI_UNREVIEWED | 394.4 | NOT_ASSESSABLE | NOT_ASSESSABLE | PERCIST_BLOCKED_BY_SUL | EANM-SAME-SYSTEM-SETTINGS |
| 10 | 241 | SIEMENS 1080 / SIEMENS 1080 | PET/CT 2007C / PET/CT 2007C | None / None | 67.2 / 55.0 | 12.2 | False / False | PASS / PASS | VERIFIED_SAMPLED / VERIFIED_SAMPLED | True / True | OSEM2D 4i8s / OSEM2D 4i8s | 4 / 4 | 8 / 8 | XYZ G5.00 / XYZ G5.00 | None / None | None / None | AI_UNREVIEWED / AI_UNREVIEWED;NON_EXPERT_CORRECTED;RADIOLOGIST_CORRECTED | 405.0 | NOT_ASSESSABLE | NOT_ASSESSABLE | PERCIST_BLOCKED_BY_SUL | EANM-SAME-SYSTEM-SETTINGS |

Blocking checks per candidate:

- 172 UNKNOWN: VT-TRACER-SAME | FAIL: EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY | identity: FAIL
- 210 UNKNOWN: VT-TRACER-SAME | FAIL: EANM-SAME-SYSTEM-SETTINGS;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-WINDOW;VT-PROTOCOL-IDENTITY | identity: FAIL
- 102 UNKNOWN: VT-TRACER-SAME | FAIL: EANM-SAME-SYSTEM-SETTINGS;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-WINDOW;VT-PROTOCOL-IDENTITY | identity: FAIL
- 149 UNKNOWN: VT-TRACER-SAME | FAIL: EANM-SAME-SYSTEM-SETTINGS;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-WINDOW;VT-PROTOCOL-IDENTITY | identity: FAIL
- 103 UNKNOWN: VT-TRACER-SAME | FAIL: EANM-SAME-SYSTEM-SETTINGS;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-WINDOW;VT-PROTOCOL-IDENTITY | identity: FAIL
- 197 UNKNOWN: VT-TRACER-SAME | FAIL: EANM-SAME-SYSTEM-SETTINGS;EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-PROTOCOL-IDENTITY | identity: FAIL
- 187 UNKNOWN: VT-TRACER-SAME | FAIL: EANM-SAME-SYSTEM-SETTINGS;EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-PROTOCOL-IDENTITY | identity: FAIL
- 077 UNKNOWN: VT-TRACER-SAME | FAIL: EANM-SAME-SYSTEM-SETTINGS;EANM-UPTAKE-DIFF;EANM-UPTAKE-WINDOW;QIBA-UPTAKE-DIFF;QIBA-UPTAKE-WINDOW;VT-PROTOCOL-IDENTITY | identity: FAIL
- 120 UNKNOWN: EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY;VT-TRACER-SAME | FAIL: EANM-UPTAKE-WINDOW;QIBA-UPTAKE-WINDOW | identity: UNKNOWN
- 241 UNKNOWN: EANM-SAME-SYSTEM-SETTINGS;VT-PROTOCOL-IDENTITY;VT-TRACER-SAME | FAIL: EANM-UPTAKE-DIFF;QIBA-UPTAKE-DIFF | identity: UNKNOWN

**Reading the table:**
- **Why VT-PROTOCOL-IDENTITY FAILs** (e.g. 172):
  - the manufacturer text changes from `CPS` to `SIEMENS` on the same 1080 model after a
    software upgrade;
  - the kernel text changes from `X-Y-Z Gaussian F` to `XYZ G5.00`.

  Both differ under the exact-match rule. The rule is not loosened: a site record would be
  needed to show these are the same settings.
- **Voxel size UNKNOWN** comes from the 12-slice sampling (no full slice stack). It would
  resolve on download. The tracer gap would not.
- **Download size** is PET plus the smallest matching CT, both timepoints.
- **Decay check `VERIFIED_SAMPLED`** means DecayFactor ↔ FrameReferenceTime was checked on the
  12 sampled slices only.

**Best QIBA/EANM candidate (closest, not decidable): ACRIN-NSCLC-FDG-PET-172.**
- CPS/Siemens 1080, OSEM2D 2i8s at both timepoints;
- uptake 71.0 / 65.7 min (Δ 5.4), within the QIBA/EANM windows;
- predicted QIBA and EANM verdict: **NOT_ASSESSABLE** (protocol identity / system settings FAIL
  on manufacturer and kernel text), with the tracer still UNKNOWN;
- about 415 MB.

Downloading it would not produce a decidable verdict.

## Part B: PERCIST-capable candidate

**Best-subject classification** (178 subjects): PERCIST_BLOCKED_BY_SUL 24, UNKNOWN (strict SUV
refused) 154. **No remaining subject is PERCIST_READY or
PERCIST_LIVER_READY_BUT_LESION_MISSING.**

**Lesion sources in IDC** (all QIICR "AIMI lung and FDG tumor" DICOM SEG):

| Type | Series | Status |
|---|---|---|
| AI segmentation | 367 | **unreviewed: never ground truth** |
| Non-expert-corrected | 11 | |
| Radiologist-corrected | 7 | |

Radiologist-corrected subjects:

| Subject | Problem |
|---|---|
| 037 (baseline) | GE Discovery ST; strict SUV refuses (DECAY_FACTOR_INCONSISTENT); uptake 93/97 min |
| 054 (baseline) | CPS 1024; SUV refused; no CT in the PET frame; no height |
| 083 | GE Discovery LS; SUV refused (IMPLAUSIBLE_RADIONUCLIDETOTALDOSE / units) |
| 134 (follow-up) | GE; SUV refused; scanner changes STE → RX |
| 131, 192, 241 (follow-up only) | Siemens; SUV PASS, but no height → PERCIST_BLOCKED_BY_SUL; not at baseline |

**Already-downloaded pairs (outside the ranking, for completeness):**

| Pair | Status | Lesion source | Classification |
|---|---|---|---|
| **168** | SUV/SUL/uptake/liver all PASS; reconstruction NOT_ESTABLISHED | baseline AIMI **AI** SEG (0.23 MB), unreviewed | **PERCIST_BLOCKED_BY_RECON** (lesion also missing) |
| 167 | SUV/SUL PASS, height, CT FoR | baseline **non-expert-corrected** SEG (1.64 MB) | PERCIST NOT_ASSESSABLE on uptake (56.5 / 84.2 min; Δ 27.7 > 15), and recon identity UNKNOWN |

**Best PERCIST candidate: ACRIN-NSCLC-FDG-PET-168 (already local).**
- It is the only real pair where everything except reconstruction identity and a baseline
  lesion target is resolved.
- A lesion target needs a human-reviewed mask. The baseline AI SEG may serve only as a
  **proposal** under a lesion review gate, built on the same principles as the reference
  review gate, which does not exist yet.
- Even with a reviewed lesion, PERCIST stays INSUFFICIENT_INFORMATION until reconstruction
  identity is established.

## Recommendation

- No further ACRIN subject download is justified for QIBA/EANM decidability.
- A decidable QIBA/EANM case needs a collection with coded tracer identity, BQML/START and a
  verifiable decay model, height, and encoded reconstruction parameters. That is a census of
  other IDC collections (the roadmap's next multi-tracer PET/CT step), not more ACRIN subjects.
- The single highest-value next download is the **168 baseline AIMI AI SEG (≈0.23 MB, 1
  instance)**, to drive a human lesion-review workflow on the best PERCIST pair. Its
  prerequisites are listed in the final report. This task does not download it.
