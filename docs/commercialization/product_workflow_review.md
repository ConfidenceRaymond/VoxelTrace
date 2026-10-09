# Product workflow review: friction and UI (2026-10-09)

Goal: a design partner can run the whole workflow without Claude Code, without writing
Python, and without hand-editing YAML.

## Friction audit

| Friction | Before | Now |
|---|---|---|
| Claude Code needed | not needed for the audit, but the only end-to-end walkthroughs were developer notes | not needed; every step is a CLI command or an app page (`pilot_sop.md`, `customer_onboarding.md`) |
| Manual Python commands | the audit was documented via `scripts/run_trial_audit.py` in user docs | user docs use `voxeltrace audit` or the *Intake and Audit* page; `scripts/` remains for developers (census, downloads, fixtures) |
| Editing YAML by hand | `trial.yaml` had to be written by hand | `voxeltrace init-trial` and the page button write a starter file (safe defaults; sites never guessed). Reference reviews were already written by the page; lesion reviews by page or CLI |
| Developer-only paths | the app defaults and `data-inventory` used the source-checkout parent; on a pip install they pointed inside `site-packages` | `workspace_root()`: `$VOXELTRACE_WORKSPACE`, else the source-checkout parent, else the current directory |
| Hardcoded local paths | README and some docs showed `/home/dell/...` | README uses `<workspace>`; the remaining occurrences are in historical and development docs only (`../public_repo_audit.md`) |
| No UI for running an audit or getting reports | CLI only | new page *Intake and Audit*: validate-input, init-trial, audit, bundle verification, executive summary, PDF/JSON/zip downloads |
| AI-first landing page | Home was a developer smoke test titled "Local AI for Quantitative PET Intelligence" | Home is a product overview with the workflow; system status and the synthetic smoke test sit in a collapsed expander |

## Defects found while preparing the commercial demo (fixed, with regression tests)

1. **The audit crashed when the trial had a reference review file.** It only worked with
   `--qc-images`; the copy into the bundle ran before `reviews/` existed. The same applied
   to adjudication logs.
2. **Bundles recorded review and attestation file paths as given**, which could reveal site or
   patient directory names. They now record file names only, unless `--input-paths-in-clear`
   is set.
3. **The executive summary undercounted subjects** (single-timepoint subjects were left out)
   and **omitted decided failures that have no reason code** (for example uptake out of
   window). Both are fixed.

## UI review against the proposed flow

| Proposed step | Current page / command | Status |
|---|---|---|
| Overview | Home | fixed (product overview) |
| Data Intake | *Intake and Audit* §1–2 | added |
| Preflight | intake table; `voxeltrace preflight` for detail | adequate |
| Trial Audit | *Intake and Audit* §3 | added |
| Pair Detail | pair-verdict tables on the audit page; per-check detail in `pair_checks.csv` | adequate; a dedicated pair-detail page would help (not built, to avoid rebuilding) |
| Reference Review | page 4 | existing |
| Lesion Review | page 6 | existing |
| Adjudication | `voxeltrace adjudicate` (CLI only) | gap: no page; acceptable for pilots run with support |
| Reports | *Intake and Audit* §4 (downloads) | added |
| Provenance | *Reconstruction Evidence*, *Protocol and Claims*, *Imaging Ingestion* pages; bundle manifest | existing; page names are developer-oriented |

**Not done, deliberately:** page renaming and reordering (it would break links and gives
little value now), a pair-detail page, and an adjudication page. All three are candidates
after design-partner feedback.

**Remaining friction:**
- The Streamlit app is not part of the installed package. The UI needs the repository
  checkout and `pip install .[app]`; the CLI works from a plain install.
- There is no authentication. The app is single-user and localhost only.
