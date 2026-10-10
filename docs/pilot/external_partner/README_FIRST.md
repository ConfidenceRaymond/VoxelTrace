# VoxelTrace first external pilot: README FIRST

**RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.** VoxelTrace is research and trial-QC
software. It has no regulatory clearance and must not be used for patient care.

This folder is the intake package for a first retrospective pilot with an external design
partner. Full list with descriptions: [PARTNER_PACKET_INDEX.md](PARTNER_PACKET_INDEX.md). Read it in this order:

| # | Document | For |
|---|---|---|
| 1 | this file | everyone |
| 2 | [DATA_REQUIREMENTS.md](DATA_REQUIREMENTS.md), [partner_intake.yaml](partner_intake.yaml) | the person preparing the export |
| 2b | [GE_PHILIPS_DATA_REQUEST.md](GE_PHILIPS_DATA_REQUEST.md) | partners with GE or Philips scanners |
| 3 | [TRANSFER_CHECKLIST.md](TRANSFER_CHECKLIST.md) | data manager / IT |
| 4 | [PILOT_SCOPE_TEMPLATE.md](PILOT_SCOPE_TEMPLATE.md) | both parties, signed off before transfer |
| 5 | [PARTNER_REVIEW_GUIDE.md](PARTNER_REVIEW_GUIDE.md) | the partner's PET physicist |
| 6 | [TEXT_IMPLIED_REVIEW_PACKET.md](TEXT_IMPLIED_REVIEW_PACKET.md) | the partner's PET physicist (first scientific question) |
| 7 | [PILOT_DELIVERY_CHECKLIST.md](PILOT_DELIVERY_CHECKLIST.md) | what you receive |
| 8 | [PILOT_FEEDBACK_FORM.md](PILOT_FEEDBACK_FORM.md) | after delivery |
| — | [FIRST_PILOT_RUNBOOK.md](FIRST_PILOT_RUNBOOK.md), [EXTERNAL_PILOT_GATE.md](EXTERNAL_PILOT_GATE.md) | VoxelTrace operator (internal) |

## What VoxelTrace does

Before anyone interprets an SUV change, VoxelTrace checks whether the PET scans being compared
(across timepoints, sites, scanners and reconstruction protocols) are **comparable enough for
that change to mean something**. For each baseline/follow-up pair and each rule set (QIBA FDG
1.14, EANM FDG 2.0, PERCIST 1.0) it returns:

| Verdict | Meaning |
|---|---|
| `ASSESSABLE` | the evidence supports interpreting SUV change under this rule set |
| `ASSESSABLE_WITH_WARNINGS` | as above, with stated caveats |
| `NOT_ASSESSABLE` | a criterion was decided and not met (e.g. uptake time outside the window) |
| `INSUFFICIENT_INFORMATION` | required evidence is missing; never treated as a pass |

Every verdict links to the rule, the DICOM field, its value at both timepoints, how far that
value can be trusted, and what would resolve it. The audit is deterministic (same data and
version give the same result) and uses no AI model.

## Current status and limitations (please read)

- **External expert validation is pending.** No independent PET physicist has yet compared
  VoxelTrace's verdicts with their own. Your physicist's review in this pilot is part of that
  evidence.
- **Vendor coverage:** Siemens scanners have been validated on real public longitudinal pairs.
  GE has been validated for ingestion only, and Philips for metadata only. Expect more
  `INSUFFICIENT_INFORMATION` on GE and Philips exports; that reflects a limit of VoxelTrace's
  validated scope, not a finding about your data.
- **Open scientific question (TEXT_IMPLIED):** when a reconstruction parameter (e.g. TOF) is not
  encoded, VoxelTrace currently treats identical reconstruction text on both scans as identical
  reconstruction. Such pairs are flagged `TEXT_IMPLIED`; see the review packet.
- **PERCIST** verdicts need human reference-region and lesion review; no real pair has a
  complete PERCIST verdict yet.
- Only FDG PET/CT. Non-FDG tracers, PET/MR, brain PET and long-axial-FOV systems are out of scope.
- Plausible but wrong header values (e.g. a mistyped weight) cannot be detected from DICOM.

## What you will receive

A delivery package of derived outputs only (no DICOM, no pixel data, no identifiers):
executive summary (PDF + JSON), pair table, site/scanner summary, unresolved items, reason and
remediation table, evidence trace, DRAFT site queries, the checksummed evidence bundle, a
verification report and a methodology/limitations note. See
[PILOT_DELIVERY_CHECKLIST.md](PILOT_DELIVERY_CHECKLIST.md).

## What requires human review (by your qualified staff)

- liver / blood-pool reference regions proposed by VoxelTrace (PERCIST);
- lesion segmentations used as PERCIST targets;
- pairing questions (e.g. two visits on the same day);
- every `TEXT_IMPLIED` verdict, and any verdict you disagree with.

VoxelTrace never records a review decision itself.

## What VoxelTrace does NOT do

- diagnose, stage, or assess treatment response;
- segment lesions or decide which lesion is a target;
- approve reference regions;
- change a verdict because of a review, attestation or adjudication (these are recorded beside it);
- send anything to your sites (site queries are drafts for you to edit and send);
- use AI for any measurement, verdict or review;
- de-identify your data (the export you send must already be de-identified).
