# Business model options

**Evidence today:**
- working software on 9 real public pairs;
- 0 customer interviews completed;
- 0 design partners;
- external expert validation pending;
- no demand data.

The comparison below rests on reasoning about the product and the buyers, not on market
evidence.

| Model | How it works | Strengths | Weaknesses / risks | Fit with current evidence |
|---|---|---|---|---|
| 1. Software-only | customer licenses and runs it | scalable; low service cost | buyers of regulated QC rarely adopt unvalidated software alone; no validation package or support yet | weak now |
| 2. Software + PET physics service | software plus expert configuration, review support and interpretation of findings | matches what core labs actually need (judgement on INSUFFICIENT_INFORMATION cases); builds trust while validation is pending | scales with people; needs PET physics capacity | strong |
| 3. Retrospective audit service | VoxelTrace staff run audits on completed studies and deliver a report | no IT integration; fast to start; shows value on the customer's own data | data-transfer and DUA burden; looks like consulting | strong as an entry point |
| 4. Enterprise licensing | annual on-prem licence for core labs or CROs | recurring revenue | requires QMS, security review, support and validation package (not yet) | later (gate 4) |
| 5. Open-core | research tier open (already MIT); trial-audit workflow, support and validation package commercial | credibility with physicists; community scrutiny of rules | the open core can be self-hosted by capable customers; the dividing line must be clear | compatible; the repository is already public |
| 6. CRO / core-lab partnership | embedded in a core lab's offering; revenue share or licence | uses the partner's sponsor relationships and QA | dependence on one partner; slower to iterate | strong medium-term |
| 7. Sponsor-direct audit | sponsor buys an independent audit of its own trial data | the buyer feels the endpoint risk directly | the sponsor may not hold the images; core-lab sensitivity about being audited | to test in interviews |

## Recommendation (provisional)

Start with **3 + 2**: a retrospective comparability audit delivered with PET-physics support,
on the customer's own completed study. Run it locally at the customer where possible. Keep
the open research core (5), and aim at a core-lab partnership (6) once two audits have shown
value.

**Why this, given current evidence:**
- It needs no API, role-based access or QMS that do not exist yet.
- It turns the honest weak point (no external validation yet) into a joint exercise: the
  partner's physicists adjudicate.
- It produces the evidence that is missing, namely effort per study, the value of findings
  and the buyer's budget.

**What would change the recommendation:**
- Interviews show core labs will not let an outside party audit them. Then lead with
  partnership (6).
- Sponsors show a strong budget for independent audits. Then use sponsor-direct (7).
- Nobody reports comparability problems as costly. Then revisit the product itself.
