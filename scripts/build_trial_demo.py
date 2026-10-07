#!/usr/bin/env python3
"""Build the hackathon Trial Comparability Audit demo (REAL baseline + SYNTHETIC_PERTURBATION
follow-ups) under ../outputs/synthetic_comparability/ and run the audit with each rule set.

Never implies that synthetic follow-ups came from real patients. Originals are untouched
(baselines are read-only symlinks). Fails if a QIBA verdict differs from the expected one.
"""

from __future__ import annotations

import json
import sys

import yaml

from voxeltrace.config import REPO_ROOT
from voxeltrace.trial.audit import run_trial_audit
from voxeltrace.trial.export import export_audit
from voxeltrace.trial.perturb import EXPECTED, KINDS, perturb_case
from voxeltrace.trial.summary import site_summary

HACK = REPO_ROOT.parent
REAL = HACK / "data/fdg_pet_ct_lesions/PETCT_0011f3deaf/dicom"
OTHERS = {"PETCT_db3bac356a": "SITE-B", "PETCT_bd52fdf529": "SITE-C"}
OUT = HACK / "outputs/synthetic_comparability"


def main() -> int:
    perturbed = OUT / "perturbed"
    trial = OUT / "trial_demo"
    trial.mkdir(parents=True, exist_ok=True)
    sites, synth = {}, {}
    for i, kind in enumerate(KINDS):
        dst = perturbed / kind
        if not (dst / "SYNTHETIC_PERTURBATION.txt").exists():
            perturb_case(REAL, dst, kind)
        subj = f"DEMO-{i + 1:02d}-{kind.upper()}"
        (trial / subj).mkdir(exist_ok=True)
        for tp, target in (("BASELINE", REAL), ("FOLLOWUP", dst)):
            link = trial / subj / tp
            if not link.exists():
                link.symlink_to(target, target_is_directory=True)
        sites[subj] = "SITE-A" if i % 2 == 0 else "SITE-D"
        synth[f"{subj}/FOLLOWUP"] = f"SYNTHETIC_PERTURBATION {kind}"
    for subj, site in OTHERS.items():
        (trial / subj).mkdir(exist_ok=True)
        link = trial / subj / "BASELINE"
        if not link.exists():
            link.symlink_to(
                HACK / f"data/fdg_pet_ct_lesions/{subj}/dicom", target_is_directory=True
            )
        sites[subj] = site
    (trial / "trial.yaml").write_text(
        yaml.safe_dump(
            {
                "trial_id": "VOXELTRACE-DEMO-001",
                "ruleset": "qiba-fdg-1.14",
                "timepoint_order": ["BASELINE", "FOLLOWUP"],
                "sites": sites,
                "synthetic_perturbations": synth,
                "site_flags": {"SITE-A": {"earl_approved_reconstruction": True}},
                "note": "BASELINE = real public data (read-only links); "
                "FOLLOWUP = SYNTHETIC_PERTURBATION copies, NOT real follow-up scans.",
            },
            sort_keys=False,
        )
    )
    ok = True
    for rs in ("qiba-fdg-1.14", "percist-1.0", "eanm-fdg-2.0"):
        audit = run_trial_audit(trial, ruleset=rs)
        export_audit(audit, OUT / f"audit_{rs}")
        print(f"== {rs} ({audit.ruleset_version})")
        for p in audit.pairs:
            kind = p.pair.subject_id.split("-", 2)[2].lower()
            failed = [
                c.rule_id
                for c in p.checks
                if c.status in ("FAIL", "UNKNOWN") and c.impact == "blocking"
            ]
            line = (
                f"  {p.pair.subject_id:34} {p.verdict:26} blocking: {failed} "
                f"reasons: {sorted({r.code for r in p.reasons})}"
            )
            if rs == "qiba-fdg-1.14":
                exp_v, exp_rules = EXPECTED[kind]
                match = p.verdict == exp_v and set(exp_rules) <= set(failed)
                ok &= match
                line += "  [expected OK]" if match else f"  [MISMATCH: expected {exp_v}]"
            print(line)
        print("  summary:", json.dumps(site_summary(audit)["verdicts"]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
