# Reconstruction attestation policy (research; NOT enabled)

RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.

**Question:** may a site-supplied protocol record or signed reconstruction attestation
(`ReconstructionAttestation`, trust LEVEL_C; see `docs/reconstruction_audit_168.md`) satisfy
baseline/follow-up protocol identity?

**Status: research only.**
- No rule imports the trust model, and VT-PROTOCOL-IDENTITY is unchanged.
- ACRIN-NSCLC-FDG-PET-168 stays NOT_ESTABLISHED / UNKNOWN.

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
