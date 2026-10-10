# Design-partner target-account template

A structured list to plan outreach. **Fill it only from public information or your own
relationships.** Do not scrape private data, do not buy contact lists, and do not enter a
person's name or e-mail unless they gave it to you. Rows below are placeholders; no
organisation or contact has been researched or contacted.

The machine-readable copy is [target_accounts_template.csv](target_accounts_template.csv)
(same columns; keep the filled version outside the repository if it contains contacts).

## Columns

| Column | Content | Allowed values / notes |
|---|---|---|
| `segment` | account type | IMAGING_CORE_LAB, CRO_IMAGING, RADIOPHARMA, ACADEMIC_PET_CENTER, TRIAL_COORDINATING_CENTER |
| `organization` | public organisation name | from public sources only |
| `likely_buyer_role` | role that owns the budget | e.g. "VP imaging operations", "head of clinical imaging" (role, not a person) |
| `technical_evaluator_role` | role that would judge the rules | e.g. "PET physicist", "QC lead" |
| `pet_modality` | what they run | FDG PET/CT; PET/MR; non-FDG (note tracer); multicentre / single site |
| `current_workflow` | how they check comparability today, if known | "unknown" until an interview says otherwise |
| `why_voxeltrace_may_matter` | the specific hypothesis | e.g. "multicentre FDG trials with mixed GE/Siemens sites" |
| `public_evidence` | where the hypothesis comes from | link to a public trial registry entry, paper or charter |
| `relationship` | how we could reach them | NONE, CONFERENCE, MUTUAL_CONTACT, INBOUND, EXISTING |
| `outreach_status` | pipeline state | NOT_CONTACTED, CONTACTED, INTERVIEWED, PILOT_DISCUSSED, PILOT_AGREED, DECLINED |
| `interview_ids` | links to scored interviews | see `interview_scoring_rubric.md` |
| `evidence_required` | what they would need before a pilot | e.g. "expert validation", "GE results", "security review", "DPA" |
| `next_action` / `next_action_date` | one action | |
| `notes` | no PHI, no personal data beyond what was volunteered | |

## Segment hypotheses (to test in interviews, not facts)

| Segment | Likely buyer | Likely evaluator | Why it may matter | Evidence they will likely require |
|---|---|---|---|---|
| Imaging core lab | operations / scientific director | PET physicist, QC lead | site queries and re-reads cost staff time | expert agreement, vendor coverage for their sites, deployment on their infrastructure |
| CRO imaging group | head of imaging services | imaging scientist | multicentre QC at scale, audit trail | throughput, validation, SOP fit |
| Radiopharmaceutical company | imaging lead of a quantitative programme | imaging scientist / physicist | endpoint risk from non-comparable scans | validation on their scanners, regulatory posture |
| Academic PET centre | department or physics lead | PET physicist | retrospective studies, publications | open methods, reproducibility |
| Trial coordinating centre | imaging committee chair | imaging core physicist | cooperative-group trials with mixed scanners | free/low-cost pilot, publication |
