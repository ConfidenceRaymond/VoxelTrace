# Non-Siemens (GE, Philips) validation strategy

## The gap, measured

From census v3 (IDC v25, header samples only, 2026-10-09):

| Vendor / model | Series | SUV-eligible | Dominant refusals |
|---|---|---|---|
| GE Discovery STE | 491 | 3 | DECAY_FACTOR_INCONSISTENT 355, NEGATIVE_DECAY_INTERVAL 77, UNSUPPORTED_UNITS 69 (PROPCPS) |
| GE Discovery LS | 194 | 2 | DECAY_FACTOR_INCONSISTENT 166, UNSUPPORTED_UNITS 70 (CPS) |
| GE Discovery ST | 159 | 0 | DECAY_FACTOR_INCONSISTENT 128, UNSUPPORTED_UNITS 78 |
| GE Discovery 690 | 126 | 0 | DECAY_FACTOR_INCONSISTENT 126 (mostly PSMA) |
| GE Advance / RX / 710 | 68 | 0 | DECAY_FACTOR_INCONSISTENT, UNSUPPORTED_UNITS (GML, PROPCPS) |
| Philips GEMINI TF / Allegro | 177 | 0 | INVALID_ACQUISITION_DATETIME 100, UNSUPPORTED_UNITS 81 (CNTS), SCAN_REFERENCE_AMBIGUOUS 24 |

Public GE and Philips FDG exports are refused almost entirely, so **downloading more of them
cannot validate quantification**. It would only re-confirm refusals that the headers already
predict. No such download is planned, which follows the instruction not to download cases
known to fail.

## What is not known

The refusals are deliberate and correct under the current rules. Two scientific questions are
still open:

1. **GE DECAY_FACTOR_INCONSISTENT.** In ACRIN-094 (GE Discovery LS), and likewise in ACRIN-153
   (CPS 1023), the stored DecayFactor disagrees with
   2^(FrameReferenceTime / T½). The disagreement could come from three sources:
   - a vendor convention (DecayFactor relative to a different reference);
   - anonymiser time shifting (as already shown for Siemens private times);
   - a real inconsistency.

   VoxelTrace does not choose between them. The rule will not be relaxed to obtain a PASS. A
   change needs a documented, versioned evidence path, such as the vendor's published DICOM
   conformance statement, with a regression test and a new rule version.
2. **Philips CNTS units.** Converting counts to activity concentration needs Philips private
   attributes. Interpreting undocumented private tags is not allowed, so CNTS stays
   UNSUPPORTED_UNITS unless a published conformance statement documents the attribute and a
   phantom confirms it.

## Plan, in priority order

1. **Metadata-only analysis, no new pixel data.** From the census header samples already
   indexed, tabulate the ratio DecayFactor / 2^(FRT/T½) per GE model and software version.
   - If the ratio equals a single interpretable quantity (for example the decay from injection
     to series start), record that as a hypothesis together with the public conformance
     statement text that does or does not support it.
   - Output: a versioned evidence note. No rule change without explicit sign-off.
2. **Design-partner phantom scans (preferred route).** Ask a GE and a Philips partner site for
   one NEMA/EARL phantom acquisition with a known activity concentration, exported through
   their normal trial pathway. This tests quantification against physical ground truth without
   relying on patient metadata, and moves the model directly to QUANT_VALIDATED or documents
   why not.
3. **Partner patient pairs.** Two or three de-identified baseline/follow-up pairs per modern
   model (for example GE Discovery MI / Omni, Philips Vereos), exported the way the partner's
   trials export. This reaches PAIR_VALIDATED and feeds the blinded expert package.
4. **Public data only where the headers predict success.** If a public GE or Philips series
   becomes SUV-eligible in a future census (new collection or IDC version), follow the existing
   frozen-plan procedure.

## Claims until then

VoxelTrace must not be described as validated on GE or Philips quantification. The correct
statement is:

> GE: ingestion validated on Discovery LS (two scans SUV PASS without an independent cross-check;
> one correctly refused). Philips: metadata only.
