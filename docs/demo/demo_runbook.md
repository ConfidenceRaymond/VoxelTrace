# Demo runbook (5–7 minutes, non-developer audience)

**Data:** DEMONSTRATION DATA only: `<workspace>/outputs/commercial_demo_audit/trial`. It has
9 subjects: 7 declared **synthetic perturbations** of one real public Siemens pair (identity,
reconstruction blur, reconstruction metadata, uptake violation, missing dose, anonymization
loss, correction mismatch), plus 2 real public single-timepoint scans. No partner data, no
PHI. Say "demonstration data" on screen.

**Prepared beforehand** (the audit takes about 5 minutes, so run it before the meeting):

```bash
cd <workspace>/outputs && mkdir -p demo_live && cd demo_live
voxeltrace run-pilot --input ../commercial_demo_audit/trial --output pilot
```

Open in tabs: `pilot/delivery_package/executive_summary.pdf`, `pair_results.csv`,
`site_summary.csv` (a spreadsheet viewer), and a terminal in `demo_live`.
`B=pilot/audit/audit_bundle`, `P=pilot/delivery_package`.

| # | Time | Show | Command / file | Say |
|---|---|---|---|---|
| 1 | 0:00 | Dataset intake | `ls ../commercial_demo_audit/trial` | "One folder per subject and visit, as a core lab would send it." |
| 2 | 0:30 | Validate input | `voxeltrace validate-input ../commercial_demo_audit/trial \| head -20` | "Before any audit: can each scan be used as exported? Plain language plus the exact DICOM field." |
| 3 | 1:15 | Preflight | `column -s, -t < $B/preflight/preflight.csv \| head` | "Per scan: ready to quantify, or why not." |
| 4 | 1:45 | Protocol fingerprint | `column -s, -t < $B/protocol/fingerprints.csv \| head` | "Each scan's protocol is fingerprinted: scanner, software, reconstruction, corrections." |
| 5 | 2:15 | Pair comparability | `$P/pair_results.csv` | "Four verdicts per pair and guideline. Identity → ASSESSABLE; reconstruction changed → NOT_ASSESSABLE; dose missing → INSUFFICIENT_INFORMATION, never a pass." |
| 6 | 3:00 | Reason code | `$P/remediation_matrix.csv` (row MISSING_RADIONUCLIDETOTALDOSE) | "Every reason says what it means and whether a re-export, site records or a reviewer can fix it." |
| 7 | 3:30 | Evidence trace | `voxeltrace explain-pair $B --subject DEMO-03-RECON_METADATA --ruleset qiba-fdg-1.14` | "Why? Rule, field, value at both visits, trust level, source tag." |
| 8 | 4:15 | Site/scanner summary | `$P/site_summary.csv` | "By site and scanner: what is ready, what is not, top reasons, drift." |
| 9 | 4:45 | PDF | `$P/executive_summary.pdf` | "The page a director reads. Validation status is stated on it." |
| 10 | 5:30 | Verify delivery | `voxeltrace verify-delivery $P` | "The partner can verify every file, and the privacy scan." |
| 11 | 6:00 | Verify bundle | `voxeltrace verify-bundle $B` | "The evidence bundle is checksummed; any change is detected." |
| — | 6:30 | Close | — | "External expert validation is pending; would a retrospective audit of one of your completed studies be useful?" |

**Do not:** claim validation, customers or regulatory status; show unreleased features; lead
with AI. The optional local explanation model is **not** part of the demo; mention it only if
asked ("an optional, local explainer; it never decides anything").

**If something fails:** show the prepared outputs; never re-run with different data.
