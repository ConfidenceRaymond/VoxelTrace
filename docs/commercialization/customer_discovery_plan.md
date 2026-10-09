# Customer discovery: 20-interview plan

**Rules:**
- Learn before pitching. Do not open with AI; the audit uses none.
- Never claim validation, customers, prices or regulatory status.
- Record no patient information.

Short role-specific guides already exist in `../commercial/discovery_*.md`. This plan
schedules and standardises them.

## Segments and targets

| Segment | n | Who | Why |
|---|---|---|---|
| PET physicists / core-lab scientific directors | 5 | academic and core-lab PET physicists | own the comparability judgement; can say whether the rules are right |
| Imaging CRO / core-lab leaders | 5 | operations or business leads at imaging CROs and core labs | own the workflow, staff time and site queries; likely buyer or channel |
| Radiopharma / pharma imaging leads | 5 | sponsor imaging scientists for quantitative PET programmes | feel the endpoint risk; hold budget |
| Multicentre trial investigators | 3 | PIs or imaging leads of academic cooperative-group PET trials | retrospective datasets; publication-driven quality needs |
| Imaging AI / data-infrastructure leads | 2 | platform or data teams that move trial images | integration path; build-vs-buy |

**Sourcing (no contact made yet):** personal network, authors of multicentre quantitative
PET papers, SNMMI/EANM physics community events, and the core labs named in public trial
charters. Log every outreach attempt.

## Outreach message (adapt per person; no attachment, no pitch deck)

> Subject: 20 minutes on PET comparability in multicentre trials?
>
> Hello <name>, I'm researching how teams decide whether quantitative PET scans from
> different timepoints, sites and scanners are comparable before SUV changes are
> interpreted. Your work on <specific study/paper/role> suggests you deal with this directly.
> Could I ask you about your current process and the problems you run into? 20–30 minutes,
> nothing to buy, and I'm happy to share what I learn across interviews (anonymised).
> Thank you, <name>

## 30-minute interview guide

| Min | Topic | Questions |
|---|---|---|
| 0–3 | Context | role; studies and tracers; sites and scanners; who else is involved |
| 3–10 | **Current workflow** | walk me through the last time you checked whether a baseline/follow-up pair was comparable; what did you look at, in what order, with which tools? |
| 10–15 | **Painful recent event** | tell me about the last time a scan could not be used, or a problem was found late; what was missing, how was it found, what did it cost (time, data, money, credibility)? |
| 15–18 | **Staff time and site queries** | minutes per pair; who does it; how many site queries; turnaround; how often the answer is "unknown" |
| 18–21 | **Reconstruction mismatches, insufficient metadata, data loss** | how often reconstruction differs from qualification; how you learn the settings; how de-identification affects weight, height, times and dose; how many pairs are lost or excluded |
| 21–24 | **Current scripts and tools** | what you use (in-house scripts, vendor tools, spreadsheets); who maintains it; what it misses |
| 24–27 | **Build vs buy; budget owner; purchase trigger** | would you build or buy this? who would pay, from which budget? what event would make you look for a solution now (audit finding, regulator question, new multicentre study)? |
| 27–30 | Close | may I follow up? who else should I talk to? would a retrospective audit of a completed study be useful, and what agreement would it need? |

Only if asked "what are you building?": describe it in one sentence, with no AI and no
claims. "Software that checks, before analysis, whether PET scans across timepoints and
sites are comparable under QIBA/EANM/PERCIST, and explains every 'cannot decide'."

## Notes template (one file per interview, `interviews/<date>_<segment>_<n>.md`, no names in the file name)

```
Date / interviewer / segment / organisation type (not name in shared notes)
Context:
Current workflow (their words):
Most painful recent event (what, when, cost, how found):
Staff time per pair / per study:
Site queries (volume, turnaround, typical content):
Reconstruction mismatch frequency:
Metadata / de-identification losses:
Current tools / scripts:
Build vs buy stance:
Budget owner / purchase process:
Purchase trigger:
Quotes worth keeping (verbatim):
Pain score 0–3 (0 none, 3 urgent, costly, recent) and why:
Would they share data for a retrospective audit? Under what terms?
Follow-ups / referrals:
```

## Decision criteria (after 20 interviews)

| Signal | Threshold to proceed with the audit-first model | If missed |
|---|---|---|
| Painful, recent, costly comparability event reported | ≥ 8 of 20 with pain score ≥ 2 | revisit the problem framing |
| Identified budget owner for QC/audit | ≥ 5 interviews name a budget and a signer | test the partnership model |
| Willing to run or share a retrospective dataset | ≥ 2 organisations | do not build further features; continue discovery |
| Current tooling inadequate (scripts/spreadsheets, or nothing) | ≥ 10 of 20 | assess the competing tools named |
| Physicists agree the rule framing is useful | ≥ 3 of 5 physicists | revise rules / output before selling |

Record results in `kpi_framework.md`. No pricing decision is taken before these thresholds
are evaluated.
