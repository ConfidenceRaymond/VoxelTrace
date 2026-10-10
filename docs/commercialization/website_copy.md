# Website copy (draft)

**Words this site never uses:**
- "AI diagnoses";
- "clinically validated";
- "FDA approved" or "cleared";
- "guarantees comparability";
- customer logos or testimonials (none exist).

Every page footer reads: *Research software. Not a medical device. Independent external
validation in progress.*

---

## HOME

**Quantitative trust for PET imaging.**

Know whether your PET scans can be compared, before you interpret a change in SUV.

VoxelTrace checks every baseline and follow-up scan across timepoints, sites, scanners and
reconstruction protocols against the standard your trial follows (QIBA, EANM or PERCIST). It
tells you which pairs are comparable, which are not, and exactly what is missing when the
data cannot decide.

[See how it works] [Talk to us about a retrospective audit]

---

## PRODUCT

**VoxelTrace Retrospective PET Comparability Audit.**

- **Preflight:** every scan's quantitative prerequisites, including units, decay correction,
  dose, timing, patient factors, reconstruction and CT alignment.
- **Strict SUV/SUL:** computed only when the headers support it; otherwise refused, with the
  reason.
- **Protocol fingerprints and drift:** see when a site's scanner, software or reconstruction
  changed.
- **Pair comparability:** a verdict per pair under QIBA FDG-PET/CT 1.14, EANM FDG 2.0 or
  PERCIST 1.0 (ASSESSABLE / ASSESSABLE_WITH_WARNINGS / NOT_ASSESSABLE /
  INSUFFICIENT_INFORMATION), each with reasons.
- **Human review where it matters:** reference regions and lesion targets count only after a
  qualified reviewer accepts them.
- **Evidence bundle:** every result is traceable to the exact inputs, rules and versions, and
  checksum-verified.

What it does not do: diagnose, classify treatment response, segment lesions as ground truth,
harmonize images, or make clinical decisions.

---

## HOW IT WORKS

1. **Intake.** Point VoxelTrace at a de-identified study. It reports which scans can be
   audited and what needs re-export.
2. **Configure.** Choose the rule set and timepoint order, and add your site map.
3. **Audit.** Deterministic checks run per scan and per pair. The same input always gives the
   same result.
4. **Review.** Your physicists confirm reference regions and lesion targets, and adjudicate
   disputed pairs.
5. **Report.** An executive summary, pair tables, site rollup, draft site queries, a PDF and
   a verifiable evidence bundle.

---

## FOR CORE LABS

- See protocol drift by site before it reaches your endpoint reads.
- Turn "we can't tell" into a specific, actionable site query.
- Keep one auditable record of why each pair was accepted, flagged or excluded.
- Runs on your own workstation: your data does not need to leave your environment.

---

## FOR RADIOPHARMA

- An independent check that the quantitative PET behind your endpoint is comparable across
  sites and timepoints.
- Explicit, source-cited rules: QIBA, EANM and PERCIST, each with versions.
- Findings you can discuss with your core lab: verdicts, reasons and evidence, not opinions.

---

## VALIDATION

We say exactly where we are.

- Tested on 9 real public longitudinal PET/CT pairs from 4 collections and 6 scanner models,
  and on synthetic perturbation fixtures. Over 700 automated tests.
- Comparability checks have been audited end to end on several Siemens scanner models (public data). Quantitative checks
  on GE and Philips are **not yet validated**.
- **Independent external expert validation is pending.** A blinded physicist study is
  prepared but no reviewer has returned a form yet, and no agreement result exists yet. We will publish the method and results when
  complete.
- Known limitations are documented and shipped with every version.

---

## SECURITY / LOCAL-FIRST

- Runs locally by default. The audit makes no network calls and uses no AI model.
- Input file paths are pseudonymised in evidence bundles. Bundles are checksum-verified, and
  review logs are hash-chained.
- No images are included in reports or bundles.
- We do not claim certification against any security or privacy framework.

---

## RESEARCH

VoxelTrace grew from research on quantitative PET reproducibility. The research core is open
source (MIT). Rules cite their sources: QIBA FDG-PET/CT Profile 1.14, EANM FDG PET/CT
guideline 2.0 and PERCIST 1.0.

---

## CONTACT

Interested in a retrospective comparability audit of a completed multicentre PET study, or in
becoming a design partner? Tell us about your study (no patient data, please).

[Contact form: name, organisation, role, study type, message]
