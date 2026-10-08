#!/usr/bin/env python3
"""Build and freeze dev_v3 from the frozen dev_v2 set (see voxeltrace.evaluation.dev_v3).

Outputs ../outputs/eval_v3/<subject>/{examples.jsonl, examples_qwen3vl.jsonl} (images are
referenced from ../outputs/training_dev/<subject>/images, never copied or re-rendered),
../outputs/eval_v3/manifest.json and ../outputs/eval_reference/dev_v3.json (frozen, bound to
evaluator vt-eval-2). Files are made read-only. Refuses to overwrite an existing dev_v3.
"""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from collections import Counter
from pathlib import Path

import voxeltrace
from voxeltrace.config import REPO_ROOT
from voxeltrace.evaluation.dev_v3 import GENERATOR_VERSION, added_claims, carry_over, qwen_messages
from voxeltrace.evaluation.evaluator_v2 import EVALUATOR_V2_VERSION, freeze_eval_set_v2
from voxeltrace.evaluation.runner import load_frozen
from voxeltrace.evidence.acquisition import AcquisitionProtocol
from voxeltrace.evidence.corrections import CorrectionEvidence
from voxeltrace.evidence.protocol import ProtocolEvidence
from voxeltrace.evidence.reconstruction import ReconstructionProtocol
from voxeltrace.evidence.scanner import ScannerEvidence
from voxeltrace.quant.suv import git_state
from voxeltrace.schemas import QuantEvidence

OUT = REPO_ROOT.parent / "outputs"
V2 = OUT / "eval_reference" / "dev_v2.json"
V2_MANIFEST = OUT / "eval_v2" / "manifest.json"
V3_DIR = OUT / "eval_v3"
V3_FROZEN = OUT / "eval_reference" / "dev_v3.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_protocol(d: Path) -> ProtocolEvidence:
    sc = ScannerEvidence.model_validate_json((d / "scanner_evidence.json").read_text())
    return ProtocolEvidence(
        series_uid=sc.series_uid,
        scanner=sc,
        acquisition=AcquisitionProtocol.model_validate_json(
            (d / "acquisition_protocol.json").read_text()
        ),
        reconstruction=ReconstructionProtocol.model_validate_json(
            (d / "reconstruction_protocol.json").read_text()
        ),
        corrections=CorrectionEvidence.model_validate_json(
            (d / "correction_evidence.json").read_text()
        ),
    )


def make_read_only(p: Path) -> None:
    p.chmod(p.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def main() -> int:
    if V3_FROZEN.exists() or V3_DIR.exists():
        print("dev_v3 already exists; refusing to overwrite", file=sys.stderr)
        return 2
    v2_def = json.loads(V2.read_text())
    v2 = load_frozen(v2_def)  # raises if any dev_v2 file changed
    v2_manifest = json.loads(V2_MANIFEST.read_text())
    for rel, h in v2_manifest["evidence_sha256"].items():
        if sha(OUT / rel) != h:
            raise SystemExit(f"evidence changed since dev_v2: {rel}")
    for rel, h in v2_manifest["image_sha256"].items():
        if sha(OUT / "training_dev" / rel) != h:
            raise SystemExit(f"image changed since dev_v2: {rel}")

    by_subject: dict[str, list[dict]] = {}
    for r in v2:
        by_subject.setdefault(r["provenance"]["subject_pseudonym"], []).append(r)
    V3_DIR.mkdir(parents=True)
    dropped: dict[str, list[str]] = {}
    for subject, recs in sorted(by_subject.items()):
        recs = sorted(recs, key=lambda r: r["id"])
        base = next(
            r
            for r in recs
            if r["class"] == "CLAIM_VERIFICATION"
            and {"quantitative_evidence", "protocol_evidence"} <= set(r["context"] or {})
        )
        ctx = {k: base["context"][k] for k in ("quantitative_evidence", "protocol_evidence")}
        d = OUT / subject
        ev = QuantEvidence.model_validate_json((d / "evidence.json").read_text())
        added, dropped[subject] = added_claims(
            subject, ev, load_protocol(d), ctx, base["provenance"]
        )
        v3 = [carry_over(r) for r in recs] + added
        sd = V3_DIR / subject
        sd.mkdir()
        (sd / "examples.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in v3)
        )
        (sd / "examples_qwen3vl.jsonl").write_text(
            "".join(json.dumps(qwen_messages(r, subject), sort_keys=True) + "\n" for r in v3)
        )
    frozen = freeze_eval_set_v2([V3_DIR / s for s in sorted(by_subject)], "dev_v3")
    frozen["parent"] = {"name": "dev_v2", "definition_sha256": sha(V2), "files": v2_def["files"]}
    V3_FROZEN.write_text(json.dumps(frozen, indent=2) + "\n")

    allrecs = [
        json.loads(x)
        for s in sorted(by_subject)
        for x in (V3_DIR / s / "examples.jsonl").read_text().splitlines()
    ]
    added_recs = [r for r in allrecs if r["v3_added"]]
    sha_c, dirty = git_state()
    manifest = {
        "name": "dev_v3",
        "parent_dataset": "dev_v2",
        "dev_v2_definition_sha256": sha(V2),
        "dev_v3_definition_sha256": sha(V3_FROZEN),
        "dev_v3_files": frozen["files"],
        "generator": GENERATOR_VERSION,
        "evaluator_version": EVALUATOR_V2_VERSION,
        "voxeltrace_version": voxeltrace.__version__,
        "git_commit": sha_c,
        "git_dirty": dirty,
        "n_examples": len(allrecs),
        "n_carried_over": len(allrecs) - len(added_recs),
        "n_v3_added": len(added_recs),
        "carry_over_changes": dict(Counter(c for r in allrecs for c in r["v3_changes"])),
        "family_counts": dict(Counter(r["family"] for r in allrecs)),
        "label_distribution": dict(
            Counter(
                r["target"].get("label")
                or r["target"].get("pair_verdict")
                or r["target"].get("status")
                or r["family"]
                for r in allrecs
            )
        ),
        "v3_added_by_variant_and_label": dict(
            Counter(f"{r['v3_variant']}:{r['target']['label']}" for r in added_recs)
        ),
        "dropped_variants": dropped,
        "evidence_sha256": v2_manifest["evidence_sha256"],
        "image_sha256": v2_manifest["image_sha256"],
        "notes": [
            "Built from frozen dev_v2; dev_v1 and dev_v2 untouched.",
            "Carried-over records: only the first question paragraph may be reworded "
            "(natural negation; SUVpeak value-only). Targets, evidence and images unchanged.",
            "v3_added labels come from the existing claims-1 rules; variants whose rule label "
            "differs from the intended one are dropped (listed), never relabelled.",
            "Same system prompt and message construction as dev_v2.",
            "Frozen before any model run; scored with vt-eval-2 only; never edited.",
        ],
    }
    (V3_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for s in sorted(by_subject):
        for f in (V3_DIR / s).iterdir():
            make_read_only(f)
        make_read_only(V3_DIR / s)
    make_read_only(V3_DIR / "manifest.json")
    make_read_only(V3_DIR)
    make_read_only(V3_FROZEN)
    print(
        json.dumps(
            {
                k: manifest[k]
                for k in (
                    "n_examples",
                    "n_carried_over",
                    "n_v3_added",
                    "carry_over_changes",
                    "family_counts",
                    "label_distribution",
                    "v3_added_by_variant_and_label",
                    "dropped_variants",
                    "dev_v3_definition_sha256",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
