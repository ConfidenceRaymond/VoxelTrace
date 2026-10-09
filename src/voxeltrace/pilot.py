"""Whole-trial comparability audit v2 (VT-AUDIT-PACKAGE-1): one command, one evidence bundle.

  run_audit(input_dir, output_dir, config=..., rulesets=..., attestations=..., adjudications=...)

Steps (all deterministic; no AI): discovery -> preflight -> ingestion + strict quantitative
validation + pair rules (unchanged trial audit, once per rule set) -> protocol fingerprints and
pair fingerprint comparison -> site drift -> review tasks -> attestation status -> human
adjudication status -> DRAFT site queries -> reports -> immutable bundle (manifest + sha256).

The report keeps evidence classes apart and never mixes them: REAL vs SYNTHETIC data,
HUMAN-REVIEWED evidence, EXTERNALLY ATTESTED evidence, IMAGE-DERIVED corroboration (not produced
by the audit) and UNRESOLVED evidence. Automated verdicts are never modified.
"""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import voxeltrace
from voxeltrace.bundle import finalize_bundle, inputs_manifest, runtime_environment, sha256_file
from voxeltrace.evidence.fingerprint import build_fingerprint, compare_protocol_fingerprints
from voxeltrace.executive import top_page, top_page_md
from voxeltrace.pdf import markdown_to_pdf
from voxeltrace.preflight import preflight_batch
from voxeltrace.preflight.export import export_preflight
from voxeltrace.quant.suv import git_state
from voxeltrace.trial.adjudication import adjudication_status, load_adjudications
from voxeltrace.trial.audit import TrialAudit, run_trial_audit
from voxeltrace.trial.discovery import discover_trial
from voxeltrace.trial.drift import ScanRecord, detect_drift
from voxeltrace.trial.export import export_audit
from voxeltrace.trial.layers import assessability_layers
from voxeltrace.trial.site_queries import site_queries, site_queries_md
from voxeltrace.trial.summary import attestation_rows, pair_rows
from voxeltrace.versions import AUDIT_PACKAGE_SCHEMA, BUNDLE_SCHEMA, SCHEMAS, rule_bundle

RULESETS = ("qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0")
DETERMINISTIC = [
    "preflight", "strict SUV/SUL validation", "protocol evidence extraction", "pair rules",
    "protocol fingerprints", "drift detection", "site query templates", "checksums",
]  # fmt: skip
NON_DETERMINISTIC = ["timestamps (started_at, finalized_at)", "runtime environment record"]


def _csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        fields: list[str] = []
        for r in rows:
            fields += [k for k in r if k not in fields]
        w = csv.DictWriter(fh, fieldnames=fields or ["empty"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def run_audit(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    config: str | Path | None = None,
    rulesets: tuple[str, ...] = RULESETS,
    attestations: str | Path | None = None,
    adjudications: str | Path | None = None,
    hash_inputs: bool = True,
    qc_images: bool = False,
    clear_input_paths: bool = False,
) -> dict[str, Any]:
    input_dir, out = Path(input_dir), Path(output_dir)
    bundle = out / "audit_bundle"
    if bundle.exists():
        raise FileExistsError(f"{bundle} exists; bundles are immutable (choose a new output)")
    bundle.mkdir(parents=True)
    started = datetime.now(UTC).isoformat(timespec="seconds")
    layout = discover_trial(input_dir, config)

    # 1. preflight
    pf = preflight_batch(input_dir)
    export_preflight(pf, bundle / "preflight")

    # 2. trial audits (unchanged code) per rule set
    audits: dict[str, TrialAudit] = {}
    for rs in rulesets:
        audits[rs] = run_trial_audit(
            input_dir, rs, config_path=config, attestations_file=attestations,
            qc_dir=bundle / "reviews" / "qc" if qc_images and rs == rulesets[0] else None,
        )  # fmt: skip
        export_audit(audits[rs], bundle / "rules" / rs)
        _csv(bundle / "pair_verdicts" / f"{rs}.csv", pair_rows(audits[rs]))
    first = audits[rulesets[0]]

    # 3. protocol fingerprints + pair comparisons
    fps, records, fp_rows = {}, [], []
    for t in first.timepoints:
        if t.protocol is None:
            continue
        fp = build_fingerprint(t.protocol, series_pseudonym=t.pet_series_pseudonym)
        fps[(t.subject_id, t.timepoint)] = fp
        dt = t.protocol.acquisition.acquisition_start_datetime
        date = str(dt.value)[:10] if dt.known else None
        records.append(ScanRecord(site=layout.sites.get(t.subject_id) or "UNASSIGNED",
                                  subject=t.subject_id, timepoint=t.timepoint,
                                  scan_pseudonym=t.pet_series_pseudonym or f"{t.subject_id}/{t.timepoint}",
                                  date=date, fingerprint=fp))  # fmt: skip
        fp_rows.append({"subject": t.subject_id, "timepoint": t.timepoint,
                        "site": layout.sites.get(t.subject_id) or "UNASSIGNED",
                        "protocol_fingerprint_sha256": fp.protocol_fingerprint_sha256,
                        "scan_fingerprint_sha256": fp.scan_fingerprint_sha256,
                        "fields_present": f"{fp.completeness['present']}/{fp.completeness['total']}",
                        "missing": ";".join(fp.completeness["missing"])})  # fmt: skip
    _json(bundle / "protocol" / "fingerprints.json",
          {f"{k[0]}/{k[1]}": v.model_dump(mode="json") for k, v in fps.items()})  # fmt: skip
    _csv(bundle / "protocol" / "fingerprints.csv", fp_rows)
    comps = {}
    for p in first.pairs:
        a, b = (
            fps.get((p.pair.subject_id, p.pair.baseline)),
            fps.get((p.pair.subject_id, p.pair.followup)),
        )
        if a and b:
            comps[f"{p.pair.subject_id}/{p.pair.baseline}->{p.pair.followup}"] = (
                compare_protocol_fingerprints(a, b).model_dump(mode="json"))  # fmt: skip
    _json(bundle / "protocol" / "pair_fingerprint_comparisons.json", comps)

    # 4. drift
    drift = detect_drift(records)
    _json(bundle / "protocol" / "drift.json", drift.model_dump(mode="json"))
    _csv(bundle / "protocol" / "drift_events.csv", [e.model_dump() for e in drift.events])

    # 5. quantitative evidence (status only; numbers stay in rules/<rs>/trial_audit.json)
    quant = [
        {"subject": t.subject_id, "timepoint": t.timepoint,
         "data_origin": "SYNTHETIC_PERTURBATION" if t.synthetic_perturbation else "REAL",
         "suv_status": t.suv_status, "suv_refusal_codes": ";".join(t.suv_refusal_codes),
         "uptake_min": round(t.uptake_s / 60, 2) if t.uptake_s else None,
         **{f"sul_{k}": v.status for k, v in (t.sul or {}).items()}}
        for t in first.timepoints
    ]  # fmt: skip
    _csv(bundle / "quantitative" / "timepoints.csv", quant)

    # 6. reviews (read-only copy of the human review file, if any) + review tasks
    review_file = Path(layout.reference_review_file) if layout.reference_review_file else None
    review_info: dict[str, Any] = {
        "review_file_present": bool(review_file and review_file.exists())
    }
    if review_file and review_file.exists():
        (bundle / "reviews").mkdir(parents=True, exist_ok=True)
        shutil.copy(review_file, bundle / "reviews" / "reference_review.yaml")
        review_info["review_file_sha256"] = sha256_file(review_file)
    tasks = [
        {"subject": t.subject_id, "timepoint": t.timepoint, "region": name, "status": r.status,
         "review_decision": r.review_decision or "",
         "task": "HUMAN_REVIEW_REQUIRED" if r.status == "PROPOSED_REQUIRES_REVIEW" else ""}
        for t in first.timepoints for name, r in (("LIVER", t.liver), ("BLOOD_POOL", t.blood_pool)) if r
    ]  # fmt: skip
    _csv(bundle / "reviews" / "review_status.csv", tasks)
    _json(bundle / "reviews" / "review_info.json", review_info)

    # 7. attestations (QIBA only reads them)
    att_rows = attestation_rows(audits["qiba-fdg-1.14"]) if "qiba-fdg-1.14" in audits else []
    _csv(bundle / "attestations" / "attestations.csv", att_rows)

    # 8. human adjudication status (automated verdicts unchanged)
    adj_records, chain = (
        load_adjudications(adjudications) if adjudications else ([], {"status": "NO_FILE"})
    )
    if adjudications and Path(adjudications).exists():
        (bundle / "adjudications").mkdir(parents=True, exist_ok=True)
        shutil.copy(adjudications, bundle / "adjudications" / "adjudications.jsonl")
    adj_rows = [r for a in audits.values() for r in adjudication_status(a.pairs, adj_records)]
    _csv(bundle / "adjudications" / "adjudication_status.csv", adj_rows)
    _json(bundle / "adjudications" / "chain.json", chain)

    # 9. DRAFT site queries
    items = []
    for sc in pf.scans:
        for f in sc.findings + [x for s in sc.series for x in s.findings]:
            items.append({"site": layout.sites.get(sc.subject or ""), "subject": sc.subject or sc.scan,
                          "scan": sc.scan, "reason_code": f.reason_code, "field": f.field,
                          "evidence": f.evidence})  # fmt: skip
    for rs, a in audits.items():
        for p in a.pairs:
            for c in p.checks:
                if c.status not in ("FAIL", "UNKNOWN"):
                    continue
                for r in c.reasons:  # one item per reason: code, field and detail stay together
                    code = r.code
                    if code == "MISSING_REQUIRED_TAG" and "SULpeak" in (r.field or ""):
                        code = "LESION_TARGET_MISSING"
                    items.append({"site": layout.sites.get(p.pair.subject_id),
                                  "subject": p.pair.subject_id,
                                  "scan": f"{rs} {p.pair.baseline}->{p.pair.followup}",
                                  "reason_code": code, "field": f"{c.rule_id}: {r.field or ''}",
                                  "evidence": r.detail})  # fmt: skip
    queries = site_queries(items)
    _json(bundle / "reports" / "site_queries.json", queries)
    (bundle / "reports" / "site_queries.md").write_text(site_queries_md(queries))

    # 10. reports
    summary = _summary(pf, audits, drift, tasks, att_rows, adj_rows, fps)
    _json(bundle / "reports" / "summary.json", summary)
    page = top_page(layout.config.trial_id, summary, audits)
    _json(bundle / "reports" / "executive_summary.json", page)
    (bundle / "reports" / "EXECUTIVE_SUMMARY.md").write_text(top_page_md(page))
    report = (
        top_page_md(page)
        + "\n---\n\n"
        + _report_md(layout.config.trial_id, summary, audits, drift, queries)
    )
    (bundle / "reports" / "AUDIT_PACKAGE_REPORT.md").write_text(report)
    (bundle / "reports" / "AUDIT_PACKAGE_REPORT.pdf").write_bytes(
        markdown_to_pdf(report, title=f"VoxelTrace audit {layout.config.trial_id}")
    )

    # 11. inputs + manifest
    inp = (
        inputs_manifest(input_dir, clear_paths=clear_input_paths)
        if hash_inputs
        else {"skipped": True}
    )
    _json(bundle / "inputs_manifest.json", inp)
    sha, dirty = git_state()
    rb = rule_bundle()
    manifest = finalize_bundle(bundle, {
        "schema": BUNDLE_SCHEMA,
        "audit_package_schema": AUDIT_PACKAGE_SCHEMA,
        "voxeltrace_version": voxeltrace.__version__,
        "git_commit": sha, "git_dirty": dirty,
        "schema_versions": SCHEMAS,
        "rule_bundle_sha256": rb["rule_bundle_sha256"],
        "rule_versions": {k: {"version": v["version"], "rules": {r["rule_id"]: r["version"] for r in v["rules"]}}
                          for k, v in rb["rulesets"].items() if k in rulesets},
        "rulesets_run": list(rulesets),
        "trial_id": layout.config.trial_id,
        "inputs_sha256": inp.get("inputs_sha256"),
        "input_files": inp.get("file_count"),
        "started_at": started,
        "runtime_environment": runtime_environment(),
        "deterministic_components": DETERMINISTIC,
        "non_deterministic_components": NON_DETERMINISTIC,
        "ai_components": "none (no model is used by the audit)",
        "disclaimer": voxeltrace.DISCLAIMER,
    })  # fmt: skip
    return {"bundle": str(bundle), "manifest": manifest, "summary": summary}


def _summary(pf, audits, drift, tasks, att_rows, adj_rows, fps) -> dict[str, Any]:
    out: dict[str, Any] = {
        "preflight": pf.summary,
        "fingerprints": {"scans": len(fps), "distinct_protocols": len({f.protocol_fingerprint_sha256 for f in fps.values()})},
        "drift_events": dict(Counter(e.event for e in drift.events)),
        "review_tasks_pending": sum(t["task"] == "HUMAN_REVIEW_REQUIRED" for t in tasks),
        "attestations": len(att_rows),
        "adjudications": dict(Counter(r["adjudication_status"] for r in adj_rows)),
        "rulesets": {},
    }  # fmt: skip
    for rs, a in audits.items():
        rows = pair_rows(a)
        ii = [r for r in rows if r["verdict"] == "INSUFFICIENT_INFORMATION"]
        out["rulesets"][rs] = {
            "pairs": len(rows),
            "verdicts_real": dict(Counter(r["verdict"] for r in rows if r["data_origin"] == "REAL")),
            "verdicts_synthetic": dict(Counter(r["verdict"] for r in rows if r["data_origin"] != "REAL")),
            "ii_reason_codes": dict(Counter(c for r in ii for c in r["reason_codes"].split(";") if c)),
            "rule_status": {c.rule_id: dict(Counter(x.status for p in a.pairs for x in p.checks if x.rule_id == c.rule_id))
                            for c in (a.pairs[0].checks if a.pairs else [])},
            "layers": {f"{p.pair.subject_id}": assessability_layers(p) for p in a.pairs},
            "externally_attested_pairs": [p.pair.subject_id for p in a.pairs
                                          if any(c.status == "PASS_WITH_WARNING" for c in p.checks)],
            "human_reviewed_reference_timepoints": sorted({f"{t.subject_id}/{t.timepoint}" for t in a.timepoints
                                                           for r in (t.liver, t.blood_pool) if r and r.review_decision}),
            "unresolved_rules": dict(Counter(c.rule_id for p in a.pairs for c in p.checks
                                             if c.impact == "blocking" and c.status == "UNKNOWN")),
        }  # fmt: skip
        scanners = Counter()
        for t in a.timepoints:
            if t.protocol is not None:
                sc = t.protocol.scanner
                scanners[
                    f"{sc.manufacturer.value} {sc.manufacturer_model_name.value} sw={sc.software_versions.value}"
                ] += 1
        out["scanners"] = dict(scanners)
    return out


def _report_md(trial_id, s, audits, drift, queries) -> str:
    L = [f"# VoxelTrace PET Comparability Audit: {trial_id}", "",
         f"{voxeltrace.DISCLAIMER} Deterministic audit; no AI. Automated verdicts are never modified by review, attestation or adjudication records, which are reported separately.", "",
         "## Preflight", "", f"```\n{json.dumps(s['preflight'], indent=2)}\n```", "",
         "## Scanners", ""] + [f"- {k}: {v} scan(s)" for k, v in s.get("scanners", {}).items()]  # fmt: skip
    for rs, r in s["rulesets"].items():
        L += ["", f"## {rs}", "",
              "### REAL DATA verdicts", "", f"{r['verdicts_real'] or 'none'}", "",
              "### SYNTHETIC TEST DATA verdicts", "", f"{r['verdicts_synthetic'] or 'none'}", "",
              "### HUMAN-REVIEWED EVIDENCE", "", f"reference regions with a human decision: {r['human_reviewed_reference_timepoints'] or 'none'}", "",
              "### EXTERNALLY ATTESTED EVIDENCE", "", f"pairs whose protocol identity rests on a LEVEL_C attestation: {r['externally_attested_pairs'] or 'none'}", "",
              "### IMAGE-DERIVED CORROBORATION", "", "none (the audit never uses image-derived evidence for a rule)", "",
              "### UNRESOLVED EVIDENCE", "", f"blocking UNKNOWN rules: {r['unresolved_rules'] or 'none'}",
              f"II reason codes: {r['ii_reason_codes'] or 'none'}", "",
              "### Rule status", ""] + [f"- {k}: {v}" for k, v in r["rule_status"].items()]  # fmt: skip
    L += ["", "## Protocol drift", "", f"events: {s['drift_events'] or 'none'}"]
    for site in drift.sites:
        L.append(
            f"- {site.site}: {site.scans} scans, {site.distinct_protocol_fingerprints} distinct protocols, events {site.events or 'none'}"
        )
    L += ["", "## Review tasks", "", f"pending human reference-region reviews: {s['review_tasks_pending']}",
          "", "## Attestations / adjudications", "", f"attestations supplied: {s['attestations']}",
          f"adjudication status: {s['adjudications'] or 'none'}", "",
          f"## DRAFT site queries ({len(queries)})", "", "See reports/site_queries.md (not sent)."]  # fmt: skip
    return "\n".join(L) + "\n"
