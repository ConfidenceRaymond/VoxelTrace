# TEXT_IMPLIED review packet: first scientific adjudication question

**For:** the partner's PET physicist. **Status:** open question; no expert answer has been
received. **Rule behaviour is unchanged** by this packet. Your answers inform a possible future,
separately versioned rule change.

> **If you are also a reviewer in VoxelTrace's blinded external validation** (package frozen at
> tag `v0.3.0-external-validation`), complete and return those case forms **before** reading
> this packet, and do not open Appendix B before answering Part A. Part A shows the evidence
> only, not VoxelTrace's verdicts.

## The question

> When a reconstruction parameter (iterations, subsets, time-of-flight, PSF / resolution
> modelling) is **not encoded** in DICOM at one or both timepoints, may two scans be treated as
> having the **same** value because their `ReconstructionMethod` text is identical?

## Current interpretation (VT-PROTOCOL-IDENTITY v1)

- If a parameter is encoded at both timepoints, the values are compared directly. A parameter
  parsed from the text itself (e.g. `3i24s` → 3 iterations, 24 subsets) counts as encoded, at
  trust LEVEL_D (vendor free text).
- If a parameter is not encoded but the `ReconstructionMethod` text is **identical** on both
  scans, it is counted as SAME. This is the *text-implied* identity.
- Different texts are never treated as identical; a changed text gives an identity FAIL.
- The post-filter (`ConvolutionKernel`) must be known on both scans; otherwise identity is
  UNKNOWN.
- Since 0.4.0, `pair_results.csv → reconstruction_evidence` reports `TEXT_IMPLIED: <parameters>`
  for such pairs, and `NOT_ESTABLISHED: <parameters>` when a parameter is missing and there is
  no identical text.

**Why identical text is currently treated as identity evidence.** At a given site, scanner and
software version, the vendor writes the reconstruction protocol's description into
`ReconstructionMethod`. When the same protocol is re-used, the description repeats. Identical
text therefore suggests, but does not prove, that the same protocol was used. The rule was
written to avoid refusing every pair whose export omits individual parameters. Its limitation
is recorded in the rule definition ("iterations/subsets/TOF/PSF may come from vendor free
text") and in the false-safe risk register (FS-01).

**Alternative conservative interpretation.** Identical text implies only the parameters the
text actually encodes; anything else is UNKNOWN unless documented (site protocol,
attestation, vendor documentation).

| | If the current interpretation is wrong | If the conservative interpretation is wrong |
|---|---|---|
| Effect | **false-safe**: a site changed TOF/PSF/iterations without changing the text; the pair is reported comparable and an SUV change could be misread | **false-unsafe**: genuinely identical protocols are reported INSUFFICIENT_INFORMATION; more site queries and fewer usable pairs |
| Visible to the user? | only through the `TEXT_IMPLIED` flag | yes (II with the missing parameter named) |

## Part A: blinded evidence table (answer before Appendix B)

Real public pairs from VoxelTrace's development cohort. Case codes are specific to this packet.
"Encoded" means present as a standard attribute or parsed from the text; "not encoded" means
neither.

| Case | Scanner (both timepoints) | ReconstructionMethod (baseline / follow-up) | Encoded | Not encoded | ConvolutionKernel known |
|---|---|---|---|---|---|
| TI-1 | CPS 1080 | `OSEM2D 2i8s` / `OSEM2D 2i8s` | method, iterations, subsets, filter | TOF, PSF | yes |
| TI-2 | GE Discovery LS | `OSEM` / `OSEM` | method | iterations, subsets, TOF, PSF | **no** |
| TI-3 | CPS 1023 | `OSEM 2i8s` / `OSEM 2i8s` | method, iterations, subsets | TOF, PSF | **no** |
| TI-4 | Siemens Biograph64 (`syngo MI.PET/CT 2011A`) | `PSF 3i24s` / `PSF 3i24s` | method, iterations, subsets, PSF, filter | TOF | yes |
| TI-5 | Siemens Biograph40 mCT | `PSF 3i12s` / `PSF 3i12s` | method, iterations, subsets, PSF, filter | TOF | yes |

For contrast (not text-implied): a Siemens Biograph128 mCT pair with `PSF+TOF 2i21s` on both
scans has every parameter encoded in the text.

### Questions for each case (TI-1 … TI-5)

For each case:

- **Q1.** Is reconstruction identity established from this evidence alone? Answer
  *Yes / No / Only with site documentation*.
- **Q2.** If not, which document would settle it? Answer *site protocol / console screenshot /
  signed attestation / vendor documentation*.

### General questions

- **Q3.** For Siemens texts of the form `[PSF][+TOF] <n>i<m>s`, is the absence of `TOF` in the
  text sufficient evidence that TOF was off? On which systems and software versions?
- **Q4.** For generic texts (e.g. `OSEM`, `OSEM2D`, `3D IR`, `VPFX`), should identical text ever
  imply identical iterations, subsets, TOF or PSF?
- **Q5.** How often do you expect reconstruction parameters to be unencoded in your exports, and
  how often do sites change them between visits without changing the protocol name?
- **Q6.** Which policy would you prefer (see below), and why?

### Possible future policies (none adopted)

| Option | Effect |
|---|---|
| A | keep v1 and the TEXT_IMPLIED flag; physicist review of flagged pairs |
| B | text implies only parameters it encodes, using a vendor-specific grammar where documented; otherwise UNKNOWN |
| C | a text-implied identity downgrades the verdict to ASSESSABLE_WITH_WARNINGS |
| D | text-implied identity only with a documented vendor dictionary or a site attestation |

Any change would be a **new rule version** (VT-PROTOCOL-IDENTITY v2) with regression tests. It
would be introduced after the blinded external validation, whose frozen package must keep its
answers, and announced to partners.

## Your answers

| Case | Q1 | Q2 | Basis (experience / document / site protocol) |
|---|---|---|---|
| TI-1 | | | |
| TI-2 | | | |
| TI-3 | | | |
| TI-4 | | | |
| TI-5 | | | |

| | Answer |
|---|---|
| Q3 | |
| Q4 | |
| Q5 | |
| Q6 (preferred option) | |

Reviewer role: `<...>` · Date: `<...>` · Blinded validation forms returned first? yes / no / not a validation reviewer

---

## Appendix B: VoxelTrace's current result (open only after answering Part A)

<details>
<summary>Show</summary>

| Case | Source pair | QIBA 1.14 | EANM 2.0 | PERCIST 1.0 | Does text-implied identity change the outcome today? |
|---|---|---|---|---|---|
| TI-1 | ACRIN-NSCLC-FDG-PET-050 | NOT_ASSESSABLE | NOT_ASSESSABLE | NOT_ASSESSABLE | no: uptake-time criteria fail regardless |
| TI-2 | ACRIN-NSCLC-FDG-PET-094 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | no: post-filter unknown and strict SUV refused |
| TI-3 | ACRIN-NSCLC-FDG-PET-153 | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | INSUFFICIENT_INFORMATION | no: post-filter unknown and strict SUV refused |
| TI-4 | CCTH-B02 | **ASSESSABLE** | **ASSESSABLE_WITH_WARNINGS** | INSUFFICIENT_INFORMATION (reference review pending; SUL evidence missing) | **yes**: under the conservative interpretation, TOF would be UNKNOWN and QIBA/EANM would become INSUFFICIENT_INFORMATION |
| TI-5 | MSB-07612 | NOT_ASSESSABLE | NOT_ASSESSABLE | INSUFFICIENT_INFORMATION | no: uptake-time criterion fails regardless |

Source: `voxeltrace run-pilot` on the 9-pair real cohort at release `v0.4.0` (pair verdicts
byte-identical to the frozen validation bundle). ACRIN-167 and ACRIN-168 (GE Discovery LS, no
reconstruction text at all) are `NOT_ESTABLISHED`, not text-implied, and are not part of this
question.

</details>
