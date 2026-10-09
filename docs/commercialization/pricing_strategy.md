# Pricing strategy: models to test (no prices)

**No price, benchmark or willingness-to-pay figure appears here, because none has been
collected.** Prices are set only after the interview evidence listed for each model exists
(`customer_discovery_plan.md`).

| Model | Buyer | Benefits | Disadvantages | Likely procurement path | Evidence needed before setting a price |
|---|---|---|---|---|---|
| **Fixed retrospective audit** (one study, fixed scope) | sponsor imaging lead; core-lab director | simple to buy; matches a one-off question ("can we trust this endpoint?"); low commitment | revenue does not recur; scope creep in large studies; human-review time varies | project or study budget; possibly a purchase order under an existing vendor framework | current cost of comparability QC per study (staff hours × rate as the buyer describes it); a recent incident and its cost; who signs |
| **Per-trial setup fee** (configuration, rule pack, site map, intake) | core lab; CRO imaging operations | pays for real onboarding work; filters unserious pilots | friction at the start; buyers may expect setup to be free | added to a statement of work | how long onboarding takes today for a new trial; whether setup fees are normal for their imaging vendors |
| **Per-timepoint analysis** | core lab (pass-through to sponsor) | scales with volume; fits how core labs already price reads | unpredictable for the buyer; incentive arguments about re-runs; small studies earn little | per-unit line item in the core lab's sponsor contract | how the core lab prices other per-timepoint services (their structure, not their numbers); volumes per year |
| **Annual enterprise licence** | core lab or CRO; large sponsor imaging group | recurring; supports deployment and support costs | long sales cycle; needs the security review, validation package and support SLA that do not yet exist | IT, QA and procurement review; vendor qualification | deployment model they would accept; QA requirements (CSV/Part 11 expectations); budget owner; number of studies per year |
| **API / SDK licence** | imaging informatics or AI platform teams | integrates into existing pipelines; low service burden | no API exists yet; harder to show value; easy to commoditise | technical evaluation, then licence agreement | whether any platform would embed comparability checks; what they use now |
| **Support / validation package** (documentation, IQ/OQ templates, change notices) | QA at core labs and sponsors | needed for regulated use; pairs with an enterprise licence | needs a quality system that does not exist yet (`quality_system_roadmap.md`) | QA vendor assessment | what validation documentation their QA asks of software vendors today |

## Sequence to test

1. Fixed retrospective audit, priced only after the first 10 interviews. A discounted or
   no-fee design-partner pilot is the place to learn effort per study, not to set price.
2. Setup fee plus per-timepoint pricing, discussed with core labs once two pilots show real
   effort per timepoint.
3. Enterprise licence and validation package only after gate 3 (`release_gates.md`).

## Questions to ask, not prices to quote

- "What does a quantitative endpoint QC problem cost you when it is found late?"
- "Who would pay for an independent comparability audit, and from which budget?"
- "How do you buy similar services today: per study, per timepoint, or annually?"
