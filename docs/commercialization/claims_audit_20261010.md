# Commercial claims audit (2026-10-10)

Scope: `docs/commercialization/` (incl. `website/`, `outreach/`), `docs/pilot/` (incl.
`external_partner/`), `README.md`. Method: search for regulatory, clinical, validation, vendor,
savings and AI language, then manual review of every hit in context.

## Blocked claim classes (must never appear as an affirmative statement)

clinical validation · medical-device approval / clearance (FDA, Health Canada, CE / EU MDR) ·
diagnostic capability · treatment-response classification · complete multi-vendor validation ·
guaranteed comparability · guaranteed cost savings · guaranteed regulator or trial acceptance ·
AI-first positioning or AI making any measurement or decision.

## Result

| Finding | File | Action |
|---|---|---|
| "Several Siemens models validated end to end" could be read as expert/clinical validation | `sales_one_pager.md` | reworded: "audited end to end on public pairs (software validation; no external expert agreement yet)" |
| "Independent external expert validation is in progress" overstated (0 reviewers recruited, 0 forms returned) | `website_copy.md` | "pending … no reviewer has returned a form yet" |
| "Comparability checks are validated on several Siemens scanner models" | `website_copy.md` | "audited end to end … (public data)" |
| "Over 600 automated tests" stale | `website_copy.md` | "Over 700" |
| "External physicist validation is in progress" | `demo_script.md` | "pending" |
| All other hits | regulatory analysis in `intended_use_draft.md`, exclusion lists, "does not / never" statements, forbidden-claims lists | no change |

No affirmative clinical, regulatory, diagnostic, response, multi-vendor, savings or AI claim
remains. Intended use stays: retrospective PET trial QC, research and comparability audit;
not for clinical diagnosis or treatment decisions.
