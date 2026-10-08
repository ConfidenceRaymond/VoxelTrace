"""QIBA-only reconstruction identity with external attestation (trust LEVEL_C).

Used ONLY by the qiba-fdg-1.14 rule set; EANM and PERCIST keep the shared
``reconstruction_identity`` unchanged. Basis: QIBA FDG-PET/CT v1.14 accepts metadata not
captured by the scanner from trial documentation (lines 934-939; Appendix E lists
"Reconstruction method"); docs/reconstruction_attestation_policy.md.

PROTOCOL_IDENTITY (reported in ``observed`` whenever an attestation was supplied, and by
``protocol_identity(check)`` for every check):
  ESTABLISHED               DICOM (LEVEL_A) shows identity                  -> PASS
  ESTABLISHED_WITH_WARNING  every DICOM-unknown reconstruction parameter is
                            filled by VALID, in-scope LEVEL_C attestations
                            at BOTH timepoints and they agree             -> PASS_WITH_WARNING
  NOT_ESTABLISHED           anything still unknown                          -> UNKNOWN
  CONTRADICTED              DICOM differs, attested values differ between
                            timepoints, or an attestation disagrees with
                            DICOM / another attestation                     -> FAIL
Attestations never fill non-reconstruction unknowns (units, voxel size, corrections ...).
With no attestation supplied the check is byte-identical to the shared rule.
"""

from __future__ import annotations

from typing import Any

from voxeltrace.evidence.attestation import RECON_PARAMETERS, AttestationOutcome, _norm
from voxeltrace.evidence.comparability import CORRECTIONS_COMPARED
from voxeltrace.rules.common import reconstruction_identity
from voxeltrace.rules.schema import Rule, RuleCheck
from voxeltrace.trial.reasons import Reason
from voxeltrace.trial.schema import PairContext, ScanTimepoint

RULESET_ID = "qiba-fdg-1.14"
VERSION_SUFFIX = "+qiba-attestation-1"
WARNING = "EXTERNAL RECONSTRUCTION ATTESTATION USED"
_DICOM_ATTR = {
    "reconstruction_method": "reconstruction_method",
    "iterations": "iterations",
    "subsets": "subsets",
    "post_filter": "convolution_kernel",
    "time_of_flight": "time_of_flight",
    "psf_resolution_modelling": "psf_resolution_modelling",
}
_STATUS_TO_IDENTITY = {
    "PASS": "ESTABLISHED",
    "PASS_WITH_WARNING": "ESTABLISHED_WITH_WARNING",
    "UNKNOWN": "NOT_ESTABLISHED",
    "FAIL": "CONTRADICTED",
}


def protocol_identity(c: RuleCheck) -> str | None:
    """PROTOCOL_IDENTITY of a VT-PROTOCOL-IDENTITY check (any rule set)."""
    if c.rule_id != "VT-PROTOCOL-IDENTITY":
        return None
    if isinstance(c.observed, dict) and "protocol_identity" in c.observed:
        return c.observed["protocol_identity"]
    return _STATUS_TO_IDENTITY.get(c.status)


def _dicom(tp: ScanTimepoint, param: str) -> Any:
    f = getattr(tp.protocol.reconstruction, _DICOM_ATTR[param])
    return f.value if f.known else None


def _evidence(o: AttestationOutcome, used: bool) -> dict[str, Any]:
    return {
        "attestation_id": o.attestation_id,
        "timepoint": o.timepoint,
        "status": o.status,
        "in_scope": RULESET_ID in o.rule_scope,
        "used": used,
        "attestor_role": o.attestor_role,
        "source_type": o.source_type,
        "source_sha256": o.source_sha256,
        "trust_level": o.trust_level,
        "reasons": o.reasons,
    }


def _finish(
    base: RuleCheck,
    status: str,
    outs: list[AttestationOutcome],
    used: set[str],
    reasons: list[Reason],
    message: str,
) -> RuleCheck:
    obs = dict(base.observed) if isinstance(base.observed, dict) else {"dicom": base.observed}
    obs["protocol_identity"] = _STATUS_TO_IDENTITY[status]
    obs["attestation_evidence"] = [_evidence(o, o.attestation_id in used) for o in outs]
    if used:
        obs["warning"] = WARNING
    return base.model_copy(
        update={
            "status": status,
            "observed": obs,
            "rule_version": base.rule_version + VERSION_SUFFIX,
            "reasons": (base.reasons if status == "UNKNOWN" else []) + reasons,
            "message": message,
        }
    )


def qiba_reconstruction_identity(rule: Rule, ctx: PairContext) -> RuleCheck:
    base = reconstruction_identity(rule, ctx)
    supplied = ctx.recon_attestations
    if not supplied:
        return base  # unchanged behaviour
    b, f = ctx.baseline, ctx.followup
    outs = [o for tp in (b.timepoint, f.timepoint) for o in supplied.get(tp, [])]
    if b.protocol is None or f.protocol is None:
        return _finish(base, "UNKNOWN", outs, set(), [], base.message)
    usable = {
        tp.timepoint: [o for o in supplied.get(tp.timepoint, []) if o.in_scope(RULESET_ID)]
        for tp in (b, f)
    }
    not_usable = [
        Reason(
            code="RECONSTRUCTION_ATTESTATION_NOT_USABLE",
            field=o.attestation_id,
            detail=f"{o.timepoint}: {o.status}"
            + ("" if RULESET_ID in o.rule_scope else " (rule set not in rule_scope)")
            + (f" {';'.join(o.reasons)}" if o.reasons else ""),
            confidence="CONFIRMED",
            evidence_basis="attestation validation",
        )
        for o in outs
        if not o.in_scope(RULESET_ID)
    ]

    # 1. contradictions: attestation vs DICOM, attestation vs attestation (per timepoint)
    contra: list[str] = []
    effective: dict[str, dict[str, Any]] = {}
    for tp in (b, f):
        eff: dict[str, Any] = {}
        for p in RECON_PARAMETERS:
            dicom = _dicom(tp, p)
            att_vals = {
                _norm(o.attestation.value(p))
                for o in usable[tp.timepoint]
                if o.attestation is not None and o.attestation.value(p) is not None
            }
            if len(att_vals) > 1:
                contra.append(f"{tp.timepoint}.{p}: attestations disagree {sorted(att_vals)}")
            if dicom is not None and att_vals and _norm(dicom) not in att_vals:
                contra.append(f"{tp.timepoint}.{p}: DICOM {dicom!r} vs attested {sorted(att_vals)}")
            eff[p] = _norm(dicom) if dicom is not None else next(iter(att_vals), None)
        applied = tp.protocol.corrections.applied_set()
        for o in usable[tp.timepoint]:
            att_corr = o.attestation.corrections if o.attestation else None
            if att_corr is not None and applied is not None:
                a = {c.casefold() for c in att_corr} & set(CORRECTIONS_COMPARED)
                d = applied & set(CORRECTIONS_COMPARED)
                if a != d:
                    contra.append(
                        f"{tp.timepoint}.corrections: DICOM {sorted(d)} vs attested {sorted(a)}"
                    )
        effective[tp.timepoint] = eff
    used_ids = {o.attestation_id for tp in usable for o in usable[tp]}
    if contra:
        return _finish(
            base,
            "FAIL",
            outs,
            set(),
            [
                Reason(
                    code="RECONSTRUCTION_ATTESTATION_CONTRADICTS",
                    detail=c,
                    confidence="CONFIRMED",
                    evidence_basis="LEVEL_A DICOM vs LEVEL_C attestation",
                )
                for c in contra
            ],
            "CONTRADICTED: " + "; ".join(contra),
        )
    if base.status in ("PASS", "FAIL"):
        # DICOM decides; attestations only corroborated (no contradiction found above)
        return _finish(base, base.status, outs, set(), not_usable if base.status == "FAIL" else [],
                       base.message)  # fmt: skip

    # 2. DICOM UNKNOWN: may LEVEL_C fill every unknown reconstruction parameter?
    unk = [k for k, v in (base.observed or {}).items() if v == "UNKNOWN"]
    non_recon = [u for u in unk if u not in RECON_PARAMETERS]
    if non_recon or not usable[b.timepoint] or not usable[f.timepoint]:
        why = (
            f"non-reconstruction fields unknown {non_recon} (attestation cannot fill)"
            if non_recon
            else "no valid in-scope attestation at "
            + ", ".join(tp.timepoint for tp in (b, f) if not usable[tp.timepoint])
        )
        return _finish(base, "UNKNOWN", outs, set(), not_usable, f"NOT_ESTABLISHED: {why}")
    missing, differ = [], []
    for p in unk:
        vb, vf = effective[b.timepoint][p], effective[f.timepoint][p]
        if vb is None or vf is None:
            missing.append(p)
        elif vb != vf:
            differ.append(f"{p}: {vb} vs {vf}")
    if differ:
        return _finish(
            base,
            "FAIL",
            outs,
            used_ids,
            [
                Reason(
                    code="RECONSTRUCTION_ATTESTATION_CONTRADICTS",
                    detail=d,
                    confidence="CONFIRMED",
                    evidence_basis="LEVEL_C attestation at both timepoints",
                )
                for d in differ
            ],
            f"CONTRADICTED (externally attested): {differ}; {WARNING}",
        )
    if missing:
        return _finish(
            base,
            "UNKNOWN",
            outs,
            set(),
            not_usable
            + [
                Reason(
                    code="RECONSTRUCTION_ATTESTATION_NOT_USABLE",
                    field=p,
                    detail=f"{p} unknown in DICOM and not attested at both timepoints",
                    confidence="CONFIRMED",
                    evidence_basis="attestation content",
                )
                for p in missing
            ],
            f"NOT_ESTABLISHED: not attested {missing}",
        )
    return _finish(
        base,
        "PASS_WITH_WARNING",
        outs,
        used_ids,
        [
            Reason(
                code="EXTERNAL_RECONSTRUCTION_ATTESTATION",
                field=",".join(unk),
                detail=f"{WARNING}: {unk} established from LEVEL_C attestations "
                + ", ".join(sorted(used_ids))
                + " (externally attested, NOT DICOM-proven)",
                confidence="CONFIRMED",
                evidence_basis="validated LEVEL_C attestation (QIBA v1.14 Appendix E)",
            )
        ],
        f"ESTABLISHED_WITH_WARNING: {WARNING}",
    )
