# Product readiness scorecard (2026-10-09)

**Maturity levels:**

| Level | Meaning |
|---|---|
| 0 NOT_STARTED | nothing exists |
| 1 PROTOTYPE | works on examples; not validated |
| 2 INTERNALLY_VALIDATED | validated by our own tests and real public data |
| 3 EXTERNALLY_TESTABLE | an outside person can install, run and evaluate it |
| 4 DESIGN_PARTNER_READY | used on a partner's data with acceptable results |
| 5 PRODUCTION_READY | supported, validated and released |

| Dimension | Level | Evidence | Gap to next level |
|---|---|---|---|
| Scientific validation | **2** | strict SUV/SUL validators and rule sets with 580 tests; 117/117 emittable reason codes have known-answer tests; census predictions vs full series 29/30 fields on 3 external pairs; ACRIN 094/153 refusals explained (vendor decay timing); 168 reconstruction audit | independent expert agreement (no labels yet) |
| Multi-vendor coverage | **1** | real decided verdicts only on **Siemens** (Biograph mCT, Biograph64, CPS 1080). GE Discovery LS: SUV path works (167/168) but reconstruction identity is never encoded. Philips: all open exports refused (CNTS). United Imaging: no open DICOM | a decidable GE and Philips pair; Philips CNTS path (documented); UIH data |
| Real longitudinal coverage | **2** | 8 real pairs (5 ACRIN, 3 external): 2 QIBA ASSESSABLE, 1 decided NOT_ASSESSABLE, 5 INSUFFICIENT_INFORMATION / refused, all explained | more decided pairs; a PERCIST-complete pair (needs a lesion review gate) |
| Automation | **3** | one command (`voxeltrace audit`) from folder to bundle; preflight, inspect, verify, summarize, attestation and adjudication commands; 20 s for one real subject; about 3 subjects/min | single-pass multi-rule-set audit; batching for large trials |
| Auditability | **3** | immutable bundles with sha256 checksums and tamper detection; versioned schemas and rule-bundle hash; hash-bound reviews and attestations; hash-chained adjudications; evidence classes separated in reports | bundle signatures |
| Deployment | **3** | fresh-venv install verified (after declaring Pillow); CI green on Python 3.11/3.12; deployment doc; local-first, no network or GPU needed | packaged release (wheel/container) |
| External validation | **1** | BLINDED/UNBLINDED physicist package and scoring implemented; **no external labels collected** | ≥ 30–50 real pairs reviewed by ≥ 2 physicists; false-safe analysis |
| Pilot readiness | **2** | SOP, data requirements, checklist, limitations, end-to-end example on real data | lesion review gate; one partner dry run |
| Commercial validation | **0** | discovery script and pilot package written; no design-partner conversations held | customer discovery interviews |
| Regulatory readiness | **0** | research prototype; no QMS, no clearance | out of scope at this stage |

## Overall classification: **EXTERNAL_VALIDATION_READY**

**Justification:**
- An external PET physicist can install VoxelTrace from git, run `voxeltrace audit` on
  public or their own de-identified data, verify the bundle, and score agreement with the
  BLINDED package.
- Real decided verdicts exist: QIBA ASSESSABLE ×2 and decided NOT_ASSESSABLE ×1, all
  explained.
- It is **not** DESIGN_PARTNER_READY:
  - no external labels;
  - Siemens-only decided coverage;
  - PERCIST cannot complete without a lesion review gate;
  - no partner data has been processed.
