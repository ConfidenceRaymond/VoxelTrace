# Reconstruction attestation policy (QIBA-only path implemented; EANM/PERCIST not enabled)

RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.

**Question:** may a site-supplied protocol record or signed reconstruction attestation
(`ReconstructionAttestation`, trust LEVEL_C; see `docs/reconstruction_audit_168.md`) satisfy
baseline/follow-up protocol identity?

**Status (updated 2026-10-08): QIBA-only evidence path implemented; see "Implementation"
below.**
- EANM and PERCIST are unchanged and never read attestations.
- No attestation exists for any real subject.
- ACRIN-NSCLC-FDG-PET-168 stays NOT_ESTABLISHED / UNKNOWN under all three rule sets.

**Classifications:**

| Class | Meaning |
|---|---|
| SUPPORTED_BY_STANDARD | the text explicitly accepts such records |
| SUPPORTED_WITH_INTERPRETATION | the text implies it but does not say it |
| NOT_SUPPORTED | the text excludes it |
| UNCLEAR | the text is silent |

No permission is inferred beyond the quoted text.

## Sources read (full text)

| Rule set | Document | Retrieved |
|---|---|---|
| qiba-fdg-1.14 | QIBA Profile *FDG-PET/CT as an Imaging Biomarker Measuring Response to Cancer Therapy*, v1.14 (Nov 18 2016, updated Jun 15 2023). https://qmic.org/wp-content/uploads/2025/11/QIBA_FDG-PET_Profile_v114.pdf | PDF, full text |
| eanm-fdg-2.0 | Boellaard R et al. *FDG PET/CT: EANM procedure guidelines for tumour imaging: version 2.0*. EJNMMI 2015;42:328–354. https://snmmi.org/common/Uploaded%20files/Web/Clinical%20Practice/Procedure%20Standards/2018/2015_GL_PET_CT_TumorImaging_V2.pdf (also PMC4315529) | PDF, full text |
| percist-1.0 | Wahl RL et al. *From RECIST to PERCIST*. J Nucl Med 2009;50(Suppl 1):122S–150S. https://jnm.snmjournals.org/content/jnumed/50/Suppl_1/122S.full.pdf | PDF, full text |

**Not retrieved, so not used:**
- the QIBA conformance self-attestation form (qibawiki link returned HTML, not the PDF);
- QIBA v1.13 PDF (same);
- EANM guideline v3.0 (2025), which is not the rule set version used here.

## QIBA FDG-PET/CT v1.14: **SUPPORTED_BY_STANDARD** (as a metadata source; scope caveats below)

**Identity requirement:**
- "For consistency, clinical trial subjects should be imaged on the same device over the entire
  course of a study" (lines 388–389).
- "The follow up scans should be performed with identical acquisition parameters as the first
  (baseline), inclusive of all the parameters required for both the CT and PET acquisitions"
  (397–398).
- Resolution recovery / TOF "should be consistent for a given subject across multiple time
  points" (971–973).

**Parameters:**
- Study Sponsor: "The key PET reconstruction parameters (algorithm, iterations, smoothing, field
  of view, voxel size) shall be specified."
- Technologist: these "shall be followed and set as specified" (§3.3.1 table after line 560).

**Non-DICOM records are explicitly accepted as the evidence source:**
- "The actual details of imaging for each subject at each time point should always be
  recorded" (429–430).
- "Baseline level … compliance requires that the DICOM image set … and necessary metadata (that
  is not currently captured by all PET scanner acquisition processes) is captured in trial
  documentation, e.g., case report forms" (934–939).
- Appendix E (1455–1462): the capture mechanism "ranges from paper notes, to scanned forms or
  electronic data records, to direct entry … into pre-specified DICOM fields". The fields to be
  recorded include "Protocol specific … PET … Reconstruction method" (2.a.iv) and software
  version numbers (1.d).
- Facility qualification must be documented, with "forms, checklists or other process
  documents" presented on request (681–684).

**Scope caveats** (VoxelTrace must not over-read):
1. Appendix E lists only "Reconstruction method". The full key parameter set (iterations,
   smoothing, FOV, voxel size) appears as sponsor-specified parameters in §3.3.1. An attestation
   should therefore state the full §3.3.1 set, not only a method name.
2. The profile accepts records as the **capture mechanism for metadata**. It defines no
   attestation format, signer role or verification procedure. The `ReconstructionAttestation`
   schema (source document, attestor, sha256 of attachment, rule applicability) is a VoxelTrace
   design choice.
3. Accepted records establish what was *recorded*, not that the scanner applied it. QIBA relies
   on site qualification and QC for the latter.

**Implication if enabled later:** a QIBA-scoped attestation for **both** timepoints stating the
§3.3.1 parameters could resolve VT-PROTOCOL-IDENTITY UNKNOWN → PASS_WITH_WARNING. A mismatch
would give FAIL. Not enabled.

## EANM FDG PET/CT v2.0: **UNCLEAR** (silent on the form of evidence)

**Identity requirement:** "the use of the same PET/CT system and identical acquisition and
reconstruction settings should be applied when making multiple examinations in the same
patient" (Procedure, patient preparation / uptake interval section). The uptake interval must be
the same "to within 10 min".

**Records:**
- The guideline asks that the uptake interval be "recorded".
- For reports: "Routine processing parameters are usually not stated in the report, but any
  special circumstances requiring additional processing … should be described."
- It names no record type (protocol export, site document, attestation) as evidence that
  reconstruction settings were identical. **The text is silent.**

**EARL:**
- The guideline relies on EARL accreditation and "EARL-approved reconstruction settings" for
  harmonised quantification (Image reconstruction section; EARL SOPs).
- EARL accreditation is an external, documented programme. A record that both scans used the
  site's EARL-accredited reconstruction could be argued to support **EANM-EARL-RECON**.
- That is **SUPPORTED_WITH_INTERPRETATION at most**, and only for EANM-EARL-RECON. It is not
  general protocol identity, and EANM v2.0 does not say so.

**Implication:** VoxelTrace should not accept a generic attestation for EANM-SAME-SYSTEM-SETTINGS
on the strength of this guideline alone. Any EANM policy is a VoxelTrace/trial-sponsor decision
and must be labelled as such.

## PERCIST 1.0: **UNCLEAR** (silent)

**Identity requirement:**
- "Same scanner, or same scanner model at same site, injected dose, acquisition protocol (2- vs.
  3-dimensional), and software for reconstruction, should be used. Scanners should provide
  reproducible data and be properly calibrated" (Table 7, PERCIST 1.0 column).
- Also: "Absolute and rigorous standardization of the protocol for PET is required to achieve
  reproducible SUVs" (text).

**Records:**
- The PERCIST 1.0 column says only that exploratory lesion parameters "can be recorded".
- It does **not** state how acquisition/reconstruction identity is evidenced.
- The documentation items next to it in Table 7 ("Coregistration method should be recorded",
  etc.) belong to the **EORTC** column and are not PERCIST requirements.

**Note:** PERCIST's literal reconstruction requirement is coarser than VoxelTrace's:
- PERCIST asks for the same scanner (or model at the same site), the same 2D/3D acquisition and
  the same **reconstruction software**.
- VT-PROTOCOL-IDENTITY is a VoxelTrace prerequisite (not a PERCIST rule). It also asks for
  method, iterations, subsets, filter, TOF and PSF.

That difference is documented here, not acted on. Thresholds and rules are unchanged.

## Summary

| Rule set | Classification | Basis | Enable? |
|---|---|---|---|
| QIBA FDG 1.14 | **SUPPORTED_BY_STANDARD** (as a metadata source) | §3.1 / §4.2 lines 934–939, Appendix E: trial documentation, paper/scanned/electronic records accepted for metadata incl. reconstruction method | Candidate for a future, explicitly versioned rule change, LEVEL_C → PASS_WITH_WARNING, both timepoints, full §3.3.1 parameter set |
| EANM FDG 2.0 | **UNCLEAR** | requires identical settings; silent on evidence form. EARL-accredited recon record arguably relevant to EANM-EARL-RECON only (interpretation) | No, unless the trial sponsor defines it |
| PERCIST 1.0 | **UNCLEAR** | requires same scanner/model/site, 2D/3D, reconstruction software; silent on evidence form | No, unless the trial sponsor defines it |

**Not decided here (user decisions before any wiring):**
1. Whether to enable LEVEL_C for QIBA only.
2. Which attestor roles are acceptable (site physicist, imaging core lab).
3. Whether a trial imaging charter can stand in for per-scan records.
4. Whether `confidence: BELIEVED` is ever acceptable. The recommendation is no.

## Implementation (QIBA only)

| Piece | Location |
|---|---|
| Schema, loading, validation | `src/voxeltrace/evidence/attestation.py` (`voxeltrace.recon-attestation/2`) |
| QIBA rule variant | `src/voxeltrace/rules/qiba_identity.py`; wired in `rules/registry.py` for `qiba-fdg-1.14` only |
| Audit wiring | `trial/audit.py` (`attestations_file=` or trial.yaml `recon_attestation_file`; explicit only, never picked up by default) |
| Report | `trial/summary.py` `attestation_rows`, AUDIT_REPORT.md section, `reconstruction_attestations.csv`, app page `5_Reconstruction_Evidence.py` (report only) |
| Tests | `tests/test_qiba_attestation.py` |

**Attestor roles:**

| Role | Accepted? |
|---|---|
| QUALIFIED_PET_PHYSICIST | yes |
| NUCLEAR_MEDICINE_PHYSICIST | yes |
| IMAGING_CORE_QC_LEAD | yes, only with documented PET QC responsibility |
| SITE_PET_TECHNOLOGIST | only if countersigned by one of the above (not self) |
| INVESTIGATOR, RADIOLOGIST, STUDY_COORDINATOR, VENDOR_REPRESENTATIVE, OTHER | rejected |
| UNSIGNED_NOTE source | rejected |
| missing attestor or series binding | schema error |
| `confidence: BELIEVED` | rejected |

**Charter policy:**
- A `TRIAL_IMAGING_CHARTER` source without a charter binding (site, scanner model, software or
  period, scan-level applicability) is `EXPECTED_PROTOCOL_ONLY` and never establishes
  identity.
- The same applies to a bound charter without a hash-bound scan-level corroborating source
  (SCANNER_PROTOCOL_EXPORT, SITE_PROTOCOL_RECORD or SIGNED_ATTESTATION).

**Binding and staleness:** every source and corroborating document is sha256-bound.

| Condition | Result |
|---|---|
| Edited document | STALE |
| Missing document | INVALID |
| Different study or series UID than the audited PET | STALE |
| Different manufacturer, model or software than the audited PET | STALE |
| Wrong subject or timepoint | INVALID |
| Scan facts unverifiable | INVALID |
| Simulated record in a production audit | INVALID |

**Rule behaviour (VT-PROTOCOL-IDENTITY under qiba-fdg-1.14 only):**

| Situation | Check status | PROTOCOL_IDENTITY |
|---|---|---|
| no attestation supplied | unchanged; byte-identical to the shared rule | ESTABLISHED / NOT_ESTABLISHED / CONTRADICTED from PASS / UNKNOWN / FAIL |
| DICOM unknown only for reconstruction parameters, and VALID in-scope attestations at both timepoints fill every one with equal values | **PASS_WITH_WARNING** | **ESTABLISHED_WITH_WARNING** |
| attested values differ between timepoints, attestation vs DICOM differ, or two attestations disagree | FAIL | CONTRADICTED |
| non-reconstruction unknowns (units, voxel size, corrections), one timepoint only, incomplete, stale, invalid or out of scope | UNKNOWN | NOT_ESTABLISHED |

**When an attestation is used,** the check carries:
- attestation IDs, source sha256, attestor role and trust level (LEVEL_C);
- reason `EXTERNAL_RECONSTRUCTION_ATTESTATION`;
- rule version suffix `+qiba-attestation-1`;
- the warning **EXTERNAL RECONSTRUCTION ATTESTATION USED**.

The verdict can then be at most ASSESSABLE_WITH_WARNINGS, never ASSESSABLE.

**168 dry run** (`scripts/dry_run_qiba_attestation_168.py`): this used SIMULATED placeholder
values in a temporary directory, deleted afterwards. The summary is at
`../outputs/dry_runs/qiba_attestation_168_summary.json` and contains no attestation.

| Check | Result |
|---|---|
| Production mode | refuses the simulated records |
| Test mode, QIBA | `INSUFFICIENT_INFORMATION / NOT_ESTABLISHED` → `ASSESSABLE_WITH_WARNINGS / ESTABLISHED_WITH_WARNING` |
| Test mode, EANM and PERCIST | byte-identical, still INSUFFICIENT_INFORMATION |

Regenerating the real 168 audits with the new code reproduces every pair, check, CSV and
report byte-for-byte.
