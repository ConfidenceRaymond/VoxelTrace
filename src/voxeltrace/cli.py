"""VoxelTrace command line (deterministic; no AI involved in any subcommand).

voxeltrace preflight <path> [--out DIR] [--format text|json|csv]
voxeltrace inspect <path>
voxeltrace audit --input DIR [--config trial.yaml] --output DIR [--ruleset ID ...]
voxeltrace run-pilot --input DIR --output DIR [--trial-id ID]   (one command, see pilot_run.py)
voxeltrace deliver <pilot-or-bundle> --out DIR / verify-delivery <package>
voxeltrace verify-bundle <bundle>
voxeltrace summarize <bundle>
voxeltrace list-reviews <bundle>
voxeltrace adjudicate ... --confirm    (explicit human action only)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DISCLAIMER = "RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS."


def _validate_input(a: argparse.Namespace) -> int:
    from voxeltrace.validate_input import EXIT_CODES, format_text, validate_input

    r = validate_input(a.path)
    print(json.dumps(r, indent=2) if a.format == "json" else format_text(r))
    return EXIT_CODES[r["decision"]]


def _version_text() -> str:
    import voxeltrace
    from voxeltrace.versions import SCHEMAS, rule_bundle

    rb = rule_bundle()
    rules = ", ".join(f"{k} ({v['version']})" for k, v in sorted(rb["rulesets"].items()))
    schemas = ", ".join(f"{k}={v}" for k, v in sorted(SCHEMAS.items()))
    return (f"voxeltrace {voxeltrace.__version__}\nrule sets: {rules}\n"
            f"rule bundle sha256: {rb['rule_bundle_sha256']}\nschemas: {schemas}")  # fmt: skip


def _init_trial(a: argparse.Namespace) -> int:
    from voxeltrace.trial.init_trial import write_trial_yaml

    try:
        p = write_trial_yaml(
            a.folder, trial_id=a.trial_id, ruleset=a.ruleset, timepoint_order=a.timepoints
        )
    except (FileExistsError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"wrote {p}\n{p.read_text()}")
    return 0


def _data_inventory(a: argparse.Namespace) -> int:
    from voxeltrace.config import REPO_ROOT, workspace_root
    from voxeltrace.inventory import format_text, inventory

    ws = workspace_root()
    root = Path(a.root) if a.root else ws
    r = inventory(root, REPO_ROOT if (REPO_ROOT / "configs").is_dir() else root / "voxeltrace")
    text = json.dumps(r, indent=2) if a.format == "json" else format_text(r)
    if a.out:
        out = Path(a.out).resolve()
        if not out.is_relative_to(ws):
            print(f"error: --out must be inside the workspace {ws}", file=sys.stderr)
            return 2
        if out.exists():
            print(f"error: {out} exists (never overwritten)", file=sys.stderr)
            return 2
        out.write_text(text + "\n")
    print(text)
    return 0


def _preflight(a: argparse.Namespace) -> int:
    from voxeltrace.preflight import preflight_batch
    from voxeltrace.preflight.export import export_preflight, rows

    path = Path(a.path)
    if not path.exists():
        print(f"error: {path} does not exist", file=sys.stderr)
        return 2
    batch = preflight_batch(path)
    if a.out:
        for p in export_preflight(batch, a.out):
            print(f"wrote {p}")
    elif a.format == "csv":
        import csv

        from voxeltrace.preflight.export import CSV_FIELDS

        w = csv.DictWriter(sys.stdout, fieldnames=CSV_FIELDS)
        w.writeheader()
        w.writerows(rows(batch))
        return 0
    elif a.format == "json":
        print(batch.model_dump_json(indent=2))
        return 0
    print(DISCLAIMER)
    print(json.dumps(batch.summary, indent=2))
    for sc in batch.scans:
        print(f"{sc.subject or '-'}/{sc.scan}: {sc.state}")
        for f in sc.findings:
            print(f"    [{f.severity}] {f.reason_code}: {f.evidence}")
        for s in sc.series:
            print(f"  PET {s.series_pseudonym} ({s.n_instances} instances): {s.state}")
            for f in s.findings:
                print(f"    [{f.severity}] {f.reason_code}: {f.evidence}")
    return 0


def _inspect(a: argparse.Namespace) -> int:
    from voxeltrace.ingest import discover_dicom

    disc = discover_dicom(Path(a.path))
    print(DISCLAIMER)
    for s in disc.series:
        print(f"{s.category:5} {len(s.instances):5} instances  frames-of-reference "
              f"{len(s.frame_of_reference_uids)}  {s.series_description or ''}")  # fmt: skip
    for w in disc.warnings:
        print(f"warning {w.code}: {w.message}")
    return 0


def _audit(a: argparse.Namespace) -> int:
    from voxeltrace.pilot import RULESETS, run_audit

    cfg = Path(a.config) if a.config else Path(a.input) / "trial.yaml"
    if not Path(a.input).is_dir():
        print(
            f"error: the input folder {a.input} does not exist [INPUT_NOT_FOUND]", file=sys.stderr
        )
        return 2
    if not cfg.exists():
        print(f"error: no trial configuration at {cfg}. Create one with `voxeltrace init-trial "
              f"{a.input} --trial-id <ID>` or pass --config, or use `voxeltrace run-pilot`, which "
              "writes it outside the input [TRIAL_CONFIG_MISSING]", file=sys.stderr)  # fmt: skip
        return 2
    try:
        res = run_audit(
            a.input, a.output, config=a.config, rulesets=tuple(a.ruleset or RULESETS),
            attestations=a.attestations, adjudications=a.adjudications,
            hash_inputs=not a.no_input_hashes, qc_images=a.qc_images,
            clear_input_paths=a.input_paths_in_clear,
        )  # fmt: skip
    except FileExistsError:
        print(f"error: {a.output} already holds an audit bundle. Bundles are never overwritten; "
              "choose a new --output folder [BUNDLE_EXISTS]", file=sys.stderr)  # fmt: skip
        return 2
    except ValueError as exc:  # invalid trial.yaml content
        print(
            f"error: the trial configuration is invalid: {exc} [TRIAL_CONFIG_INVALID]",
            file=sys.stderr,
        )
        return 2
    print(DISCLAIMER)
    print(f"bundle: {res['bundle']}")
    print(json.dumps({k: v for k, v in res["summary"].items() if k != "rulesets"}, indent=2))
    for rs, r in res["summary"]["rulesets"].items():
        print(f"{rs}: real {r['verdicts_real']} synthetic {r['verdicts_synthetic']}")
    return 0


def _run_pilot(a: argparse.Namespace) -> int:
    from voxeltrace.pilot_run import EXIT_CODES, acceptance_md, run_pilot

    try:
        res = run_pilot(
            a.input, a.output, trial_id=a.trial_id, config=a.config, timepoints=a.timepoints,
            rulesets=tuple(a.ruleset) if a.ruleset else None, attestations=a.attestations,
            adjudications=a.adjudications, strict_intake=a.strict_intake, delivery=not a.no_delivery,
        )  # fmt: skip
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    acc = res["acceptance"]
    if a.format == "json":
        print(
            json.dumps(
                {"acceptance": acc, "delivery": res["delivery"], "steps": res["steps"]}, indent=2
            )
        )
    else:
        print(acceptance_md(acc))
        print(f"outputs: {res['output']}")
        if res["delivery"]:
            print(
                f"delivery package: {res['delivery']['status']} {res['delivery'].get('package', '')}"
            )
        for s in res["steps"]:
            print(f"  {s['step']}: {s['seconds']} s")
    return EXIT_CODES[acc["status"]]


def _deliver(a: argparse.Namespace) -> int:
    from voxeltrace.delivery import build_delivery_package

    try:
        r = build_delivery_package(a.source, a.out)
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(r, indent=2))
    return 0 if r["status"] == "OK" else 1


def _verify_delivery(a: argparse.Namespace) -> int:
    from voxeltrace.delivery import verify_delivery

    r = verify_delivery(a.package)
    print(json.dumps(r, indent=2))
    return 0 if r["status"] == "OK" else 1


def _intake_map(a: argparse.Namespace) -> int:
    from voxeltrace.intake import map_intake, stage_intake

    tmap = dict(x.split("=", 1) for x in a.timepoint_map or [])
    m = map_intake(a.drop, levels=tuple(a.levels.split("/")), timepoint_map=tmap or None)
    out = Path(a.out)
    if out.exists():
        print(f"error: {out} exists (never overwritten)", file=sys.stderr)
        return 2
    out.write_text(json.dumps(m, indent=2) + "\n")
    print(f"{m['drop_label']}: {m['status']} ({len(m['scans'])} scan folder(s), "
          f"{len(m['ignored_files'])} ignored file(s)); mapping written to {out}")  # fmt: skip
    for s in m["scans"]:
        print(f"  {s['staged_subject']}/{s['timepoint_raw']} -> {s['timepoint']}: {s['status']}"
              f" PET={s['pet_selected']} CT={s['ct_selected']} SEG={s['segmentation_selected']}")  # fmt: skip
        for f in s["findings"]:
            print(f"      [{f['severity']}] {f['code']}: {f['detail']}")
    for f in m["pairing"]["findings"]:
        print(f"  pairing [{f['severity']}] {f['subject']} {f['code']}: {f['detail']}")
    if a.stage:
        if not a.trial_id:
            print("error: --stage needs --trial-id", file=sys.stderr)
            return 2
        r = stage_intake(m, a.drop, a.stage, trial_id=a.trial_id)
        print(f"staged {len(r['staged'])} scan(s) into {a.stage}; skipped {len(r['skipped'])}: "
              f"{[x['scan'] for x in r['skipped']]}")  # fmt: skip
    return 0 if m["status"] in ("MAPPED", "MAPPED_WITH_WARNINGS") else 2


def _explain_pair(a: argparse.Namespace) -> int:
    from voxeltrace.trace import explain_pair

    print(DISCLAIMER)
    print(explain_pair(a.bundle, a.subject, a.ruleset))
    return 0


def _remediation(a: argparse.Namespace) -> int:
    import csv

    from voxeltrace.remediation import remediation_matrix

    rows = remediation_matrix()
    if a.format == "json":
        print(json.dumps(rows, indent=2))
        return 0
    w = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return 0


def _verify(a: argparse.Namespace) -> int:
    from voxeltrace.bundle import verify_bundle

    r = verify_bundle(a.bundle)
    print(json.dumps(r, indent=2))
    return 0 if r["status"] == "OK" else 1


def _summarize(a: argparse.Namespace) -> int:
    p = Path(a.bundle) / "reports" / "summary.json"
    if not p.exists():
        print(f"error: {p} not found", file=sys.stderr)
        return 2
    s = json.loads(p.read_text())
    print(DISCLAIMER)
    print(json.dumps({k: v for k, v in s.items() if k != "rulesets"}, indent=2))
    for rs, r in s["rulesets"].items():
        print(f"{rs}: real {r['verdicts_real']}; unresolved {r['unresolved_rules']}")
    ex = Path(a.bundle) / "reports" / "executive_summary.json"
    if ex.exists():  # bundles from earlier versions have no executive summary
        from voxeltrace.executive import executive_summary

        print("\n".join(["", *executive_summary(json.loads(ex.read_text()))]))
    return 0


def _list_reviews(a: argparse.Namespace) -> int:
    p = Path(a.bundle) / "reviews" / "review_status.csv"
    if not p.exists():
        print(f"error: {p} not found", file=sys.stderr)
        return 2
    import csv

    rows = list(csv.DictReader(p.open()))
    pending = [r for r in rows if r.get("task") == "HUMAN_REVIEW_REQUIRED"]
    print(f"{len(pending)} pending human reference-region review(s); {len(rows)} regions total")
    for r in rows:
        print(
            f"  {r['subject']}/{r['timepoint']} {r['region']}: {r['status']} {r['review_decision']}"
        )
    return 0


def _adjudicate(a: argparse.Namespace) -> int:
    """Append ONE human adjudication. Requires --confirm; never run by automation."""
    from datetime import UTC, datetime

    import voxeltrace
    from voxeltrace.quant.suv import git_state
    from voxeltrace.trial.adjudication import Adjudication, EvidenceItem, append_adjudication

    if not a.confirm:
        print("refused: adjudication requires --confirm (explicit human action)", file=sys.stderr)
        return 2
    ev = [
        EvidenceItem(description=d, attachment_sha256=h)
        for d, h in (x.split("=", 1) for x in a.evidence or [])
    ]
    rec = Adjudication(
        adjudication_id=a.id, subject=a.subject, baseline=a.baseline, followup=a.followup,
        ruleset_id=a.ruleset, automated_verdict=a.automated_verdict,
        automated_result_sha256=a.result_sha256, affected_rules=a.rules or [], action=a.action,
        adjudicated_verdict=a.new_verdict, reason=a.reason, supplied_evidence=ev,
        reviewer_id=a.reviewer, reviewer_role=a.role, timestamp=datetime.now(UTC),
        software_version=voxeltrace.__version__, git_commit=git_state()[0], created_via="HUMAN_CLI",
    )  # fmt: skip
    h = append_adjudication(a.log, rec, confirmed=True)
    print(f"appended {a.id} (chain {h})")
    return 0


def _att_template(a: argparse.Namespace) -> int:
    """Pre-fill ONLY binding facts read from DICOM. Never fills reconstruction values or the
    attestor; the result is not a valid attestation until a qualified person completes it."""
    import yaml

    from voxeltrace.evidence.attestation import SCHEMA
    from voxeltrace.trial.audit import scan_facts
    from voxeltrace.trial.timepoint import build_timepoint

    tp = build_timepoint(a.scan_dir, subject=a.subject, timepoint=a.timepoint, auto_reference=False)
    f = scan_facts(tp, a.scan_dir)
    blank = {
        "attestation_id": "", "subject_id": a.subject, "timepoint": a.timepoint,
        "study_instance_uid": f.study_instance_uid, "series_instance_uid": f.series_instance_uid,
        "manufacturer": f.manufacturer, "manufacturer_model_name": f.manufacturer_model_name,
        "software_version": (f.software_versions or [None])[0],
        "reconstruction_method": None, "iterations": None, "subsets": None, "post_filter": None,
        "time_of_flight": None, "psf_resolution_modelling": None, "corrections": None,
        "source": {"source_type": "", "path": "", "sha256": ""}, "corroborating_sources": [],
        "attestor_id": "", "attestor_role": "", "attested_at": "", "rule_scope": ["qiba-fdg-1.14"],
        "notes": "", "confidence": "", "simulated": False,
    }  # fmt: skip
    doc = {"schema": SCHEMA, "_instructions": "UNSIGNED TEMPLATE generated by VoxelTrace from DICOM "
           "binding facts only. A qualified PET physicist / nuclear medicine physicist / imaging "
           "core QC lead (or a countersigned technologist) must fill every empty field from the "
           "scanner protocol record and attach the source document (sha256). VoxelTrace never "
           "fills reconstruction values.", "attestations": [blank]}  # fmt: skip
    Path(a.out).write_text(yaml.safe_dump(doc, sort_keys=False))
    print(f"wrote UNSIGNED TEMPLATE {a.out} (not a valid attestation until completed)")
    return 0


def _att_validate(a: argparse.Namespace) -> int:
    from voxeltrace.evidence.attestation import load_attestations, validate_attestation
    from voxeltrace.trial.audit import scan_facts
    from voxeltrace.trial.timepoint import build_timepoint

    good, rejected = load_attestations(a.attestations)
    rows = [o.model_dump(exclude={"attestation"}) for o in rejected]
    for key, lst in good.items():
        subj, tp_name = key.split("/", 1)
        d = Path(a.input) / subj / tp_name
        if not d.exists():
            rows += [
                {
                    "attestation_id": x.attestation_id,
                    "status": "INVALID",
                    "reasons": ["NO_MATCHING_SCAN"],
                }
                for x in lst
            ]
            continue
        tp = build_timepoint(d, subject=subj, timepoint=tp_name, auto_reference=False)
        facts = scan_facts(tp, d)
        rows += [
            validate_attestation(x, facts, Path(a.attestations).parent).model_dump(
                exclude={"attestation"}
            )
            for x in lst
        ]
    print(json.dumps(rows, indent=2, default=str))
    return 0 if rows and all(r["status"] == "VALID" for r in rows) else 1


def _export_validation(a: argparse.Namespace) -> int:
    from voxeltrace.expert_validation import export_package

    paths = export_package(a.bundle, a.out, mode=a.mode)
    print(f"{len(paths)} case packets ({a.mode}) in {a.out}; answer key is COORDINATOR_ONLY")
    return 0


def _score_validation(a: argparse.Namespace) -> int:
    from voxeltrace.expert_validation import score_responses

    print(json.dumps(score_responses(a.package, a.responses), indent=2))
    return 0


def _inspect_brain(a: argparse.Namespace) -> int:
    from voxeltrace.brain_intake import inspect_brain

    print(json.dumps(inspect_brain(a.path), indent=2, default=str))
    return 0


def _lesion_qc(a: argparse.Namespace) -> int:
    """Render QC images + current review status for every supplied segment (no decision)."""
    from voxeltrace.trial.lesion_review import load_reviews
    from voxeltrace.trial.lesion_review_context import load_lesion_context

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ctx = load_lesion_context(
        a.scan_dir,
        a.subject,
        a.timepoint,
        load_reviews(a.log) if a.log else ([], {"status": "NO_FILE"}),
    )
    rows = []
    for it in ctx["items"]:
        ev = it["evidence"]
        name = f"{a.subject}_{a.timepoint}_seg{ev.candidate.segment_number}.png"
        if it["png"]:
            (out / name).write_bytes(it["png"])
        rows.append({**ev.candidate.model_dump(mode="json"), "review_status": ev.review_status,
                     "status_reasons": ev.reasons, "qc_warnings": it["qc_warnings"], "qc_image": name if it["png"] else None})  # fmt: skip
    (out / "lesion_candidates.json").write_text(json.dumps({"quant_eligible": ctx["quant_eligible"], "unit": ctx["unit"],
                                                            "ct_note": ctx["ct_note"], "segments": rows}, indent=2) + "\n")  # fmt: skip
    print(
        f"{len(rows)} segment(s); images and lesion_candidates.json in {out} (no decision recorded)"
    )
    return 0


def _lesion_review(a: argparse.Namespace) -> int:
    """Append ONE human lesion review for one segment (requires --confirm)."""
    from voxeltrace.trial.lesion_review import append_review, load_reviews
    from voxeltrace.trial.lesion_review_context import build_review, load_lesion_context

    if not a.confirm:
        print("refused: lesion review requires --confirm (explicit human action)", file=sys.stderr)
        return 2
    ctx = load_lesion_context(a.scan_dir, a.subject, a.timepoint, load_reviews(a.log))
    it = next(
        (x for x in ctx["items"] if x["evidence"].candidate.segment_number == a.segment), None
    )
    if it is None:
        print(f"error: segment {a.segment} not found", file=sys.stderr)
        return 2
    if a.expect_mask_sha256 and it["evidence"].candidate.mask_sha256 != a.expect_mask_sha256:
        print("refused: mask hash differs from the one you reviewed", file=sys.stderr)
        return 2
    rec = build_review(it["evidence"], reviewer_id=a.reviewer, reviewer_role=a.role, decision=a.decision,
                       note=a.note or "", created_via="HUMAN_CLI")  # fmt: skip
    append_review(a.log, rec, confirmed=True)
    print(f"recorded {a.decision} for segment {a.segment} (mask {rec.mask_sha256[:12]})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="voxeltrace",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="VoxelTrace: vendor-neutral quantitative PET comparability, provenance and "
        f"trial audit. {DISCLAIMER}",
    )
    ap.add_argument("--version", action="version", version=_version_text())
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser(
        "preflight",
        help="read-only quantitative preflight of a series, scan, subject or trial folder",
        description="Inspect DICOM headers before quantification. Never computes SUV/SUL. "
        "States: READY_TO_QUANTIFY, READY_WITH_WARNINGS, DO_NOT_QUANTIFY, NEEDS_REVIEW.",
    )
    p.add_argument("path", help="series, scan, subject or trial directory")
    p.add_argument("--out", help="write preflight.json and preflight.csv to this directory")
    p.add_argument("--format", choices=["text", "json", "csv"], default="text")
    p.set_defaults(func=_preflight)

    p = sub.add_parser(
        "validate-input",
        help="intake decision for a submitted folder: ACCEPT_FOR_AUDIT / ACCEPT_WITH_WARNINGS / "
        "NEEDS_REEXPORT / UNSUPPORTED (read-only)",
        description="Exit code 0 = accept (with or without warnings), 2 = NEEDS_REEXPORT, 3 = UNSUPPORTED.",
    )
    p.add_argument("path", help="series, scan, subject or trial directory")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=_validate_input)

    p = sub.add_parser(
        "init-trial",
        help="write a starter trial.yaml for a <subject>/<timepoint>/<DICOM> folder (never overwrites)",
    )
    p.add_argument("folder")
    p.add_argument("--trial-id", required=True)
    p.add_argument(
        "--ruleset",
        choices=["qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0"],
        default="qiba-fdg-1.14",
    )
    p.add_argument("--timepoints", nargs="+", help="timepoint folder names in chronological order")
    p.set_defaults(func=_init_trial)

    p = sub.add_parser(
        "data-inventory",
        help="read-only inventory of project data, outputs and disk use (never deletes)",
    )
    p.add_argument("--root", help="workspace root (default: parent of this repository)")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.add_argument("--out", help="also write the inventory to this new file inside the workspace")
    p.set_defaults(func=_data_inventory)

    p = sub.add_parser("inspect", help="list the DICOM series found under a path (read-only)")
    p.add_argument("path")
    p.set_defaults(func=_inspect)

    p = sub.add_parser(
        "inspect-brain",
        help="read-only inventory of a brain PET study (BIDS or DICOM); no quantification",
    )
    p.add_argument("path")
    p.set_defaults(func=_inspect_brain)

    p = sub.add_parser("audit", help="whole-trial comparability audit -> immutable evidence bundle")
    p.add_argument("--input", required=True, help="trial folder: <subject>/<timepoint>/<DICOM>")
    p.add_argument("--config", help="trial.yaml (default: <input>/trial.yaml)")
    p.add_argument("--output", required=True, help="new output directory (never overwritten)")
    p.add_argument(
        "--ruleset", action="append", choices=["qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0"]
    )
    p.add_argument(
        "--attestations", help="site-supplied reconstruction attestation file (QIBA only)"
    )
    p.add_argument("--adjudications", help="human adjudication log (JSON lines)")
    p.add_argument("--no-input-hashes", action="store_true", help="skip hashing every input file")
    p.add_argument("--qc-images", action="store_true", help="render reference-proposal QC images")
    p.add_argument(
        "--input-paths-in-clear",
        action="store_true",
        help="record input file paths in clear (default: sha256 of paths only)",
    )
    p.set_defaults(func=_audit)

    p = sub.add_parser(
        "run-pilot",
        help="validate-input -> (init-trial) -> audit -> verify-bundle -> acceptance -> delivery package",
        description="One-command retrospective pilot. Writes pilot_acceptance.json "
        "(VT-PILOT-ACCEPTANCE-1). Exit 0 = AUDIT_COMPLETE[_WITH_REVIEW_PENDING], 1 = AUDIT_BLOCKED, "
        "2 = NEEDS_REEXPORT (or usage error), 3 = UNSUPPORTED.",
    )
    p.add_argument("--input", required=True, help="trial folder: <subject>/<timepoint>/<DICOM>")
    p.add_argument("--output", required=True, help="new (or empty) output directory")
    p.add_argument("--trial-id", help="needed when the input has no trial.yaml and no --config")
    p.add_argument("--config", help="trial.yaml (default: <input>/trial.yaml)")
    p.add_argument("--timepoints", nargs="+", help="timepoint folder names in chronological order")
    p.add_argument(
        "--ruleset", action="append", choices=["qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0"]
    )
    p.add_argument("--attestations")
    p.add_argument("--adjudications")
    p.add_argument(
        "--strict-intake", action="store_true", help="audit only if intake accepts the folder"
    )
    p.add_argument("--no-delivery", action="store_true", help="skip the delivery package")
    p.add_argument("--format", choices=["text", "json"], default="text")
    p.set_defaults(func=_run_pilot)

    p = sub.add_parser(
        "deliver", help="build a sanitized design-partner delivery package from a pilot or bundle"
    )
    p.add_argument("source", help="run-pilot output folder or audit_bundle directory")
    p.add_argument("--out", required=True, help="new package directory (never overwritten)")
    p.set_defaults(func=_deliver)

    p = sub.add_parser(
        "verify-delivery", help="verify a delivery package (checksums, bundle, privacy scan)"
    )
    p.add_argument("package")
    p.set_defaults(func=_verify_delivery)

    p = sub.add_parser(
        "intake-map",
        help="interpret a partner data drop (site/subject/timepoint folders) -> intake_mapping.json",
        description="Headers only. PET is selected only by the deterministic rules R1 NAC, R2 "
        "secondary capture, R3 units; ambiguity is NEEDS_REVIEW (exit 2). --stage symlinks the "
        "selected series of the mapped scans into a trial folder with trial.yaml.",
    )
    p.add_argument("drop")
    p.add_argument("--out", required=True, help="new intake_mapping.json")
    p.add_argument(
        "--levels", default="site/subject/timepoint", help="folder levels, e.g. subject/timepoint"
    )
    p.add_argument("--timepoint-map", nargs="*", help="raw=canonical, e.g. 'Week 6=followup'")
    p.add_argument("--stage", help="new trial folder to stage the mapped scans into")
    p.add_argument("--trial-id")
    p.set_defaults(func=_intake_map)

    p = sub.add_parser(
        "explain-pair",
        help="why a pair got its verdict: rule -> reason -> field -> trust/source -> raw metadata",
    )
    p.add_argument("bundle")
    p.add_argument("--subject", required=True)
    p.add_argument("--ruleset", choices=["qiba-fdg-1.14", "eanm-fdg-2.0", "percist-1.0"])
    p.set_defaults(func=_explain_pair)

    p = sub.add_parser(
        "remediation-matrix", help="print every reason code with its remediation routes"
    )
    p.add_argument("--format", choices=["csv", "json"], default="csv")
    p.set_defaults(func=_remediation)

    p = sub.add_parser("verify-bundle", help="verify an evidence bundle's checksums (tamper check)")
    p.add_argument("bundle")
    p.set_defaults(func=_verify)

    p = sub.add_parser("summarize", help="print the summary of an evidence bundle")
    p.add_argument("bundle")
    p.set_defaults(func=_summarize)

    p = sub.add_parser("list-reviews", help="list human review tasks recorded in a bundle")
    p.add_argument("bundle")
    p.set_defaults(func=_list_reviews)

    p = sub.add_parser(
        "attestation-template",
        help="write an UNSIGNED reconstruction-attestation template (binding facts only)",
    )
    p.add_argument("--scan-dir", required=True)
    p.add_argument("--subject", required=True)
    p.add_argument("--timepoint", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=_att_template)

    p = sub.add_parser(
        "validate-attestations", help="validate a site-supplied attestation file against the scans"
    )
    p.add_argument("--input", required=True, help="trial folder <subject>/<timepoint>/")
    p.add_argument("--attestations", required=True)
    p.set_defaults(func=_att_validate)

    p = sub.add_parser(
        "export-validation",
        help="export a BLINDED/UNBLINDED expert validation package from a bundle",
    )
    p.add_argument("--bundle", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--mode", choices=["BLINDED", "UNBLINDED"], default="BLINDED")
    p.set_defaults(func=_export_validation)

    p = sub.add_parser(
        "score-validation", help="score filled expert response forms against VoxelTrace verdicts"
    )
    p.add_argument("--package", required=True)
    p.add_argument("--responses")
    p.set_defaults(func=_score_validation)

    p = sub.add_parser(
        "lesion-qc",
        help="render QC images + review status of supplied lesion segments (no decision)",
    )
    p.add_argument("scan_dir")
    p.add_argument("--subject", required=True)
    p.add_argument("--timepoint", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--log", help="lesion review log (JSON lines)")
    p.set_defaults(func=_lesion_qc)

    p = sub.add_parser("lesion-review", help="append ONE human lesion review (requires --confirm)")
    p.add_argument("scan_dir")
    for name in ("subject", "timepoint", "log", "reviewer", "role"):
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--segment", type=int, required=True)
    p.add_argument(
        "--decision", required=True, choices=["ACCEPT", "REJECT", "REJECT_AND_REPLACE_REQUIRED"]
    )
    p.add_argument("--expect-mask-sha256", help="the mask hash shown in the QC you reviewed")
    p.add_argument("--note")
    p.add_argument("--confirm", action="store_true", help="I am the named human reviewer")
    p.set_defaults(func=_lesion_review)

    p = sub.add_parser("adjudicate", help="append ONE human pair adjudication (requires --confirm)")
    for name in ("log", "id", "subject", "baseline", "followup", "ruleset", "automated-verdict",
                 "result-sha256", "action", "reason", "reviewer", "role"):  # fmt: skip
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--new-verdict")
    p.add_argument("--rules", nargs="*")
    p.add_argument("--evidence", nargs="*", help="description=sha256 (repeatable)")
    p.add_argument("--confirm", action="store_true", help="I am the named human reviewer")
    p.set_defaults(func=_adjudicate)
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
