# GE and Philips data request (for partners using these scanners)

VoxelTrace's strict SUV checks refuse most **public** GE and Philips FDG exports. That does not
mean your data will fail, but we cannot claim GE or Philips validation until real partner
exports (or a phantom) have been audited. Background and full table:
`docs/validation/non_siemens_gap_analysis.md`. The checks will not be relaxed to make data
pass; a vendor-specific path is added only with vendor documentation and a test.

## What fails in public exports, and what you can change

| Blocking field (DICOM) | Seen in public exports of | Likely cause | Fixed by your re-export? | Phantom can test? |
|---|---|---|---|---|
| `DecayFactor` vs `FrameReferenceTime` disagree | all GE models in public data (incl. Discovery 690), some Philips | scanner-specific decay-reference convention (shown for GE Discovery LS 16.01) | **no** | **yes**, with your vendor's conformance statement |
| `Units` not BQML (CPS, PROPCPS, GML, CNTS) | GE LS/ST/STE/RX/Advance; Philips GEMINI TF / Allegro | a raw, non-attenuation-corrected or processed series was exported; older Philips CNTS | **yes**: export the AC series in BQML | only if CNTS must be supported |
| `CorrectedImage` without ATTN | GE ST/RX; Philips TF | non-attenuation-corrected series exported | **yes** | no |
| injection vs scan time negative or implausible | GE STE/ST/RX | de-identification shifted times inconsistently | **yes**: keep times on one clock | no |
| `RadionuclideTotalDose`, injection time or weight missing | GE STE, LS (and the public GE phantom) | removed by de-identification or not filled at the scanner | **yes** | needs a nominal mass convention |
| `AcquisitionDate/Time` invalid; scan reference ambiguous | Philips GEMINI TF Big Bore / TF 16 | unknown (export or anonymizer) | **maybe** | **yes** |
| `SoftwareVersions` missing | GE LS/ST/STE; Philips Big Bore | removed by de-identification | **yes** (retain device identity) | no |
| iterations / subsets / TOF / PSF / filter not in standard attributes | all GE and Philips public exports | scanner-specific (text only) | **no**; a protocol sheet or signed attestation resolves it (QIBA, with a warning) | no |

## Most useful data from you, in priority order

1. **One phantom acquisition** (NEMA IEC body or uniform cylinder) with the activity record,
   exported through your trial pathway (`docs/validation/phantom_validation_plan.md`).
2. **The decay-reference statement** for each model/software: one sentence from your physicist
   or the conformance-statement page.
3. **2–3 baseline/follow-up FDG pairs per model**, de-identified with times on one clock and
   device identity and patient characteristics retained, plus each protocol sheet.

Models that would add the most evidence (none validated today): GE **Discovery MI / Omni /
690 / 710**, Philips **Vereos / Vereos Digital**, and any GE Discovery STE/LS still in trial use.
Older Philips GEMINI TF exports in CNTS units are a lower priority.

Minimum fields and the "do not send" list: [DATA_REQUIREMENTS.md](DATA_REQUIREMENTS.md).
