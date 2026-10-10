# Retrospective pilot workflow (operator guide and dry-run record)

RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.

This is the route an operator follows **without Claude Code or a developer**. Every command
is deterministic and runs offline; no AI model is used. Partner-facing overview:
[README_FIRST.md](README_FIRST.md). Detailed SOP: [../pilot_sop.md](../pilot_sop.md).

## 1. Preferred route

```bash
# 0. install (see ../deployment.md): python3.12 -m venv .venv && . .venv/bin/activate && pip install -e ".[app,dev]"

# 1a. nested partner drop (site/subject/timepoint, any naming): interpret, review, stage
voxeltrace validate-input <drop>                # optional first look; flags nested layouts
voxeltrace intake-map <drop> --out intake_mapping.json \
    --stage <trial> --trial-id <TRIAL-ID> [--timepoint-map "Week 6=followup"]
#    -> read the printed mapping; NEEDS_REVIEW scans are NOT staged (ask the site, or remove
#       the extra series and map again). intake_mapping.json is an operator file: keep it,
#       do not deliver it (it contains source paths and series descriptions).

# 1b. or a <subject>/<timepoint>/<DICOM> folder you already have
voxeltrace init-trial <trial> --trial-id <TRIAL-ID> --timepoints baseline followup   # optional
#    add `sites: {SUBJ: SITE}` to trial.yaml for site rollups (never guessed)

# 2. everything else in one command
voxeltrace run-pilot --input <trial> --output <work> [--trial-id <ID> if no trial.yaml]

# 3. check and hand over
voxeltrace verify-delivery <work>/delivery_package
voxeltrace explain-pair <work>/audit/audit_bundle --subject <SUBJ>    # "why this verdict?"
```

`run-pilot` = `validate-input` → (`init-trial` into `<work>/config/` when the input has no
trial.yaml; the input is never written) → `audit` → `verify-bundle` →
`pilot_acceptance.json` → `deliver`. It calls the same modules as the individual commands,
which remain available for step-by-step use.

| Exit | Status (`pilot_acceptance.json` → `status`) | Meaning |
|---|---|---|
| 0 | `AUDIT_COMPLETE` | nothing pending |
| 0 | `AUDIT_COMPLETE_WITH_REVIEW_PENDING` | valid results; some verdicts wait for human review |
| 1 | `AUDIT_BLOCKED` | bundle verification failed, or a BLOCKING pairing finding; no package is built |
| 2 | `NEEDS_REEXPORT` | audit not run (no scans, invalid trial.yaml, or `--strict-intake` refused), or a usage error |
| 3 | `UNSUPPORTED` | audit not run: every scan is outside scope (e.g. non-FDG) |

**Audit gate:** by default scans needing re-export are still audited (they get
`INSUFFICIENT_INFORMATION` / `NOT_ASSESSABLE` and DRAFT site queries, which is the useful
output for a site). `--strict-intake` audits only when intake accepts the whole folder.

**Manual steps that remain** (by design, never automated):
1. Confirming the intake mapping and resolving `NEEDS_REVIEW` scans with the site.
2. Declaring sites in trial.yaml.
3. Human reference-region and lesion review (Reference Review / Lesion Review app pages),
   then re-running into a new output folder.
4. Editing and sending DRAFT site queries.

## 2. Dry run A: real 9-pair cohort, step by step (2026-10-09, x86_64)

Data: the 9 real public longitudinal pairs of `outputs/external_validation_cohort_v1/trial`
(ACRIN-NSCLC-FDG-PET, CC-Tumor-Heterogeneity, CMB-MEL, FDG-PET-CT-Lesions), staged as
symlinks into a fresh folder `outputs/pilot_runs/e2e_x86_20261009/trial` without trial.yaml.
Full log: `outputs/pilot_runs/e2e_x86_20261009/run_log.txt`.

| Step | Command | Exit | Time |
|---|---|---|---|
| version | `voxeltrace --version` | 0 | 0.3 s |
| intake (no trial.yaml) | `voxeltrace validate-input trial --format json` | 2 (NEEDS_REEXPORT: 4 of 18 scans) | 11.8 s |
| config | `voxeltrace init-trial trial --trial-id E2E-X86-DRYRUN --timepoints baseline followup` | 0 | 0.3 s |
| intake | `voxeltrace validate-input trial` | 2 | 12.2 s |
| preflight | `voxeltrace preflight trial --out work/preflight` | 0 | 11.8 s |
| audit | `voxeltrace audit --input trial --output work/audit_v1` | 0 | 187 s |
| verify | `voxeltrace verify-bundle work/audit_v1/audit_bundle` | 0 (OK) | 0.3 s |
| summary | `voxeltrace summarize …`, `voxeltrace list-reviews …` | 0 | 0.3 s each |

Result: QIBA 2 ASSESSABLE / 1 ASSESSABLE_WITH_WARNINGS / 3 INSUFFICIENT_INFORMATION / 3
NOT_ASSESSABLE; EANM 3 / 3 / 3 (AW / II / NA); PERCIST 7 II / 2 NA; 17 reference-region
proposals pending review. **The three pair-verdict CSVs are byte-identical to the frozen
`external_validation_cohort_v1/audit_v2` bundle produced on the GB10 (aarch64)**, so the
migration to x86_64 changed no verdict.

Friction found and addressed in this session:

| Friction | Change |
|---|---|
| Six commands to get from a folder to a deliverable | `voxeltrace run-pilot` |
| `validate-input` exits 2 for the whole cohort because 4 of 18 scans need re-export, which reads like "stop" | the run-pilot gate audits anyway and records the policy; `--strict-intake` keeps the stricter behaviour |
| No sanitized hand-over format | `voxeltrace deliver` / `verify-delivery` (privacy scan, checksums) |
| Subjects without declared sites are pooled as UNASSIGNED; drift then compares different centres (here 132 "drift" events) | first page now says so explicitly; `intake-map --stage` writes `sites:` from the drop |
| Segmentation file names (SOP Instance UIDs) were written into `trial_audit.json` | names are hashed unless `--input-paths-in-clear` |
| "Why is this pair not comparable?" needed reading three JSON files | `voxeltrace explain-pair`, `pair_evidence_trace.csv` |

## 3. Dry run B: one command on the same cohort

`voxeltrace run-pilot --input trial --output run_pilot_v1` → exit 0,
`AUDIT_COMPLETE_WITH_REVIEW_PENDING`, wall 3 min 49 s, peak RSS 2.9 GB (validate-input 13.4 s,
audit 215 s, verify 0.003 s, delivery 0.6 s). The delivery package verified (`verify-delivery`
OK, 79 files, privacy scan CLEAN; `sha256sum -c DELIVERY_CHECKSUMS.sha256` OK). Pair verdicts
again byte-identical to the frozen cohort.

## 4. Dry run C: simulated partner drop (intake robustness, not validation)

`scripts/make_partner_drop.py` rebuilt the public cohort as a core lab might send it
(`outputs/partner_drop_sim/PartnerDrop_2026-10`): 3 sites, subjects renamed `Subject001…008`,
visits named `Baseline/Follow-Up`, `pre/post`, `BL/FU1`, series folders `PT_AC`, `CT_WB`,
`series_1`, `Segmentations`; one subject without CT; a protocol PDF placeholder, a JSON
sidecar, transfer notes, `.DS_Store`, `__MACOSX/`; plus two **simulated** modified copies of a
real PET series (new UIDs, labelled SIMULATED): a non-attenuation-corrected series and a second
AC reconstruction.

| Step | Result |
|---|---|
| `validate-input <drop>` | NEEDS_REEXPORT with `MULTIPLE_STUDIES_IN_SCAN` on every misread "scan", pointing to `intake-map` (before this session it reported only MULTIPLE_PET_SERIES and treated `__MACOSX` as a subject) |
| `intake-map … --stage staged_trial` (4.4 s) | 16 scan folders; 5 files ignored with reasons; NAC copy excluded by rule R1; **the follow-up with two AC PET series is NEEDS_REVIEW and not staged**; 15 scans staged with `sites:` and `timepoint_order` |
| `run-pilot --input staged_trial` (3 min 22 s) | `AUDIT_COMPLETE_WITH_REVIEW_PENDING`, 7 pairs, package OK |
| verdict check | **21 of 21 pair × rule-set rows identical** (verdict, reason codes, blocking rules) to the source subjects in the frozen cohort |

## 5. Generated artefacts (per run)

```
<work>/config/trial.yaml            only when the input had none
<work>/intake/validate_input.json
<work>/audit/audit_bundle/          immutable evidence bundle (+ pairing/, reports/site_summary.csv)
<work>/pilot_acceptance.json        VT-PILOT-ACCEPTANCE-1
<work>/PILOT_SUMMARY.md
<work>/pilot_run_log.json           step timings (only non-deterministic file besides manifests)
<work>/delivery_package/            see README_FIRST.md section 5
```
