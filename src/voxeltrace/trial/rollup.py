"""Site and scanner rollup (VT-SITE-ROLLUP-1). Reporting only; counts, never verdicts.

One row per (level, site, scanner, rule set):
  level SITE     every scan / pair of the site (subjects without a site are UNASSIGNED)
  level SCANNER  the scans of one scanner model at the site; a pair counts under a scanner
                 only when both of its scans are on it, otherwise under ``MIXED_SCANNERS``

The rows reconcile exactly with the subject-level outputs (``check_rollup``): for every rule
set, SITE rows sum to the preflight scan count and the pair-verdict counts, and the SCANNER
rows of a site sum to its SITE row.

Reconstruction evidence maturity is the weakest trust level over the reconstruction fields of
each scan's protocol fingerprint (LEVEL_A structured attribute ... NONE missing), counted per
level. ``missing_metadata_rate`` is the mean fraction of fingerprint fields MISSING over the
scans that have a fingerprint.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

SITE_ROLLUP_SCHEMA = "VT-SITE-ROLLUP-1"
RECON_FIELDS = ("reconstruction_method", "iterations", "subsets", "filter_kernel",
                "time_of_flight", "psf_resolution_modelling")  # fmt: skip
TRUST_RANK = ("LEVEL_A", "LEVEL_B", "LEVEL_C", "LEVEL_D", "LEVEL_E", "LEVEL_U", "NONE")
VERDICTS = ("ASSESSABLE", "ASSESSABLE_WITH_WARNINGS", "NOT_ASSESSABLE", "INSUFFICIENT_INFORMATION")
SCAN_STATES = ("READY_TO_QUANTIFY", "READY_WITH_WARNINGS", "DO_NOT_QUANTIFY", "NEEDS_REVIEW")
MIXED = "MIXED_SCANNERS"
UNKNOWN_SCANNER = "UNKNOWN_SCANNER"


def _recon_maturity(fp: Any) -> str:
    levels = []
    for f in RECON_FIELDS:
        fld = fp.fields.get(f)
        if fld is None or fld.trust == "NOT_APPLICABLE":
            continue
        levels.append(fld.trust if fld.trust in TRUST_RANK else "LEVEL_U")
    return max(levels, key=TRUST_RANK.index) if levels else "NONE"


def pair_blocking_codes(p: Any) -> set[str]:
    """Blocking FAIL/UNKNOWN reason codes of one pair (a decided FAIL without a reason code is
    reported as '<rule_id> FAIL'), as in the executive summary."""
    codes = set()
    for c in p.checks:
        if c.impact == "blocking" and c.status in ("FAIL", "UNKNOWN"):
            codes.update(r.code for r in c.reasons)
            if c.status == "FAIL" and not c.reasons:
                codes.add(f"{c.rule_id} FAIL")
    return codes


def site_rollup(sites: dict[str, str], pf: Any, audits: dict[str, Any], fps: dict, drift: Any) -> list[dict[str, Any]]:  # fmt: skip
    first = next(iter(audits.values())) if audits else None
    site_of = lambda subj: sites.get(subj or "") or "UNASSIGNED"  # noqa: E731
    scanner_of: dict[tuple[str, str], str] = {}
    pseudo_scanner: dict[str, str] = {}
    if first is not None:
        for t in first.timepoints:
            sc = t.scanner or UNKNOWN_SCANNER
            scanner_of[(t.subject_id, t.timepoint)] = sc
            if t.pet_series_pseudonym:
                pseudo_scanner[t.pet_series_pseudonym] = sc

    # scan-level facts (rule-set independent)
    scan_rows = []
    for sc in pf.scans:
        key = (sc.subject or sc.scan, sc.scan)
        fp = fps.get(key)
        missing = (len(fp.completeness.get("missing", [])) / fp.completeness["total"]
                   if fp is not None and fp.completeness.get("total") else None)  # fmt: skip
        scan_rows.append({"site": site_of(sc.subject), "scanner": scanner_of.get(key, UNKNOWN_SCANNER),
                          "state": sc.state, "recon": _recon_maturity(fp) if fp is not None else "NO_FINGERPRINT",
                          "missing": missing})  # fmt: skip
    drift_by: Counter = Counter()
    for e in drift.events if drift is not None else []:
        drift_by[(e.site, pseudo_scanner.get(e.new_scan, UNKNOWN_SCANNER))] += 1

    rows = []
    for rs, a in audits.items():
        pair_rows = []
        for p in a.pairs:
            s1 = scanner_of.get((p.pair.subject_id, p.pair.baseline), UNKNOWN_SCANNER)
            s2 = scanner_of.get((p.pair.subject_id, p.pair.followup), UNKNOWN_SCANNER)
            pair_rows.append({"site": site_of(p.pair.subject_id), "scanner": s1 if s1 == s2 else MIXED,
                              "verdict": p.verdict, "codes": pair_blocking_codes(p)})  # fmt: skip
        groups: dict[tuple[str, str], dict[str, list]] = defaultdict(
            lambda: {"scans": [], "pairs": []}
        )
        for r in scan_rows:
            groups[("SITE", r["site"], "*")]["scans"].append(r)  # type: ignore[index]
            groups[("SCANNER", r["site"], r["scanner"])]["scans"].append(r)  # type: ignore[index]
        for r in pair_rows:
            groups[("SITE", r["site"], "*")]["pairs"].append(r)  # type: ignore[index]
            groups[("SCANNER", r["site"], r["scanner"])]["pairs"].append(r)  # type: ignore[index]
        for (level, site, scanner), g in sorted(groups.items()):
            st = Counter(r["state"] for r in g["scans"])
            vd = Counter(r["verdict"] for r in g["pairs"])
            reasons = Counter(c for r in g["pairs"] for c in r["codes"])
            recon = Counter(r["recon"] for r in g["scans"])
            miss = [r["missing"] for r in g["scans"] if r["missing"] is not None]
            if level == "SITE":
                ndrift = sum(n for (s, _), n in drift_by.items() if s == site)
            else:
                ndrift = drift_by.get((site, scanner), 0)
            rows.append({
                "level": level, "site": site, "scanner": scanner, "ruleset": rs,
                "scans_total": len(g["scans"]),
                **{f"scans_{k.lower()}": st.get(k, 0) for k in SCAN_STATES},
                "pairs_total": len(g["pairs"]),
                **{f"pairs_{k.lower()}": vd.get(k, 0) for k in VERDICTS},
                "top_reasons": ";".join(f"{c}({n})" for c, n in sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))[:3]),
                "recon_evidence_maturity": ";".join(f"{k}:{recon[k]}" for k in sorted(recon, key=lambda k: (TRUST_RANK + ("NO_FINGERPRINT",)).index(k))),
                "drift_events": ndrift,
                "missing_metadata_rate": round(sum(miss) / len(miss), 3) if miss else None,
                "scans_without_fingerprint": recon.get("NO_FINGERPRINT", 0),
            })  # fmt: skip
    return rows


def check_rollup(rows: list[dict[str, Any]], pf: Any, audits: dict[str, Any]) -> list[str]:
    """Reconciliation errors (empty list = consistent)."""
    errs = []
    n_scans = len(pf.scans)
    for rs, a in audits.items():
        site_rows = [r for r in rows if r["ruleset"] == rs and r["level"] == "SITE"]
        if sum(r["scans_total"] for r in site_rows) != n_scans:
            errs.append(f"{rs}: SITE scans do not sum to {n_scans}")
        if sum(r["pairs_total"] for r in site_rows) != len(a.pairs):
            errs.append(f"{rs}: SITE pairs do not sum to {len(a.pairs)}")
        want = Counter(p.verdict for p in a.pairs)
        for v in VERDICTS:
            if sum(r[f"pairs_{v.lower()}"] for r in site_rows) != want.get(v, 0):
                errs.append(f"{rs}: SITE {v} does not sum to {want.get(v, 0)}")
        for sr in site_rows:
            sub = [
                r
                for r in rows
                if r["ruleset"] == rs and r["level"] == "SCANNER" and r["site"] == sr["site"]
            ]
            for k in ("scans_total", "pairs_total", *[f"pairs_{v.lower()}" for v in VERDICTS],
                      *[f"scans_{s.lower()}" for s in SCAN_STATES], "drift_events"):  # fmt: skip
                if sum(r[k] for r in sub) != sr[k]:
                    errs.append(f"{rs}/{sr['site']}: SCANNER rows do not sum to the SITE {k}")
            if sr["scans_total"] != sum(sr[f"scans_{s.lower()}"] for s in SCAN_STATES):
                errs.append(f"{rs}/{sr['site']}: scan states do not sum to scans_total")
    return errs


def sites_requiring_action(rows: list[dict[str, Any]], ruleset: str) -> list[dict[str, Any]]:
    """SITE rows of ``ruleset`` with any scan not ready, or any pair not ASSESSABLE*."""
    out = []
    for r in rows:
        if r["level"] != "SITE" or r["ruleset"] != ruleset:
            continue
        not_ready = r["scans_do_not_quantify"] + r["scans_needs_review"]
        blocked = r["pairs_not_assessable"] + r["pairs_insufficient_information"]
        if not_ready or blocked:
            out.append({"site": r["site"], "scans_not_ready": not_ready, "pairs_not_usable": blocked,
                        "pairs_total": r["pairs_total"], "top_reasons": r["top_reasons"]})  # fmt: skip
    return out
