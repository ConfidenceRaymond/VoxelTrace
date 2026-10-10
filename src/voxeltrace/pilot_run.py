"""One-command retrospective pilot (``voxeltrace run-pilot``) and the pilot acceptance contract
(VT-PILOT-ACCEPTANCE-1). Orchestration only: every step calls the existing module that the
individual commands use (validate-input, init-trial, audit, verify-bundle, delivery package);
no business logic is duplicated and no AI is involved.

  <output>/
    config/trial.yaml          only when the input has none (written by init-trial logic)
    intake/validate_input.json
    audit/audit_bundle/        the immutable evidence bundle (``voxeltrace audit``)
    pilot_acceptance.json      VT-PILOT-ACCEPTANCE-1 (deterministic for identical inputs)
    PILOT_SUMMARY.md           the same, for people
    pilot_run_log.json         step timings (the only non-deterministic file)
    delivery_package/          sanitized design-partner package (unless --no-delivery)

Statuses (``status``; the intake decision is also kept in ``intake_status``):
  NEEDS_REEXPORT / UNSUPPORTED     the audit was not run (gate below)
  AUDIT_BLOCKED                    the audit ran but its output must not be used: the bundle
                                   failed verification, or the pairing audit found a BLOCKING
                                   layout problem
  AUDIT_COMPLETE_WITH_REVIEW_PENDING  results are valid; some verdicts wait on human review
                                   (reference regions, lesions, pairing items)
  AUDIT_COMPLETE                   nothing pending

Audit gate (explicit, recorded in the contract):
  default        run unless intake found no scans, an invalid trial.yaml, or only UNSUPPORTED
                 scans. Scans needing re-export are audited (they receive INSUFFICIENT_
                 INFORMATION / NOT_ASSESSABLE verdicts and DRAFT site queries).
  strict_intake  run only when the folder decision is ACCEPT_FOR_AUDIT / ACCEPT_WITH_WARNINGS.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

PILOT_ACCEPTANCE_SCHEMA = "VT-PILOT-ACCEPTANCE-1"
INTAKE_STATUS = {
    "ACCEPT_FOR_AUDIT": "ACCEPTED_FOR_AUDIT",
    "ACCEPT_WITH_WARNINGS": "ACCEPTED_WITH_WARNINGS",
    "NEEDS_REEXPORT": "NEEDS_REEXPORT",
    "UNSUPPORTED": "UNSUPPORTED",
}
STATUSES = (
    "ACCEPTED_FOR_AUDIT", "ACCEPTED_WITH_WARNINGS", "NEEDS_REEXPORT", "UNSUPPORTED",
    "AUDIT_COMPLETE", "AUDIT_COMPLETE_WITH_REVIEW_PENDING", "AUDIT_BLOCKED",
)  # fmt: skip
EXIT_CODES = {"AUDIT_COMPLETE": 0, "AUDIT_COMPLETE_WITH_REVIEW_PENDING": 0, "AUDIT_BLOCKED": 1,
              "NEEDS_REEXPORT": 2, "UNSUPPORTED": 3}  # fmt: skip
REVIEW_CODES = ("REFERENCE_REVIEW_REQUIRED", "REFERENCE_REVIEW_OUTDATED", "REFERENCE_REVIEW_INVALID",
                "LESION_REVIEW_REQUIRED", "MANUAL_OR_REFERENCE_MASK_REQUIRED")  # fmt: skip
UNSUPPORTED_AUDIT_CODES = (
    "UNSUPPORTED_VENDOR",
    "UNSUPPORTED_SOFTWARE_VERSION",
    "UNSUPPORTED_PRIVATE_TAG",
)


def audit_gate(intake: dict[str, Any], strict: bool) -> tuple[bool, str | None]:
    """(run the audit?, status if not)."""
    layout_blocking = [x for x in intake["layout"] if x["severity"] == "BLOCKING"]
    decisions = [s["decision"] for s in intake.get("scans", [])]
    if layout_blocking or not decisions:
        return False, "NEEDS_REEXPORT"
    if all(d == "UNSUPPORTED" for d in decisions):
        return False, "UNSUPPORTED"
    if strict and intake["decision"] not in ("ACCEPT_FOR_AUDIT", "ACCEPT_WITH_WARNINGS"):
        return False, INTAKE_STATUS[intake["decision"]]
    return True, None


def _intake_block(intake: dict[str, Any]) -> dict[str, Any]:
    by = Counter(s["decision"] for s in intake.get("scans", []))
    return {
        "decision": intake["decision"],
        "scan_decisions": dict(sorted(by.items())),
        "layout_findings": [
            {"code": x["code"], "severity": x["severity"]} for x in intake["layout"]
        ],
        "scans_needing_reexport": sorted(
            f"{s['subject'] or '-'}/{s['scan']}"
            for s in intake.get("scans", [])
            if s["decision"] == "NEEDS_REEXPORT"
        ),  # fmt: skip
    }


def build_acceptance(
    intake: dict[str, Any],
    *,
    strict_intake: bool,
    bundle: Path | None,
    output_dir: Path,
    verification: dict[str, Any] | None,
) -> dict[str, Any]:
    """Deterministic for identical inputs and code (no timestamps, no absolute paths)."""
    import voxeltrace
    from voxeltrace.quant.suv import git_state
    from voxeltrace.versions import SCHEMAS, rule_bundle

    sha, dirty = git_state()
    rb = rule_bundle()
    run, gate_status = audit_gate(intake, strict_intake)
    unsupported = sorted({r["code"] for s in intake.get("scans", []) for r in s["reasons"]
                          if r["severity"] == "UNSUPPORTED" or r["code"] in ("UNSUPPORTED_UNITS", "UNSUPPORTED_DECAY_CORRECTION")})  # fmt: skip
    doc: dict[str, Any] = {
        "schema": PILOT_ACCEPTANCE_SCHEMA,
        "status": gate_status,
        "intake_status": INTAKE_STATUS[intake["decision"]],
        "audit_status": "NOT_RUN",
        "audit_gate": {"policy": "strict_intake" if strict_intake else "default", "audit_run": run},
        "software": {
            "voxeltrace_version": voxeltrace.__version__,
            "git_commit": sha,
            "git_dirty": dirty,
            "rule_bundle_sha256": rb["rule_bundle_sha256"],
            "rule_versions": {k: v["version"] for k, v in sorted(rb["rulesets"].items())},
            "schemas": SCHEMAS,
        },  # fmt: skip
        "intake": _intake_block(intake),
        "unsupported_features": unsupported,
        "blocking_reasons": [],
        "disclaimer": voxeltrace.DISCLAIMER,
    }
    if not run or bundle is None:
        doc["blocking_reasons"] = ["audit not run: " + (gate_status or "unknown")]
        return doc

    rep = bundle / "reports"
    manifest = json.loads((bundle / "manifest.json").read_text())
    summary = json.loads((rep / "summary.json").read_text())
    page = json.loads((rep / "executive_summary.json").read_text())
    pairing = json.loads((bundle / "pairing" / "pairing_audit.json").read_text())
    review_pairs: Counter = Counter()
    unsup_audit: set[str] = set()
    for r in summary["rulesets"].values():
        for code, n in r.get("ii_reason_codes", {}).items():
            if code in REVIEW_CODES:
                review_pairs[code] += n
            if code in UNSUPPORTED_AUDIT_CODES:
                unsup_audit.add(code)
    doc["unsupported_features"] = sorted(set(unsupported) | unsup_audit)
    doc["dataset"] = {
        "trial_id": manifest.get("trial_id"),
        "inputs_sha256": manifest.get("inputs_sha256"),
        "input_files": manifest.get("input_files"),
        "subjects": page.get("subjects"), "scans": page.get("scans"), "pairs": page.get("pairs"),
        "real_pairs": page.get("real_pairs"),
    }  # fmt: skip
    doc["software"]["rule_versions_run"] = manifest.get("rule_versions")
    doc["preflight_summary"] = summary["preflight"]
    doc["verdicts"] = page["verdicts"]
    doc["review_requirements"] = {
        "reference_region_reviews_pending": summary.get("review_tasks_pending", 0),
        "ii_reason_codes_requiring_review": dict(sorted(review_pairs.items())),
        "pairing_items_needing_review": pairing["severity_counts"].get("NEEDS_REVIEW", 0),
        "note": "Only a qualified human reviewer can resolve these; VoxelTrace never records a review.",
    }
    doc["pairing"] = {"status": pairing["status"], "severity_counts": pairing["severity_counts"],
                      "subjects_blocked": pairing["subjects_blocked"]}  # fmt: skip
    doc["output"] = {
        "bundle": bundle.relative_to(output_dir).as_posix(),
        "bundle_checksums_sha256": manifest.get("checksums_sha256"),
        "verification_status": (verification or {}).get("status", "NOT_RUN"),
        "files_checked": (verification or {}).get("files_checked"),
    }
    blocking = []
    if doc["output"]["verification_status"] != "OK":
        blocking.append(f"evidence bundle verification: {doc['output']['verification_status']}")
    if pairing["status"] == "BLOCKED":
        blocking.append(
            f"pairing audit BLOCKING for subject(s): {', '.join(pairing['subjects_blocked'])}"
        )
    pending = (doc["review_requirements"]["reference_region_reviews_pending"] or review_pairs
               or doc["review_requirements"]["pairing_items_needing_review"])  # fmt: skip
    audit_status = ("AUDIT_BLOCKED" if blocking else
                    "AUDIT_COMPLETE_WITH_REVIEW_PENDING" if pending else "AUDIT_COMPLETE")  # fmt: skip
    doc.update(status=audit_status, audit_status=audit_status, blocking_reasons=blocking)
    return doc


def acceptance_md(doc: dict[str, Any]) -> str:
    L = [f"# VoxelTrace pilot acceptance: {doc['status']}", "", doc["disclaimer"], "",
         f"- Intake: {doc['intake_status']} (scan decisions {doc['intake']['scan_decisions']})",
         f"- Audit: {doc['audit_status']} (gate policy {doc['audit_gate']['policy']})"]  # fmt: skip
    if "dataset" in doc:
        d = doc["dataset"]
        L += [f"- Dataset: {d['trial_id']}: {d['subjects']} subject(s), {d['scans']} scan(s), {d['pairs']} pair(s); "
              f"input sha256 {d['inputs_sha256']}",
              f"- Evidence bundle: {doc['output']['bundle']} verification {doc['output']['verification_status']}",
              f"- Pairing audit: {doc['pairing']['status']} {doc['pairing']['severity_counts']}",
              f"- Review pending: {doc['review_requirements']['reference_region_reviews_pending']} reference region(s); "
              f"{doc['review_requirements']['ii_reason_codes_requiring_review'] or 'no'} review-type II reasons",
              "", "| Rule set | " + " | ".join(next(iter(doc["verdicts"].values()))) + " |",
              "|---|" + "---|" * len(next(iter(doc["verdicts"].values())))]  # fmt: skip
        L += [
            f"| {rs} | " + " | ".join(str(n) for n in v.values()) + " |"
            for rs, v in doc["verdicts"].items()
        ]
    L += ["", f"Unsupported features: {', '.join(doc['unsupported_features']) or 'none'}",
          f"Blocking reasons: {'; '.join(doc['blocking_reasons']) or 'none'}",
          f"Software: voxeltrace {doc['software']['voxeltrace_version']} commit {doc['software']['git_commit']}"
          f"{' (dirty)' if doc['software']['git_dirty'] else ''}; rule bundle {doc['software']['rule_bundle_sha256']}"]  # fmt: skip
    return "\n".join(L) + "\n"


def run_pilot(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    trial_id: str | None = None,
    config: str | Path | None = None,
    timepoints: list[str] | None = None,
    rulesets: tuple[str, ...] | None = None,
    attestations: str | Path | None = None,
    adjudications: str | Path | None = None,
    strict_intake: bool = False,
    delivery: bool = True,
) -> dict[str, Any]:
    from voxeltrace.bundle import verify_bundle
    from voxeltrace.pilot import RULESETS, run_audit
    from voxeltrace.trial.init_trial import write_trial_yaml
    from voxeltrace.validate_input import validate_input

    inp, out = Path(input_dir), Path(output_dir)
    if not inp.is_dir():
        raise FileNotFoundError(f"{inp} is not a directory")
    if out.exists() and any(out.iterdir()):
        raise FileExistsError(
            f"{out} exists and is not empty (pilot outputs are never overwritten)"
        )
    out.mkdir(parents=True, exist_ok=True)
    log: list[dict[str, Any]] = []

    def step(name: str, fn, *a, **kw):
        t0 = time.perf_counter()
        try:
            return fn(*a, **kw)
        finally:
            log.append({"step": name, "seconds": round(time.perf_counter() - t0, 3)})

    cfg = (
        Path(config) if config else (inp / "trial.yaml" if (inp / "trial.yaml").exists() else None)
    )
    if cfg is None:
        if not trial_id:
            raise ValueError("the input has no trial.yaml: pass --trial-id (or --config)")
        cfg = step("init-trial", write_trial_yaml, inp, trial_id=trial_id, timepoint_order=timepoints,
                   out=out / "config" / "trial.yaml")  # fmt: skip
    intake = step("validate-input", validate_input, inp, cfg)
    (out / "intake").mkdir()
    (out / "intake" / "validate_input.json").write_text(json.dumps(intake, indent=2) + "\n")
    run, _ = audit_gate(intake, strict_intake)
    bundle = verification = None
    if run:
        res = step("audit", run_audit, inp, out / "audit", config=cfg, rulesets=tuple(rulesets or RULESETS),
                   attestations=attestations, adjudications=adjudications)  # fmt: skip
        bundle = Path(res["bundle"])
        verification = step("verify-bundle", verify_bundle, bundle)
    acc = build_acceptance(intake, strict_intake=strict_intake, bundle=bundle, output_dir=out,
                           verification=verification)  # fmt: skip
    (out / "pilot_acceptance.json").write_text(json.dumps(acc, indent=2) + "\n")
    (out / "PILOT_SUMMARY.md").write_text(acceptance_md(acc))
    pkg = None
    if delivery and acc["status"] in ("AUDIT_COMPLETE", "AUDIT_COMPLETE_WITH_REVIEW_PENDING"):
        from voxeltrace.delivery import build_delivery_package

        pkg = step("delivery-package", build_delivery_package, out, out / "delivery_package")
    (out / "pilot_run_log.json").write_text(json.dumps({"steps": log, "note": "timings only; not part of any "
                                                       "checksum or verdict"}, indent=2) + "\n")  # fmt: skip
    return {"acceptance": acc, "output": str(out), "delivery": pkg, "steps": log}
