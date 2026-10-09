# Sample audit: DEMONSTRATION DATA

**DEMONSTRATION DATA. This is not a customer trial, and the verdicts are not findings about
any patient or site.**

**Source:**
- Trial `VOXELTRACE-DEMONSTRATION-AUDIT`: 9 subjects, 7 baseline/follow-up pairs, 16 scans.
- Baselines are real public de-identified PET/CT from IDC FDG-PET-CT-Lesions (DOI
  10.7937/gkr0-xv29, CC BY 4.0).
- Follow-ups are SYNTHETIC_PERTURBATION copies (identity, reconstruction blur,
  reconstruction metadata, uptake violation, missing dose, anonymization loss, correction
  mismatch). They are not real follow-up scans.
- Subject folders are relabelled DEMO-nn. Sites (SITE-A to SITE-D) are fictitious labels.

**Sanitisation, checked on 2026-10-09:**
- the bundle contains no public collection subject ID, no DICOM UID and no local path;
- input paths are recorded as sha256 only;
- review file locations are recorded as file names only;
- no image of any kind is included.

Reference-region decisions in this demo come from the development fixture's review file:
only its DEMO-* entries, unchanged. They are fixture data, not expert review.

| File | Content |
|---|---|
| `DEMO_EXECUTIVE_SUMMARY.md` | top page: counts, verdicts per rule set, top blocking reasons, recommendations |
| `DEMO_AUDIT_REPORT.pdf` | full report (byte-reproducible) |
| `DEMO_pair_verdicts_<ruleset>.csv` | pair verdict tables |
| `DEMO_subject_timepoint_matrix_qiba.csv` | subject × timepoint matrix |
| `DEMO_failure_reasons_qiba.csv` | failed / unknown checks with reasons |
| `DEMO_site_summary_qiba.json` | site, scanner, software and reconstruction rollup |
| `DEMO_drift_events.csv` | protocol drift events |
| `DEMO_evidence_bundle.zip` | the complete immutable evidence bundle (60 files) |
| `DEMO_verification_report.json` | `voxeltrace verify-bundle` output (status OK) |

**To regenerate:** `voxeltrace audit --input outputs/commercial_demo_audit/trial --output
<new folder>`. The workspace layout is described in `../../pilot_sop.md`.
