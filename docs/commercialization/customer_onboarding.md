# Customer onboarding: retrospective comparability audit pilot

This workflow is not legal advice. It does not claim compliance with HIPAA, GDPR, 21 CFR
Part 11, ICH GCP or any other framework; no such compliance has been established. The
customer's privacy, legal and QA functions decide what their data and processes require.

## 1. NDA / data-use agreement

- Execute a mutual NDA before any technical detail of the customer's trial is shared.
- Before any data moves, agree a data-use agreement (DUA) or equivalent. It covers:
  - the purpose (comparability audit of named studies only);
  - de-identification responsibility (the customer's);
  - permitted uses and prohibited re-identification;
  - storage location;
  - retention and deletion;
  - who may access the data;
  - whether aggregate, non-identifying statistics may be used (opt-in only; never assumed).
- **Preferred alternative: no data transfer.** The customer runs VoxelTrace locally and
  shares only outputs they choose (step 3).

## 2. Dataset requirements

- **Layout:** `<subject>/<timepoint>/<DICOM files>`. Subject folder names must be
  pseudonymous codes.
- **Modality:** FDG PET/CT. Known non-FDG tracers are UNSUPPORTED.
- **Retained header fields** (needed for a decidable result):
  - PatientWeight; PatientSize and PatientSex (for SUL);
  - RadionuclideTotalDose and RadiopharmaceuticalStartDateTime;
  - Series and Acquisition date/time;
  - Units = BQML, DecayCorrection, CorrectedImage;
  - reconstruction attributes;
  - the CT series in the PET frame of reference.
- **Where fields go missing:** de-identification profiles that strip patient characteristics
  or dates make pairs INSUFFICIENT_INFORMATION, not wrong. The intake report shows exactly
  which fields are missing.
- **Optional:** DICOM SEG lesion masks, a site/scanner map, site imaging manuals and signed
  reconstruction attestations.

## 3. Secure transfer: assumptions, not guarantees

| Option | Description |
|---|---|
| **A (default)** | Customer-run, local. VoxelTrace is installed on the customer's machine (`pip install` from the repository). No data leaves the customer. They share the evidence bundle, which carries pseudonymised paths and no images. |
| **B** | Encrypted transfer to an agreed, access-controlled workstation, under the DUA. The transfer method is chosen by the customer's IT. |

VoxelTrace makes no network calls during an audit. The optional explanation model is local
only and is never used by the audit.

## 4. Run `validate-input`

Run `voxeltrace validate-input <folder>` (or use the *Intake and Audit* page). The result is
per scan, with catalogued fixes:

- ACCEPT_FOR_AUDIT;
- ACCEPT_WITH_WARNINGS;
- NEEDS_REEXPORT;
- UNSUPPORTED.

## 5. Data acceptance or re-export decision

| Intake result | Decision (customer and VoxelTrace together) |
|---|---|
| ACCEPT_* | proceed |
| NEEDS_REEXPORT | the customer re-exports the listed fields, or accepts that the affected pairs will be INSUFFICIENT_INFORMATION |
| UNSUPPORTED | excluded from the pilot and listed in the scope |

Record the decision in the pilot scope (`pilot_scope_template.md`).

## 6. Audit configuration

- Run `voxeltrace init-trial <folder> --trial-id <id> --ruleset <ruleset>`. It sets the
  timepoint order from the folder layout.
- The customer supplies the site map. Sites are never guessed.
- Choose the rule set or sets per the trial charter. The audit always runs all three
  (QIBA 1.14, EANM 2.0, PERCIST 1.0); the scope names the one(s) that matter.
- Parameter overrides are allowed only where the charter differs. Each one is recorded in
  every output.

## 7. Processing

- Run `voxeltrace audit --input <trial> --output <new folder>`.
- Outputs are never overwritten. Every re-run goes to a new folder and produces a new bundle.
- Run `voxeltrace verify-bundle` on every bundle before it is shared.

## 8. Human review

Customer-nominated qualified reviewers record these decisions. VoxelTrace staff never record
customer decisions.

- Reference regions (liver, blood pool) on the Reference Review page.
- Lesion targets (PERCIST) on the Lesion Review page.
- Disputed pairs with `voxeltrace adjudicate`.

Then re-run the audit into a new folder.

## 9. Report review

- Hold a walkthrough of the executive summary, verdicts, top blocking reasons, drift events
  and draft site queries.
- The customer decides which site queries to send. VoxelTrace never sends them.

## 10. Final delivery

The delivery contains:

- the final evidence bundle;
- `verify-bundle` output;
- the PDF and CSV reports;
- a scope-completion note listing exclusions and unresolved items;
- the software version and tag, and the rule-bundle hash.

## 11. Retention and deletion confirmation

- Delete or return customer data at the end of the period agreed in the DUA.
- `voxeltrace data-inventory` lists what is held. Deletion itself is a deliberate,
  customer-confirmed action outside VoxelTrace, which never deletes anything.
- Send a written confirmation listing what was deleted, when, and what (if anything) is kept,
  such as the evidence bundle with the customer's consent.
