"""Explicit schema and rule-bundle versions (see docs/schema_versioning.md).

Every exported artefact names the schema it was written with. Changing an artefact's
structure or meaning requires a NEW version string; old versions stay readable.
"""

from __future__ import annotations

import hashlib
import json

from voxeltrace.evidence.attestation import SCHEMA as ATTESTATION_SCHEMA
from voxeltrace.evidence.fingerprint import FP_SCHEMA
from voxeltrace.preflight.schema import PREFLIGHT_SCHEMA
from voxeltrace.trial.adjudication import ADJUDICATION_SCHEMA
from voxeltrace.trial.drift import DRIFT_SCHEMA

EVIDENCE_SCHEMA = "VT-EVIDENCE-1"  # ProtocolEvidence / EvidenceField (evidence/protocol.py)
TRIAL_AUDIT_SCHEMA = "VT-TRIAL-AUDIT-1"  # TrialAudit JSON (trial/audit.py); earlier files = v1
AUDIT_PACKAGE_SCHEMA = "VT-AUDIT-PACKAGE-1"  # whole-trial audit v2 outputs (pilot.py)
BUNDLE_SCHEMA = "VT-BUNDLE-1"  # immutable evidence bundle (bundle.py)
SITE_QUERY_SCHEMA = "VT-SITE-QUERY-1"

SCHEMAS = {
    "evidence": EVIDENCE_SCHEMA,
    "protocol_fingerprint": FP_SCHEMA,
    "preflight": PREFLIGHT_SCHEMA,
    "trial_audit": TRIAL_AUDIT_SCHEMA,
    "audit_package": AUDIT_PACKAGE_SCHEMA,
    "drift": DRIFT_SCHEMA,
    "attestation": ATTESTATION_SCHEMA,
    "adjudication": ADJUDICATION_SCHEMA,
    "bundle": BUNDLE_SCHEMA,
    "site_query": SITE_QUERY_SCHEMA,
}


def rule_bundle() -> dict:
    """Rule sets with every rule's id, version, impact and parameters, plus a sha256 over the
    canonical JSON: a changed threshold or rule changes the hash."""
    from voxeltrace.rules.registry import REGISTRY, get_ruleset

    sets = {}
    for rid in sorted(REGISTRY):
        rs = get_ruleset(rid)
        sets[rid] = {
            "version": rs.version,
            "standard": rs.standard,
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "version": r.version,
                    "impact": r.impact,
                    "parameters": r.parameters,
                    "function": getattr(fn, "__name__", repr(fn)),
                }
                for r, fn in rs.rules
            ],
        }
    canon = json.dumps(sets, sort_keys=True, separators=(",", ":"), default=str)
    return {"rulesets": sets, "rule_bundle_sha256": hashlib.sha256(canon.encode()).hexdigest()}
