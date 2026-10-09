# Design partner program

## Ideal partner

- Holds a **multicentre PET dataset with a quantitative endpoint** (FDG; SUV-based).
- Willing to run VoxelTrace locally or share a **retrospective, de-identified** dataset under
  a written agreement.
- Has **PET physics expertise** able to adjudicate verdicts and review reference regions and
  lesion targets.
- Multiple sites and scanners preferred, ideally including GE or Philips. This is the
  biggest validation gap (`../vendor_validation_matrix.md`).
- Can give an hour of feedback at three points: intake, first report, final review.

## What the partner receives

- A comparability audit of an agreed study (scope per `pilot_scope_template.md`):
  - per-pair verdicts under the chosen rule sets;
  - reasons, drift events and a site rollup;
  - draft site queries.
- Findings: a summary of what blocks quantitative interpretation, and what a re-export or a
  site attestation could recover.
- The immutable evidence bundle, its verification report, and PDF/CSV/JSON reports.
- A summary workshop (about 60 min) with the partner's physicists and operations staff.
- Influence over rule packs, outputs and workflow priorities.

## What VoxelTrace needs from the partner

- **Feedback:** usefulness of outputs, wording of reasons and site queries, and workflow fit.
- **Expert adjudication:** the partner's physicists review disputed verdicts and every
  NOT_ASSESSABLE / INSUFFICIENT_INFORMATION call. A partner adjudication is recorded as the
  partner's, never as VoxelTrace's.
- **Workflow timing:** time spent on intake, review and report reading, compared with their
  current process.
- **False-safe review:** explicit review of every pair VoxelTrace calls ASSESSABLE*, to find
  any the partner would not accept. This is the most important safety input.
- **Aggregate statistics:** permission to use aggregate, non-identifying validation
  statistics, **only where agreed in writing** (for example verdict distribution or
  agreement rates).

## Not assumed

- No publication rights, co-authorship, data ownership or reuse beyond the agreed study.
- No right to name the partner publicly without written consent.
- No exclusivity in either direction unless agreed.
- No fees or payments are implied by this document.

## Program steps

1. NDA, then a discovery call (`customer_discovery_plan.md`).
2. DUA or a local-run agreement; scope signed.
3. Intake (`validate-input`), then an acceptance or re-export decision.
4. Audit; partner reviews (reference, lesion, adjudication); re-run.
5. Report walkthrough and feedback session; false-safe review.
6. Final delivery; deletion confirmation; a short written retrospective (what worked, what
   did not, would they pay, who would).

## Partner status

**None yet.** Gate 1 (design-partner readiness) is met on the software side. No partner has
been approached.
