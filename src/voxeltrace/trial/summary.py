"""Subject x timepoint matrix and site-level comparability summary."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any

from voxeltrace.trial.audit import TrialAudit

VERDICTS = ("ASSESSABLE", "ASSESSABLE_WITH_WARNINGS", "NOT_ASSESSABLE", "INSUFFICIENT_INFORMATION")


def matrix(audit: TrialAudit) -> list[dict[str, Any]]:
    rows = []
    by_pair = {(p.pair.subject_id, p.pair.followup): p for p in audit.pairs}
    for tp in audit.timepoints:
        p = by_pair.get((tp.subject_id, tp.timepoint))
        rows.append(
            {
                "subject": tp.subject_id,
                "timepoint": tp.timepoint,
                "site": tp.site_id,
                "synthetic_perturbation": tp.synthetic_perturbation or "",
                "scanner": tp.scanner,
                "software": tp.software,
                "reconstruction": tp.reconstruction,
                "suv_status": tp.suv_status,
                "uptake_min": round(tp.uptake_s / 60, 2) if tp.uptake_s else None,
                "liver_reference": tp.liver.status if tp.liver else None,
                "blood_pool_reference": tp.blood_pool.status if tp.blood_pool else None,
                "pair_verdict": p.verdict
                if p
                else (
                    "BASELINE"
                    if any(
                        q.pair.subject_id == tp.subject_id and q.pair.baseline == tp.timepoint
                        for q in audit.pairs
                    )
                    else "NO_PAIR"
                ),
                "reason_codes": ";".join(sorted({r.code for r in p.reasons})) if p else "",
                "failed_rules": ";".join(c.rule_id for c in p.checks if c.status == "FAIL")
                if p
                else "",
            }
        )
    return rows


def site_summary(audit: TrialAudit) -> dict[str, Any]:
    tps = {(t.subject_id, t.timepoint): t for t in audit.timepoints}
    out: dict[str, Any] = {
        "scans_analyzed": len(audit.timepoints),
        "pairs_analyzed": len(audit.pairs),
        "verdicts": dict(Counter(p.verdict for p in audit.pairs)),
        "synthetic_pairs": sum(1 for p in audit.pairs if p.synthetic_perturbation),
    }
    for dim in ("site", "scanner", "software", "reconstruction"):
        table: dict[str, Counter] = defaultdict(Counter)
        for p in audit.pairs:
            f = tps[(p.pair.subject_id, p.pair.followup)]
            key = {
                "site": f.site_id,
                "scanner": f.scanner,
                "software": f.software,
                "reconstruction": f.reconstruction,
            }[dim] or "UNKNOWN"
            table[str(key)][p.verdict] += 1
        out[f"by_{dim}"] = {k: dict(v) for k, v in sorted(table.items())}
    reasons: Counter = Counter()
    failures: Counter = Counter()
    for p in audit.pairs:
        for code in sorted({r.code for r in p.reasons}):  # sorted: set order varies per process
            reasons[code] += 1
        for c in p.checks:
            if c.status == "FAIL":
                failures[c.rule_id] += 1
    out["insufficient_information_by_reason"] = dict(reasons.most_common())
    out["reference_regions"] = {
        region: dict(
            Counter(
                (getattr(t, attr).status if getattr(t, attr) else "NOT_EVALUATED")
                for t in audit.timepoints
            )
        )
        for region, attr in (("LIVER", "liver"), ("BLOOD_POOL", "blood_pool"))
    }
    out["failures_by_rule"] = dict(failures.most_common())
    return out


REFERENCE_COLUMNS = [
    "subject",
    "timepoint",
    "region",
    "status",
    "source",
    "method",
    "centre_patient_mm",
    "diameter_mm",
    "length_mm",
    "voxel_count",
    "volume_ml",
    "suv_mean",
    "suv_sd",
    "cov",
    "suv_max",
    "sul_mean",
    "sul_sd",
    "usable_by_rules",
    "review_status",
    "review_decision",
    "reviewer",
    "algorithm_version",
    "proposal_sha256",
    "qc_image",
    "refusal",
]


def reference_rows(audit: TrialAudit) -> list[dict[str, Any]]:
    """One row per timepoint x region. Values of unreviewed proposals are shown for review
    only; ``usable_by_rules`` is true only for COMPUTED regions."""
    rows = []
    for tp in audit.timepoints:
        for region, res in (("LIVER", tp.liver), ("BLOOD_POOL", tp.blood_pool)):
            row: dict[str, Any] = {"subject": tp.subject_id, "timepoint": tp.timepoint}
            row["region"] = region
            if res is None:
                row.update(status="NOT_EVALUATED", usable_by_rules=False)
            else:
                d = res.model_dump()
                row.update({k: d.get(k) for k in REFERENCE_COLUMNS if k in d})
                row["usable_by_rules"] = res.status == "COMPUTED"
                row["review_status"] = review_status_of(res)
            rows.append(row)
    return rows


def review_status_of(res) -> str:
    """UNREVIEWED / ACCEPTED / ADJUSTED / REJECTED / OUTDATED / INVALID for an automatic
    proposal; '' for supplied regions or when no proposal exists."""
    if res is not None and res.source == "SYNTHETIC_INHERITED":
        return (
            "SYNTHETIC_INHERITED_REFERENCE"
            if res.status == "SYNTHETIC_INHERITED_REFERENCE"
            else "INHERITANCE_REFUSED"
        )
    if res is None or res.source != "AUTO_PROPOSAL" or res.status == "AUTO_NOT_FOUND":
        return ""
    return {
        "PROPOSED_REQUIRES_REVIEW": "UNREVIEWED",
        "REVIEW_OUTDATED": "OUTDATED",
        "REVIEW_INVALID": "INVALID",
        "REJECTED_BY_REVIEWER": "REJECTED",
    }.get(res.status) or {"ACCEPT": "ACCEPTED", "ADJUST": "ADJUSTED"}.get(
        res.review_decision or "", ""
    )


def review_worksheet(audit: TrialAudit) -> dict[str, Any]:
    """Pre-filled reference_review.yaml content (schema voxeltrace.reference-review/2) for
    every proposal that still needs a decision (UNREVIEWED, OUTDATED or INVALID). Every
    decision stays PENDING until a human edits it; the Reference Review page is the
    preferred way to record decisions."""
    import voxeltrace
    from voxeltrace.quant.suv import git_state
    from voxeltrace.trial.reference import REVIEW_SCHEMA, rule_context_for

    commit, dirty = git_state()
    reviews: dict[str, dict[str, Any]] = {}
    for tp in audit.timepoints:
        for region, res in (("LIVER", tp.liver), ("BLOOD_POOL", tp.blood_pool)):
            if review_status_of(res) not in ("UNREVIEWED", "OUTDATED", "INVALID"):
                continue
            geom = {
                "method": res.method
                or (
                    "SPHERE_AT_SUPPLIED_CENTRE"
                    if region == "LIVER"
                    else "CYLINDER_AT_SUPPLIED_CENTRE"
                ),
                "centre_patient_mm": list(res.centre_patient_mm or ()),
                "diameter_mm": res.diameter_mm,
                "length_mm": res.length_mm,
            }
            reviews.setdefault(f"{tp.subject_id}/{tp.timepoint}", {})[region] = {
                "subject": tp.subject_id,
                "timepoint": tp.timepoint,
                "region": region,
                "decision": "PENDING",
                "proposal_sha256": res.proposal_sha256,
                "proposal_algorithm_version": res.algorithm_version,
                "proposal_geometry": geom,
                "final_geometry": geom,
                "reviewer": "",
                "reviewed_at": "",
                "note": None,
                "software_version": voxeltrace.__version__,
                "git_commit": f"{commit}{'+dirty' if dirty else ''}",
                "rule_context": rule_context_for(region).model_dump(),
                "preview_unreviewed": {
                    "suv_mean": res.suv_mean,
                    "sul_mean": res.sul_mean,
                    "cov": res.cov,
                    "suv_max": res.suv_max,
                    "voxel_count": res.voxel_count,
                    "measurement_qc": res.refusal or "PASS",
                },
                "qc_image": res.qc_image,
                "previous_status": res.status,
            }
    return {"schema": REVIEW_SCHEMA, "reviews": reviews}


# --------------------------------------------------------------------------------------
# Pair, rule and failure tables; concise report (REAL and SYNTHETIC kept separate)
# --------------------------------------------------------------------------------------


def _origin(p) -> str:
    return "SYNTHETIC_PERTURBATION" if p.synthetic_perturbation else "REAL"


def pair_rows(audit: TrialAudit) -> list[dict[str, Any]]:
    tps = {(t.subject_id, t.timepoint): t for t in audit.timepoints}
    rows = []
    for p in audit.pairs:
        f = tps.get((p.pair.subject_id, p.pair.followup))
        rows.append(
            {
                "data_origin": _origin(p),
                "synthetic_perturbation": (f.synthetic_perturbation if f else None) or "",
                "subject": p.pair.subject_id,
                "baseline": p.pair.baseline,
                "followup": p.pair.followup,
                "ruleset": f"{p.ruleset_id} {p.ruleset_version}",
                "verdict": p.verdict,
                "protocol_comparability": p.comparability_category or "",
                "blocking_fail": ";".join(
                    c.rule_id for c in p.checks if c.impact == "blocking" and c.status == "FAIL"
                ),
                "blocking_unknown": ";".join(
                    c.rule_id for c in p.checks if c.impact == "blocking" and c.status == "UNKNOWN"
                ),
                "warnings": ";".join(
                    [
                        c.rule_id
                        for c in p.checks
                        if c.impact == "warning" and c.status in ("FAIL", "UNKNOWN")
                    ]
                    + [
                        f"{c.rule_id}(EXTERNALLY_ATTESTED)"
                        for c in p.checks
                        if c.status == "PASS_WITH_WARNING"
                    ]
                ),
                "reason_codes": ";".join(sorted({r.code for r in p.reasons})),
            }
        )
    return rows


def rule_rows(audit: TrialAudit) -> list[dict[str, Any]]:
    """Per rule x data origin: PASS / FAIL / UNKNOWN counts (origins never pooled)."""
    table: dict[tuple[str, str], Counter] = defaultdict(Counter)
    meta: dict[str, tuple[str, str]] = {}
    for p in audit.pairs:
        for c in p.checks:
            table[(c.rule_id, _origin(p))][c.status] += 1
            meta[c.rule_id] = (c.impact, c.standard)
    attested = any(cnt.get("PASS_WITH_WARNING") for cnt in table.values())
    return [
        {
            "rule_id": rid,
            "standard": meta[rid][1],
            "impact": meta[rid][0],
            "data_origin": origin,
            "PASS": cnt.get("PASS", 0),
            # never folded into PASS; column only present when an attestation was used
            **({"PASS_WITH_WARNING": cnt.get("PASS_WITH_WARNING", 0)} if attested else {}),
            "FAIL": cnt.get("FAIL", 0),
            "UNKNOWN": cnt.get("UNKNOWN", 0),
        }
        for (rid, origin), cnt in sorted(table.items())
    ]


def attestation_rows(audit: TrialAudit) -> list[dict[str, Any]]:
    """Report-only view of every supplied reconstruction attestation and whether the
    QIBA rule used it. Empty when no attestation file was supplied."""
    used: dict[str, list[str]] = defaultdict(list)
    for p in audit.pairs:
        for c in p.checks:
            if c.rule_id == "VT-PROTOCOL-IDENTITY" and isinstance(c.observed, dict):
                for e in c.observed.get("attestation_evidence", []):
                    if e.get("used"):
                        used[e["attestation_id"]].append(
                            f"{p.pair.subject_id} {p.pair.baseline}->{p.pair.followup}: "
                            f"{c.observed.get('protocol_identity')}"
                        )
    return [
        {
            "attestation_id": o.attestation_id,
            "subject": o.subject_id,
            "timepoint": o.timepoint,
            "status": o.status,
            "trust_level": o.trust_level,
            "attestor_role": o.attestor_role or "",
            "source_type": o.source_type or "",
            "source_sha256": o.source_sha256 or "",
            "rule_scope": ";".join(o.rule_scope),
            "affected_rule_set": audit.ruleset_id if used.get(o.attestation_id) else "",
            "used_for": "; ".join(used.get(o.attestation_id, [])),
            "reasons": ";".join(o.reasons),
        }
        for o in audit.recon_attestations
    ]


def compact_observed(observed: Any) -> str:
    """JSON of a check's observed value; for field-by-field comparisons only the fields that
    are not SAME are kept, so the differing field is visible."""
    if isinstance(observed, dict) and any(v == "SAME" for v in observed.values()):
        observed = {k: v for k, v in observed.items() if v != "SAME"}
    return json.dumps(observed, default=str)


def failure_rows(audit: TrialAudit) -> list[dict[str, Any]]:
    """Every FAIL / UNKNOWN check. failure_class: TECHNICAL (a condition was evaluated and
    not met) or MISSING_DATA (it could not be evaluated). Whether a synthetic failure was
    expected is judged against pre-declared expectations by the caller, never here."""
    rows = []
    for p in audit.pairs:
        for c in p.checks:
            if c.status not in ("FAIL", "UNKNOWN"):
                continue
            rows.append(
                {
                    "data_origin": _origin(p),
                    "subject": p.pair.subject_id,
                    "pair": f"{p.pair.baseline}->{p.pair.followup}",
                    "verdict": p.verdict,
                    "rule_id": c.rule_id,
                    "impact": c.impact,
                    "status": c.status,
                    "failure_class": "TECHNICAL" if c.status == "FAIL" else "MISSING_DATA",
                    "observed": compact_observed(c.observed),
                    "condition": c.expected,
                    "reason_codes": ";".join(sorted({r.code for r in c.reasons})),
                    "reason_detail": " | ".join(r.detail for r in c.reasons),
                }
            )
    return rows


def audit_report_md(audit: TrialAudit) -> str:
    """Concise human-readable report. REAL and SYNTHETIC_PERTURBATION findings are kept in
    separate sections and are never combined into one rate."""
    lines = [
        f"# Trial audit {audit.trial_id}: {audit.ruleset_id} ({audit.ruleset_version})",
        "",
        "RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. Comparability/assessability audit "
        "only; no biological or treatment response is assessed.",
        "",
        f"- Scans: {len(audit.timepoints)}; pairs: {len(audit.pairs)}; reference reviews "
        f"applied: {audit.reference_reviews_applied}",
    ]
    if audit.overrides:
        lines.append(f"- Trial overrides: {'; '.join(audit.overrides)}")
    for origin, title in (
        ("REAL", "REAL DATA FINDINGS"),
        ("SYNTHETIC_PERTURBATION", "SYNTHETIC_PERTURBATION FINDINGS"),
    ):
        pairs = [r for r in pair_rows(audit) if r["data_origin"] == origin]
        lines += ["", f"## {title}", ""]
        if origin == "REAL":
            real_tps = [t for t in audit.timepoints if not t.synthetic_perturbation]
            lines.append(f"Real scans: {len(real_tps)}.")
            for t in real_tps:
                refs = ", ".join(
                    f"{name} {r.status if r else 'NOT_EVALUATED'}"
                    for name, r in (("liver", t.liver), ("blood pool", t.blood_pool))
                )
                lines.append(
                    f"- {t.subject_id}/{t.timepoint}: SUV {t.suv_status}; {refs}"
                    + (
                        f"; timepoint reasons: {sorted({r.code for r in t.reasons})}"
                        if t.reasons
                        else ""
                    )
                )
        if not pairs:
            lines.append(f"Pairs: none ({origin.lower()}).")
            continue
        verdicts = Counter(r["verdict"] for r in pairs)
        lines += [
            "",
            "Verdicts: " + ", ".join(f"{v} {verdicts.get(v, 0)}" for v in VERDICTS),
            "",
            "| subject | verdict | blocking FAIL | blocking UNKNOWN | warnings |",
            "|---|---|---|---|---|",
        ]
        lines += [
            f"| {r['subject']} | {r['verdict']} | {r['blocking_fail'] or '-'} | "
            f"{r['blocking_unknown'] or '-'} | {r['warnings'] or '-'} |"
            for r in pairs
        ]
    att = attestation_rows(audit)
    if att:
        lines += ["", "## Reconstruction attestations (LEVEL_C; report only)", ""]
        if any(r["used_for"] for r in att):
            lines += ["> **EXTERNAL RECONSTRUCTION ATTESTATION USED.** Reconstruction identity "
                      "for the pairs below is externally attested, NOT DICOM-proven "
                      "(QIBA rule set only).", ""]  # fmt: skip
        lines += [
            "| attestation | subject/timepoint | status | role | source | sha256 | used for |",
            "|---|---|---|---|---|---|---|",
        ]
        lines += [
            f"| {r['attestation_id']} | {r['subject']}/{r['timepoint']} | {r['status']} | "
            f"{r['attestor_role']} | {r['source_type']} | {r['source_sha256'][:12]} | "
            f"{r['used_for'] or '-'} |"
            for r in att
        ]
    lines += ["", "## Reference regions", ""]
    for region, counts in site_summary(audit)["reference_regions"].items():
        lines.append(f"- {region}: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    return "\n".join(lines) + "\n"
