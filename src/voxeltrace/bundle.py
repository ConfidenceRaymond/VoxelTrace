"""Immutable evidence bundle (VT-BUNDLE-1): manifest + sha256 checksums + verification.

Layout (under <out>/audit_bundle/):
  manifest.json, inputs_manifest.json, checksums.sha256 and the component directories
  (preflight/, protocol/, quantitative/, rules/, pair_verdicts/, reviews/, attestations/,
  adjudications/, reports/).

checksums.sha256 lists every file except manifest.json and itself. manifest.json records the
sha256 of checksums.sha256. ``verify_bundle`` recomputes all hashes and reports MODIFIED,
MISSING and UNLISTED files and a checksum-list mismatch. This proves INTEGRITY relative to the
manifest; it is not a signature (anyone who rewrites both can forge it). Files are made
read-only after writing.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BUNDLE_DIRS = (
    "preflight", "protocol", "quantitative", "rules", "pair_verdicts", "reviews",
    "attestations", "adjudications", "reports",
)  # fmt: skip


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inputs_manifest(root: Path, *, clear_paths: bool = False) -> dict[str, Any]:
    """sha256 + size of every input file and a root hash over them. Paths are recorded only
    as sha256(relative path) unless ``clear_paths`` (site file names can carry identifiers);
    the root hash is identical either way, so integrity checks do not need clear paths."""
    files = []
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        rel = str(p.relative_to(root))
        entry = {"path_sha256": hashlib.sha256(rel.encode()).hexdigest(), "bytes": p.stat().st_size,
                 "sha256": sha256_file(p), "_rel": rel}  # fmt: skip
        if clear_paths:
            entry["path"] = rel
        files.append(entry)
    canon = "".join(f"{f['_rel']}\0{f['sha256']}\n" for f in files)
    for f in files:
        del f["_rel"]
    return {"root_label": "input" if not clear_paths else root.name, "paths_in_clear": clear_paths,
            "files": files, "file_count": len(files), "total_bytes": sum(f["bytes"] for f in files),
            "inputs_sha256": hashlib.sha256(canon.encode()).hexdigest()}  # fmt: skip


def runtime_environment() -> dict[str, Any]:
    import numpy
    import pydantic
    import pydicom

    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "packages": {
            "numpy": numpy.__version__,
            "pydicom": pydicom.__version__,
            "pydantic": pydantic.__version__,
        },  # fmt: skip
    }


def finalize_bundle(bundle: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Write checksums.sha256 over every file (except manifest/checksums), then manifest.json
    with the checksums hash. Makes all files read-only."""
    files = sorted(
        p for p in bundle.rglob("*")
        if p.is_file() and p.name not in ("manifest.json", "checksums.sha256")
    )  # fmt: skip
    lines = [f"{sha256_file(p)}  {p.relative_to(bundle)}" for p in files]
    ck = bundle / "checksums.sha256"
    ck.write_text("\n".join(lines) + "\n")
    manifest = {**manifest, "checksums_sha256": sha256_file(ck), "files": len(files),
                "finalized_at": datetime.now(UTC).isoformat(timespec="seconds")}  # fmt: skip
    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str) + "\n")
    for p in [*files, ck, bundle / "manifest.json"]:
        os.chmod(p, 0o444)
    return manifest


def verify_bundle(bundle: str | Path) -> dict[str, Any]:
    bundle = Path(bundle)
    out: dict[str, Any] = {"bundle": str(bundle), "status": "OK", "modified": [], "missing": [],
                           "unlisted": [], "checksum_list": "OK"}  # fmt: skip
    mpath, ck = bundle / "manifest.json", bundle / "checksums.sha256"
    if not mpath.exists() or not ck.exists():
        out["status"] = "INVALID"
        out["error"] = "manifest.json or checksums.sha256 missing"
        return out
    manifest = json.loads(mpath.read_text())
    if sha256_file(ck) != manifest.get("checksums_sha256"):
        out["checksum_list"] = "MISMATCH"
    listed = {}
    for line in ck.read_text().splitlines():
        if line.strip():
            h, rel = line.split("  ", 1)
            listed[rel] = h
    for rel, h in listed.items():
        p = bundle / rel
        if not p.exists():
            out["missing"].append(rel)
        elif sha256_file(p) != h:
            out["modified"].append(rel)
    actual = {str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_file()}
    out["unlisted"] = sorted(actual - set(listed) - {"manifest.json", "checksums.sha256"})
    if out["modified"] or out["missing"] or out["unlisted"] or out["checksum_list"] != "OK":
        out["status"] = "TAMPERED"
    out["schema_versions"] = manifest.get("schema_versions")
    out["git_commit"] = manifest.get("git_commit")
    out["files_checked"] = len(listed)
    return out
