# README FIRST: VoxelTrace Retrospective PET Comparability Audit

**For:** a design partner (imaging core lab, CRO imaging group, sponsor or academic PET centre)
considering a retrospective pilot.

**RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.** VoxelTrace does not assess treatment
response, diagnose, or replace a physicist's or reader's judgement.

## 1. What VoxelTrace does

VoxelTrace answers one question before anyone interprets an SUV change:

> Are these PET scans, across timepoints, sites, scanners and reconstruction protocols,
> comparable enough for the SUV change to mean something?

For every baseline/follow-up pair it returns one of four verdicts per rule set (QIBA FDG 1.14,
EANM FDG 2.0, PERCIST 1.0), with the exact rule, DICOM field and evidence behind it:

| Verdict | Meaning |
|---|---|
| `ASSESSABLE` | The evidence supports interpreting SUV change under this rule set |
| `ASSESSABLE_WITH_WARNINGS` | As above, with listed caveats (e.g. reconstruction identity from a signed site attestation) |
| `NOT_ASSESSABLE` | A criterion was decided and not met (e.g. uptake time outside the window). A re-export cannot change it |
| `INSUFFICIENT_INFORMATION` | Evidence is missing. **Never treated as a pass.** The reason codes say what is missing and who can supply it |

The audit is deterministic: the same data and software version give the same verdicts. No
AI model is involved in any verdict, measurement or recommendation.

## 2. What to send

A de-identified copy, under a data-use agreement, of:

- **One attenuation-corrected PET series per visit** (DICOM PET Image Storage, Units = BQML).
- **The CT acquired with it** (same frame of reference), if available. Needed only for
  reference-region proposals (PERCIST).
- **Lesion segmentations** (DICOM SEG) if you want PERCIST target evidence; optional.
- **A visit list**: which folder is baseline and which is follow-up, and which site each
  subject belongs to. A spreadsheet is enough.
- **Optional:** scanner protocol sheets or reconstruction attestations for sites whose DICOM
  omits reconstruction settings.

Folder layout: either `<subject>/<timepoint>/...` or `<site>/<subject>/<timepoint>/...`. Any
sub-folder structure below the timepoint is fine. Extra files (PDFs, notes, other series) are
listed and ignored; nothing in your folder is modified.

### De-identification that keeps the audit possible (DICOM PS3.15 options)

- Retain patient characteristics: **weight, height, sex** (SUV and SUL need them).
- Retain device identity: **manufacturer, model, software version**.
- Retain longitudinal temporal information: **injection and scan times on the same clock**
  (shifted dates are fine if shifted consistently within a subject).
- Keep the **Radiopharmaceutical Information Sequence** (injected activity, half-life,
  injection time).

## 3. What NOT to send

- Patient names, MRNs, accession numbers, dates of birth, addresses, or any direct identifier.
- Subject folder names that are real identifiers. Use pseudonyms (they appear in the reports).
- Screen captures, MIPs, movies, or NIfTI-only data (not quantitative input).
- Data you are not authorised to share under your data-use agreement.

## 4. What it checks

1. **Intake** (`validate-input`, `intake-map`): how your folders were interpreted, which PET
   series was selected and why (only three deterministic rules; ambiguity is held back as
   `NEEDS_REVIEW`, never guessed), what was ignored.
2. **Preflight**: whether each scan can be quantified as exported.
3. **Strict SUV validation**: refuses to compute SUV if any required input is missing or
   inconsistent.
4. **Protocol evidence**: scanner, software, reconstruction, corrections, timing, each with a
   trust level (structured DICOM attribute vs. vendor free text vs. site attestation).
5. **Pair rules**: the three published rule sets, each rule versioned.
6. **Longitudinal pairing safety**: duplicate visits, the same scan under two visits or two
   subjects, visit-order anomalies, inconsistent patient identifiers (compared as hashes).
7. **Site and scanner rollup, protocol drift.**

## 5. What you receive

A delivery package (built by `voxeltrace deliver`), containing only derived outputs:

| File | What it is |
|---|---|
| `README_FIRST.md` | This dataset's status, counts and how to read the package |
| `executive_summary.pdf` / `.json` | One page: readiness, comparability, top issues, sites requiring action, unresolved review |
| `unresolved_items.csv` | Everything waiting on a site or a reviewer, and who can resolve it |
| `recommended_site_queries/` | DRAFT queries to your sites (VoxelTrace never sends anything) |
| `pair_results.csv` | Every pair and rule set; `pairing_status` must be `OK` before a verdict is used |
| `site_summary.csv`, `scan_preflight.csv`, `protocol_drift.csv` | Detail by site, scanner, scan |
| `remediation_matrix.csv` | Each reason code: meaning, and whether re-export, site records or human review can fix it |
| `evidence_bundle/` | The immutable audit record (checksummed) |
| `pilot_acceptance.json` | Machine-readable pilot status (VT-PILOT-ACCEPTANCE-1) |
| `methodology_and_limitations.md`, `software_version.txt` | Method, validation status, versions |

No DICOM, pixel data, patient identifiers or local file paths. Every package passes an
automated pattern scan for identifiers, paths, e-mail addresses and secrets before it is
released (a safety net, not a de-identification method).

## 6. What requires human review

VoxelTrace **never records a review decision**. These items stay `INSUFFICIENT_INFORMATION`
until a qualified person (PET physicist / nuclear medicine physician / core-lab QC lead)
records a decision:

- liver / blood-pool reference regions proposed by VoxelTrace (PERCIST);
- lesion segmentations used as PERCIST targets;
- pairing items marked `NEEDS_REVIEW` (e.g. two visits on the same day);
- optional pair adjudications (recorded separately; automated verdicts are never changed).

## 7. Current validation status (be aware before you rely on it)

- **External expert validation is PENDING.** No independent PET physicist has yet compared
  VoxelTrace verdicts with their own; a blinded validation package is frozen at tag
  `v0.3.0-external-validation`.
- **Vendor coverage:** Siemens scanners validated on real public longitudinal pairs; GE
  validated for ingestion only (no independent quantitative check); Philips metadata only.
  Non-Siemens data may legitimately receive `INSUFFICIENT_INFORMATION` where vendor timing
  semantics are not documented. That is a limitation, not a finding about your data.
- **No real pair has a complete PERCIST verdict** without human reference-region and lesion
  review.
- Not supported: non-FDG tracers (reported `UNSUPPORTED`), PET/MR, brain PET quantification,
  long-axial-FOV systems.

## 8. Limitations

- Integrity checks prove the delivered files match their checksums; they are not a digital
  signature.
- Without declared sites, "drift" compares different centres; please send the site list.
- Rule thresholds follow the cited guidelines and are not tuned to your data.
- Results describe the evidence in the export you supplied; a better export can change
  `INSUFFICIENT_INFORMATION`, never `NOT_ASSESSABLE`.

## 9. How to verify a delivered package

With VoxelTrace installed:

```bash
voxeltrace verify-delivery <package>
```

This checks every file against `DELIVERY_CHECKSUMS.sha256`, re-verifies `evidence_bundle/`
and repeats the privacy scan. Expected: `"status": "OK"`.

Without VoxelTrace (any Linux/macOS shell):

```bash
cd <package> && sha256sum -c DELIVERY_CHECKSUMS.sha256
cd evidence_bundle && sha256sum -c checksums.sha256
```

## 10. How the operator runs it

```bash
# nested drop (site/subject/timepoint): map, review, stage
voxeltrace intake-map <drop> --out intake_mapping.json --stage <trial> --trial-id <ID>
# or a <subject>/<timepoint> folder directly:
voxeltrace run-pilot --input <trial> --output <work> [--trial-id <ID>]
voxeltrace verify-delivery <work>/delivery_package
```

`run-pilot` exit codes: 0 audit complete (review may be pending), 1 audit blocked, 2 needs
re-export / usage error, 3 unsupported. Details: [pilot_workflow.md](pilot_workflow.md).
