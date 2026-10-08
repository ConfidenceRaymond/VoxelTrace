# Quantitative PET census v2 (ACRIN-NSCLC-FDG-PET) and why one-header screening is insufficient

Code: `src/voxeltrace/census/sampled.py`, `scripts/census_v2_acrin.py`.
Data: `../data/census/acrin_nsclc_fdg_pet_v2/`. v1 files are untouched.
Metadata only; no image volumes were downloaded.

## Why one header per series is not enough (product finding)

Census v1 read **one** instance header per PET series and applied hand-written heuristics. The
two real ACRIN pairs downloaded afterwards showed what that misses.

- **094 (GE Discovery LS):** every series-level attribute looked complete:
  - BQML, START, ATTN/DECY, dose, injection time, weight, height, tracer, reconstruction text;
  - CT in the same study.

  Strict SUV still refused all slices with `DECAY_FACTOR_INCONSISTENT`. The defect is
  **slice/bed-level**: DecayFactor and FrameReferenceTime disagree on every bed (see
  [vendor_decay_timing.md](vendor_decay_timing.md)). A single header shows one consistent-looking
  value, and only several beds expose the relation.
- **153 (CPS 1023):**
  - v1 saw "PET + CT in the study". In fact **no CT series shares the PET
    FrameOfReferenceUID**, so reference regions are impossible.
  - v1 did not check the tracer code (absent → VT-TRACER-SAME UNKNOWN) or the timing.
  - FrameReferenceTime is 0 on every slice while DecayFactor varies per bed, a contradiction
    visible only across beds.
  - Height is missing (v1 got this right).

**Lesson:** quantitative eligibility is a property of the *whole slice stack and its relations*
(DecayFactor vs FrameReferenceTime vs AcquisitionTime per bed, CT ↔ PET frame of reference). It
is not a property of the series header. A screen must:

- sample several slices across beds;
- run the **same validator** that will make the decision;
- check cross-series relations.

## Census v2 method

- **PET:** for each of the 588 AC-primary PET series, the full object listing, then **12
  slice headers** chosen deterministically (evenly spaced over the sorted object keys), each read
  by HTTP byte range (≤ 64 KB). Raw bytes are never stored.
- **Evaluation:** VoxelTrace's own code, unchanged, runs on the sampled headers:
  - the strict SUVbw validator (`validate_suv_eligibility`), including the DecayFactor check;
  - the protocol extractors;
  - the QIBA, EANM and PERCIST pair rules (`assess_pair`).

  `sampled_header_audit` mirrors `audit_pet_headers`. A test, and the four real series, show
  the two audits are identical.
- **CT:** one header per CT series (462) in those studies, giving FrameOfReferenceUID and
  ImageType.
- **Pairs:** per patient, the best AC PET series of the first two study dates.
- **Limitations:**
  - only sampled slices are checked;
  - object-key order is not slice order. Sampling can miss the first bed, and then a different
    refusal code can appear (153 follow-up: `SCAN_REFERENCE_AMBIGUOUS` instead of
    `DECAY_FACTOR_INCONSISTENT`, same outcome).
  - **DECAY_FACTOR_UNVERIFIED:** series without DecayFactor/FrameReferenceTime on every slice
    pass with this warning (existing validator behaviour). Their pass is weaker evidence.

## Validation against the downloaded cases (v1 / v2 / actual)

| Item | 094 baseline | 094 follow-up | 153 baseline | 153 follow-up |
|---|---|---|---|---|
| Strict SUV | v1 LIKELY_ANALYZABLE ✗ / v2 REFUSED DF ✓ / actual REFUSED DF | v1 ✗ / v2 ✓ / REFUSED DF | v1 WITH_WARNINGS ✗ / v2 REFUSED DF ✓ / REFUSED DF | v1 ✗ / v2 REFUSED (SCAN_REFERENCE_AMBIGUOUS) ✓ outcome / REFUSED DF |
| Height | ✓ / ✓ / yes | ✓ / ✓ / yes | ✓ / ✓ / no | ✓ / ✓ / no |
| CT in PET frame | v1 not checked / v2 yes ✓ / yes | – / ✓ / yes | – / v2 no ✓ / no | – / ✓ / no |
| Tracer code | not checked / PRESENT ✓ | – / ✓ | – / MISSING ✓ | – / MISSING ✓ |
| FRT=0 with DecayFactor ≠ 1 | – / no ✓ | – / no ✓ | – / yes ✓ | – / yes ✓ |

v2 predicts every outcome correctly. v1 was wrong on SUV for all four.

## Collection-level results (588 AC PET series; predictions, not proof)

| Measure | Rate |
|---|---|
| Strict SUV predicted to pass | **13.8 %** (81) |
| DecayFactor consistent (not `DECAY_FACTOR_INCONSISTENT`) | 42.0 %; 21.9 % unverified (tags absent) |
| FRT = 0 with DecayFactor ≠ 1 | 110 series |
| Patient height present | 52.7 % |
| CT shares PET FrameOfReferenceUID | 61.6 % |
| Tracer code present | 58.7 % |
| Reconstruction iterations known | 31.5 % |

Refusals: `DECAY_FACTOR_INCONSISTENT` 341, `UNSUPPORTED_UNITS` 168,
`UNSUPPORTED_DECAY_CORRECTION` 86, `IMPLAUSIBLE_RADIONUCLIDETOTALDOSE` 45,
`SCAN_REFERENCE_AMBIGUOUS` 24, weight missing or non-positive 31, other 11.

By vendor (SUV-eligible / series):

| Vendor | SUV-eligible | Height | CT same frame | Tracer |
|---|---|---|---|---|
| GE | **5 / 310** (all Discovery LS with DECAY_FACTOR_UNVERIFIED) | 310 | 250 | 309 |
| Siemens/CTI | 76 / 185 | **0** | 104 | 3 |
| Philips | 0 / 93 (non-BQML) | 0 | 8 | 33 |

## Re-ranked pairs (167)

| Category | Pairs |
|---|---|
| HIGH_CONFIDENCE_ANALYZABLE | 1 (GE) |
| ANALYZABLE_WITH_WARNINGS | 24 (all Siemens/CTI: no height, tracer code missing) |
| LIKELY_INSUFFICIENT | 142 (**85 %**) |

- **QIBA prediction for decidable pairs:** NOT_ASSESSABLE (uptake window or difference, or
  protocol identity). No pair is predicted ASSESSABLE under QIBA.
- **PERCIST:** stays INSUFFICIENT_INFORMATION until reference regions are reviewed, and is
  impossible without height (SUL) for all Siemens/CTI pairs.

**Top candidates by vendor** (`pairs_v2.csv`):

| Vendor | Candidates |
|---|---|
| GE | **ACRIN-NSCLC-FDG-PET-167** (Discovery LS ×2, 168 d, HIGH_CONFIDENCE, ~202 MB; SUV passes with `DECAY_FACTOR_UNVERIFIED`) |
| Siemens/CTI | **050** (CPS 1080 ×2, 171 d, ~322 MB), 095 (CPS 1080, ~336 MB), 131 (CPS 1080, ~336 MB), 192 (Siemens 1094, ~381 MB). All: no height, tracer code missing, reconstruction iterations known |
| Philips | none analyzable (all non-BQML / DecayCorrection NONE) |
