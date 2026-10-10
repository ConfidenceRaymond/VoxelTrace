# 5-minute product demo

**Data:**
- DEMONSTRATION DATA only: `outputs/commercial_demo_audit/trial` (9 subjects, 7 pairs, 4
  sites).
- Real public de-identified baselines with SYNTHETIC_PERTURBATION follow-ups.
- Subject folders relabelled DEMO-nn.
- Say this aloud at the start.

**Setup before the call:**
- `streamlit run app/Home.py` running.
- The audit already run to `outputs/commercial_demo_audit/audit`, because live audits take
  minutes.
- A terminal open in the workspace.
- Copies of the deliverables are in `docs/commercialization/sample_audit/`.

| Time | Step | Show | Say (key line) |
|---|---|---|---|
| 0:00 | Framing | Home page | "This is about whether two scans *can* be compared, before anyone interprets a change. No diagnosis, no AI in the audit." |
| 0:20 | 1. Import trial | *Intake and Audit* page, trial folder; `trial.yaml` shown (created by `init-trial`) | "The study arrives as subject/timepoint folders. The configuration is generated from the layout; your site map is added, never guessed." |
| 0:50 | 2. Preflight | *Check input*: per-scan decisions | "Before any SUV is computed we check every prerequisite. DEMO-05's follow-up has no injected dose, so it needs a re-export, and we say exactly which field." |
| 1:30 | 3. Protocol fingerprint | `protocol/fingerprints.csv` or the *Protocol and Claims* page | "Each scan gets a fingerprint of scanner, software and reconstruction, with how much each field can be trusted." |
| 2:00 | 4. Pair comparability | *Intake and Audit* page §4, pair verdicts (QIBA) | "1 ASSESSABLE, 4 NOT_ASSESSABLE, 2 INSUFFICIENT_INFORMATION. 'Cannot decide' is a result in its own right, not a silent include." |
| 2:40 | 5. Failure reason | top blocking reasons; DEMO-04 | "The follow-up was acquired at 90 minutes; the QIBA window is 55–75 minutes and the rule cites section 3.2.1.1. A re-export cannot change a measured time, so the site can't fix it." |
| 3:10 | 6. Site-level rollup | `site_summary.json`, `drift_events.csv` | "Site A and site D: which sites drive the problems, and when the protocol changed." |
| 3:40 | 7. Evidence trace | `pair_checks.csv` row → observed values → preflight/fingerprint field → `manifest.json` versions | "Every verdict traces back to the exact header value, the rule version and the input hash." |
| 4:15 | 8. PDF / evidence bundle | download the PDF and the bundle zip; run `voxeltrace verify-bundle` | "The PDF is byte-reproducible. The bundle is checksum-verified, so you can prove nothing changed after delivery." |
| 4:40 | 9. (Optional) local explanation | **not part of the current product workflow**: no page explains results with a model today. If asked: "A local model could later summarise a report in words. It would never change a value or verdict, and nothing leaves your machine." | |
| 4:50 | Close | validation status | "External physicist validation is pending; I'll show you exactly what is and isn't validated. Would a retrospective audit of one of your completed studies be useful?" |

**Do not:**
- show real patient identifiers;
- claim validation, customers or regulatory status;
- lead with AI;
- improvise prices.
