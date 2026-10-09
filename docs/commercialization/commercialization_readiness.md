# Commercialization readiness (2026-10-09)

**External expert validation: PENDING.** There are 0 interviews, 0 design partners and 0
customers.

## What can we sell today?

Nothing as validated software. Honestly offered today: a **no-fee or design-partner
retrospective comparability audit** of a completed FDG PET/CT study.
- It runs locally at the partner where possible.
- It is clearly labelled as research software with external validation pending.
- It comes with PET-physics support.

A paid offer waits for gate 3 (`release_gates.md`).

## What can we pilot today?

- A design-partner retrospective audit (gate 1 is met for the software). The full flow is
  `customer_onboarding.md`, using `validate-input`, `init-trial`, `audit`, the review pages,
  the reports and the verified bundle.
- **Best fit:** multicentre FDG PET/CT with quantitative endpoints, on Siemens scanners (the
  only vendor with pair-level validation). GE and Philips pilots double as validation work and
  must be labelled so.

## What can we only research today?

- GE and Philips quantification, United Imaging and Canon.
- PERCIST end-to-end on real data: no real pair has completed human liver and lesion review.
- Brain PET (metadata intake only), PET/MR, PSMA and other tracers, SPECT/CT.
- Optional language-model explanation (not part of the product workflow).
- API and enterprise deployment.

## Who is the first buyer?

**Hypothesis, to be tested by interviews:** the director of an imaging core lab, or a
sponsor's quantitative imaging lead, with a completed multicentre FDG PET study whose
quantitative endpoint was questioned or required many site queries. Physicists are the key
influencers and validators. The budget owner is unknown, which is the first thing to learn.

## What is the first deliverable?

A retrospective comparability audit of one study, containing:
- an executive summary and PDF;
- pair verdict tables under the charter's rule set;
- subject × timepoint matrix, site rollup and drift events;
- failure reasons with remediations and draft site queries;
- a verified evidence bundle;
- a findings workshop.

All of these are shown on DEMONSTRATION DATA in `sample_audit/`.

## What evidence is missing?

1. Independent PET physicist agreement and false-safe analysis (`../external_validation_pending.md`).
2. Any customer discovery evidence: pain, frequency, cost, budget owner, purchase trigger.
3. An outside dataset audited by its holder.
4. Non-Siemens quantitative validation.
5. A complete real PERCIST verdict. PETCT_97320b0b58 awaits human liver and lesion
   decisions. The development-only internal acceptance requested on 2026-10-09 was **not
   recorded**: the action was blocked in this session pending the owner's explicit
   confirmation (see the final report).
6. Effort per study (needed for pricing) and willingness to pay.

## What is the next commercial gate?

**Gate 2, retrospective pilot.** It needs a recruited design partner with an outside
dataset, their physicists' feedback including the false-safe review, a reproducible
deployment at their site, and no unresolved false-safe issue.

## What should we stop building?

- **New rule sets, tracers and modalities** (brain, PET/MR, PSMA, SPECT) until a partner asks
  and pays for them.
- **AI and language-model features.** They are not part of the value and they add regulatory
  and trust risk.
- **More public-data censuses and downloads**, beyond targeted validation gaps (GE/Philips via
  partners).
- **UI polish** beyond fixing what partners report.
- **Enterprise features** (API, RBAC, cloud) until gate 3 evidence shows who would buy them.

Focus instead on the 20 interviews, one design partner, and external physicist review.
