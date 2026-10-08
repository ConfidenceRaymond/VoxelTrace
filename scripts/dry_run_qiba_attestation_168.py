#!/usr/bin/env python3
"""DRY RUN ONLY: what would a valid QIBA reconstruction attestation change for ACRIN 168?

Creates a SIMULATED (test-only) attestation fixture for both 168 timepoints in a temporary
directory that is deleted afterwards, runs the unchanged audit with
``allow_simulated_attestations=True`` and compares QIBA / EANM / PERCIST with the plain audit.
The reconstruction values in the fixture are PLACEHOLDERS, not 168's real parameters (which
are unknown). No production attestation is written; the 168 namespace is not modified.

Writes only ../outputs/dry_runs/qiba_attestation_168_summary.json (no attestation inside).
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import yaml

from voxeltrace.config import REPO_ROOT
from voxeltrace.evidence.attestation import SCHEMA
from voxeltrace.rules.qiba_identity import protocol_identity
from voxeltrace.trial.audit import run_trial_audit, scan_facts
from voxeltrace.trial.discovery import discover_trial

NS = REPO_ROOT.parent / "outputs" / "acrin_longitudinal_168"
OUT = REPO_ROOT.parent / "outputs" / "dry_runs" / "qiba_attestation_168_summary.json"
RULESETS = ("qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0")
PLACEHOLDER = dict(
    reconstruction_method="SIMULATED-PLACEHOLDER",
    iterations=1,
    subsets=1,
    post_filter="SIMULATED-PLACEHOLDER",
    time_of_flight=False,
    psf_resolution_modelling=False,
)


def summarise(audit) -> dict:
    p = audit.pairs[0]
    c = next(c for c in p.checks if c.rule_id == "VT-PROTOCOL-IDENTITY")
    return {
        "verdict": p.verdict,
        "VT-PROTOCOL-IDENTITY": c.status,
        "PROTOCOL_IDENTITY": protocol_identity(c),
        "checks": {x.rule_id: x.status for x in p.checks},
        "attestations_used": [
            e["attestation_id"]
            for e in (c.observed or {}).get("attestation_evidence", [])
            if isinstance(c.observed, dict) and e["used"]
        ],
    }


def main() -> int:
    trial = NS / "trial"
    layout = discover_trial(trial)
    before = {rs: run_trial_audit(trial, rs) for rs in RULESETS}
    tps = {t.timepoint: t for t in before["qiba-fdg-1.14"].timepoints}
    subj = next(iter(layout.scans))
    with tempfile.TemporaryDirectory(prefix="vt_sim_attest_") as tmp:
        tmp = Path(tmp)
        content = b"SIMULATED scanner protocol export - dry run only"
        (tmp / "sim_export.txt").write_bytes(content)
        atts = []
        for name, tp in tps.items():
            fx = scan_facts(tp, layout.scans[subj][name])
            atts.append(
                {
                    "attestation_id": f"SIMULATED-168-{name}",
                    "subject_id": subj,
                    "timepoint": name,
                    "study_instance_uid": fx.study_instance_uid,
                    "series_instance_uid": fx.series_instance_uid,
                    "manufacturer": fx.manufacturer,
                    "manufacturer_model_name": fx.manufacturer_model_name,
                    "software_version": fx.software_versions[0],
                    **PLACEHOLDER,
                    "source": {
                        "source_type": "SCANNER_PROTOCOL_EXPORT",
                        "path": "sim_export.txt",
                        "sha256": hashlib.sha256(content).hexdigest(),
                    },
                    "attestor_id": "SIMULATED",
                    "attestor_role": "QUALIFIED_PET_PHYSICIST",
                    "attested_at": "2026-10-08T00:00:00Z",
                    "rule_scope": list(RULESETS),  # all three: proves EANM/PERCIST ignore it
                    "notes": "SIMULATED dry-run fixture; placeholder values; never production",
                    "confidence": "CONFIRMED",
                    "simulated": True,
                }
            )
        f = tmp / "sim_attestations.yaml"
        f.write_text(yaml.safe_dump({"schema": SCHEMA, "attestations": atts}))
        refused = run_trial_audit(trial, "qiba-fdg-1.14", attestations_file=f)
        after = {
            rs: run_trial_audit(trial, rs, attestations_file=f, allow_simulated_attestations=True)
            for rs in RULESETS
        }
        outcomes = [o.model_dump(mode="json") for o in after["qiba-fdg-1.14"].recon_attestations]
    out = {
        "note": "DRY RUN with SIMULATED placeholder attestations; not a result for 168. The "
        "production 168 audit has no attestation and stays NOT_ESTABLISHED / UNKNOWN.",
        "production_mode_refuses_simulated": [o.status for o in refused.recon_attestations],
        "fixture_validation": [
            {k: o[k] for k in ("attestation_id", "status", "reasons")} for o in outcomes
        ],  # fmt: skip
        "before": {rs: summarise(a) for rs, a in before.items()},
        "after_simulated_attestation": {rs: summarise(a) for rs, a in after.items()},
    }
    out["eanm_percist_unchanged"] = all(
        out["before"][rs] == out["after_simulated_attestation"][rs]
        for rs in ("eanm-fdg-2.0", "percist-1.0")
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
