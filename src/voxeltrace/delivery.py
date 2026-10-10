"""Sanitized design-partner delivery package (VT-DELIVERY-1).

  build_delivery_package(source, out)   source = a run-pilot output folder or an audit bundle
  verify_delivery(package)              checksums + evidence bundle + privacy scan

Package contents (no DICOM, no pixel data, no absolute paths, no hidden files):
  README_FIRST.md                 what the package is, how to read it, how to verify it
  executive_summary.pdf / .json   first page of the audit (counts, readiness, sites, reviews)
  pair_results.csv                every pair verdict, all rule sets, with pairing status and
                                  plain-language reasons
  scan_preflight.csv              per-scan preflight findings with plain-language wording
  site_summary.csv                site / scanner rollup (reconciles with the pair results)
  protocol_drift.csv              protocol drift events
  unresolved_items.csv            everything waiting on a site or a human reviewer
  remediation_matrix.csv          what each reason code means and what can fix it
  pair_evidence_trace.csv         verdict -> rule -> reason -> field -> trust/source -> raw metadata
  recommended_site_queries/       DRAFT site queries (never sent by VoxelTrace)
  evidence_bundle/                the immutable audit bundle, byte-for-byte
  verification_report.json        verify-bundle result for evidence_bundle/
  pilot_acceptance.json           VT-PILOT-ACCEPTANCE-1 (when built from a run-pilot folder)
  methodology_and_limitations.md  method, validation status and limitations
  software_version.txt            code, rule and schema versions
  privacy_scan.json               conservative pattern scan result (must be CLEAN)
  DELIVERY_MANIFEST.json, DELIVERY_CHECKSUMS.sha256

The package is built in ``<out>.partial`` and renamed only when the evidence bundle verifies
and the privacy scan is CLEAN; otherwise nothing is published and the findings are written to
``<out>.privacy_findings.json`` beside it. Nothing is ever overwritten.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from pathlib import Path
from typing import Any

DELIVERY_SCHEMA = "VT-DELIVERY-1"
CHECKSUMS = "DELIVERY_CHECKSUMS.sha256"


def _sha(p: Path) -> str:
    from voxeltrace.bundle import sha256_file

    return sha256_file(p)


def _read_csv(p: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(p.open())) if p.exists() else []


def _write_csv(p: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = []
        for r in rows:
            fields += [k for k in r if k not in fields]
    buf = io.StringIO()
    w = csv.DictWriter(
        buf, fieldnames=fields or ["empty"], extrasaction="ignore", lineterminator="\n"
    )
    w.writeheader()
    w.writerows(rows)
    p.write_text(buf.getvalue())


def _locate(source: Path) -> tuple[Path, Path | None]:
    if (source / "manifest.json").exists() and (source / "checksums.sha256").exists():
        return source, None
    b = source / "audit" / "audit_bundle"
    if b.is_dir():
        acc = source / "pilot_acceptance.json"
        return b, acc if acc.exists() else None
    raise FileNotFoundError(f"{source}: neither an audit bundle nor a run-pilot output folder")


def _plain(codes: str) -> str:
    from voxeltrace.remediation import customer_wording

    return " | ".join(customer_wording(c) for c in codes.split(";") if c)


def _pair_results(bundle: Path) -> list[dict[str, Any]]:
    from voxeltrace.trial.pairing_audit import pairing_status_by_subject

    pairing_file = bundle / "pairing" / "pairing_audit.json"
    status = (
        pairing_status_by_subject(json.loads(pairing_file.read_text()))
        if pairing_file.exists()
        else {}
    )
    rows = []
    for f in sorted((bundle / "pair_verdicts").glob("*.csv")):
        for r in _read_csv(f):
            rows.append({**r, "ruleset_file": f.stem,
                         "pairing_status": status.get(r["subject"], status.get("*", "OK")) if status else "NOT_RUN",
                         "plain_language_reasons": _plain(r.get("reason_codes", ""))})  # fmt: skip
    return rows


def _unresolved(bundle: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in _read_csv(bundle / "reviews" / "review_status.csv"):
        if r.get("task") == "HUMAN_REVIEW_REQUIRED":
            out.append({"type": "REFERENCE_REGION_REVIEW", "subject": r["subject"], "scope": r["timepoint"],
                        "ruleset": "", "item": r["region"], "reason_codes": "REFERENCE_REVIEW_REQUIRED",
                        "resolved_by": "qualified human reviewer (Reference Review page)"})  # fmt: skip
    pf = bundle / "pairing" / "pairing_audit.json"
    if pf.exists():
        for f in json.loads(pf.read_text())["findings"]:
            if f["severity"] in ("BLOCKING", "NEEDS_REVIEW"):
                out.append({"type": f"PAIRING_{f['severity']}", "subject": f["subject"],
                            "scope": ";".join(f["timepoints"]), "ruleset": "", "item": f["code"],
                            "reason_codes": f["code"], "resolved_by": "site / study coordinator (folder layout)"})  # fmt: skip
    for f in sorted((bundle / "pair_verdicts").glob("*.csv")):
        for r in _read_csv(f):
            if r["verdict"] != "INSUFFICIENT_INFORMATION":
                continue
            codes = r.get("reason_codes", "")
            who = ("qualified human reviewer" if any(c in codes for c in ("REVIEW_REQUIRED", "MASK_REQUIRED"))
                   else "site (re-export or documentation)")  # fmt: skip
            out.append({"type": "BLOCKING_UNKNOWN_RULES", "subject": r["subject"],
                        "scope": f"{r['baseline']}->{r['followup']}", "ruleset": f.stem,
                        "item": r.get("blocking_unknown", ""), "reason_codes": codes, "resolved_by": who})  # fmt: skip
    for r in _read_csv(bundle / "preflight" / "preflight.csv"):
        if r.get("scan_state") in ("DO_NOT_QUANTIFY", "NEEDS_REVIEW") and r.get("severity") in (
            "BLOCKING",
            "NEEDS_REVIEW",
        ):
            out.append({"type": f"SCAN_{r['scan_state']}", "subject": r["subject"], "scope": r["scan"],
                        "ruleset": "", "item": r["field"], "reason_codes": r["reason_code"],
                        "resolved_by": "site (re-export)" if r.get("recoverable") == "YES" else "site (confirm; may be unrecoverable)"})  # fmt: skip
    for r in out:
        r["plain_language"] = _plain(r["reason_codes"])
    return out


def methodology_md(manifest: dict[str, Any]) -> str:
    rv = manifest.get("rule_versions", {})
    return "\n".join([
        "# Methodology and limitations", "",
        "RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. VoxelTrace assesses whether quantitative PET "
        "scans are comparable enough for SUV changes to be interpreted. It never assesses treatment response "
        "and never diagnoses.", "",
        "## Method", "",
        "1. Preflight reads DICOM headers only and classifies every scan READY_TO_QUANTIFY, "
        "READY_WITH_WARNINGS, DO_NOT_QUANTIFY or NEEDS_REVIEW.",
        "2. Strict SUV input validation refuses to quantify when any required input (units, decay "
        "correction, injected activity, injection time, weight, rescale) is missing or inconsistent. "
        "Nothing is guessed.",
        "3. Protocol evidence (scanner, software, reconstruction, corrections, timing) is extracted "
        "with a trust level per field. Vendor free text is never treated as structured evidence.",
        "4. Each baseline/follow-up pair is evaluated by versioned, published rule sets: "
        + ", ".join(f"{k} ({v.get('version')})" for k, v in sorted(rv.items())) + ".",
        "5. Every pair receives ASSESSABLE, ASSESSABLE_WITH_WARNINGS, NOT_ASSESSABLE (a criterion was "
        "decided and not met) or INSUFFICIENT_INFORMATION (evidence missing; never treated as a pass).",
        "6. Reference regions (PERCIST) are proposed deterministically but count only after a qualified "
        "human accepts them. Lesion segmentations count only after human acceptance.",
        "7. A pairing audit checks the longitudinal layout (duplicate timepoints, the same scan under two "
        "visits or subjects, order anomalies). It never re-pairs scans.",
        "8. All outputs are written to an immutable evidence bundle with sha256 checksums.", "",
        "No AI model is used by the audit. Recommendations are fixed catalogue text for the reason codes "
        "that occurred.", "",
        "## Validation status", "",
        "- External expert (PET physicist) validation of the verdicts is PENDING.",
        "- Vendor coverage: Siemens models were validated on real public longitudinal pairs; GE was "
        "validated for ingestion only; Philips for metadata only. Non-Siemens strict SUV may be refused "
        "where vendor timing semantics are not documented.",
        "- No real pair has a complete PERCIST verdict without human reference-region and lesion review.", "",
        "## Limitations", "",
        "- Integrity checks prove the bundle matches its manifest; they are not a digital signature.",
        "- The privacy scan of this package is a conservative pattern check, not a de-identification "
        "method or a HIPAA/GDPR compliance determination. The sender remains responsible for de-identification.",
        "- Site drift is only meaningful when sites are declared; subjects without a declared site are "
        "grouped as UNASSIGNED and their 'drift' compares different centres.",
        "- Rule thresholds follow the cited guidelines; they are not tuned to this dataset.",
        "- Results describe comparability evidence in the supplied export only.", "",
    ])  # fmt: skip


def readme_md(manifest: dict[str, Any], page: dict[str, Any], acc: dict[str, Any] | None) -> str:
    status = acc["status"] if acc else "NOT_RECORDED (built from a bare audit bundle)"
    v = page.get("verdicts", {})
    L = [
        f"# README FIRST: VoxelTrace PET comparability audit {manifest.get('trial_id')}", "",
        "RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS.", "",
        f"Pilot status: **{status}**", "",
        f"- {page.get('subjects')} subject(s), {page.get('scans')} scan(s), {page.get('pairs')} baseline/follow-up pair(s).",
        f"- VoxelTrace {manifest.get('voxeltrace_version')}, commit {manifest.get('git_commit')}, "
        f"rule bundle sha256 {manifest.get('rule_bundle_sha256')}.",
        f"- Input dataset sha256 (over every input file): {manifest.get('inputs_sha256')}.", "",
        "## Verdicts", "",
    ]  # fmt: skip
    L += [f"- {rs}: " + ", ".join(f"{n} {k}" for k, n in c.items() if n) for rs, c in v.items()]
    L += [
        "", "## Read in this order", "",
        "1. `executive_summary.pdf`: the one-page result (readiness, comparability, top issues, sites "
        "requiring action, unresolved human review).",
        "2. `unresolved_items.csv`: what is waiting, and who can resolve it.",
        "3. `recommended_site_queries/site_queries.md`: DRAFT queries to send to sites (edit, approve and "
        "send through your own channel; VoxelTrace sends nothing).",
        "4. `pair_results.csv`: every pair and rule set. `pairing_status` must be OK before a verdict is used.",
        "   `pair_evidence_trace.csv` answers 'why this verdict?': rule, reason, DICOM field, value, trust level and "
        "source at both timepoints, and the raw-metadata finding behind it.",
        "5. `site_summary.csv`, `scan_preflight.csv`, `protocol_drift.csv`: detail by site, scanner and scan.",
        "6. `remediation_matrix.csv`: what each reason code means and whether a re-export, a site record or a "
        "human review can fix it.",
        "7. `methodology_and_limitations.md`: method, validation status, limitations.", "",
        "## What the verdicts mean", "",
        "- ASSESSABLE / ASSESSABLE_WITH_WARNINGS: the evidence supports interpreting SUV change under that "
        "rule set (warnings are listed).",
        "- NOT_ASSESSABLE: a criterion was decided and not met (for example uptake time outside the window). "
        "A re-export cannot change it.",
        "- INSUFFICIENT_INFORMATION: evidence is missing. It is never treated as a pass; the reason codes say "
        "what is missing and who can supply it.", "",
        "## Human review", "",
        "VoxelTrace never records a reference-region, lesion or adjudication decision. Items listed as "
        "requiring review stay unresolved until a qualified person records them.", "",
        "## Verify this package", "",
        "With VoxelTrace installed: `voxeltrace verify-delivery <this folder>` (checks every file against "
        "DELIVERY_CHECKSUMS.sha256, re-verifies evidence_bundle/ and repeats the privacy scan).",
        "Without VoxelTrace: `sha256sum -c DELIVERY_CHECKSUMS.sha256` in this folder, then "
        "`sha256sum -c checksums.sha256` inside evidence_bundle/.", "",
        "## Not included", "",
        "No DICOM, no pixel data, no patient identifiers, no local file paths. Subject and timepoint labels "
        "are the folder names supplied by the sender.", "",
    ]  # fmt: skip
    return "\n".join(L)


def build_delivery_package(source: str | Path, out: str | Path) -> dict[str, Any]:
    import voxeltrace
    from voxeltrace.bundle import verify_bundle
    from voxeltrace.cli import _version_text
    from voxeltrace.pdf import markdown_to_pdf
    from voxeltrace.privacy_scan import scan_directory
    from voxeltrace.remediation import remediation_matrix

    source, out = Path(source), Path(out)
    bundle, acc_file = _locate(source)
    partial = out.with_name(out.name + ".partial")
    rejected = out.with_name(out.name + ".privacy_findings.json")
    for p in (out, partial):
        if p.exists():
            raise FileExistsError(f"{p} exists (delivery packages are never overwritten)")
    v = verify_bundle(bundle)
    if v["status"] != "OK":
        raise ValueError(f"evidence bundle verification {v['status']}: refusing to package")
    acc = json.loads(acc_file.read_text()) if acc_file else None
    if acc and acc["status"] not in ("AUDIT_COMPLETE", "AUDIT_COMPLETE_WITH_REVIEW_PENDING"):
        raise ValueError(
            f"pilot status {acc['status']}: refusing to package ({acc['blocking_reasons']})"
        )
    manifest = json.loads((bundle / "manifest.json").read_text())
    rep = bundle / "reports"
    page = json.loads((rep / "executive_summary.json").read_text())

    partial.mkdir(parents=True)
    shutil.copytree(bundle, partial / "evidence_bundle")
    vr = verify_bundle(partial / "evidence_bundle")
    vr["bundle"] = "evidence_bundle"
    (partial / "verification_report.json").write_text(json.dumps(vr, indent=2) + "\n")
    shutil.copy(rep / "executive_summary.json", partial / "executive_summary.json")
    (partial / "executive_summary.pdf").write_bytes(
        markdown_to_pdf(
            (rep / "EXECUTIVE_SUMMARY.md").read_text(),
            title=f"VoxelTrace {manifest.get('trial_id')}",
        )
    )
    _write_csv(partial / "pair_results.csv", _pair_results(bundle))
    pf_rows = _read_csv(bundle / "preflight" / "preflight.csv")
    _write_csv(
        partial / "scan_preflight.csv",
        [{**r, "plain_language": _plain(r.get("reason_code", ""))} for r in pf_rows],
    )
    site_rows = _read_csv(rep / "site_summary.csv")
    _write_csv(
        partial / "site_summary.csv",
        site_rows or [{"note": "not produced by this VoxelTrace version"}],
    )
    _write_csv(partial / "protocol_drift.csv", _read_csv(bundle / "protocol" / "drift_events.csv"))
    _write_csv(partial / "unresolved_items.csv", _unresolved(bundle),
               ["type", "subject", "scope", "ruleset", "item", "reason_codes", "resolved_by", "plain_language"])  # fmt: skip
    _write_csv(partial / "remediation_matrix.csv", remediation_matrix())
    from voxeltrace.trace import evidence_trace

    _write_csv(partial / "pair_evidence_trace.csv", evidence_trace(bundle))
    (partial / "recommended_site_queries").mkdir()
    for name in ("site_queries.md", "site_queries.json"):
        shutil.copy(rep / name, partial / "recommended_site_queries" / name)
    if acc:
        (partial / "pilot_acceptance.json").write_text(json.dumps(acc, indent=2) + "\n")
    (partial / "methodology_and_limitations.md").write_text(methodology_md(manifest))
    (partial / "software_version.txt").write_text(
        _version_text() + f"\ngit commit: {manifest.get('git_commit')}"
        f"{' (dirty)' if manifest.get('git_dirty') else ''}\naudit run by voxeltrace {manifest.get('voxeltrace_version')}; "
        f"package built by voxeltrace {voxeltrace.__version__}\n"
    )  # fmt: skip
    (partial / "README_FIRST.md").write_text(readme_md(manifest, page, acc))

    scan = scan_directory(partial)
    if scan["status"] != "CLEAN":
        rejected.write_text(json.dumps(scan, indent=2) + "\n")
        return {"status": "REJECTED_PRIVACY", "partial": str(partial), "findings": str(rejected),
                "categories": scan["categories"]}  # fmt: skip
    (partial / "privacy_scan.json").write_text(json.dumps(scan, indent=2) + "\n")
    files = sorted(
        p
        for p in partial.rglob("*")
        if p.is_file() and p.name not in (CHECKSUMS, "DELIVERY_MANIFEST.json")
    )
    (partial / "DELIVERY_MANIFEST.json").write_text(json.dumps({
        "schema": DELIVERY_SCHEMA, "trial_id": manifest.get("trial_id"),
        "pilot_status": acc["status"] if acc else None,
        "evidence_bundle_checksums_sha256": manifest.get("checksums_sha256"),
        "inputs_sha256": manifest.get("inputs_sha256"),
        "voxeltrace_version": voxeltrace.__version__, "files": len(files) + 1,
    }, indent=2) + "\n")  # fmt: skip
    files = sorted(p for p in partial.rglob("*") if p.is_file() and p.name != CHECKSUMS)
    (partial / CHECKSUMS).write_text(
        "".join(f"{_sha(p)}  {p.relative_to(partial).as_posix()}\n" for p in files)
    )
    partial.rename(out)
    return {"status": "OK", "package": str(out), "files": len(files) + 1,
            "checksums_sha256": _sha(out / CHECKSUMS)}  # fmt: skip


def verify_delivery(package: str | Path) -> dict[str, Any]:
    from voxeltrace.bundle import verify_bundle
    from voxeltrace.privacy_scan import scan_directory

    pkg = Path(package)
    out: dict[str, Any] = {
        "schema": DELIVERY_SCHEMA,
        "status": "OK",
        "modified": [],
        "missing": [],
        "unlisted": [],
    }
    ck = pkg / CHECKSUMS
    if not ck.exists():
        return {**out, "status": "INVALID", "error": f"{CHECKSUMS} missing"}
    listed = {}
    for line in ck.read_text().splitlines():
        if line.strip():
            h, rel = line.split("  ", 1)
            listed[rel] = h
    for rel, h in sorted(listed.items()):
        p = pkg / rel
        if not p.exists():
            out["missing"].append(rel)
        elif _sha(p) != h:
            out["modified"].append(rel)
    actual = {p.relative_to(pkg).as_posix() for p in pkg.rglob("*") if p.is_file()}
    out["unlisted"] = sorted(actual - set(listed) - {CHECKSUMS})
    vb = verify_bundle(pkg / "evidence_bundle")
    out["evidence_bundle"] = vb["status"]
    scan = scan_directory(pkg)
    out["privacy_scan"] = scan["status"]
    out["privacy_categories"] = scan["categories"]
    if out["modified"] or out["missing"] or out["unlisted"]:
        out["status"] = "TAMPERED"
    if vb["status"] != "OK":
        out["status"] = "BUNDLE_" + vb["status"]
    if scan["status"] != "CLEAN" and out["status"] == "OK":
        out["status"] = "PRIVACY_FINDINGS"
    out["files_checked"] = len(listed)
    out["sha256_of_checksums"] = hashlib.sha256(ck.read_bytes()).hexdigest()
    return out
