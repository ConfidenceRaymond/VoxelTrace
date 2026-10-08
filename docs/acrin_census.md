# ACRIN-NSCLC-FDG-PET metadata census (2026-10-08)

**Method.** Two sources, with no image volumes downloaded:

- **Series metadata:** the IDC index (`idc-index` 0.13.0).
- **Headers:** for each of the 997 PT series, the header of **one** instance, read by an HTTP
  byte range (16 KB, at most 64 KB) from IDC's public bucket and parsed with pydicom
  `stop_before_pixels`. In total, 16.3 MB of header bytes were read.
- **Storage:** raw bytes are not stored; only parsed attributes are kept.

The NBIA `getDicomTags` endpoint returned HTTP 500, which is why the byte-range route was used.

**Scripts:**
- `scripts/census_acrin.py` (run in `../tmp/census-venv`);
- `scripts/analyze_acrin_census.py`.

**Outputs:** `../data/census/acrin_nsclc_fdg_pet/`:
- `series_index.csv`, `pet_headers.jsonl`;
- `pet_series_risk.csv`, `candidate_pairs.csv`, `census_summary.json`.

These are not tracked by git.

**Data:** CC BY 3.0. Dates are de-identified (shifted to about 1960) but consistent within a
patient, so intervals are meaningful.

## Size

| Item | Count |
|---|---|
| Patients | 242 |
| Series | 3,762: CT 2,259, PT 997, SEG 385, MR 70, other 51 |
| PET total | 12.05 GB |
| AC primary PET series (ATTN in CorrectedImage; not NAC/MIP) | 588 |
| Studies with AC PET and CT | 398 |
| Patients with a baseline and follow-up candidate pair | **141** |
| …same scanner model at both timepoints | 119 |
| …same model and same reconstruction description | 114 |

## Predicted II risk (one header per series; NOT proof of assessability)

| | LIKELY_ANALYZABLE | LIKELY_ANALYZABLE_WITH_WARNINGS | LIKELY_INSUFFICIENT_INFORMATION | UNKNOWN |
|---|---|---|---|---|
| AC primary PET series (588) | 177 | 160 | 251 | 0 |
| Candidate pairs (141) | 53 (all GE) | 57 (all Siemens/CTI) | 31 (15 GE, 11 Siemens/CTI, 5 Philips) | 0 |

**II reasons (AC primary series):**

| Reason | Series |
|---|---|
| Units not BQML | 168 (Philips CNTS/GML; GE Advance PROPCNTS/GML/1CM) |
| DecayCorrection not START | 86 (mostly Philips NONE) |
| DERIVED ImageType | 55 (MIMvista re-saved series → provenance) |
| No reconstruction description | 53 |
| Weight missing | 31 |
| Dose, injection time or half-life missing | 9 |

**Warnings:** patient height is present in only 310/588 AC series. Without it SUL is refused,
so the PERCIST liver rules are UNKNOWN; this is the Siemens/CTI pattern.

## Private-tag and metadata patterns

- **Private creators:**
  - `GEMS_PETD_01` (103 series), `SIEMENS MEDCOM HEADER` (89+), `Philips PET Private Group`
    (74);
  - the anonymizer/curation creators CTP and Posda; MAROTECH.
- **Philips:** every Philips series uses CNTS/GML with DecayCorrection NONE. Strict SUVbw
  refuses them. A documented Philips path (private SUV/activity scale factors) would be needed;
  until then they are a known II source.
- **GE:** reconstruction descriptions are often only "OSEM" or "3D IR", without iteration or
  subset counts. VT-PROTOCOL-IDENTITY may then be UNKNOWN even when both scans are
  quantifiable, because iterations exist only in GE private attributes, which are not used.
  **This is the main caveat on the GE "LIKELY_ANALYZABLE" label.**
- **CPS/CTI (Siemens lineage):** reconstruction is fully specified ("OSEM 2i8s", "OSEM2D
  3i8s"), with BQML and START. But PatientSize is missing, so no SUL.
- **Frame of reference:** the CT's frame of reference was not read. Whether the CT is in the
  PET frame of reference, which reference proposals require, is unverified.

## Ranked candidates for the first real longitudinal download (NOT downloaded)

| Rank | Subject | Scanner (both) | Interval | Prediction | Recon | Height | Est. PET + CT size |
|---|---|---|---|---|---|---|---|
| 1 | ACRIN-NSCLC-FDG-PET-094 | GE Discovery LS | 200 d | LIKELY_ANALYZABLE | OSEM → OSEM (no iteration counts) | yes | 24 MB |
| 2 | ACRIN-NSCLC-FDG-PET-153 | CPS 1023 | 164 d | WITH_WARNINGS (no height) | OSEM 2i8s → OSEM 2i8s | no | 21 MB |
| 3 | ACRIN-NSCLC-FDG-PET-041 | GE Discovery ST | 145 d | LIKELY_ANALYZABLE | OSEM → OSEM | yes | 25 MB |
| 4 | ACRIN-NSCLC-FDG-PET-121 | GE Discovery LS | 102 d | LIKELY_ANALYZABLE | OSEM → OSEM | yes | 24 MB |
| 5 | ACRIN-NSCLC-FDG-PET-148 | Philips Allegro | 131 d | LIKELY_INSUFFICIENT (CNTS/NONE) | 3D-RAMLA | no | 181 MB |

- **Interpretation of the intervals:** they are consistent with ACRIN 6668's pre-treatment scan
  and post-chemoradiotherapy scan. VoxelTrace does not assess response.
- **Recommended first download:** pairs 1 and 2 (about 45 MB together).
  - **Pair 1 (GE)** exercises PERCIST's liver rules on a real pair (height present). It also
    tests whether GE reconstruction parameters are sufficient.
  - **Pair 2 (CPS)** exercises protocol identity with fully specified reconstruction. It is
    expected to show the SUL/height II path.
- **Optional negative control:** pair 5 (Philips) for the non-BQML refusal path.

**Requires explicit approval before download.**

## Validation against downloaded data (2026-10-08)

Two candidates (094, 153) were downloaded and analysed; see
[acrin_longitudinal.md](acrin_longitudinal.md).

| Prediction | Result |
|---|---|
| Scanner, model, height availability, reconstruction description | correct 4/4 |
| Strict-SUV eligibility | **wrong 4/4**: all refused with `DECAY_FACTOR_INCONSISTENT` |

**Size estimates were wrong.** They used the smallest CT series, the scout. Real PET + AC CT
pairs are about 250 MB.

**Census v2 should:**
- read DecayFactor and FrameReferenceTime from two slices per series, and check
  DecayFactor = 2^(FRT/T½);
- record the CT FrameOfReferenceUID against the PET's;
- record tracer code presence;
- price the AC CT, not the scout.
