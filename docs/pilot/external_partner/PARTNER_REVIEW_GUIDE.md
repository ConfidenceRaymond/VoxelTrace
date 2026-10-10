# Review guide for the partner's PET physicist

Your judgement is the reference in this pilot. VoxelTrace records nothing on your behalf, and
your decisions never overwrite its automated verdicts; both are reported side by side so
disagreements stay visible.

Start with `unresolved_items.csv` (what is waiting and who can resolve it) and
`pair_evidence_trace.csv` (why each verdict was given). With VoxelTrace installed,
`voxeltrace explain-pair <evidence_bundle> --subject <SUBJ>` prints the same trace per pair.

## 1. Reference regions (PERCIST liver / blood pool)

VoxelTrace proposes regions deterministically from the CT; they count only after you accept them.

For each proposal (QC image + proposal hash on the Reference Review page or worksheet):
- Is the sphere entirely in normal liver parenchyma (right lobe), away from lesions, vessels,
  edges and artefacts? Blood pool: within the descending aorta lumen, away from the wall?
- Is it on the PET of the stated timepoint (check the subject/timepoint label)?
- Record **ACCEPT**, **ADJUST** (give a new centre) or **REJECT**, with your identifier.
- A review is bound to that exact proposal; if the proposal changes it becomes OUTDATED and must
  be repeated.

## 2. Lesions (PERCIST targets)

- Only supplied segmentations are shown; VoxelTrace does not segment or pick targets.
- For each segment: is it a lesion (not physiological uptake), on the right scan, and is the mask
  acceptable for SULpeak? Record ACCEPT / REJECT / REJECT_AND_REPLACE_REQUIRED.
- Reviews are bound to the mask hash; a changed mask needs a new review.

## 3. Reconstruction evidence

In `pair_results.csv`, the `reconstruction_evidence` column says how reconstruction identity
was established:

| Value | Meaning | What to check |
|---|---|---|
| STRUCTURED (LEVEL_A) | standard DICOM attributes | spot-check against the site protocol |
| FREE_TEXT (LEVEL_D) | parsed from vendor text (e.g. `PSF+TOF 2i21s`) | does the text really encode the parameters? |
| ATTESTED (LEVEL_C) | a signed site attestation (QIBA only, verdict carries a warning) | is the attestation credible and scan-specific? |
| **TEXT_IMPLIED** | a parameter is not encoded and was judged identical only because the text is identical | **see section 4** |
| NOT_ESTABLISHED | a parameter is not encoded and there is no identical text; identity is not established (the pair is usually INSUFFICIENT_INFORMATION or NOT_ASSESSABLE) | is the parameter available from the site? |

## 4. TEXT_IMPLIED cases

Treat every TEXT_IMPLIED `ASSESSABLE` / `ASSESSABLE_WITH_WARNINGS` verdict as **unconfirmed**
until you have answered the questions in
[TEXT_IMPLIED_REVIEW_PACKET.md](TEXT_IMPLIED_REVIEW_PACKET.md). If you have the site protocol,
check the parameter directly.

## 5. INSUFFICIENT_INFORMATION cases

For each `INSUFFICIENT_INFORMATION` pair, the reason codes say what is missing. Please judge:
- **Is the missing evidence really needed?** If you would compare the pair without it, say so
  (possible false-unsafe result); if you agree it is needed, say so.
- **Can it be obtained?** re-export, site records, attestation, or your review (the
  `remediation_matrix.csv` columns show which apply).
- **Would the pair be comparable if obtained?** Your prediction helps calibrate the rules.

Record each judgement on the [PILOT_FEEDBACK_FORM.md](PILOT_FEEDBACK_FORM.md). Please flag any
`ASSESSABLE` verdict you consider not comparable as a **false-safe concern** first: it is the
most important feedback you can give.
