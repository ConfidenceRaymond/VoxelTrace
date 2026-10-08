# Multi-vendor validation plan

Status: plan only (2026-10-08). **No large download has started.** Facts marked
*(verify)* come from collection descriptions or challenge pages. They must be confirmed from
DICOM headers in Step 1 before any reliance.

## Goal

Estimate, per vendor and scanner family, how often VoxelTrace's deterministic gates return
INSUFFICIENT_INFORMATION on real-world exports, and why. The reason taxonomy splits the
causes into missing timing, missing dose, stripped anthropometrics, missing reconstruction
metadata and absent private tags.

The goal is also to confirm that strict SUV, SUL, protocol evidence and comparability behave
correctly beyond the single Siemens Biograph mCT seen so far.

**Current evidence:** 3 subjects, 1 scanner model (Siemens Biograph mCT), 1 site, no real
follow-up pairs. Every real-world rate is therefore unknown.

## Step 1: metadata-only census (no pixel downloads)

Use the NBIA REST API (series metadata) and the NCI Imaging Data Commons BigQuery DICOM tables
to tabulate standard attributes per collection:

- `Manufacturer`, `ManufacturerModelName`, `SoftwareVersions`;
- `Units`, `DecayCorrection`, `CorrectedImage`;
- `RadiopharmaceuticalInformationSequence`, with dose and start time;
- `PatientWeight`, `PatientSize`, `PatientSex`;
- `ReconstructionMethod`, `ConvolutionKernel`;
- the de-identification method codes;
- studies per patient (longitudinal availability).

**Output:** a census table per vendor and model, plus a prediction of the fraction of series
expected to fail each gate. This uses only the attributes the census can see; private tags
need pixel-free header downloads in Step 2.

## Step 2: bounded header samples

- **Sample:** about 20 series per vendor and model, headers only (`stop_before_pixels`). That
  is enough to check private-tag presence (Siemens `SIEMENS MED PT`, GE `GEMS_PETD_01`,
  Philips `7053`) and the anonymizer's handling of them.

## Step 3: bounded full-series pilots

- **Sample:** 3–5 subjects per vendor, chosen from the census, with full DICOM and a
  verified-hash, bounded download (as for the current 3 subjects).
- **Checks:** run quantification and the protocol and trial audit, then cross-check strict SUV
  against an independent implementation (as done for PETCT_0011f3deaf).

## Candidates per vendor

| Vendor / class | Likely public data | Longitudinal | Tracer | Scanner models | Metadata quality / private tags | Recon metadata | Suitability for an II-rate estimate |
|---|---|---|---|---|---|---|---|
| **Siemens** | TCIA FDG-PET-CT-Lesions (in use); TCIA PSMA-PET-CT-Lesions (LMU); ACRIN-NSCLC-FDG-PET *(verify mix)* | FDG-Lesions: essentially no. PSMA: 597 studies / 378 patients, so repeat studies exist. ACRIN 6668: baseline + post-CRT (173 evaluable post-treatment) | FDG; PSMA (LMU) | Biograph mCT (FDG-Lesions); mCT Flow 20, Biograph 64 TruePoint (LMU) | Standard attributes good. `SIEMENS MED PT` decay-correction datetime present; already shown −86 400 s inconsistent after date shifting | `ReconstructionMethod` free text (e.g. "PSF+TOF 2i21s"), `ConvolutionKernel` | **High**: largest public volume; but anonymizer date-shifting creates known private/standard inconsistencies |
| **GE** | TCIA Head-Neck-PET-CT (3 of 4 centres GE Discovery ST/STE *(verify)*); LMU PSMA (Discovery 690); ACRIN 6668 / ACRIN-HNSCC *(verify)* | ACRIN trials: yes (multi-timepoint by design); Head-Neck-PET-CT: mostly single | FDG; PSMA | Discovery ST/STE/690 | `GEMS_PETD_01` scan datetime needed for some decay-correction cases; older exports may use non-BQML units or decay-correction variants VoxelTrace refuses | Reconstruction often only in private or free text | **High** for II-rate: older GE exports are exactly where refusals concentrate |
| **Philips** | TCIA Head-Neck-PET-CT (CHUS, Gemini GXL 16 *(verify)*); ACRIN trials (Allegro/Gemini common in ACRIN sites *(verify)*) | ACRIN: yes | FDG | Gemini GXL/TF, Allegro | Philips private group `7053` (SUV scale factor, activity concentration factor); Units can be `CNTS` → strict SUV refuses (`UNSUPPORTED_VENDOR` / non-BQML) | Sparse standard reconstruction attributes | **High** for II-rate; likely the highest refusal fraction. Needs the documented Philips path before any positive SUV claim |
| **United Imaging (uMI)** | No open FDG DICOM collection found; challenge or industry data only | Unknown | FDG | uMI 550/780 | Unknown private dictionary; VoxelTrace has no vendor module (`UNSUPPORTED_VENDOR`) | Unknown | **Low** until a public source exists; ask challenge organizers or collaborators |
| **uEXPLORER / long-axial-FOV** | UDPET challenge (Bern / SJTU): 1060 uEXPLORER + 387 Biograph Vision Quadra, whole-body FDG, DICOM, signed data-transfer agreement | No (single studies, with simulated dose levels) | FDG | uEXPLORER (United Imaging); Biograph Vision Quadra (Siemens LAFOV) | Unknown; low-dose images are *simulated* by rebinning, so they must be flagged synthetic-like (not real protocol variation) | Reported OSEM 4i5s + TOF + PSF *(verify)* | **Medium**: tests geometry (very long axial extent, slice count), UIH metadata and LAFOV reference-region placement; not for longitudinal II rates |

**Repeatability anchor:** TCIA RIDER Lung PET-CT (CC BY 3.0; ~243 subjects). It includes a
phantom test-retest component. Vendor and patient test-retest content must be *verified* in
Step 1. If patient same-day repeats exist, it is the best real dataset for the
`PERCIST-LIVER-SUL-STABILITY` rule without treatment effects.

## Vendor × architecture matrix (open-data availability, 2026-10-08)

Availability codes:
- **OPEN-DICOM:** public DICOM confirmed.
- **GATED:** requires an agreement.
- **NONE-FOUND:** no open DICOM found in this search.
- **(verify):** reported by a secondary source, not yet checked in headers.

| Vendor | CONVENTIONAL_AFOV | LONG_AFOV | TOTAL_BODY | PET_MR |
|---|---|---|---|---|
| **Siemens** | OPEN-DICOM: FDG-PET-CT-Lesions (Biograph mCT); PSMA-PET-CT-Lesions (mCT Flow, Biograph 64); ACRIN-NSCLC-FDG-PET (CPS/CTI 1023/1024/1080/1094 lineage, see census) | GATED: Biograph Vision Quadra in UDPET (387 subjects; simulated low-dose = synthetic) | n/a (Quadra is long-axial, not total-body) | NONE-FOUND in this search (Biograph mMR open data to be searched; verify) |
| **GE** | OPEN-DICOM: ACRIN-NSCLC-FDG-PET (Discovery ST/STE/LS/RX, Advance; census); Head-Neck-PET-CT (Discovery ST/STE, verify); PSMA LMU (Discovery 690) | NONE-FOUND | NONE-FOUND | NONE-FOUND (SIGNA PET/MR) |
| **Philips** | OPEN-DICOM: ACRIN-NSCLC-FDG-PET (Allegro, Guardian; census); Head-Neck-PET-CT (Gemini GXL, verify) | NONE-FOUND | NONE-FOUND | NONE-FOUND |
| **United Imaging** | **uMI family** (uMI 510/550/780/Panorama): NONE-FOUND | NONE-FOUND | **uEXPLORER**: GATED only (UDPET, 1060 subjects, DICOM, signed data-transfer agreement, simulated low-dose); **no open uEXPLORER DICOM dataset found** | **uPMR (e.g. uPMR 790)**: NONE-FOUND |

**Update (2026-10-08, second search):**

| Source | Scanner | Status |
|---|---|---|
| TCIA "Healthy-Total-Body-CTs" (Selfridge et al. 2023, doi 10.7937/NC7Z-4F76) | United Imaging uEXPLORER, UC Davis | **CT only** (30 healthy adults; FDG PET "planned for a future update"); one listing says limited access; real data; not usable for PET quantification |
| UC Davis EXPLORER research-data page | total-body PET | **GATED** (data transfer agreement); scanner mix and DICOM availability not confirmed |
| UDPET | uEXPLORER and Biograph Vision Quadra | **GATED** (DTA), DICOM; low-dose images are SIMULATED |
| uMI Panorama (FDA K241585), uMI 780, uPMR 790 (FDA K183014/K222540/K234154) | United Imaging | regulatory and performance records only; **no open dataset found** |
| CERMEP-IDB-MRXFDG | FDG brain PET/CT (not PET/MR) | GATED (request form), single timepoint |
| CAI2R Knoll et al. | brain FDG PET/MR, Biograph mMR | raw/list-mode research data, single session; DICOM not stated |

**Implications:**
- Every LONG_AFOV, TOTAL_BODY and PET_MR cell, and every United Imaging cell, is currently
  unvalidated. VoxelTrace has no United Imaging vendor module, so such scans refuse with
  `UNSUPPORTED_VENDOR` wherever vendor-specific handling would be needed.
- Strict SUV uses only standard attributes. It may still work on UIH exports that carry
  BQML/START and complete timing.
- **Next United Imaging step:** request UDPET access (DTA) or a collaborator export, and run
  the Step 1/2 header census only.

## Rule applicability caveats

- **FDG only:** QIBA FDG 1.14, PERCIST 1.0 and EANM FDG 2.0 apply to FDG. PSMA studies must
  be audited for protocol comparability only. The tracer gate (`VT-TRACER-SAME`) and
  standard selection must keep FDG rules off PSMA data.
- **Simulated low-dose data:** UDPET low-dose images are simulated. Like VoxelTrace's own
  perturbations, they are SYNTHETIC and must never be pooled with real findings.

## Deliverables and success criteria

1. **Census:** per vendor and model, n series, % passing strict SUV, and II reasons by
   frequency. Reported separately per collection; never pooled across real and synthetic data.
2. **Independent cross-check:** strict SUV checked against an independent implementation on
   ≥ 3 subjects per vendor (difference ≤ 1e-6 relative), or a documented refusal reason.
3. **Vendor modules:** Philips and GE vendor-module validation against conformance statements
   before any private attribute is used.
4. **Reference regions:** proposer failure rate per vendor and scanner (requires human review
   of every proposal, as now). It is not reportable as a rate until n ≥ 30 reviewed proposals
   per scanner family.
5. **Real longitudinal pairs:** first from ACRIN 6668 (FDG, baseline + post-treatment, CT at
   both timepoints *(verify)*). This exercises the liver stability rule on real pairs.

## ACRIN census result (done, metadata only)

See [acrin_census.md](acrin_census.md).

| Item | Result |
|---|---|
| Candidate patients with a real baseline + follow-up pair | **141** |
| …likely analyzable (all GE) | 53 |
| …with warnings (all Siemens/CTI: patient height missing) | 57 |
| …likely insufficient (all Philips CNTS/NONE; GE Advance non-BQML; MIMvista derived) | 31 |

## Highest-priority first step

Step 1 census of ACRIN-NSCLC-FDG-PET, Head-Neck-PET-CT and RIDER Lung PET-CT through NBIA and
IDC metadata (minutes, no pixels). It answers vendor mix, longitudinal structure and metadata
completeness before any download.

Sources:
- [IDC ACRIN-NSCLC-FDG-PET](https://portal.imaging.datacommons.cancer.gov/collections/acrin_nsclc_fdg_pet)
- [UDPET dataset](https://ultra-low-dose-pet.grand-challenge.org/Dataset/)
- [MICCAI 2025 UDPET paper](https://papers.miccai.org/miccai-2025/0959-Paper0232.html)
- [HECKTOR 2022 overview (Canadian centres and scanners)](https://arxiv.org/pdf/2201.04138)
- [Head-Neck-PET-CT derivative (Zenodo)](https://doi.org/10.5281/zenodo.5808389)
- [IDC RIDER Lung PET-CT](https://portal.imaging.datacommons.cancer.gov/collections/rider_lung_pet_ct)
- [IDC PSMA-PET-CT-Lesions](https://portal.imaging.datacommons.cancer.gov/collections/psma_pet_ct_lesions)
- [autoPET IV dataset](https://autopet-iv.grand-challenge.org/dataset/)
