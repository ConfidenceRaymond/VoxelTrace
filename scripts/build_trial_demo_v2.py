#!/usr/bin/env python3
"""Build the v2 synthetic comparability demo (fixtures only; runs NO audit).

  ../outputs/synthetic_comparability/perturbed_v2/<kind>/   PT + SEG + CT (copied unchanged)
                                                            + synthetic_fixture.json
  ../outputs/synthetic_comparability/trial_demo_v2/         trial.yaml + read-only links

BASELINE = real public data (read-only links). FOLLOWUP = SYNTHETIC_PERTURBATION copy whose
CT is the baseline CT copied unchanged (CT_COPIED_UNCHANGED_FROM_BASELINE). Follow-ups inherit
the baseline's human-accepted reference geometry as SYNTHETIC_INHERITED_REFERENCE. The
production review file (trial_demo/reference_review.yaml) is referenced read-only, never
copied or modified. v1 fixtures and outputs are left untouched. Refuses to overwrite.
"""

from __future__ import annotations

import sys

import yaml

from voxeltrace.config import REPO_ROOT
from voxeltrace.trial.perturb import KINDS, perturb_case

HACK = REPO_ROOT.parent
OUT = HACK / "outputs" / "synthetic_comparability"
REAL = HACK / "data/fdg_pet_ct_lesions/PETCT_0011f3deaf/dicom"
OTHERS = {"PETCT_db3bac356a": "SITE-B", "PETCT_bd52fdf529": "SITE-C"}


def main() -> int:
    perturbed, trial = OUT / "perturbed_v2", OUT / "trial_demo_v2"
    if perturbed.exists() or trial.exists():
        print("v2 fixtures exist; refusing to overwrite", file=sys.stderr)
        return 2
    trial.mkdir(parents=True)
    sites, synth, inherit = {}, {}, {}
    for i, kind in enumerate(KINDS):
        dst = perturb_case(REAL, perturbed / kind, kind, with_ct=True)
        subj = f"DEMO-{i + 1:02d}-{kind.upper()}"
        (trial / subj).mkdir()
        (trial / subj / "BASELINE").symlink_to(REAL, target_is_directory=True)
        (trial / subj / "FOLLOWUP").symlink_to(dst, target_is_directory=True)
        sites[subj] = "SITE-A" if i % 2 == 0 else "SITE-D"
        synth[f"{subj}/FOLLOWUP"] = f"SYNTHETIC_PERTURBATION {kind}"
        inherit[f"{subj}/FOLLOWUP"] = {"parent": f"{subj}/BASELINE"}
        print(f"built {kind}")
    for subj, site in OTHERS.items():
        (trial / subj).mkdir()
        (trial / subj / "BASELINE").symlink_to(
            HACK / f"data/fdg_pet_ct_lesions/{subj}/dicom", target_is_directory=True
        )
        sites[subj] = site
    (trial / "trial.yaml").write_text(
        yaml.safe_dump(
            {
                "trial_id": "VOXELTRACE-DEMO-002",
                "ruleset": "qiba-fdg-1.14",
                "timepoint_order": ["BASELINE", "FOLLOWUP"],
                "sites": sites,
                "synthetic_perturbations": synth,
                # SYNTHETIC fixture: keeps the historical (unreviewed-mask) PERCIST target
                # explicitly; real-data trials always require lesion review
                "lesion_evidence_policy": "LEGACY_UNREVIEWED_ALLOWED",
                "synthetic_reference_inheritance": inherit,
                "reference_review_file": "../trial_demo/reference_review.yaml",
                "site_flags": {"SITE-A": {"earl_approved_reconstruction": True}},
                "note": "BASELINE = real public data (read-only links); FOLLOWUP = "
                "SYNTHETIC_PERTURBATION copies with CT_COPIED_UNCHANGED_FROM_BASELINE; NOT real "
                "follow-up scans. Reference reviews are read from the v1 production file "
                "(read-only).",
            },
            sort_keys=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
