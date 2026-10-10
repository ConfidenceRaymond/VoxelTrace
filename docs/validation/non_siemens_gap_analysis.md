# GE / Philips gap analysis: why strict SUV refuses, and what could resolve it

Date: 2026-10-09. **No download, no rule change.** Sources: census v3 header samples
(IDC v25; `data/census/public_pet_v3/pet_series_v3.jsonl`), tabulated by
`scripts/non_siemens_gap.py` into `outputs/non_siemens_gap/non_siemens_gap_v3.json`; the
ACRIN GE Discovery LS full-series investigation (`../vendor_decay_timing.md`); the vendor
matrix (`../vendor_validation_matrix.md`). ACRIN-NSCLC-FDG-PET (census v2) is excluded from the
counts below; its GE Discovery LS pairs are the INGESTION_VALIDATED evidence.

The strict SUV path is not weakened by anything in this document. Each "possible resolution"
needs evidence first (a vendor conformance statement, a phantom, a partner re-export) and, if it
leads to a new path, a new versioned check with regression tests.

## 1. Datasets available

| Vendor / model | Public collections (census v3) | PET series | FDG series | Strict-SUV eligible (all / FDG) |
|---|---|---|---|---|
| GE Discovery STE | ACRIN-FLT-Breast, Breast-Diagnosis, QIN-Breast, QIN PET Phantom, RIDER Lung, RIDER Phantom, TCGA-LUAD, CC-Tumor-Heterogeneity | 491 | 320 | 3 / 1 |
| GE Discovery LS | ACRIN-FLT-Breast | 194 | 101 | 2 / 1 |
| GE Discovery ST | ACRIN-FLT-Breast | 159 | 139 | 0 / 0 |
| GE Discovery 690 | Anti-PD-1 Lung, PSMA-PET-CT-Lesions, TCGA-UCEC | 126 | 4 | 0 / 0 |
| GE Discovery RX | Anti-PD-1 Lung, TCGA-UCEC | 18 | 18 | 0 / 0 |
| GE Discovery 710 | Anti-PD-1 Lung | 9 | 0 | 0 / 0 |
| GE Advance | RIDER Lung | 41 | 28 | 0 / 0 |
| Philips GEMINI TF TOF 16 | ACRIN-FLT-Breast, NaF-Prostate | 135 | 14 | 0 / 0 |
| Philips GEMINI TF Big Bore | ACRIN-FLT-Breast | 36 | 36 | 0 / 0 |
| Philips Allegro Body(C) | Anti-PD-1 Lung | 4 | 4 | 0 / 0 |
| Philips GEMINI TF TOF 64 | CC-Tumor-Heterogeneity | 2 | 2 | 0 / 0 |

Plus, with full series processed (ACRIN-NSCLC-FDG-PET): GE Discovery LS ACRIN-167 and -168
(strict SUV PASS, DecayFactor absent so not cross-checked) and ACRIN-094 (refused
DECAY_FACTOR_INCONSISTENT). No Philips series has been processed in full.

## 2. Why strict SUV refuses: blockers by model (FDG series, census v3)

| Vendor / model | Blocking refusal codes (count) | Blocking field(s) |
|---|---|---|
| GE Discovery STE | DECAY_FACTOR_INCONSISTENT 228; NEGATIVE_DECAY_INTERVAL 58; MISSING_RADIONUCLIDETOTALDOSE 27; MISSING_INJECTION_TIME 27; NONPOSITIVE_PATIENTWEIGHT 26 | DecayFactor vs FrameReferenceTime; injection vs scan time; RadiopharmaceuticalInformationSequence; PatientWeight |
| GE Discovery LS | DECAY_FACTOR_INCONSISTENT 90; UNSUPPORTED_UNITS 49 (CPS); MISSING_RADIONUCLIDETOTALDOSE 6; SERIES_TIME_AFTER_ACQUISITION 4; MISSING_INJECTION_TIME 3 | DecayFactor/FRT; Units; dose; series vs acquisition time |
| GE Discovery ST | DECAY_FACTOR_INCONSISTENT 108; UNSUPPORTED_UNITS 69 (PROPCPS); MISSING_CORRECTION 69; IMPLAUSIBLE_DECAY_INTERVAL 28; NONPOSITIVE_RESCALE_SLOPE 26 | DecayFactor/FRT; Units; CorrectedImage (no ATTN); timing; RescaleSlope |
| GE Discovery RX | DECAY_FACTOR_INCONSISTENT 15; UNSUPPORTED_UNITS 7; MISSING_CORRECTION 7; NEGATIVE_DECAY_INTERVAL 3 | as above |
| GE Discovery 690 | DECAY_FACTOR_INCONSISTENT 4 (all 4 FDG series; 122 non-FDG are PSMA) | DecayFactor/FRT |
| GE Advance | DECAY_FACTOR_INCONSISTENT 28; UNSUPPORTED_UNITS 14 (GML / 1CM) | DecayFactor/FRT; Units |
| Philips GEMINI TF Big Bore | SCAN_REFERENCE_AMBIGUOUS 24; UNSUPPORTED_UNITS 17 (CNTS); MISSING_CORRECTION 17; INVALID_ACQUISITION_DATETIME 10; DECAY_FACTOR_INCONSISTENT 2 | scan reference time; Units; CorrectedImage; AcquisitionDate/Time |
| Philips GEMINI TF TOF 16 | INVALID_ACQUISITION_DATETIME 10; UNSUPPORTED_UNITS 5; MISSING_CORRECTION 5; SCAN_REFERENCE_AMBIGUOUS 4 | as above |
| Philips Allegro Body(C) | UNSUPPORTED_UNITS 4 (CNTS); DECAY_FACTOR_INCONSISTENT 4; MISSING_CORRECTION 2 | Units; DecayFactor/FRT; CorrectedImage |
| Philips GEMINI TF TOF 64 | DECAY_FACTOR_INCONSISTENT 2 | DecayFactor/FRT |

Field presence that matters for the pair rules (all series of the model):

| Model | SoftwareVersions missing | Height present | Iterations / subsets / kernel / TOF / PSF as standard attributes |
|---|---|---|---|
| GE Discovery LS | 187 / 194 | 194 / 194 | none (method text only) |
| GE Discovery ST | 159 / 159 | 159 / 159 | none |
| GE Discovery STE | 205 / 491 | 436 / 491 | kernel in 93; others none |
| GE Discovery 690 / RX / 710 | 0 | all | none |
| Philips GEMINI TF Big Bore | 36 / 36 | 36 / 36 | none |
| Philips GEMINI TF TOF 16 | 8 / 135 | 135 / 135 | none |

So even where strict SUV would pass, `VT-PROTOCOL-IDENTITY` will usually be UNKNOWN
(reconstruction identity not in standard attributes) unless the method text is parseable or a
site attestation is supplied (QIBA only), and same-system rules are UNKNOWN where software is
missing.

## 3. Likely cause and whether a re-export or a phantom could resolve it

Cause classes: **export-specific** (which series / options the site exported), **anonymization-
specific** (removed or shifted by de-identification), **scanner-specific** (vendor encoding
convention), **unknown**. "Likely" is a judgement from the header pattern, stated as such.

| Blocker | GE models | Philips models | Likely cause | Confidence | Partner re-export resolves? | Phantom can test? |
|---|---|---|---|---|---|---|
| DECAY_FACTOR_INCONSISTENT | all, incl. modern 690 | Allegro, TF 64, Big Bore (few) | **scanner-specific**: in Discovery LS 16.01 FrameReferenceTime holds frame start and DecayFactor the mid-frame decay (`../vendor_decay_timing.md`); same pattern suspected for other GE models, not verified | GE LS: PLAUSIBLE_BUT_UNVERIFIED; others UNKNOWN | **No** (re-export reproduces it) | **Yes**: a phantom of known activity plus the model's conformance statement would decide the decay reference |
| UNSUPPORTED_UNITS (CPS, PROPCPS, GML, 1CM) | LS, ST, RX, Advance, STE | — | **export-specific**: non-BQML series (raw/NAC counts or SUV-unit copies) exported next to or instead of the BQML series | PROBABLE (BQML series exist in the same models) | **Yes**: export the attenuation-corrected BQML series | not needed |
| UNSUPPORTED_UNITS (CNTS) | — | Big Bore, TF 16, Allegro | **scanner-specific** for older Philips exports (counts need private scaling that is not documented) or export choice (BQML exists for 75/135 TF 16 series) | PROBABLE | **Maybe**: if the system can export BQML | **Yes**, if a CNTS path were ever proposed, it would need a phantom plus a published conformance statement |
| MISSING_CORRECTION (no ATTN) | ST, RX | Big Bore, TF 16, Allegro | **export-specific**: NAC series included | PROBABLE (co-occurs with non-BQML units) | **Yes** | no |
| NEGATIVE / IMPLAUSIBLE_DECAY_INTERVAL | STE, ST, RX | — | **anonymization-specific** (injection and scan times shifted differently) or data entry | POSSIBLE | **Yes**, if de-identification keeps times on one clock (PS3.15 Retain Longitudinal Temporal Information) | no |
| MISSING_RADIONUCLIDETOTALDOSE / MISSING_INJECTION_TIME / NONPOSITIVE_PATIENTWEIGHT | STE (RIDER phantom), LS | — | **anonymization- or export-specific** (sequence or weight not filled; the RIDER phantom has weight 0) | PROBABLE | **Yes** | a phantom needs a documented "weight" convention (SUV of a phantom is defined only with an agreed nominal mass) |
| INVALID_ACQUISITION_DATETIME / SCAN_REFERENCE_AMBIGUOUS | — | Big Bore, TF 16 | **unknown** (malformed or missing acquisition timing; anonymizer or export) | UNKNOWN | **Maybe** | **Yes** (a phantom export from the same pathway shows whether the timing is complete) |
| SoftwareVersions missing | LS, ST, STE | Big Bore | **anonymization-specific** (device identity removed) | PROBABLE | **Yes** (PS3.15 Retain Device Identity) | no |
| Reconstruction parameters only in free text | all | all | **scanner-specific** (no standard attributes populated) | CONFIRMED in headers | **No** (re-export reproduces it); a site protocol sheet / attestation is the route | no |

## 4. What this means

- **Downloading more public GE / Philips data cannot validate quantification.** The headers
  already predict the refusals. Of 1,215 public non-Siemens PET series, 2 FDG series are
  strict-SUV eligible.
- **The decisive GE question is scanner-specific** (decay reference semantics). It needs the
  model's DICOM conformance statement and a phantom, not more patient data.
- **Most other blockers are export or de-identification choices** that a design partner can
  fix by exporting the AC BQML series with the PS3.15 retain options, which is what the
  partner data request asks for (`ge_philips_partner_data_request.md`).
- **Public phantom data exist but do not settle the question:** the QIN PET Phantom GE
  Discovery STE series (22) are refused for DECAY_FACTOR_INCONSISTENT, and the RIDER Phantom
  series (20) lack dose, injection time and weight. They were not downloaded; their headers
  are already in the census. They become useful only together with GE documentation of the
  decay reference.

## 5. Scanner models that would be most useful

| Priority | Models | Why |
|---|---|---|
| 1 | GE Discovery MI, Omni, 690, 710 | current GE fleet; the decay-reference question (DecayFactor/FrameReferenceTime) is unresolved on every GE model seen |
| 2 | Philips Vereos / Vereos Digital | current Philips fleet; no Philips series has been processed in full |
| 3 | GE Discovery STE / LS still used in trials | public refusals already characterised; partner exports would test re-export fixes |
| 4 | Philips GEMINI TF (BQML exports) | older but common in archives; CNTS exports stay unsupported without documentation |

Partner-facing version: `../pilot/external_partner/GE_PHILIPS_DATA_REQUEST.md`.

## 6. Status statement (unchanged)

> GE: ingestion validated on Discovery LS (two scans SUV PASS without an independent
> cross-check; one correctly refused). Philips: metadata only. No GE or Philips model is
> QUANT_VALIDATED, PAIR_VALIDATED or EXPERT_VALIDATED.
