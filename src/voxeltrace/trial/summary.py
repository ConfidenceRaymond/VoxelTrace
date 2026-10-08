"""Subject x timepoint matrix and site-level comparability summary."""

from __future__ import annotations

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
        for code in {r.code for r in p.reasons}:
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
