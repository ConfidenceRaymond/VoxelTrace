# Commercial release gates

A gate passes only when every item has written evidence. Gates are never relaxed to meet a
date. External expert validation remains its own release gate
(`../external_validation_pending.md`).

## GATE 1: DESIGN PARTNER (complete for the software; partner not yet recruited)

| Requirement | Evidence |
|---|---|
| installable independently | clean venv install; `voxeltrace --version` |
| one-command audit; evidence bundle verifies | `voxeltrace audit`, `verify-bundle` |
| external validation package | blinded 9-pair cohort with leak guard |
| reference and lesion review gates | hash-bound, human-only |
| deterministic reports | executive summary, byte-reproducible PDF |
| known limitations documented | `../known_limitations.md` |
| no developer tooling needed | `init-trial`, *Intake and Audit* page (`product_workflow_review.md`) |
| demonstration package | `sample_audit/`, `demo_script.md` |

## GATE 2: RETROSPECTIVE PILOT

| Requirement | Status |
|---|---|
| external physicist feedback (at minimum: a design partner's physicists review verdicts and the false-safe candidates) | not started |
| at least one outside dataset audited (not public data chosen by us) | not started |
| no unresolved false-safe issue | none known; none can be known before review |
| reproducible deployment at the partner (documented install, same version, bundle verifies) | procedure exists; not yet done outside |
| signed scope and data agreement | templates exist; none signed |

## GATE 3: PAID PILOT

| Requirement | Status |
|---|---|
| customer acceptance of a retrospective pilot deliverable | — |
| contracts and data terms executed (NDA, DUA/DPA, SOW) | — |
| customer security review passed for the chosen deployment | — |
| validated deliverable process (release checklist, locked version, verification steps, issue handling) | partly: tags and bundle verification exist; no release checklist or issue process |
| price set from interview and pilot evidence | — |

## GATE 4: PRODUCTION

Requires substantially more, including at least:
- completed external expert validation (all seven items of `../external_validation_pending.md`);
- non-Siemens quantitative validation;
- a quality system appropriate to the customers (`quality_system_roadmap.md`);
- authentication, role-based access, audit trail with authenticated identities, and signed
  releases;
- support and incident processes;
- regulatory counsel's confirmation of the intended-use boundary;
- insurance and contracts in place.
