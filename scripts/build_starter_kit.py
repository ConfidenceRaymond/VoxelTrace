#!/usr/bin/env python3
"""Build the sanitized external-partner starter kit and a deterministic ZIP.

  build_starter_kit.py --demo-delivery <run-pilot>/delivery_package --out <dir>/external_partner_starter_kit

Writes <out>/ (folder), <out>.zip, <out>.sha256 and <out>_manifest.json. Contents: the
partner-facing documents, a sanitized SAMPLE delivery package built from DEMONSTRATION data,
verification instructions, a version/readiness note and a result-interpretation guide.
Never: DICOM, images other than the text PDF, model files, logs, source data, local paths.

Fails closed: the sample package must pass verify-delivery and the whole kit must pass the
privacy scan; otherwise nothing is zipped. The ZIP is byte-reproducible (sorted entries,
fixed timestamp 1980-01-01 00:00, fixed permissions, DEFLATE level 9).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PARTNER = REPO / "docs" / "pilot" / "external_partner"
SEND = ["README_FIRST.md", "DATA_REQUIREMENTS.md", "partner_intake.yaml", "GE_PHILIPS_DATA_REQUEST.md",
        "TRANSFER_CHECKLIST.md", "PILOT_SCOPE_TEMPLATE.md", "PARTNER_REVIEW_GUIDE.md",
        "TEXT_IMPLIED_REVIEW_PACKET.md", "PILOT_DELIVERY_CHECKLIST.md", "PILOT_FEEDBACK_FORM.md"]  # fmt: skip
FIXED = (1980, 1, 1, 0, 0, 0)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def start_here(version: str, acc: dict) -> str:
    v = acc.get("verdicts", {})
    return "\n".join([
        "# START HERE: VoxelTrace partner starter kit", "",
        "RESEARCH PROTOTYPE - NOT FOR CLINICAL DIAGNOSIS. Research and trial-QC software; no regulatory "
        "clearance. **External expert validation is pending.**", "",
        "## What VoxelTrace does", "",
        "Before anyone interprets an SUV change, VoxelTrace checks whether baseline and follow-up FDG PET "
        "scans are comparable across timepoints, sites, scanners and reconstruction protocols. Each pair gets "
        "ASSESSABLE, ASSESSABLE_WITH_WARNINGS, NOT_ASSESSABLE or INSUFFICIENT_INFORMATION per guideline "
        "(QIBA FDG 1.14, EANM FDG 2.0, PERCIST 1.0), with the DICOM evidence behind it. Deterministic, offline, "
        "no AI in any measurement or decision.", "",
        "## What to send / what NOT to send", "",
        "See `partner_docs/DATA_REQUIREMENTS.md`: de-identified FDG PET (and CT if PERCIST is in scope), a "
        "visit list or `partner_intake.yaml`, scanner and radiopharmaceutical metadata kept in the DICOM. "
        "Never: names, MRNs, accession numbers, birth dates, clinical information, real identifiers as folder names.", "",
        "## How intake is validated", "",
        "`validate-partner-intake` checks your declaration against the files; `validate-input` and `intake-map` "
        "interpret the folders, select the PET series only by explicit rules and hold any ambiguity for your "
        "answer (NEEDS_REVIEW). Nothing is chosen silently and nothing in your copy is modified.", "",
        "## What is delivered", "",
        "See `sample_delivery/` (a real package from DEMONSTRATION data) and "
        "`partner_docs/PILOT_DELIVERY_CHECKLIST.md`. Interpretation: `RESULT_INTERPRETATION_GUIDE.md`.", "",
        "## What your PET physicist reviews", "",
        "Reference regions and lesions for PERCIST, pairing questions, every TEXT_IMPLIED verdict (first "
        "scientific question: `partner_docs/TEXT_IMPLIED_REVIEW_PACKET.md`), and any verdict you disagree with. "
        "VoxelTrace never records a review decision.", "",
        "## Validation status and limitations", "",
        f"`VERSION_AND_READINESS.md`. Short version: software {version}; tested on 9 real public longitudinal "
        "pairs; Siemens validated on public pairs; GE ingestion only; Philips metadata only; external expert "
        "validation pending; FDG PET/CT only.", "",
        "## How to verify delivered artefacts", "",
        "`VERIFY_SAMPLE.md` (works with plain `sha256sum`).", "",
        "## The sample", "",
        f"`sample_delivery/` was produced from DEMONSTRATION data (synthetic perturbations of a public pair plus "
        f"public scans). Its pilot status is {acc.get('status')}; verdicts: "
        + "; ".join(f"{rs}: " + ", ".join(f"{n} {k}" for k, n in c.items() if n) for rs, c in v.items()) + ". "
        "These numbers describe the demonstration set, not VoxelTrace's accuracy.", "",
    ])  # fmt: skip


VERIFY = """# Verify the sample (and any delivered package)

Without VoxelTrace (Linux / macOS):

```bash
cd sample_delivery && sha256sum -c DELIVERY_CHECKSUMS.sha256
cd evidence_bundle && sha256sum -c checksums.sha256
```

With VoxelTrace installed:

```bash
voxeltrace verify-delivery sample_delivery        # "status": "OK", "privacy_scan": "CLEAN"
voxeltrace verify-bundle sample_delivery/evidence_bundle
```

The whole kit: `sha256sum -c external_partner_starter_kit.sha256` next to the ZIP, and
`kit_manifest.json` inside lists every file's sha256.
"""

GUIDE = """# Reading the results

| Verdict | Means | What to do |
|---|---|---|
| ASSESSABLE | evidence supports interpreting SUV change under this guideline | check `reconstruction_evidence`; TEXT_IMPLIED needs your physicist |
| ASSESSABLE_WITH_WARNINGS | as above, with caveats (listed) | read the warnings |
| NOT_ASSESSABLE | a criterion was decided and not met (e.g. uptake time) | a re-export cannot change it |
| INSUFFICIENT_INFORMATION | evidence missing; never a pass | `unresolved_items.csv` says what and who can supply it |

Columns worth knowing in `pair_results.csv`: `pairing_status` (must be OK), `reconstruction_evidence`
(STRUCTURED / FREE_TEXT / ATTESTED / TEXT_IMPLIED / NOT_ESTABLISHED), `plain_language_reasons`.
"Why this verdict?" → `pair_evidence_trace.csv`. What fixes a reason → `remediation_matrix.csv`.

In the DEMONSTRATION sample, subjects DEMO-01 … DEMO-07 each carry one deliberate synthetic change
(identity, reconstruction blur, reconstruction metadata, uptake violation, missing dose,
anonymization loss, correction mismatch); DEMO-08 / DEMO-09 are single real public scans (no pair).
"""


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo-delivery", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv[1:])
    sys.path.insert(0, str(REPO / "src"))
    import voxeltrace
    from voxeltrace.delivery import verify_delivery
    from voxeltrace.privacy_scan import scan_directory

    out = a.out
    if out.exists() or out.with_suffix(".zip").exists():
        print(f"error: {out} or its zip exists (never overwritten)", file=sys.stderr)
        return 2
    v = verify_delivery(a.demo_delivery)
    if v["status"] != "OK":
        print(f"error: sample delivery does not verify: {v['status']}", file=sys.stderr)
        return 1
    acc = json.loads((a.demo_delivery / "pilot_acceptance.json").read_text())
    if acc["software"].get("git_dirty"):
        print("error: sample delivery was produced from a dirty tree", file=sys.stderr)
        return 1
    (out / "partner_docs").mkdir(parents=True)
    for n in SEND:
        shutil.copy(PARTNER / n, out / "partner_docs" / n)
    shutil.copytree(a.demo_delivery, out / "sample_delivery")
    for p in (out / "sample_delivery").rglob("*"):
        p.chmod(0o755 if p.is_dir() else 0o644)
    (out / "START_HERE.md").write_text(start_here(voxeltrace.__version__, acc))
    (out / "VERIFY_SAMPLE.md").write_text(VERIFY)
    (out / "RESULT_INTERPRETATION_GUIDE.md").write_text(GUIDE)
    (out / "VERSION_AND_READINESS.md").write_text("\n".join([
        "# Version and readiness", "",
        f"- VoxelTrace {voxeltrace.__version__}; sample produced by commit {acc['software']['git_commit']} "
        f"(rule bundle {acc['software']['rule_bundle_sha256']}).",
        "- Readiness: RETROSPECTIVE_PILOT_READY (software and process for an unpaid retrospective pilot).",
        "- PAID_PILOT_READY: NO (external expert validation, a first real dataset and an unpaid pilot are pending).",
        "- External expert validation: PENDING (no reviewer form returned).",
        "- Vendors: Siemens validated on public pairs; GE ingestion only; Philips metadata only.",
        "- Scope: FDG PET/CT; research and trial QC; not for clinical diagnosis or treatment decisions.", ""]))  # fmt: skip
    for bad in [
        p
        for p in out.rglob("*")
        if p.is_file()
        and (p.suffix.lower() in (".dcm", ".png", ".jpg", ".nii", ".gz", ".safetensors", ".log"))
    ]:
        print(f"error: forbidden file type in kit: {bad.relative_to(out)}", file=sys.stderr)
        return 1
    scan = scan_directory(out)
    if scan["status"] != "CLEAN":
        (out.parent / f"{out.name}.privacy_findings.json").write_text(
            json.dumps(scan, indent=2) + "\n"
        )
        print(f"error: privacy scan {scan['categories']}", file=sys.stderr)
        return 1
    files = sorted(p for p in out.rglob("*") if p.is_file())
    manifest = {"schema": "VT-STARTER-KIT-1", "voxeltrace_version": voxeltrace.__version__,
                "sample_source_commit": acc["software"]["git_commit"], "privacy_scan": "CLEAN",
                "files": [{"path": p.relative_to(out).as_posix(), "bytes": p.stat().st_size, "sha256": sha(p)} for p in files]}  # fmt: skip
    (out / "kit_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    files = sorted(p for p in out.rglob("*") if p.is_file())
    zpath = out.with_suffix(".zip")
    with zipfile.ZipFile(zpath, "w") as z:
        for p in files:
            zi = zipfile.ZipInfo(f"{out.name}/{p.relative_to(out).as_posix()}", date_time=FIXED)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            zi.create_system = 3
            z.writestr(zi, p.read_bytes(), compresslevel=9)
    digest = sha(zpath)
    out.with_suffix(".sha256").write_text(f"{digest}  {zpath.name}\n")
    ext = {**{k: v for k, v in manifest.items() if k != "files"}, "zip": zpath.name, "zip_sha256": digest,
           "files": len(files), "kit_manifest_sha256": sha(out / "kit_manifest.json")}  # fmt: skip
    (out.parent / f"{out.name}_manifest.json").write_text(json.dumps(ext, indent=2) + "\n")
    print(json.dumps(ext, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
