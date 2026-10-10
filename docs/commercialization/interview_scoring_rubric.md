# Discovery interview scoring rubric

Use after each interview in `customer_discovery_plan.md`, filled from the notes the same day.
It makes interviews comparable; **it is not market validation**. A score is one person's
account on one day. Never sum scores across people to claim demand, and never report a
score without the interview count behind it.

Score each signal 0–3 from what the person **said happened**, not from what they said they
would do. If the interview did not cover a signal, record `n/a`, not 0.

| # | Signal | 0 | 1 | 2 | 3 |
|---|---|---|---|---|---|
| 1 | Pain severity (= the plan's pain score) | none | annoyance | real cost or delay in the last year | recent event that threatened an endpoint, a submission or a publication |
| 2 | Frequency | never / hypothetical | yearly | every study | every batch / weekly |
| 3 | Current staff hours on comparability / metadata QC | none | < 1 h per study | hours per study | a role or a large part of one |
| 4 | Monetary impact (their figure, or the event they describe) | none | unquantified | they named a cost range | they named a cost and who paid it |
| 5 | Regulatory / trial impact | none | internal only | site re-query or delayed read | protocol deviation, data exclusion or regulator / sponsor question |
| 6 | Existing solution quality (inverse) | solved well by a tool they like | adequate scripts maintained by staff | ad-hoc spreadsheets / manual checks | nothing, or known to miss problems |
| 7 | Urgency | none | "someday" | current programme would benefit | a named study starts or reads within 6 months |
| 8 | Buyer identified | unknown | a department | a role with budget | a named budget owner and a purchase path |
| 9 | Data availability | none | data exist, no sharing route | could share de-identified data under a DUA | offered a specific retrospective dataset |
| 10 | Willingness to pilot | no | maybe later | yes, unpaid | yes, with budget / a scope to discuss |

## Recording

```
interview_id: <date>_<segment>_<n>      (no names)
segment:
scores: {1: , 2: , 3: , 4: , 5: , 6: , 7: , 8: , 9: , 10: }
evidence per score (one line each, their words where possible):
total (0–30, n/a excluded; report as x / max):
disqualifiers observed: [e.g. no PET quantitation in their trials; in-house tool they like]
```

## Interpretation (per interview; PROVISIONAL bands, revisit after 10 interviews)

| Pattern | Reading |
|---|---|
| signals 1, 7 and 9 each ≥ 2 | candidate design partner: follow up with `design_partner_program.md` |
| signal 1 ≥ 2 but 9 ≤ 1 | real pain, no data route: keep in touch; ask what a data route needs |
| signal 6 = 0 | they have a tool they like: learn what it does; do not pitch |
| total ≤ 8 with n/a ≤ 2 | weak fit for now |

Aggregate only as counts against the thresholds already set in
`customer_discovery_plan.md` ("≥ 8 of 20 with pain score ≥ 2", etc.).
