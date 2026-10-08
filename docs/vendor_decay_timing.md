# Vendor PET decay-factor timing: ACRIN 094 (GE) and 153 (CPS) investigation

Date: 2026-10-08. Script: `scripts/investigate_decay_timing.py` (read-only; output
`../outputs/acrin_longitudinal/decay_timing.json`).

**Outcome: no new vendor path is justified. Strict SUVbw stays REFUSED
(`DECAY_FACTOR_INCONSISTENT`) on all four scans. The validator, SUV formula and thresholds are
unchanged.**

## The check that fails

`quant/suv.py::_check_decay_factor` requires, on every slice:

  DecayFactor = 2^(FrameReferenceTime / T½), within 1e-3 relative.

This follows the DICOM definitions in PS3.3 C.8.9.4.1.5:
- **Frame Reference Time:** "the time that the pixel values in the Image occurred", given as an
  offset from Series Date/Time. For a frame it is the average-activity time T_ave, which is
  "sooner than the midpoint of the Actual Frame Duration".
- **Decay Factor (0054,1321):** "the decay factor that was used to scale this image".
- **Consequence:** when images are decay-corrected to the series reference (START), the stored
  factor should equal the decay over FRT.

## GE Discovery LS, software 16.01 (094 baseline and follow-up)

**Observed, all slices:**
- **Timing:** one AcquisitionTime for the whole series (equal to SeriesTime and the GE private
  scan datetime (0009,100D)). FrameReferenceTime steps per bed: 0, 304, 607, 910, … s;
  ActualFrameDuration is 300 s.
- **Decay factor:** constant within a bed. Every bed matches 2^((FRT + T_frame/2)/T½) to
  ≤ 3.7e-5. The validator relation 2^(FRT/T½) is off by 1.56e-2 on every bed. T_ave
  (149.4 s) and the midpoint (150 s) cannot be distinguished at this precision.
- **Candidates tested:**

  | Candidate reference | Result |
  |---|---|
  | FRT | 1.56e-2 |
  | FRT + duration/2 | 3.7e-5 |
  | FRT + duration | 1.59e-2 |
  | acquisition start − series start | 1.56e-2 |
  | series start − injection | 2.75 |
  | acquisition start − injection | 2.75 |

**Interpretation:**
- This export's FrameReferenceTime holds each frame's **start** offset, not T_ave as C.8.9.4.1.5
  defines it.
- DecayFactor is consistent with decay correction to series start, evaluated at the
  frame's average-activity/mid time.

**Documentation status:**
- **GE conformance statement:** GE lists Discovery LS conformance statements (Release 1:
  Direction 2343444GSP; Release 2: Direction 5101600GD0). The PDF was **not retrievable** in
  this session (GE CDN returned HTTP 502).
- **Z-Rad / Fritsak et al. 2024:** cites the GE conformance statement for "scan start =
  AcquisitionTime − FRT", i.e. frame start, on newer GE systems. In this export AcquisitionTime
  is constant across frames, so that relation does not describe it.
- **Nothing found** documents DecayFactor-to-mid-frame for Discovery LS 16.01.

**Classification: PLAUSIBLE_BUT_UNVERIFIED.**
- **Source:** the data above, DICOM PS3.3 C.8.9.4.1.5, and Fritsak et al. (arXiv 2410.13348;
  Z-Rad).
- **Limitations:**
  - the GE document for this model and software was not read;
  - the uptake of 211.7 min is unexplained (three timing sources agree);
  - adopting "FRT = frame start" would be inferring FRT semantics from a numerical fit, which
    is forbidden.

## CPS 1023, no SoftwareVersions (153 baseline and follow-up)

**Observed:**
- **Beds:** 7 at baseline and 8 at follow-up. Each bed has its own AcquisitionTime;
  ActualFrameDuration is 180 s.
- **Frame Reference Time:** 0 on every slice.
- **Decay factor:** constant within a bed and different between beds (1.0095 … 1.134). Each bed
  matches 2^((AcquisitionTime − SeriesTime + T_frame/2)/T½) to ≤ 6.5e-5. The validator relation
  (FRT = 0, so a predicted DF of 1) is off by 0.94–13.7 %.

**Interpretation:**
- DecayFactor tracks per-bed acquisition timing relative to series start.
- FrameReferenceTime = 0 contradicts both DecayFactor and AcquisitionTime under the C.8.9.4.1.5
  definition, since FRT should equal the bed's time offset.
- The private Siemens decay-correction datetime (0071,xx22) is absent (`UNKNOWN_OR_STRIPPED`).
- "CPS" (CTI PET Systems) model codes 1023/1024/1080/1094 are not documented in any source
  found. No CTI/CPS DICOM conformance statement was found.

**Caution:**
- FDA recall records exist for **incorrect whole-body decay correction** in ECAT software
  7.2.2/7.4 (2007) and for ECAT 7.1.1b–7.2.2.
- Without SoftwareVersions, an affected version cannot be excluded.

**Classification: INTERNALLY_INCONSISTENT.**
- **Reason:** the required FrameReferenceTime (Type 1) contradicts the image's own
  DecayFactor and AcquisitionTime. The relation that does fit was found numerically and has no
  vendor documentation.
- **Source:** the data above, DICOM PS3.3 C.8.9.4.1.4 (Acquisition Time is the real-world
  start of accumulation for this image) and C.8.9.4.1.5, and the FDA recall records.
- **Limitations:**
  - no CTI/CPS documentation;
  - the software version is missing;
  - the private timing is absent.

## Decisions

| Pattern | Classification | New path? | SUV now |
|---|---|---|---|
| GE Discovery LS 16.01: FRT = frame start; DF = mid-frame | PLAUSIBLE_BUT_UNVERIFIED | **No** (needs GE Direction 5101600GD0 / 2343444GSP) | REFUSED |
| CPS 1023: FRT = 0, DF per bed | INTERNALLY_INCONSISTENT | **No** | REFUSED |

**Not done, as required:**
- no scale factor was fitted;
- the 1.56 % offset was not accepted;
- no timestamp was chosen because it fits;
- DecayFactor was not replaced;
- FRT semantics were not borrowed from newer scanners;
- no private tag was used without provenance.

**What would change the GE decision:**
- the Discovery LS Release 2 conformance statement (request via
  interop.standards@gehealthcare.com), stating how FrameReferenceTime and DecayFactor are
  defined. A documented path would then be added as a **new, versioned** check (for example
  `GE_DLS_FRAME_START_FRT`), restricted to Discovery LS and that software version. It would
  never be a change to the strict path.

## Sources

- [DICOM PS3.3 C.8.9.4 (PET Image Module, Frame Reference Time, Decay Factor)](https://dicom.nema.org/medical/dicom/current/output/chtml/part03/sect_C.8.9.4.html)
- [Fritsak et al., Vendor-Specific Approach for SUV Calculation (arXiv 2410.13348)](https://arxiv.org/html/2410.13348v2)
- [GE PET DICOM conformance statements (Discovery LS listed)](https://www.gehealthcare.com/en/products/interoperability/dicom-conformance-statements/pet)
- [MINC-users: FrameReferenceTime is loosely specified](https://mailman.bic.mni.mcgill.ca/pipermail/minc-users/2019-March/004737.html)
- FDA recall records for ECAT decay correction: [64983](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfRes/res.cfm?id=64983), [64981](https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfRes/res.cfm?id=64981)
- [FDA 510(k) K002039 (CTI ECAT EXACT / HR+)](https://beudamed.com/fda510ks/K002039)
