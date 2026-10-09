"""Read-only inventory of the project workspace (VT-DATA-INVENTORY-1). Never deletes or moves.

Reports, for the workspace root (default: the parent of this repository):
  * bytes / files / symlinks per top-level directory (symlinks are counted, never followed);
  * every downloaded imaging series folder (<...>/<subject>/<timepoint>/<PET|CT|SEG>) with
    file count and size, and whether a provenance manifest and a frozen plan with a licence
    exist for that subject;
  * output namespaces and their size; the largest directories; free disk space against the
    project's 500 GB stop threshold;
  * items worth a human look (temporary folders, series without provenance). Flagging is
    advisory: nothing is removed.
"""

from __future__ import annotations

import json
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

MODALITY_DIRS = {"PET", "CT", "SEG", "PT", "RTSTRUCT"}
FREE_SPACE_STOP_GB = 500


def _walk(root: Path) -> tuple[int, int, int, dict[Path, int]]:
    """-> (bytes, files, symlinks, bytes per directory) without following symlinks."""
    total = files = links = 0
    per_dir: dict[Path, int] = defaultdict(int)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        d = Path(dirpath)
        dirnames[:] = [x for x in dirnames if not (d / x).is_symlink()]
        for name in filenames:
            p = d / name
            if p.is_symlink():
                links += 1
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            total += size
            files += 1
            per_dir[d] += size
    return total, files, links, per_dir


def _licences(repo: Path) -> dict[tuple[str, str, str], set[str]]:
    """(subject, timepoint, modality) -> licences declared by the download allow-lists."""
    out: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for p in sorted(repo.glob("configs/**/allowlist*.json")):
        try:
            entries = json.loads(p.read_text()).get("series", [])
        except (OSError, ValueError, AttributeError):
            continue
        for e in entries:
            if e.get("license"):
                key = (
                    e.get("PatientID", ""),
                    e.get("timepoint", ""),
                    str(e.get("modality", "")).upper(),
                )
                out[key].add(e["license"])
    return out


def inventory(root: str | Path, repo: str | Path | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    repo = Path(repo).resolve() if repo else root / "voxeltrace"
    licences = _licences(repo)
    top: dict[str, Any] = {}
    all_dirs: dict[Path, int] = {}
    for d in sorted(p for p in root.iterdir() if p.is_dir() and not p.is_symlink()):
        b, f, s, per = _walk(d)
        top[d.name] = {"bytes": b, "files": f, "symlinks": s}
        all_dirs.update(per)
    series = []
    data = root / "data"
    if data.exists():
        for mod_dir in sorted(
            p for p in data.rglob("*") if p.is_dir() and p.name.upper() in MODALITY_DIRS
        ):
            if mod_dir.is_symlink():
                continue
            rel = mod_dir.relative_to(data).parts
            subject = rel[-3] if len(rel) >= 3 else None
            files = [p for p in mod_dir.iterdir() if p.is_file() and not p.is_symlink()]
            manifests = (
                list(mod_dir.parents[2].glob("provenance_manifest*.json")) if len(rel) >= 3 else []
            )
            series.append({
                "path": str(mod_dir.relative_to(root)), "subject": subject, "timepoint": rel[-2] if len(rel) >= 2 else None,
                "modality": mod_dir.name, "files": len(files), "bytes": sum(p.stat().st_size for p in files),
                "provenance_manifest": bool(manifests),
                "allowlist_licence": sorted(licences.get((subject or "", rel[-2] if len(rel) >= 2 else "", mod_dir.name.upper()), set())),
            })  # fmt: skip
    data_folders = []
    if data.exists():
        for d in sorted(p for p in data.iterdir() if p.is_dir() and not p.is_symlink()):
            b, f, _, _ = _walk(d)
            data_folders.append({"name": d.name, "bytes": b, "files": f})
    namespaces = []
    outputs = root / "outputs"
    if outputs.exists():
        for ns in sorted(p for p in outputs.iterdir() if p.is_dir() and not p.is_symlink()):
            b, f, s, _ = _walk(ns)
            namespaces.append({"name": ns.name, "bytes": b, "files": f, "symlinks": s})
    # aggregate directory sizes up to depth 2 below the root for the "largest" list
    agg: dict[Path, int] = defaultdict(int)
    for d, b in all_dirs.items():
        parts = d.relative_to(root).parts
        agg[root.joinpath(*parts[:2])] += b
    largest = [{"path": str(p.relative_to(root)), "bytes": b} for p, b in sorted(agg.items(), key=lambda kv: (-kv[1], str(kv[0])))[:10]]  # fmt: skip
    free_gb = shutil.disk_usage(root).free / 1e9
    attention = []
    if "tmp" in top and top["tmp"]["bytes"]:
        attention.append(
            f"tmp/ holds {top['tmp']['bytes'] / 1e9:.1f} GB of temporary material (review; nothing is deleted)"
        )
    for s in series:
        if s["files"] and not s["provenance_manifest"]:
            attention.append(
                f"{s['path']}: no provenance manifest found next to the subject folder"
            )
    if free_gb < FREE_SPACE_STOP_GB:
        attention.append(
            f"free disk {free_gb:.0f} GB is below the {FREE_SPACE_STOP_GB} GB stop threshold"
        )
    return {
        "schema": "VT-DATA-INVENTORY-1",
        "root": str(root),
        "top_level": top,
        "total_bytes": sum(v["bytes"] for v in top.values()),
        "imaging_series": series,
        "imaging_subjects": len({s["subject"] for s in series if s["subject"]}),
        "data_folders": data_folders,
        "output_namespaces": namespaces,
        "largest_directories": largest,
        "disk_free_gb": round(free_gb, 1),
        "needs_attention": attention,
        "note": "Read-only inventory. Nothing was deleted, moved or modified.",
    }


def format_text(r: dict[str, Any]) -> str:
    gb = lambda b: f"{b / 1e9:.2f} GB"  # noqa: E731
    L = [
        f"Workspace {r['root']}: {gb(r['total_bytes'])}; disk free {r['disk_free_gb']} GB",
        "",
        "Top level:",
    ]
    L += [
        f"  {k:12} {gb(v['bytes']):>10}  {v['files']:>7} files  {v['symlinks']:>6} symlinks"
        for k, v in r["top_level"].items()
    ]
    L += [
        "",
        f"Imaging series folders: {len(r['imaging_series'])} ({r['imaging_subjects']} subjects)",
    ]
    L += [
        f"  {s['path']:80} {s['files']:>5} files {gb(s['bytes']):>9}  licence {','.join(s['allowlist_licence']) or '-'}"
        for s in r["imaging_series"]
    ]
    L += ["", "data/ folders:"] + [
        f"  {d['name']:48} {gb(d['bytes']):>10} {d['files']:>7} files" for d in r["data_folders"]
    ]
    L += ["", "Output namespaces:"] + [
        f"  {n['name']:48} {gb(n['bytes']):>10} {n['symlinks']:>6} symlinks"
        for n in r["output_namespaces"]
    ]
    L += ["", "Largest directories:"] + [
        f"  {x['path']:60} {gb(x['bytes']):>10}" for x in r["largest_directories"]
    ]
    L += ["", "Needs attention (advisory):"] + (
        [f"  - {a}" for a in r["needs_attention"]] or ["  none"]
    )
    L += ["", r["note"]]
    return "\n".join(L)
