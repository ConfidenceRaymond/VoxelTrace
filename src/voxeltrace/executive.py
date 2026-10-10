"""Deterministic audit top page and executive summary (no AI, no free-text generation).

Every number comes from the audit objects; every recommendation is the catalogued
``remediation`` of a reason code that actually occurred (trial reason catalogue first, then the
preflight catalogue). Ordering is by count, then code, so identical audits give identical text.
Verdicts are reported, never changed.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import voxeltrace

TOP_N = 5
VERDICT_ORDER = (
    "ASSESSABLE",
    "ASSESSABLE_WITH_WARNINGS",
    "INSUFFICIENT_INFORMATION",
    "NOT_ASSESSABLE",
)


def _remediation(code: str) -> tuple[str, str]:
    from voxeltrace.preflight.reasons import CATALOG as PF
    from voxeltrace.trial.reasons import CATALOG as TR

    if code in TR:
        return TR[code].remediation, TR[code].site_can_fix
    if code in PF:
        return PF[code].remediation, PF[code].recoverable
    return "no catalogued remediation; see the pair checks for the exact evidence", "UNKNOWN"


def top_page(
    trial_id: str,
    summary: dict[str, Any],
    audits: dict[str, Any],
    *,
    rollup: list[dict[str, Any]] | None = None,
    pairing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Counts, verdict distribution per rule set, and the most frequent blocking reasons,
    counted once per pair (subject) across rule sets. With ``rollup`` / ``pairing`` (audit
    package outputs) the page also lists the sites requiring action and the pairing status."""
    pair_codes: dict[str, set[str]] = defaultdict(set)
    code_rulesets: dict[str, set[str]] = defaultdict(set)
    subjects, real_pairs = set(), set()
    failed_expected: dict[str, str] = {}
    verdicts: dict[str, dict[str, int]] = {}
    for rs, a in audits.items():
        verdicts[rs] = {v: 0 for v in VERDICT_ORDER}
        for p in a.pairs:
            key = f"{p.pair.subject_id}:{p.pair.baseline}->{p.pair.followup}"
            if not p.synthetic_perturbation:
                real_pairs.add(key)
            verdicts[rs][p.verdict] = verdicts[rs].get(p.verdict, 0) + 1
            for c in p.checks:
                if c.impact == "blocking" and c.status in ("FAIL", "UNKNOWN"):
                    for r in c.reasons:
                        pair_codes[key].add(r.code)
                        code_rulesets[r.code].add(rs)
                    if (
                        c.status == "FAIL" and not c.reasons
                    ):  # decided failure without a reason code
                        code = f"{c.rule_id} FAIL"
                        pair_codes[key].add(code)
                        code_rulesets[code].add(rs)
                        failed_expected[code] = c.expected
    for a in audits.values():
        subjects.update(t.subject_id for t in a.timepoints)
    counts = Counter(code for codes in pair_codes.values() for code in codes)
    top = []
    for code, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]:
        if code in failed_expected:  # the data were decided and do not meet the criterion
            rem, fix = (
                f"criterion not met ({failed_expected[code]}); a re-export cannot change measured values",
                "NO",
            )
        else:
            rem, fix = _remediation(code)
        top.append({"reason_code": code, "pairs_affected": n, "rulesets": sorted(code_rulesets[code]),
                    "site_can_fix": fix, "recommendation": rem})  # fmt: skip
    pf = summary.get("preflight", {})
    pf_codes = pf.get("reason_codes", {})
    from voxeltrace.trial.rollup import sites_requiring_action
    from voxeltrace.versions import EXECUTIVE_SUMMARY_SCHEMA

    states = pf.get("scan_states", {})
    ready = states.get("READY_TO_QUANTIFY", 0) + states.get("READY_WITH_WARNINGS", 0)
    lesion_pending = sorted(
        {key for key, codes in pair_codes.items() if "LESION_REVIEW_REQUIRED" in codes}
    )
    first_rs = next(iter(audits), None)
    extra = {
        "quantitative_readiness": {"scans": pf.get("scans", 0), "ready": ready,
                                   "not_ready": pf.get("scans", 0) - ready},
        "comparability": {rs: {"pairs": sum(v.values()),
                               "usable": v.get("ASSESSABLE", 0) + v.get("ASSESSABLE_WITH_WARNINGS", 0)}
                          for rs, v in verdicts.items()},
        "sites_requiring_action": sites_requiring_action(rollup, first_rs) if rollup and first_rs else [],
        "sites_ruleset": first_rs,
        "unresolved_human_review": {
            "reference_region_reviews_pending": summary.get("review_tasks_pending", 0),
            "pairs_awaiting_lesion_review": len(lesion_pending),
            "pairing_items_needing_review": (pairing or {}).get("severity_counts", {}).get("NEEDS_REVIEW", 0),
        },
        "unassigned_site_scans": sum(r["scans_total"] for r in rollup or [] if r["level"] == "SITE" and r["site"] == "UNASSIGNED" and r["ruleset"] == first_rs),
        "pairing_status": (pairing or {}).get("status", "NOT_RUN"),
        "pairing_subjects_blocked": (pairing or {}).get("subjects_blocked", []),
    }  # fmt: skip

    return {
        **extra,
        "schema": EXECUTIVE_SUMMARY_SCHEMA,
        "trial_id": trial_id,
        "subjects": len(subjects),
        "pairs": len({k for a in audits.values() for k in (f"{p.pair.subject_id}:{p.pair.baseline}->{p.pair.followup}" for p in a.pairs)}),
        "real_pairs": len(real_pairs),
        "scans": pf.get("scans", 0),
        "scan_states": pf.get("scan_states", {}),
        "verdicts": verdicts,
        "pending_reference_reviews": summary.get("review_tasks_pending", 0),
        "top_failure_reasons": top,
        "top_preflight_findings": [{"reason_code": k, "scans": v} for k, v in
                                   sorted(pf_codes.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]],
    }  # fmt: skip


def executive_summary(page: dict[str, Any]) -> list[str]:
    """Fixed-template sentences filled only with counts and catalogued remediations."""
    L = [f"{page['trial_id']}: {page['pairs']} baseline/follow-up pair(s) from {page['subjects']} subject(s), "
         f"{page['scans']} scan(s); {page['real_pairs']} pair(s) are real data."]  # fmt: skip
    for rs, v in page["verdicts"].items():
        parts = ", ".join(f"{n} {k}" for k, n in v.items() if n)
        L.append(f"{rs}: {parts or 'no pairs'}.")
    dnq = page["scan_states"].get("DO_NOT_QUANTIFY", 0)
    if dnq:
        L.append(f"{dnq} scan(s) cannot be quantified as exported (preflight DO_NOT_QUANTIFY).")
    if page["pending_reference_reviews"]:
        L.append(f"{page['pending_reference_reviews']} reference-region proposal(s) await a human decision; "
                 "until then the dependent rules stay UNKNOWN.")  # fmt: skip
    if page["top_failure_reasons"]:
        L.append("Recommended actions, most frequent blocking reason first:")
        for i, t in enumerate(page["top_failure_reasons"], 1):
            L.append(f"{i}. {t['reason_code']} ({t['pairs_affected']} pair(s); site can fix: {t['site_can_fix']}): "
                     f"{t['recommendation']}.")  # fmt: skip
    else:
        L.append("No blocking reason occurred.")
    L.append("These recommendations are the catalogued remediations of the observed reason codes. "
             "They do not change any verdict.")  # fmt: skip
    return L


def _at_a_glance(page: dict[str, Any]) -> list[str]:
    """First-page block (VT-EXECUTIVE-SUMMARY-2): readiness, comparability, sites, reviews."""
    if "quantitative_readiness" not in page:  # VT-EXECUTIVE-SUMMARY-1 pages
        return []
    q, u = page["quantitative_readiness"], page["unresolved_human_review"]
    L = ["## At a glance", "",
         f"- Quantitative readiness: {q['ready']} of {q['scans']} scan(s) can be quantified as exported; "
         f"{q['not_ready']} cannot (DO_NOT_QUANTIFY or NEEDS_REVIEW).",
         "- Comparability (pairs usable for SUV-change interpretation = ASSESSABLE or ASSESSABLE_WITH_WARNINGS):"]  # fmt: skip
    L += [f"  - {rs}: {c['usable']} of {c['pairs']}" for rs, c in page["comparability"].items()]
    L.append(f"- Longitudinal pairing check: {page['pairing_status']}"
             + (f"; subjects blocked: {', '.join(page['pairing_subjects_blocked'])}" if page["pairing_subjects_blocked"] else ""))  # fmt: skip
    L.append(f"- Unresolved human review: {u['reference_region_reviews_pending']} reference-region proposal(s), "
             f"{u['pairs_awaiting_lesion_review']} pair(s) awaiting lesion review, "
             f"{u['pairing_items_needing_review']} pairing item(s).")  # fmt: skip
    if page.get("unassigned_site_scans"):
        L.append(f"- Sites: {page['unassigned_site_scans']} scan(s) have no declared site (UNASSIGNED). Declare "
                 "`sites:` in trial.yaml; until then UNASSIGNED drift events compare different centres and are not site drift.")  # fmt: skip
    sites = page["sites_requiring_action"]
    L += ["", f"### Sites requiring action ({page['sites_ruleset']})", ""]
    if sites:
        L += [
            "| Site | Scans not ready | Pairs not usable | Pairs | Top reasons |",
            "|---|---|---|---|---|",
        ]
        L += [f"| {x['site']} | {x['scans_not_ready']} | {x['pairs_not_usable']} | {x['pairs_total']} | {x['top_reasons'] or '-'} |" for x in sites]  # fmt: skip
    else:
        L.append("none")
    return L + [""]


def top_page_md(page: dict[str, Any]) -> str:
    L = [f"# Audit summary: {page['trial_id']}", "", f"{voxeltrace.DISCLAIMER}", "",
         "| Subjects | Pairs | Real pairs | Scans | Pending reference reviews |", "|---|---|---|---|---|",
         f"| {page['subjects']} | {page['pairs']} | {page['real_pairs']} | {page['scans']} | {page['pending_reference_reviews']} |",
         "", *_at_a_glance(page), "## Verdicts", "", "| Rule set | " + " | ".join(VERDICT_ORDER) + " |",
         "|---|" + "---|" * len(VERDICT_ORDER)]  # fmt: skip
    for rs, v in page["verdicts"].items():
        L.append(f"| {rs} | " + " | ".join(str(v.get(k, 0)) for k in VERDICT_ORDER) + " |")
    L += ["", "## Top blocking reasons (pairs affected, any rule set)", "",
          "| Reason | Pairs | Rule sets | Site can fix | Recommendation |", "|---|---|---|---|---|"]  # fmt: skip
    L += [f"| {t['reason_code']} | {t['pairs_affected']} | {', '.join(t['rulesets'])} | {t['site_can_fix']} | {t['recommendation']} |"
          for t in page["top_failure_reasons"]] or ["| none | | | | |"]  # fmt: skip
    L += ["", "## Executive summary", ""] + executive_summary(page)
    return "\n".join(L) + "\n"
