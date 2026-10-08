# Synthetic longitudinal fixtures (v2) and inherited reference regions

Code:
- `src/voxeltrace/trial/perturb.py` (`with_ct=True`)
- `src/voxeltrace/trial/synthetic_reference.py`
- `scripts/build_trial_demo_v2.py`
- `scripts/report_trial_demo_v2.py`
- `configs/expectations/synthetic_demo_v2.json`

**These are test fixtures. None of this is a real follow-up scan.**

## Fixture construction

Each of the seven follow-ups is a `SYNTHETIC_PERTURBATION` of one real baseline PET
(PETCT_0011f3deaf):

- **Identity:** new UIDs; same frame of reference within the synthetic case.
- **Labels:** `SYNTHETIC_PERTURBATION` in DICOM; `ImageComments` states "NOT a real follow-up
  scan".
- **CT:** the baseline CT, **copied unchanged**. Pixels and geometry are identical; only the
  UIDs change. It is labelled `SYNTHETIC_PERTURBATION CT_COPIED_UNCHANGED_FROM_BASELINE`.
- **Manifest:** `synthetic_fixture.json` records the labels, the perturbation, the parent case,
  the parent PET content hash, and the CT geometry and pixel hashes.
- **Copy verification:** the builder verifies the copied CT is hash-identical to the parent
  CT.

Original data, v1 fixtures and the production review file are not modified. The v2 trial reads
`trial_demo/reference_review.yaml` read-only.

## `SYNTHETIC_INHERITED_REFERENCE`

**No human review is fabricated for a synthetic follow-up.** It may inherit the parent's
human-accepted region geometry, unchanged, only when every one of these holds:

1. it is declared synthetic in `trial.yaml` and carries the DICOM label and fixture manifest;
2. the inheritance is declared in `trial.yaml` (`synthetic_reference_inheritance`), and the
   declared parent is the parent recorded in the fixture manifest;
3. the parent PET content hash matches;
4. the CT geometry and pixel hashes match (child = parent = manifest);
5. the parent region is `COMPUTED` from a valid human ACCEPT/ADJUST review, or was supplied.

**Result:**
- **Status:** `SYNTHETIC_INHERITED_REFERENCE`, never `COMPUTED` and never "ACCEPTED".
- **Measurement:** on the synthetic PET at the parent's exact geometry.
- **Provenance:** the parent key, the source review hash, the parent proposal hash, and the CT
  hashes.

**Rules:**
- **Synthetic pairs only:** rules accept it only on a synthetic pair.
- **Real scans:** inheritance on a real scan is `INHERITANCE_REFUSED`, and an inherited region
  offered for a real scan is rejected (`REFERENCE_INHERITANCE_REFUSED`).
- **Human review is unchanged:** the production human-review workflow is the only route to a
  usable reference on real data.

## Frozen expectations

`configs/expectations/synthetic_demo_v2.json` (sha256 `603df5ef…b029`) was committed in
`b0baa07` before the first v2 audit. It declares, for every pair and every rule set:

- the expected verdict;
- every rule's PASS/FAIL/UNKNOWN status;
- the liver numerics.

Liver numeric expectations:
- delta 0 for pixel-identical follow-ups;
- ×2^(1800/6586.2) = 1.20857 for the 30-minute injection shift;
- for the blur: |delta| < 0.05 SUL, with liver SD, lesion SUVmax and lesion SUVpeak all
  decreasing.

The first audit run matched the manifest with **0 mismatches**.
