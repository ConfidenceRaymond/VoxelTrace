"""Report-only view of reconstruction attestation evidence from an exported trial_audit.json.

Nothing here creates, edits or signs an attestation. Used by app/pages/5_Reconstruction_Evidence.py.
"""

from __future__ import annotations

from typing import Any

BANNER = "EXTERNAL RECONSTRUCTION ATTESTATION USED"
_STATUS_TO_IDENTITY = {
    "PASS": "ESTABLISHED",
    "PASS_WITH_WARNING": "ESTABLISHED_WITH_WARNING",
    "UNKNOWN": "NOT_ESTABLISHED",
    "FAIL": "CONTRADICTED",
}


def identity_rows(audit: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per pair: PROTOCOL_IDENTITY and the attestations the rule consulted."""
    rows = []
    for p in audit.get("pairs", []):
        c = next((c for c in p["checks"] if c["rule_id"] == "VT-PROTOCOL-IDENTITY"), None)
        if c is None:
            continue
        obs = c.get("observed") if isinstance(c.get("observed"), dict) else {}
        ev = obs.get("attestation_evidence", [])
        rows.append(
            {
                "subject": p["pair"]["subject_id"],
                "pair": f"{p['pair']['baseline']} -> {p['pair']['followup']}",
                "rule_set": audit.get("ruleset_id"),
                "verdict": p["verdict"],
                "check_status": c["status"],
                "protocol_identity": obs.get("protocol_identity")
                or _STATUS_TO_IDENTITY.get(c["status"]),
                "externally_attested": any(e.get("used") for e in ev),
                "attestations_used": ", ".join(e["attestation_id"] for e in ev if e.get("used")),
                "trust_level": "LEVEL_C" if any(e.get("used") for e in ev) else "",
                "message": c.get("message", ""),
            }
        )
    return rows


def attestation_table(audit: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "attestation_id": o["attestation_id"],
            "subject/timepoint": f"{o['subject_id']}/{o['timepoint']}",
            "status": o["status"],
            "trust_level": o.get("trust_level", "LEVEL_C"),
            "attestor_role": o.get("attestor_role"),
            "source_type": o.get("source_type"),
            "source_sha256": o.get("source_sha256"),
            "rule_scope": ", ".join(o.get("rule_scope", [])),
            "reasons": "; ".join(o.get("reasons", [])),
        }
        for o in audit.get("recon_attestations", [])
    ]


def banner_needed(audit: dict[str, Any]) -> bool:
    return any(r["externally_attested"] for r in identity_rows(audit))
