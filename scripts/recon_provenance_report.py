#!/usr/bin/env python3
"""User-facing reconstruction provenance report for one real pair (reporting only).

  recon_provenance_report.py <subject> <outputs namespace> [--ruleset percist-1.0]

Reads every PET header of both timepoints (read-only), any attestation files in
<ns>/recon_attestations/*.yaml (none exist unless a site supplied one) and, if present,
<ns>/recon_corroboration.json (LEVEL_E). Writes <ns>/recon_provenance.{json,md}.
No rule, verdict or review file is touched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pydicom
import yaml

from voxeltrace.evidence.recon_trust import (
    ReconstructionAttestation,
    classify_identity,
    dicom_evidence,
    provenance_report_md,
)

ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str]) -> int:
    subject, ns = argv[1], ROOT / "outputs" / argv[2]
    ruleset = argv[argv.index("--ruleset") + 1] if "--ruleset" in argv else "percist-1.0"
    ev = {}
    for tp in ("baseline", "followup"):
        files = sorted((ROOT / "data" / "acrin_longitudinal" / subject / tp / "PET").glob("*.dcm"))
        ev[tp] = dicom_evidence([pydicom.dcmread(f, stop_before_pixels=True) for f in files], tp)
    atts = tuple(
        ReconstructionAttestation.model_validate(yaml.safe_load(p.read_text()))
        for p in sorted((ns / "recon_attestations").glob("*.yaml"))
    )
    corr_p = ns / "recon_corroboration.json"
    corr = json.loads(corr_p.read_text()) if corr_p.exists() else None
    a = classify_identity(ev["baseline"], ev["followup"], ruleset=ruleset, attestations=atts)
    out = {
        "subject": subject,
        "ruleset": ruleset,
        "attestations": len(atts),
        "assessment": a.model_dump(mode="json"),
        "evidence": {tp: [i.model_dump(mode="json") for i in v] for tp, v in ev.items()},
        "image_corroboration_overall": corr["overall"] if corr else None,
    }
    (ns / "recon_provenance.json").write_text(json.dumps(out, indent=2) + "\n")
    md = provenance_report_md(subject, a, ev, corroboration=corr, ruleset=ruleset)
    (ns / "recon_provenance.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
